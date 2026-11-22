"""Structured telemetry and event logging for simulation runs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from typing import Any

from .supervisor import DiagnosticEvent


@dataclass(frozen=True)
class StepRecord:
    """A single simulation step's telemetry record."""

    time_s: float
    scenario: str
    seed: int
    soc: float
    pack_voltage_v: float
    pack_current_a: float
    battery_temp_c: float
    ambient_temp_c: float
    requested_torque_nm: float
    applied_torque_nm: float
    motor_speed_rpm: float
    supervisor_state: str
    fault_codes: str
    sensor_quality: str
    events: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "scenario": self.scenario,
            "seed": self.seed,
            "soc": self.soc,
            "pack_voltage_v": self.pack_voltage_v,
            "pack_current_a": self.pack_current_a,
            "battery_temp_c": self.battery_temp_c,
            "ambient_temp_c": self.ambient_temp_c,
            "requested_torque_nm": self.requested_torque_nm,
            "applied_torque_nm": self.applied_torque_nm,
            "motor_speed_rpm": self.motor_speed_rpm,
            "supervisor_state": self.supervisor_state,
            "fault_codes": self.fault_codes,
            "sensor_quality": self.sensor_quality,
            "events": self.events,
        }


@dataclass
class RunSummary:
    """Aggregated summary of one scenario run."""

    scenario: str
    seed: int
    duration_s: float
    dt_s: float
    steps: int
    final_state: str
    state_transitions: int
    detected_faults: list[dict[str, Any]]
    torque_derating_steps: int
    max_battery_temp_c: float
    min_soc: float
    max_pack_current_a: float
    assertion_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "seed": self.seed,
            "duration_s": self.duration_s,
            "dt_s": self.dt_s,
            "steps": self.steps,
            "final_state": self.final_state,
            "state_transitions": self.state_transitions,
            "detected_faults": self.detected_faults,
            "torque_derating_steps": self.torque_derating_steps,
            "max_battery_temp_c": self.max_battery_temp_c,
            "min_soc": self.min_soc,
            "max_pack_current_a": self.max_pack_current_a,
            "assertion_failures": self.assertion_failures,
        }


class TelemetryLogger:
    """Collects step records and builds a run summary."""

    def __init__(self, scenario: str, seed: int) -> None:
        self.scenario = scenario
        self.seed = seed
        self.records: list[StepRecord] = []
        self._previous_state: str | None = None
        self.state_transitions = 0
        self.detected_faults: list[dict[str, Any]] = []
        self._fault_codes_seen: set[str] = set()
        self.torque_derating_steps = 0

    def log(
        self,
        time_s: float,
        soc: float,
        pack_voltage_v: float,
        pack_current_a: float,
        battery_temp_c: float,
        ambient_temp_c: float,
        requested_torque_nm: float,
        applied_torque_nm: float,
        motor_speed_rpm: float,
        supervisor_state: str,
        fault_codes: frozenset[str],
        sensor_quality: str,
        events: list[DiagnosticEvent] | None = None,
    ) -> None:
        from .supervisor import FaultCode

        event_strings = []
        if events:
            for ev in events:
                event_strings.append(f"{ev.time_s:.3f}s {ev.code} {ev.message}".strip())
                if ev.code in FaultCode.CRITICAL and ev.code not in self._fault_codes_seen:
                    self._fault_codes_seen.add(ev.code)
                    self.detected_faults.append({
                        "time_s": ev.time_s,
                        "signal": ev.signal,
                        "code": ev.code,
                        "message": ev.message,
                        "value": ev.value,
                    })
        if self._previous_state is not None and supervisor_state != self._previous_state:
            self.state_transitions += 1
        self._previous_state = supervisor_state

        if sensor_quality == "derated":
            self.torque_derating_steps += 1

        self.records.append(
            StepRecord(
                time_s=time_s,
                scenario=self.scenario,
                seed=self.seed,
                soc=soc,
                pack_voltage_v=pack_voltage_v,
                pack_current_a=pack_current_a,
                battery_temp_c=battery_temp_c,
                ambient_temp_c=ambient_temp_c,
                requested_torque_nm=requested_torque_nm,
                applied_torque_nm=applied_torque_nm,
                motor_speed_rpm=motor_speed_rpm,
                supervisor_state=supervisor_state,
                fault_codes=",".join(sorted(fault_codes)),
                sensor_quality=sensor_quality,
                events=" | ".join(event_strings),
            )
        )

    def summary(self, duration_s: float, dt_s: float) -> RunSummary:
        temps = [r.battery_temp_c for r in self.records] or [0.0]
        socs = [r.soc for r in self.records] or [0.0]
        currents = [abs(r.pack_current_a) for r in self.records] or [0.0]
        final_state = self.records[-1].supervisor_state if self.records else "INITIALISING"
        return RunSummary(
            scenario=self.scenario,
            seed=self.seed,
            duration_s=duration_s,
            dt_s=dt_s,
            steps=len(self.records),
            final_state=final_state,
            state_transitions=self.state_transitions,
            detected_faults=self.detected_faults,
            torque_derating_steps=self.torque_derating_steps,
            max_battery_temp_c=max(temps),
            min_soc=min(socs),
            max_pack_current_a=max(currents),
        )

    def write_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=StepRecord.__dataclass_fields__.keys())
            writer.writeheader()
            for record in self.records:
                writer.writerow(record.to_dict())

    def write_summary_json(self, path: str, duration_s: float, dt_s: float) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.summary(duration_s, dt_s).to_dict(), handle, indent=2)
