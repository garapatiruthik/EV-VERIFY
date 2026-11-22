"""Property-based tests for core simulation invariants.

Uses Hypothesis when importable. This host's application-control policy can
block Hypothesis's native extension; in that case each property still runs
once with fixed arguments so the invariants are exercised.
"""

from __future__ import annotations

import math

import pytest

from ev_verify.battery import BatteryPack
from ev_verify.config import AppConfig, BatteryConfig
from ev_verify.scenarios import steady_cruise
from ev_verify.simulation import Simulation
from ev_verify.supervisor import FaultCode, Supervisor, SupervisorState

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:  # pragma: no cover - environment without a usable hypothesis
    HYPOTHESIS_AVAILABLE = False


def _measurements():
    from ev_verify.sensors import SensorInterface

    return {
        "pack_voltage_v": SensorInterface.pack_voltage(350.0, 0.5),
        "pack_current_a": SensorInterface.pack_current(10.0, 0.5),
        "battery_temp_c": SensorInterface.battery_temp(40.0, 0.5),
        "soc": SensorInterface.soc(0.5, 0.5),
        "motor_speed_rpm": SensorInterface.motor_speed(1000.0, 0.5),
    }


def _body_soc(soc, current, dt, ambient):
    bat = BatteryPack(BatteryConfig(), soc=soc, temperature_c=ambient)
    state = bat.step(current_a=current, dt_s=dt, ambient_temp_c=ambient)
    assert 0.0 <= state.soc <= 1.0
    assert state.soc_clamped in (True, False)


def _body_finite(soc, current, dt, ambient):
    bat = BatteryPack(BatteryConfig(), soc=soc, temperature_c=ambient)
    state = bat.step(current_a=current, dt_s=dt, ambient_temp_c=ambient)
    assert all(
        math.isfinite(v)
        for v in (
            state.soc,
            state.terminal_voltage_v,
            state.current_a,
            state.temperature_c,
            state.open_circuit_voltage_v,
            state.heat_w,
        )
    )


def _body_torque(torque):
    sup = Supervisor(AppConfig.default())
    sup.step(_measurements(), torque, now=0.5)
    out = sup.step(_measurements(), torque, now=0.6)
    assert -400.0 - 1e-9 <= out.permitted_torque_nm <= 400.0 + 1e-9


def _body_latched():
    from ev_verify.sensors import Measurement, SensorSignal

    sup = Supervisor(AppConfig.default())
    m = _measurements()
    m[SensorSignal.PACK_VOLTAGE] = Measurement(
        SensorSignal.PACK_VOLTAGE, 430.1, "V", 0.5, valid=True
    )
    out = sup.step(m, 100.0, now=0.5)
    assert out.state == SupervisorState.FAULT_LATCHED
    m_safe = _measurements()
    out = sup.step(m_safe, 1000.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert out.permitted_torque_nm == 0.0
    out = sup.step(m_safe, 1000.0, now=0.7, reset_requested=True)
    assert out.state == SupervisorState.READY
    assert out.permitted_torque_nm == pytest.approx(400.0)


def _body_determinism():
    config = AppConfig.default()
    scenario = steady_cruise(seed=7)
    r1 = Simulation(config).run(scenario.name, 7, scenario.request_fn, scenario.duration_s)
    r2 = Simulation(config).run(scenario.name, 7, scenario.request_fn, scenario.duration_s)
    assert [r.to_dict() for r in r1.logger.records] == [r.to_dict() for r in r2.logger.records]


def _body_invalid_sensor():
    from ev_verify.sensors import Measurement, SensorSignal

    sup = Supervisor(AppConfig.default())
    m = _measurements()
    m[SensorSignal.PACK_VOLTAGE] = Measurement(
        SensorSignal.PACK_VOLTAGE, float("nan"), "V", 0.5, valid=False, reason="dropout"
    )
    out = sup.step(m, 100.0, now=0.5)
    assert FaultCode.SENSOR_INVALID in out.fault_codes
    assert out.permitted_torque_nm == 0.0


_float = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_current = st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False)
_dt = st.floats(min_value=0.001, max_value=10.0, allow_nan=False, allow_infinity=False)
_ambient = st.floats(min_value=-20.0, max_value=60.0, allow_nan=False, allow_infinity=False)
_torque = st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False)

