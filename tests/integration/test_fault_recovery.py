"""Integration tests for fault latching and reset recovery."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig
from ev_verify.scenarios import sensor_dropout
from ev_verify.simulation import Simulation
from ev_verify.supervisor import SupervisorState


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-008")
def test_fault_stays_latched_after_condition_clears():
    config = AppConfig.default()
    scenario = sensor_dropout(seed=42)
    # No reset: fault must remain latched even though the nominal measurement
    # returns after the dropout interval.
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        fault_injector=scenario.fault_injector,
        reset_requested_at=None,
    )
    latched = [
        r for r in result.logger.records if r.supervisor_state == SupervisorState.FAULT_LATCHED
    ]
    assert len(latched) > 0
    # Records after the dropout onset (t>=3) stay latched until end.
    after = [r for r in result.logger.records if r.time_s >= 3.0]
    assert all(r.supervisor_state == SupervisorState.FAULT_LATCHED for r in after)
    assert all(r.applied_torque_nm == 0.0 for r in after)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-008")
@pytest.mark.requirement("REQ-BMS-006")
def test_dropout_recovery_after_reset():
    config = AppConfig.default()
    scenario = sensor_dropout(seed=42)
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        fault_injector=scenario.fault_injector,
        reset_requested_at=scenario.reset_requested_at,
    )
    # Before reset: latched.
    before = [r for r in result.logger.records if 3.0 <= r.time_s < scenario.reset_requested_at]
    assert len(before) > 0
    assert all(r.supervisor_state == SupervisorState.FAULT_LATCHED for r in before)
    # After reset (measurement safe): back to READY.
    after = [r for r in result.logger.records if r.time_s >= scenario.reset_requested_at]
    assert len(after) > 0
    assert all(r.supervisor_state == SupervisorState.READY for r in after)
