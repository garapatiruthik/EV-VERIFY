"""Deterministic discrete-time simulation loop."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .battery import BatteryPack
from .config import AppConfig
from .fault_injection import FaultInjector
from .motor import Motor
from .sensors import SensorInterface
from .supervisor import Supervisor
from .telemetry import TelemetryLogger


@dataclass
class ScenarioRequest:
    """One control cycle's inputs to the plant."""

    time_s: float
    requested_torque_nm: float
    load_torque_nm: float
    ambient_temp_c: float


@dataclass
class SimulationResult:
    logger: TelemetryLogger
    summary: dict


class Simulation:
    """Deterministic simulation engine.

    Loop per step:
      1. read latest plant state
      2. convert plant state to nominal sensor measurements
      3. apply scheduled sensor faults (measurement layer only; plant ground
         truth is never mutated)
      4. pass measurements + requested torque to the supervisor
      5. obtain supervisor state, permitted torque and diagnostic events
      6. apply permitted torque to the motor model
      7. compute battery current/power from the motor's electrical demand
      8. update battery SOC/voltage/temperature
      9. append a structured telemetry record
      10. advance simulation time by dt
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.battery = BatteryPack(
            config.battery,
            soc=1.0,
            temperature_c=config.battery.ambient_temp_c,
        )
        self.motor = Motor(config.motor)
        self.supervisor = Supervisor(config)
        self.logger: TelemetryLogger | None = None
        self._bat_state = None
        self._mot_state = None

    def _initial_states(self) -> None:
        """Compute initial plant states with zero current/torque."""
        dt = self.config.simulation.dt_s
        ambient = self.config.battery.ambient_temp_c
        self._bat_state = self.battery.step(0.0, dt, ambient)
        self._mot_state = self.motor.step(0.0, 0.0, dt, self._bat_state.terminal_voltage_v)

    def run(
        self,
        scenario: str,
        seed: int,
        request_fn: Callable[[float], ScenarioRequest],
        duration_s: float,
        dt_s: float | None = None,
        fault_injector: FaultInjector | None = None,
        reset_requested_at: float | None = None,
        initial_soc: float | None = None,
        initial_temp_c: float | None = None,
    ) -> SimulationResult:
        if dt_s is None:
            dt_s = self.config.simulation.dt_s
        if duration_s <= 0:
            raise ValueError("duration_s must be positive")
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        if initial_soc is not None:
            if not (0.0 <= initial_soc <= 1.0):
                raise ValueError("initial_soc must be in [0, 1]")
            self.battery.soc = initial_soc
        if initial_temp_c is not None:
            self.battery.temperature_c = initial_temp_c

        self._initial_states()
        self.logger = TelemetryLogger(scenario, seed)
        t = 0.0
        prev_t = -math.inf

        while t < duration_s:
            now = t
            req = request_fn(now)

            # 1-2. latest plant state -> nominal sensor measurements.
            measurements: dict = {}
            measurements.update(SensorInterface.from_battery_state(self._bat_state, now))
            measurements.update(SensorInterface.from_motor_state(self._mot_state, now))

            # 3. scheduled sensor faults at the measurement layer only.
            fired = []
            if fault_injector is not None:
                measurements, fired = fault_injector.apply(measurements, prev_t, now)

            # 4-5. supervisor.
            reset_now = reset_requested_at is not None and now >= reset_requested_at
            out = self.supervisor.step(
                measurements,
                req.requested_torque_nm,
                now,
                reset_requested=reset_now,
            )

            # 6. apply permitted torque to the motor.
            self._mot_state = self.motor.step(
                out.permitted_torque_nm,
                req.load_torque_nm,
                dt_s,
                self._bat_state.terminal_voltage_v,
            )

            # 7-8. battery current from motor electrical demand; update battery.
            self._bat_state = self.battery.step(
                self._mot_state.dc_current_a, dt_s, req.ambient_temp_c
            )

            # 9. telemetry record (state after applying this cycle's torque).
            quality = "derated" if out.derated else ("fault" if out.fault_codes else "ok")
            self.logger.log(
                time_s=now,
                soc=self._bat_state.soc,
                pack_voltage_v=self._bat_state.terminal_voltage_v,
                pack_current_a=self._bat_state.current_a,
                battery_temp_c=self._bat_state.temperature_c,
                ambient_temp_c=req.ambient_temp_c,
                requested_torque_nm=req.requested_torque_nm,
                applied_torque_nm=out.permitted_torque_nm,
                motor_speed_rpm=self._mot_state.speed_rpm,
                supervisor_state=out.state,
                fault_codes=out.fault_codes,
                sensor_quality=quality,
                events=out.events,
            )

            # 10. advance time.
            prev_t = t
            t += dt_s

        summary = self.logger.summary(duration_s, dt_s)
        return SimulationResult(logger=self.logger, summary=summary)
