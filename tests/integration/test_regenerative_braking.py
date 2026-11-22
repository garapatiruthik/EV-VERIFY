"""Integration tests for regenerative braking."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig, BatteryConfig
from ev_verify.simulation import ScenarioRequest, Simulation


def _regen_request(t):
    torque = 100.0 if t < 5.0 else -150.0
    return ScenarioRequest(t, torque, 10.0, 25.0)


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-MOT-003")
def test_regen_produces_negative_pack_current():
    config = AppConfig(
        battery=BatteryConfig(
            capacity_ah=50.0,
            internal_resistance_ohm=0.05,
            max_discharge_current_a=2000.0,
            max_charge_current_a=2000.0,
        ),
        motor=AppConfig.default().motor,
        supervisor=AppConfig.default().supervisor,
        simulation=AppConfig.default().simulation,
    )
    result = Simulation(config).run(
        "regen",
        42,
        _regen_request,
        15.0,
    )
    neg_currents = [r for r in result.logger.records if r.pack_current_a < -1.0]
    assert len(neg_currents) > 0, "expected negative pack current during regen"


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-004")
def test_charge_current_limit_respected():
    config = AppConfig(
        battery=BatteryConfig(
            capacity_ah=50.0,
            internal_resistance_ohm=0.05,
            max_discharge_current_a=2000.0,
            max_charge_current_a=100.0,
        ),
        motor=AppConfig.default().motor,
        supervisor=AppConfig.default().supervisor,
        simulation=AppConfig.default().simulation,
    )
    result = Simulation(config).run(
        "regen_limit",
        42,
        _regen_request,
        15.0,
    )
    limit = config.battery.max_charge_current_a
    # One control-cycle latency is expected: once the over-charge current is
    # observed, the supervisor must latch and command zero torque thereafter.
    latched = False
    for record in result.logger.records:
        if latched:
            assert record.applied_torque_nm == 0.0
        if record.pack_current_a < -limit:
            latched = True
    assert latched, "expected the charge limit to be exceeded and latched"


@pytest.mark.integration
@pytest.mark.scenario
@pytest.mark.requirement("REQ-BMS-004")
@pytest.mark.requirement("REQ-BAT-002")
def test_regen_increases_soc():
    config = AppConfig(
        battery=BatteryConfig(
            capacity_ah=50.0,
            internal_resistance_ohm=0.05,
            max_discharge_current_a=2000.0,
            max_charge_current_a=2000.0,
        ),
        motor=AppConfig.default().motor,
        supervisor=AppConfig.default().supervisor,
        simulation=AppConfig.default().simulation,
    )
    result = Simulation(config).run(
        "regen_soc",
        42,
        _regen_request,
        15.0,
    )
    records = result.logger.records
    assert records[-1].soc >= min(r.soc for r in records)
