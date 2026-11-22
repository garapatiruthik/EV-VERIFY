"""Unit tests for the telemetry logger schema."""

from __future__ import annotations

import pytest

from ev_verify.supervisor import DiagnosticEvent, FaultCode
from ev_verify.telemetry import TelemetryLogger


@pytest.mark.unit
@pytest.mark.requirement("REQ-LOG-001")
def test_step_record_contains_required_fields():
    logger = TelemetryLogger("normal_city_drive", 42)
    events = [DiagnosticEvent(1.0, "pack_voltage_v", FaultCode.OVER_VOLTAGE, "trip", 430.1)]
    logger.log(
        time_s=1.0,
        soc=0.8,
        pack_voltage_v=350.0,
        pack_current_a=10.0,
        battery_temp_c=40.0,
        ambient_temp_c=25.0,
        requested_torque_nm=100.0,
        applied_torque_nm=100.0,
        motor_speed_rpm=1200.0,
        supervisor_state="READY",
        fault_codes=frozenset(),
        sensor_quality="ok",
        events=events,
    )
    record = logger.records[0]
    d = record.to_dict()
    for field in (
        "time_s",
        "scenario",
        "seed",
        "soc",
        "pack_voltage_v",
        "pack_current_a",
        "battery_temp_c",
        "ambient_temp_c",
        "requested_torque_nm",
        "applied_torque_nm",
        "motor_speed_rpm",
        "supervisor_state",
        "fault_codes",
        "sensor_quality",
        "events",
    ):
        assert field in d
    assert record.scenario == "normal_city_drive"
    assert record.seed == 42
    assert "OVER_VOLTAGE" in record.fault_codes or "OVER_VOLTAGE" in record.events
