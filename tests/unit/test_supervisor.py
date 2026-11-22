"""Unit tests for the BMS / powertrain supervisor state machine."""

from __future__ import annotations

import pytest

from ev_verify.config import AppConfig
from ev_verify.sensors import (
    Measurement,
    SensorInterface,
    SensorSignal,
)
from ev_verify.supervisor import (
    FaultCode,
    Supervisor,
    SupervisorState,
)


def _measurements(
    voltage=350.0,
    current=10.0,
    temp=40.0,
    soc=0.5,
    speed=1000.0,
    t=1.0,
    valid=True,
):
    m = {
        SensorSignal.PACK_VOLTAGE: SensorInterface.pack_voltage(voltage, t),
        SensorSignal.PACK_CURRENT: SensorInterface.pack_current(current, t),
        SensorSignal.BATTERY_TEMP: SensorInterface.battery_temp(temp, t),
        SensorSignal.SOC: SensorInterface.soc(soc, t),
        SensorSignal.MOTOR_SPEED: SensorInterface.motor_speed(speed, t),
    }
    if not valid:
        for k in m:
            m[k] = Measurement(k, float("nan"), "", t, valid=False, reason="bad")
    return m


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-001")
def test_initialising_to_ready():
    sup = Supervisor(AppConfig.default())
    out = sup.step(_measurements(t=0.5), requested_torque_nm=100.0, now=0.5)
    assert out.state == SupervisorState.READY
    assert out.permitted_torque_nm == 100.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-001")
