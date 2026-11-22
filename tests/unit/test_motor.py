"""Unit tests for the electric motor model."""

from __future__ import annotations

import math

import pytest

from ev_verify.config import MotorConfig
from ev_verify.motor import Motor


def _config(**overrides):
    base = MotorConfig()
    return MotorConfig(**{**base.__dict__, **overrides})


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-001")
def test_positive_torque_increases_speed():
    cfg = _config(inertia_kgm2=0.5, viscous_friction_nm_per_rad_s=0.0, efficiency=1.0)
    mot = Motor(cfg, speed_rad_s=0.0)
    state = mot.step(applied_torque_nm=100.0, load_torque_nm=10.0, dt_s=1.0, pack_voltage_v=350.0)
    expected = (100.0 - 10.0) / 0.5 * 1.0
    assert state.speed_rad_s == pytest.approx(expected, abs=1e-9)
    assert state.speed_rpm == pytest.approx(expected * 60.0 / (2.0 * math.pi), abs=1e-6)
    assert state.applied_torque_nm == 100.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-001")
def test_load_torque_reduces_acceleration():
    cfg = _config(inertia_kgm2=0.5, viscous_friction_nm_per_rad_s=0.0, efficiency=1.0)
    mot1 = Motor(cfg, speed_rad_s=0.0)
    mot2 = Motor(cfg, speed_rad_s=0.0)
    s1 = mot1.step(100.0, 10.0, 1.0, 350.0)
    s2 = mot2.step(100.0, 90.0, 1.0, 350.0)
    assert s2.speed_rad_s < s1.speed_rad_s


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-001")
def test_viscous_friction_opposes_motion():
    cfg = _config(inertia_kgm2=0.5, viscous_friction_nm_per_rad_s=1.0, efficiency=1.0)
    mot = Motor(cfg, speed_rad_s=100.0)
    state = mot.step(applied_torque_nm=0.0, load_torque_nm=0.0, dt_s=1.0, pack_voltage_v=350.0)
    assert state.speed_rad_s < 100.0
    assert state.speed_rad_s >= 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-002")
def test_applied_torque_clamped_to_zero_min_speed():
    cfg = _config()
    mot = Motor(cfg, speed_rad_s=0.0)
    state = mot.step(applied_torque_nm=-500.0, load_torque_nm=0.0, dt_s=1.0, pack_voltage_v=350.0)
    # Negative torque at zero speed would reverse; forward-only model clamps.
    assert state.speed_rad_s == pytest.approx(0.0, abs=1e-9)


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-003")
def test_regenerative_torque_negative_electrical_power():
    cfg = _config(efficiency=1.0, viscous_friction_nm_per_rad_s=0.0)
    mot = Motor(cfg, speed_rad_s=500.0)
    state = mot.step(applied_torque_nm=-100.0, load_torque_nm=0.0, dt_s=0.1, pack_voltage_v=350.0)
    assert state.speed_rad_s == pytest.approx(480.0, abs=1e-9)
    assert state.mechanical_power_w < 0
    assert state.electrical_power_w < 0
    assert state.dc_current_a < 0  # current returned to pack


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-003")
def test_no_regen_at_zero_speed():
    cfg = _config(efficiency=1.0)
    mot = Motor(cfg, speed_rad_s=0.0)
    state = mot.step(applied_torque_nm=-100.0, load_torque_nm=0.0, dt_s=1.0, pack_voltage_v=350.0)
    assert state.mechanical_power_w == pytest.approx(0.0, abs=1e-9)
    assert state.electrical_power_w == pytest.approx(0.0, abs=1e-9)
    assert state.dc_current_a == pytest.approx(0.0, abs=1e-9)


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-002")
def test_efficiency_draws_more_electrical_than_mechanical():
    cfg = _config(efficiency=0.9)
    mot = Motor(cfg, speed_rad_s=100.0)
    state = mot.step(applied_torque_nm=100.0, load_torque_nm=0.0, dt_s=1.0, pack_voltage_v=350.0)
    mech = state.mechanical_power_w
    elec = state.electrical_power_w
    assert elec > mech > 0


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-001")
def test_invalid_inputs_rejected():
    mot = Motor(_config(), speed_rad_s=0.0)
    with pytest.raises(ValueError):
        mot.step(100.0, 0.0, float("nan"), 350.0)
    with pytest.raises(ValueError):
        mot.step(100.0, 0.0, 0.0, 350.0)
    with pytest.raises(ValueError):
        mot.step(100.0, 0.0, 1.0, 0.0)
    with pytest.raises(ValueError):
        mot.step(float("inf"), 0.0, 1.0, 350.0)
    with pytest.raises(ValueError):
        mot.step(100.0, float("inf"), 1.0, 350.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-001")
def test_negative_initial_speed_rejected():
    with pytest.raises(ValueError):
        Motor(_config(), speed_rad_s=-10.0)
