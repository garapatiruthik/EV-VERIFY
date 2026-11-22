"""BMS / powertrain supervisor with an explicit deterministic state machine.

States:
  INITIALISING  - start-up, validate initial measurements
  READY         - normal operation; torque permitted up to configured limits
  DERATED       - soft constraint active; torque reduced
  FAULT_LATCHED - critical condition; zero torque, latched until explicit reset

Threshold semantics (documented):
  hard protective trips trip strictly above the threshold (>), never at
  equality. under-voltage trips strictly below (<).
  soft derating engages at or beyond the soft threshold (>=) and releases only
  when comfortably clear (hysteresis) to avoid chattering.

The supervisor consumes only sensor measurements, never plant ground truth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import AppConfig
from .sensors import Measurement, SensorSignal


class SupervisorState:
    INITIALISING = "INITIALISING"
    READY = "READY"
    DERATED = "DERATED"
    FAULT_LATCHED = "FAULT_LATCHED"


ALL_STATES = (
    SupervisorState.INITIALISING,
    SupervisorState.READY,
    SupervisorState.DERATED,
    SupervisorState.FAULT_LATCHED,
)


class FaultCode:
    OVER_VOLTAGE = "BMS_OVER_VOLTAGE"
    UNDER_VOLTAGE = "BMS_UNDER_VOLTAGE"
    OVER_CURRENT_DISCHARGE = "BMS_OVER_CURRENT_DISCHARGE"
    OVER_CURRENT_CHARGE = "BMS_OVER_CURRENT_CHARGE"
    OVER_TEMP = "BMS_OVER_TEMP"
    SENSOR_DROPOUT = "BMS_SENSOR_DROPOUT"
    SENSOR_STALE = "BMS_SENSOR_STALE"
    SENSOR_INVALID = "BMS_SENSOR_INVALID"
    SOC_DERATE = "BMS_SOC_DERATE"
    TEMP_DERATE = "BMS_TEMP_DERATE"
    RESET = "BMS_RESET"
    FAULT_LATCHED = "BMS_FAULT_LATCHED"

    CRITICAL = frozenset({
        OVER_VOLTAGE,
        UNDER_VOLTAGE,
        OVER_CURRENT_DISCHARGE,
        OVER_CURRENT_CHARGE,
        OVER_TEMP,
        SENSOR_DROPOUT,
        SENSOR_STALE,
        SENSOR_INVALID,
    })


SAFETY_CRITICAL_SIGNALS = frozenset({
    SensorSignal.PACK_VOLTAGE,
    SensorSignal.PACK_CURRENT,
    SensorSignal.BATTERY_TEMP,
    SensorSignal.MOTOR_SPEED,
    SensorSignal.SOC,
})


@dataclass(frozen=True)
class DiagnosticEvent:
    time_s: float
    signal: str | None
    code: str
    message: str
    value: float | None = None


@dataclass
class SupervisorOutput:
    state: str
    permitted_torque_nm: float
    fault_codes: frozenset[str]
    events: list[DiagnosticEvent] = field(default_factory=list)
    torque_limit_nm: float | None = None
    derated: bool = False


class Supervisor:
    """Deterministic battery/powertrain supervisor."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = SupervisorState.INITIALISING
        self._latched = False
        self._active_faults: frozenset[str] = frozenset()
        self._initialized = False
        self._derated_active = False

    @staticmethod
    def _measurement_valid(
        m: Measurement | None, now: float, timeout_s: float
    ) -> tuple[bool, str | None]:
        if m is None:
            return False, "missing measurement"
        if not m.valid:
            return False, m.reason or "measurement marked invalid"
        if not m.is_finite():
            return False, "non-finite value"
        if m.is_stale(now, timeout_s):
            return False, "stale measurement"
        return True, None

    def _critical_for_signal(self, signal: str, value: float) -> str | None:
        bat = self.config.battery
        if signal == SensorSignal.PACK_VOLTAGE:
            if value > bat.over_voltage_v:
                return FaultCode.OVER_VOLTAGE
            if value < bat.under_voltage_v:
                return FaultCode.UNDER_VOLTAGE
        elif signal == SensorSignal.PACK_CURRENT:
            if value > bat.max_discharge_current_a:
                return FaultCode.OVER_CURRENT_DISCHARGE
            if value < -bat.max_charge_current_a:
                return FaultCode.OVER_CURRENT_CHARGE
        elif signal == SensorSignal.BATTERY_TEMP:
            if value > bat.over_temp_c:
                return FaultCode.OVER_TEMP
        return None

    def _evaluate(
        self,
        measurements: dict[str, Measurement],
        requested_torque_nm: float,
        now: float,
    ) -> SupervisorOutput:
        events: list[DiagnosticEvent] = []
        fault_codes: set[str] = set()
        timeout_s = self.config.supervisor.stale_sensor_timeout_s
        bat = self.config.battery

        for signal in SAFETY_CRITICAL_SIGNALS:
            m = measurements.get(signal)
            ok, reason = self._measurement_valid(m, now, timeout_s)
            if not ok:
                if m is None or not m.valid:
                    code = FaultCode.SENSOR_INVALID
                elif m.is_stale(now, timeout_s):
                    code = FaultCode.SENSOR_STALE
                else:
                    code = FaultCode.SENSOR_INVALID
                fault_codes.add(code)
                events.append(
                    DiagnosticEvent(
                        now,
                        signal,
                        code,
                        reason or "invalid measurement",
                        m.value if (m is not None and m.is_finite()) else None,
                    )
                )
                continue
            critical = self._critical_for_signal(signal, m.value)
            if critical is not None:
                fault_codes.add(critical)
                events.append(
                    DiagnosticEvent(now, signal, critical, "critical threshold exceeded", m.value)
                )

        derated = False
        torque_limit = self.config.motor.max_torque_nm

        soc_m = measurements.get(SensorSignal.SOC)
        temp_m = measurements.get(SensorSignal.BATTERY_TEMP)
        soc_value = soc_m.value if (soc_m is not None and soc_m.is_finite()) else None
        temp_value = temp_m.value if (temp_m is not None and temp_m.is_finite()) else None

        if soc_value is not None and soc_value <= bat.soc_hard_min:
            fault_codes.add(FaultCode.UNDER_VOLTAGE)
            events.append(
                DiagnosticEvent(
                    now, SensorSignal.SOC, FaultCode.UNDER_VOLTAGE, "SOC at hard minimum", soc_value
                )
            )
        elif soc_value is not None and soc_value <= bat.soc_derate_start:
            derated = True
            torque_limit = min(torque_limit, self.config.motor.max_torque_nm * 0.5)
            events.append(
                DiagnosticEvent(
                    now, SensorSignal.SOC, FaultCode.SOC_DERATE, "SOC derating active", soc_value
                )
            )

        if temp_value is not None and temp_value >= bat.temp_derate_start_c:
            derated = True
            torque_limit = min(torque_limit, self.config.motor.max_torque_nm * 0.7)
            events.append(
                DiagnosticEvent(
                    now,
                    SensorSignal.BATTERY_TEMP,
                    FaultCode.TEMP_DERATE,
                    "temperature derating active",
                    temp_value,
                )
            )

        permitted = max(
            -self.config.motor.max_torque_nm,
            min(requested_torque_nm, torque_limit),
        )

        return SupervisorOutput(
            state=self.state,
            permitted_torque_nm=permitted,
            fault_codes=frozenset(fault_codes),
            events=events,
            torque_limit_nm=torque_limit if derated else None,
            derated=derated,
        )

    def _release_derate(self, measurements: dict[str, Measurement]) -> bool:
        """Hysteresis: derating releases only when comfortably clear of thresholds."""
        bat = self.config.battery
        soc_m = measurements.get(SensorSignal.SOC)
        temp_m = measurements.get(SensorSignal.BATTERY_TEMP)
        if soc_m is not None and soc_m.is_finite():
            if soc_m.value <= bat.soc_derate_start * (
                1.0 - self.config.supervisor.derate_hysteresis
            ):
                return False
        if temp_m is not None and temp_m.is_finite():
            if temp_m.value >= bat.temp_derate_start_c * (
                1.0 + self.config.supervisor.derate_hysteresis
            ):
                return False
        return True

    def step(
        self,
        measurements: dict[str, Measurement],
        requested_torque_nm: float,
        now: float,
        reset_requested: bool = False,
    ) -> SupervisorOutput:
        if not math.isfinite(requested_torque_nm):
            requested_torque_nm = 0.0

        eval_out = self._evaluate(measurements, requested_torque_nm, now)
        critical_now = bool(eval_out.fault_codes & FaultCode.CRITICAL)

        if self.state == SupervisorState.INITIALISING:
            if critical_now:
                self.state = SupervisorState.FAULT_LATCHED
                self._latched = True
                self._active_faults = eval_out.fault_codes
                return SupervisorOutput(
                    state=self.state,
                    permitted_torque_nm=0.0,
                    fault_codes=eval_out.fault_codes,
                    events=eval_out.events,
                    derated=False,
                )
            # Soft constraints may already be active at start-up; enter DERATED
            # directly in that case, otherwise READY. Only critical faults block
            # the INITIALISING -> READY/DERATED transition.
            self.state = SupervisorState.DERATED if eval_out.derated else SupervisorState.READY
            self._initialized = True
            self._derated_active = eval_out.derated
            return SupervisorOutput(
                state=self.state,
                permitted_torque_nm=eval_out.permitted_torque_nm,
                fault_codes=eval_out.fault_codes,
                events=eval_out.events,
                torque_limit_nm=eval_out.torque_limit_nm,
                derated=eval_out.derated,
            )

        if self.state == SupervisorState.FAULT_LATCHED:
            events = list(eval_out.events)
            if reset_requested and not critical_now:
                self.state = SupervisorState.READY
                self._latched = False
                self._active_faults = frozenset()
                self._derated_active = False
                events.append(
                    DiagnosticEvent(
                        now, None, FaultCode.RESET, "fault reset accepted; returning to READY"
                    )
                )
                return SupervisorOutput(
                    state=self.state,
                    permitted_torque_nm=eval_out.permitted_torque_nm,
                    fault_codes=eval_out.fault_codes,
                    events=events,
                    torque_limit_nm=eval_out.torque_limit_nm,
                    derated=eval_out.derated,
                )
            events.append(
                DiagnosticEvent(
                    now,
                    None,
                    FaultCode.FAULT_LATCHED,
                    "fault remains latched; zero torque commanded",
                )
            )
            return SupervisorOutput(
                state=self.state,
                permitted_torque_nm=0.0,
                fault_codes=self._active_faults | eval_out.fault_codes,
                events=events,
                derated=False,
            )

        # READY or DERATED.
        if critical_now:
            self.state = SupervisorState.FAULT_LATCHED
            self._latched = True
            self._active_faults = eval_out.fault_codes
            events = list(eval_out.events)
            events.append(
                DiagnosticEvent(
                    now,
                    None,
                    FaultCode.FAULT_LATCHED,
                    "critical fault latched; zero torque commanded",
                )
            )
            return SupervisorOutput(
                state=self.state,
                permitted_torque_nm=0.0,
                fault_codes=eval_out.fault_codes,
                events=events,
                derated=False,
            )

        target_derated = eval_out.derated
        if target_derated and not self._derated_active:
            new_state = SupervisorState.DERATED
            self._derated_active = True
        elif not target_derated and self._derated_active:
            if self._release_derate(measurements):
                new_state = SupervisorState.READY
                self._derated_active = False
            else:
                new_state = SupervisorState.DERATED
        else:
            new_state = SupervisorState.DERATED if target_derated else SupervisorState.READY

        self.state = new_state
        return SupervisorOutput(
            state=self.state,
            permitted_torque_nm=eval_out.permitted_torque_nm,
            fault_codes=eval_out.fault_codes,
            events=eval_out.events,
            torque_limit_nm=eval_out.torque_limit_nm,
            derated=eval_out.derated,
        )