def test_over_voltage_trips_strictly_above_threshold():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    # Exactly at threshold: no trip (> semantics).
    out = sup.step(_measurements(voltage=430.0, t=0.5), 100.0, now=0.5)
    assert out.state == SupervisorState.READY
    assert FaultCode.OVER_VOLTAGE not in out.fault_codes
    # Just above: trip + latch.
    out = sup.step(_measurements(voltage=430.1, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.OVER_VOLTAGE in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-002")
def test_under_voltage_trips_strictly_below_threshold():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(voltage=250.0, t=0.5), 100.0, now=0.5)
    assert out.state == SupervisorState.READY
    assert FaultCode.UNDER_VOLTAGE not in out.fault_codes
    out = sup.step(_measurements(voltage=249.9, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.UNDER_VOLTAGE in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-003")
def test_over_current_discharge_fault():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(current=300.0, t=0.5), 100.0, now=0.5)
    assert FaultCode.OVER_CURRENT_DISCHARGE not in out.fault_codes
    out = sup.step(_measurements(current=300.1, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.OVER_CURRENT_DISCHARGE in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-004")
def test_over_current_charge_fault():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(current=-100.0, t=0.5), 100.0, now=0.5)
    assert FaultCode.OVER_CURRENT_CHARGE not in out.fault_codes
    out = sup.step(_measurements(current=-100.1, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.OVER_CURRENT_CHARGE in out.fault_codes


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-005")
def test_over_temperature_fault():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(temp=65.0, t=0.5), 100.0, now=0.5)
    assert FaultCode.OVER_TEMP not in out.fault_codes
    out = sup.step(_measurements(temp=65.1, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.OVER_TEMP in out.fault_codes


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_missing_measurement_is_invalid_fault():
    sup = Supervisor(AppConfig.default())
    m = _measurements(t=0.5)
    del m[SensorSignal.PACK_VOLTAGE]
    out = sup.step(m, 100.0, now=0.5)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.SENSOR_INVALID in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_non_finite_measurement_is_invalid_fault():
    sup = Supervisor(AppConfig.default())
    m = _measurements(t=0.5)
    m[SensorSignal.PACK_CURRENT] = Measurement(
        SensorSignal.PACK_CURRENT, float("nan"), "A", 0.5, valid=True
    )
    out = sup.step(m, 100.0, now=0.5)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.SENSOR_INVALID in out.fault_codes


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_low_soc_torque_derating():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(soc=0.15, t=0.5), requested_torque_nm=300.0, now=0.5)
    assert out.state == SupervisorState.DERATED
    assert out.derated is True
    assert out.permitted_torque_nm == pytest.approx(200.0)  # 400 * 0.5


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_high_temp_torque_derating():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(temp=55.0, t=0.5), requested_torque_nm=300.0, now=0.5)
    assert out.state == SupervisorState.DERATED
    assert out.permitted_torque_nm == pytest.approx(280.0)  # 400 * 0.7


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_soc_hard_min_is_critical_fault():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(soc=0.05, t=0.5), 100.0, now=0.5)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.UNDER_VOLTAGE in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-008")
def test_fault_stays_latched_after_condition_clears():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    sup.step(_measurements(voltage=430.1, t=0.5), 100.0, now=0.5)
    assert sup.state == SupervisorState.FAULT_LATCHED
    # Measurement returns to normal.
    out = sup.step(_measurements(voltage=350.0, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-008")
def test_reset_requires_safe_conditions():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    sup.step(_measurements(voltage=430.1, t=0.5), 100.0, now=0.5)
    # Reset while still critical: stays latched.
    out = sup.step(_measurements(voltage=430.1, t=0.6), 100.0, now=0.6, reset_requested=True)
    assert out.state == SupervisorState.FAULT_LATCHED
    # Reset with safe condition: returns to READY.
    out = sup.step(_measurements(voltage=350.0, t=0.7), 100.0, now=0.7, reset_requested=True)
    assert out.state == SupervisorState.READY


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-008")
def test_reset_without_request_stays_lathed():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    sup.step(_measurements(voltage=430.1, t=0.5), 100.0, now=0.5)
    out = sup.step(_measurements(voltage=350.0, t=0.6), 100.0, now=0.6)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-002")
def test_permitted_torque_never_exceeds_limit():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    sup.step(_measurements(t=0.5), 100.0, now=0.5)  # reach READY
    out = sup.step(_measurements(t=0.6), requested_torque_nm=10000.0, now=0.6)
    assert out.permitted_torque_nm == pytest.approx(400.0)
    out = sup.step(_measurements(t=0.7), requested_torque_nm=-10000.0, now=0.7)
    assert out.permitted_torque_nm == pytest.approx(-400.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-002")
def test_stale_measurement_triggers_fault():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    # Fresh.
    out = sup.step(_measurements(t=0.5), 100.0, now=0.5)
    assert FaultCode.SENSOR_STALE not in out.fault_codes
    # Measurement timestamp frozen well in the past -> stale at now.
    m = _measurements(t=0.5)
    out = sup.step(m, 100.0, now=2.0)
    assert out.state == SupervisorState.FAULT_LATCHED
    assert FaultCode.SENSOR_STALE in out.fault_codes


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-001")
def test_invalid_measurement_cannot_be_trusted_as_valid():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    m = _measurements(t=0.5)
    m[SensorSignal.PACK_VOLTAGE] = Measurement(
        SensorSignal.PACK_VOLTAGE, float("nan"), "V", 0.5, valid=False, reason="dropout"
    )
    out = sup.step(m, 100.0, now=0.5)
    assert FaultCode.SENSOR_INVALID in out.fault_codes
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-MOT-002")
def test_non_finite_requested_torque_safe_default():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    sup.step(_measurements(t=0.5), 100.0, now=0.5)
    out = sup.step(_measurements(t=0.6), float("nan"), now=0.6)
    assert out.state == SupervisorState.READY
    assert out.permitted_torque_nm == 0.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_soc_derating_releases_with_hysteresis():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(soc=0.15, t=0.5), 300.0, now=0.5)
    assert out.state == SupervisorState.DERATED
    # Release threshold: 0.20 * (1 - 0.05) = 0.19. Still inside the band.
    out = sup.step(_measurements(soc=0.18, t=0.6), 300.0, now=0.6)
    assert out.state == SupervisorState.DERATED
    # Comfortably clear: derating releases.
    out = sup.step(_measurements(soc=0.25, t=0.7), 300.0, now=0.7)
    assert out.state == SupervisorState.READY


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_temp_derating_releases_with_hysteresis():
    cfg = AppConfig.default()
    sup = Supervisor(cfg)
    out = sup.step(_measurements(temp=55.0, t=0.5), 300.0, now=0.5)
    assert out.state == SupervisorState.DERATED
    # Release threshold: 50.0 * (1 + 0.05) = 52.5 C.
    out = sup.step(_measurements(temp=51.0, t=0.6), 300.0, now=0.6)
    assert out.state == SupervisorState.DERATED
    out = sup.step(_measurements(temp=45.0, t=0.7), 300.0, now=0.7)
    assert out.state == SupervisorState.READY
