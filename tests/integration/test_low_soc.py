"""Integration tests for low-SOC derating."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig, BatteryConfig
from ev_verify.scenarios import low_soc
from ev_verify.simulation import Simulation
from ev_verify.supervisor import SupervisorState


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-007")
@pytest.mark.requirement("REQ-BAT-001")
def test_soc_derating_before_hard_limit():
    config = AppConfig(
        battery=BatteryConfig(
            capacity_ah=50.0,
            internal_resistance_ohm=0.05,
            max_discharge_current_a=2000.0,
            max_charge_current_a=2000.0,
            soc_derate_start=0.20,
            soc_hard_min=0.05,
        ),
        motor=AppConfig.default().motor,
        supervisor=AppConfig.default().supervisor,
        simulation=AppConfig.default().simulation,
    )
    scenario = low_soc(seed=42)
    result = Simulation(config).run(
        scenario.name,
        42,
        scenario.request_fn,
        scenario.duration_s,
        initial_soc=scenario.initial_soc,
    )
    records = result.logger.records
    derated = [r for r in records if r.supervisor_state == SupervisorState.DERATED]
    assert len(derated) > 0, "expected SOC-based torque derating"
    assert all(0.0 <= r.soc <= 1.0 for r in records)
