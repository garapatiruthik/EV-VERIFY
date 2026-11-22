"""Unit tests for the battery pack model."""

from __future__ import annotations

import math

import pytest

from ev_verify.battery import BatteryPack
from ev_verify.config import AppConfig, BatteryConfig


def _config(**overrides):
    base = BatteryConfig()
    return BatteryConfig(**{**base.__dict__, **overrides})


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_soc_clamped_at_upper_limit():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.05)
    bat = BatteryPack(cfg, soc=1.0, temperature_c=25.0)
    state = bat.step(current_a=-1000.0, dt_s=1.0, ambient_temp_c=25.0)  # heavy charge
    assert state.soc == 1.0
    assert state.soc_clamped is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_soc_clamped_at_lower_limit():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.05)
    bat = BatteryPack(cfg, soc=0.0, temperature_c=25.0)
    state = bat.step(current_a=1000.0, dt_s=1.0, ambient_temp_c=25.0)  # heavy discharge
    assert state.soc == 0.0
    assert state.soc_clamped is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-002")
def test_positive_current_decreases_soc():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.0)
    bat = BatteryPack(cfg, soc=0.8, temperature_c=25.0)
    state = bat.step(current_a=100.0, dt_s=360.0, ambient_temp_c=25.0)  # 10 Ah removed
    assert state.soc == pytest.approx(0.6, abs=1e-9)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-002")
def test_negative_current_increases_soc():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.0)
    bat = BatteryPack(cfg, soc=0.2, temperature_c=25.0)
    state = bat.step(current_a=-100.0, dt_s=360.0, ambient_temp_c=25.0)  # 10 Ah added
    assert state.soc == pytest.approx(0.4, abs=1e-9)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-002")
def test_zero_current_preserves_soc():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.05)
    bat = BatteryPack(cfg, soc=0.5, temperature_c=25.0)
    state = bat.step(current_a=0.0, dt_s=100.0, ambient_temp_c=25.0)
    assert state.soc == pytest.approx(0.5, abs=1e-9)
    assert state.heat_w == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-003")
def test_terminal_voltage_discharge():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.05)
    bat = BatteryPack(cfg, soc=0.5, temperature_c=25.0)
    ocv = bat.open_circuit_voltage(0.5)
    state = bat.step(current_a=100.0, dt_s=1.0, ambient_temp_c=25.0)
    assert state.terminal_voltage_v == pytest.approx(ocv - 100.0 * 0.05, abs=1e-9)
    assert state.terminal_voltage_v < ocv


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-003")
def test_terminal_voltage_charge():
    cfg = _config(capacity_ah=50.0, internal_resistance_ohm=0.05)
    bat = BatteryPack(cfg, soc=0.5, temperature_c=25.0)
    ocv = bat.open_circuit_voltage(0.5)
    state = bat.step(current_a=-100.0, dt_s=1.0, ambient_temp_c=25.0)
    assert state.terminal_voltage_v == pytest.approx(ocv - (-100.0) * 0.05, abs=1e-9)
    assert state.terminal_voltage_v > ocv


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-003")
def test_open_circuit_voltage_interpolation():
    cfg = _config()
    bat = BatteryPack(cfg, soc=0.5, temperature_c=25.0)
    assert bat.open_circuit_voltage(0.5) == 350.0
    assert bat.open_circuit_voltage(0.0) == 280.0
    assert bat.open_circuit_voltage(1.0) == 410.0
    # midpoint between 0.25 (320) and 0.5 (350)
    assert bat.open_circuit_voltage(0.375) == pytest.approx(335.0, abs=1e-9)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-004")
def test_temperature_rises_under_load():
    cfg = _config(
        capacity_ah=50.0,
        internal_resistance_ohm=0.5,
        thermal_capacity_j_per_c=1000.0,
        cooling_coefficient_w_per_c=0.0,
        ambient_temp_c=25.0,
    )
    bat = BatteryPack(cfg, soc=0.8, temperature_c=25.0)
    state = bat.step(current_a=100.0, dt_s=10.0, ambient_temp_c=25.0)
    # heat = I^2*R = 5000 W over 10 s = 50000 J / 1000 J/C = 50 C rise
    assert state.temperature_c == pytest.approx(75.0, abs=1e-6)
    assert state.temperature_c > 25.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-004")
def test_temperature_cools_toward_ambient():
    cfg = _config(
        capacity_ah=50.0,
        internal_resistance_ohm=0.0,
        thermal_capacity_j_per_c=1000.0,
        cooling_coefficient_w_per_c=100.0,
        ambient_temp_c=25.0,
    )
    bat = BatteryPack(cfg, soc=0.8, temperature_c=55.0)
    state = bat.step(current_a=0.0, dt_s=10.0, ambient_temp_c=25.0)
    # cooling = 100 * (55-25) * 10 / 1000 = 30 C drop -> 25 C
    assert state.temperature_c == pytest.approx(25.0, abs=1e-6)
    assert state.temperature_c < 55.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_invalid_initial_soc_rejected():
    cfg = _config()
    with pytest.raises(ValueError):
        BatteryPack(cfg, soc=1.5, temperature_c=25.0)
    with pytest.raises(ValueError):
        BatteryPack(cfg, soc=float("nan"), temperature_c=25.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_invalid_current_rejected():
    bat = BatteryPack(_config(), soc=0.5, temperature_c=25.0)
    with pytest.raises(ValueError):
        bat.step(current_a=float("nan"), dt_s=1.0, ambient_temp_c=25.0)
    with pytest.raises(ValueError):
        bat.step(current_a=float("inf"), dt_s=1.0, ambient_temp_c=25.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_invalid_dt_rejected():
    bat = BatteryPack(_config(), soc=0.5, temperature_c=25.0)
    with pytest.raises(ValueError):
        bat.step(current_a=10.0, dt_s=0.0, ambient_temp_c=25.0)
    with pytest.raises(ValueError):
        bat.step(current_a=10.0, dt_s=-1.0, ambient_temp_c=25.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-001")
def test_negative_capacity_config_rejected():
    with pytest.raises(ValueError):
        AppConfig(battery=BatteryConfig(capacity_ah=-10.0)).validate()


@pytest.mark.unit
@pytest.mark.requirement("REQ-BAT-004")
def test_sustained_load_then_cool():
    cfg = _config(
        capacity_ah=50.0,
        internal_resistance_ohm=0.2,
        thermal_capacity_j_per_c=2000.0,
        cooling_coefficient_w_per_c=10.0,
        ambient_temp_c=25.0,
    )
    bat = BatteryPack(cfg, soc=0.8, temperature_c=25.0)
    hot = bat.step(current_a=100.0, dt_s=60.0, ambient_temp_c=25.0)
    assert hot.temperature_c > 25.0
    cool = bat.step(current_a=0.0, dt_s=600.0, ambient_temp_c=25.0)
    assert cool.temperature_c < hot.temperature_c
    assert math.isfinite(cool.temperature_c)
