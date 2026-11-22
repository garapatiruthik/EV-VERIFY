"""Integration tests for supervisor fault transitions."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig
from ev_verify.fault_injection import FaultInjector, FaultSchedule
from ev_verify.scenarios import sensor_dropout, sensor_spike, thermal_stress
from ev_verify.simulation import Simulation
from ev_verify.supervisor import SupervisorState


def _request(t):
    return type(
        "R",
        (),
        {"time_s": t, "requested_torque_nm": 100.0, "load_torque_nm": 20.0, "ambient_temp_c": 25.0},
    )()


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-006")
def test_over_voltage_spike_safe_response():
    config = AppConfig.default()
    scenario = sensor_spike(seed=42)
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        fault_injector=scenario.fault_injector,
    )
    latched = [
        r for r in result.logger.records if r.supervisor_state == SupervisorState.FAULT_LATCHED
    ]
    assert len(latched) > 0
    assert all(r.applied_torque_nm == 0.0 for r in latched)
    assert any("SENSOR_INVALID" in r.fault_codes for r in latched)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-006")
def test_under_voltage_spike_safe_response():
    config = AppConfig.default()
    schedule = FaultSchedule()
    schedule.add(5.0, "pack_voltage_v", "spike", "under-voltage injection", 200.0)
    result = Simulation(config).run(
        "under_voltage",
        42,
        _request,
        12.0,
        fault_injector=FaultInjector(schedule),
    )
    latched = [
        r for r in result.logger.records if r.supervisor_state == SupervisorState.FAULT_LATCHED
    ]
    assert len(latched) > 0
    assert all(r.applied_torque_nm == 0.0 for r in latched)
    assert any("SENSOR_INVALID" in r.fault_codes for r in latched)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-006")
def test_over_temperature_spike_safe_response():
    config = AppConfig.default()
    schedule = FaultSchedule()
    schedule.add(5.0, "battery_temp_c", "spike", "over-temperature injection", 70.0)
    result = Simulation(config).run(
        "over_temp",
        42,
        _request,
        12.0,
        fault_injector=FaultInjector(schedule),
    )
    latched = [
        r for r in result.logger.records if r.supervisor_state == SupervisorState.FAULT_LATCHED
    ]
    assert len(latched) > 0
    assert all(r.applied_torque_nm == 0.0 for r in latched)
    assert any("SENSOR_INVALID" in r.fault_codes for r in latched)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-006")
def test_sensor_dropout_safe_response():
    config = AppConfig.default()
    scenario = sensor_dropout(seed=42)
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        fault_injector=scenario.fault_injector,
    )
    faults = [
        r for r in result.logger.records if r.supervisor_state == SupervisorState.FAULT_LATCHED
    ]
    assert len(faults) > 0, "expected dropout to latch a fault"
    assert all(r.applied_torque_nm == 0.0 for r in faults)
    assert any("SENSOR_INVALID" in r.fault_codes for r in faults)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-007")
def test_thermal_stress_derates_before_trip():
    config = AppConfig(
        battery=AppConfig.default().battery,
        motor=AppConfig.default().motor,
        supervisor=AppConfig.default().supervisor,
        simulation=AppConfig.default().simulation,
    )
    # Aggressive thermal parameters so the pack heats within the scenario.
    config = AppConfig(
        battery=config.battery.__class__(
            capacity_ah=50.0,
            internal_resistance_ohm=1.0,
            thermal_capacity_j_per_c=200.0,
            cooling_coefficient_w_per_c=2.0,
            ambient_temp_c=40.0,
            over_temp_c=65.0,
            temp_derate_start_c=50.0,
            soc_derate_start=0.20,
            soc_hard_min=0.05,
        ),
        motor=config.motor,
        supervisor=config.supervisor,
        simulation=config.simulation,
    )
    scenario = thermal_stress(seed=42)
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        initial_temp_c=scenario.initial_temp_c,
    )
    derated = [r for r in result.logger.records if r.supervisor_state == SupervisorState.DERATED]
    assert len(derated) > 0, "expected temperature derating before any hard trip"