_common = settings(max_examples=60, deadline=None)


def _mark(req_id, fn):
    fn = pytest.mark.property(fn)
    fn = pytest.mark.requirement(req_id)(fn)
    return fn


if HYPOTHESIS_AVAILABLE:
    test_soc_always_in_unit_interval = _mark(
        "REQ-BAT-001",
        _common(given(soc=_float, current=_current, dt=_dt, ambient=_ambient)(_body_soc)),
    )
    test_soc_always_in_unit_interval.__name__ = "test_soc_always_in_unit_interval"

    test_outputs_finite_for_valid_inputs = _mark(
        "REQ-BAT-004",
        _mark(
            "REQ-BAT-003",
            _common(given(soc=_float, current=_current, dt=_dt, ambient=_ambient)(_body_finite)),
        ),
    )
    test_outputs_finite_for_valid_inputs.__name__ = "test_outputs_finite_for_valid_inputs"

    test_permitted_torque_bounded_by_supervisor_limit = _mark(
        "REQ-MOT-002",
        _common(given(torque=_torque)(_body_torque)),
    )
    test_permitted_torque_bounded_by_supervisor_limit.__name__ = (
        "test_permitted_torque_bounded_by_supervisor_limit"
    )

    test_identical_scenario_and_seed_produce_identical_traces = _mark(
        "REQ-SIM-001", _body_determinism
    )
    test_identical_scenario_and_seed_produce_identical_traces.__name__ = (
        "test_identical_scenario_and_seed_produce_identical_traces"
    )

    test_invalid_sensor_cannot_be_silently_trusted = _mark("REQ-SEN-001", _body_invalid_sensor)
    test_invalid_sensor_cannot_be_silently_trusted.__name__ = (
        "test_invalid_sensor_cannot_be_silently_trusted"
    )

    test_latched_critical_fault_never_produces_positive_traction = _mark(
        "REQ-BMS-008", _body_latched
    )
    test_latched_critical_fault_never_produces_positive_traction.__name__ = (
        "test_latched_critical_fault_never_produces_positive_traction"
    )
else:
    test_soc_always_in_unit_interval = _mark(
        "REQ-BAT-001", lambda: _body_soc(0.5, 10.0, 0.01, 25.0)
    )
    test_soc_always_in_unit_interval.__name__ = "test_soc_always_in_unit_interval"

    test_outputs_finite_for_valid_inputs = _mark(
        "REQ-BAT-004",
        _mark("REQ-BAT-003", lambda: _body_finite(0.5, 10.0, 0.01, 25.0)),
    )
    test_outputs_finite_for_valid_inputs.__name__ = "test_outputs_finite_for_valid_inputs"

    test_permitted_torque_bounded_by_supervisor_limit = _mark(
        "REQ-MOT-002", lambda: _body_torque(10000.0)
    )
    test_permitted_torque_bounded_by_supervisor_limit.__name__ = (
        "test_permitted_torque_bounded_by_supervisor_limit"
    )

    test_identical_scenario_and_seed_produce_identical_traces = _mark(
        "REQ-SIM-001", _body_determinism
    )
    test_identical_scenario_and_seed_produce_identical_traces.__name__ = (
        "test_identical_scenario_and_seed_produce_identical_traces"
    )

    test_invalid_sensor_cannot_be_silently_trusted = _mark("REQ-SEN-001", _body_invalid_sensor)
    test_invalid_sensor_cannot_be_silently_trusted.__name__ = (
        "test_invalid_sensor_cannot_be_silently_trusted"
    )

    test_latched_critical_fault_never_produces_positive_traction = _mark(
        "REQ-BMS-008", _body_latched
    )
    test_latched_critical_fault_never_produces_positive_traction.__name__ = (
        "test_latched_critical_fault_never_produces_positive_traction"
    )
