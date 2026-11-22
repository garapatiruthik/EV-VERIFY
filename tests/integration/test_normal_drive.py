"""Integration tests for normal drive operation."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig
from ev_verify.scenarios import normal_city_drive
from ev_verify.simulation import ScenarioRequest, Simulation
from ev_verify.supervisor import FaultCode, SupervisorState


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-SIM-001")
def test_determinism_identical_seed():
    config = AppConfig.default()
    scenario = normal_city_drive(seed=42)
    r1 = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    r2 = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    rows1 = [r.to_dict() for r in r1.logger.records]
    rows2 = [r.to_dict() for r in r2.logger.records]
    assert rows1 == rows2


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-LOG-001")
def test_telemetry_schema():
    config = AppConfig.default()
    scenario = normal_city_drive(seed=42)
    result = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    assert len(result.logger.records) > 0
    record = result.logger.records[0]
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


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-001")
@pytest.mark.requirement("REQ-BMS-002")
@pytest.mark.requirement("REQ-BMS-003")
@pytest.mark.requirement("REQ-BMS-005")
def test_normal_drive_no_critical_latch():
    config = AppConfig.default()
    scenario = normal_city_drive(seed=42)
    result = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    final = result.logger.records[-1]
    assert final.supervisor_state in (SupervisorState.READY, SupervisorState.DERATED)
    assert FaultCode.OVER_VOLTAGE not in final.fault_codes
    assert FaultCode.UNDER_VOLTAGE not in final.fault_codes
    assert FaultCode.OVER_TEMP not in final.fault_codes


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-MOT-002")
def test_applied_torque_respects_supervisor_limit():
    config = AppConfig.default()
    scenario = normal_city_drive(seed=42)
    result = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    limit = config.motor.max_torque_nm
    for record in result.logger.records:
        assert abs(record.applied_torque_nm) <= limit + 1e-9


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BAT-001")
def test_soc_stays_in_unit_interval():
    config = AppConfig.default()
    scenario = normal_city_drive(seed=42)
    result = Simulation(config).run(scenario.name, 42, scenario.request_fn, scenario.duration_s)
    for record in result.logger.records:
        assert 0.0 <= record.soc <= 1.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-SIM-001")
def test_run_rejects_invalid_inputs():
    config = AppConfig.default()
    sim = Simulation(config)
    request = lambda t: ScenarioRequest(t, 0.0, 0.0, 25.0)  # noqa: E731
    with pytest.raises(ValueError, match="duration_s must be positive"):
        sim.run("x", 1, request, -1.0)
    with pytest.raises(ValueError, match="dt_s must be positive"):
        sim.run("x", 1, request, 1.0, dt_s=0.0)
    with pytest.raises(ValueError, match="initial_soc must be in \[0, 1\]"):
        sim.run("x", 1, request, 1.0, initial_soc=1.5)
