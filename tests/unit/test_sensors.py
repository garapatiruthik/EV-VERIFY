"""Unit tests for typed sensor measurements and staleness logic."""

from __future__ import annotations

import pytest

from ev_verify.sensors import Measurement, SensorInterface


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_valid_measurement():
    m = SensorInterface.pack_voltage(350.0, 1.0)
    assert m.signal == "pack_voltage_v"
    assert m.value == 350.0
    assert m.unit == "V"
    assert m.valid is True
    assert m.is_finite()


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_invalid_measurement_rejected():
    m = Measurement("pack_voltage_v", float("nan"), "V", 1.0, valid=False, reason="dropout")
    assert m.valid is False
    assert m.is_finite() is False


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_non_finite_measurement_rejected():
    m = SensorInterface.pack_voltage(float("inf"), 1.0)
    assert m.is_finite() is False
    m2 = SensorInterface.pack_voltage(float("nan"), 1.0)
    assert m2.is_finite() is False


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-002")
def test_stale_below_timeout():
    m = SensorInterface.battery_temp(40.0, 1.0)
    assert m.is_stale(current_time_s=1.5, timeout_s=1.0) is False
    assert m.is_stale(current_time_s=2.0, timeout_s=1.0) is False  # exactly at timeout is not stale


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-002")
def test_stale_at_timeout_boundary():
    # Staleness uses strictly greater than timeout: age == timeout is fresh.
    m = SensorInterface.battery_temp(40.0, 1.0)
    assert m.is_stale(current_time_s=2.0, timeout_s=1.0) is False


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-002")
def test_stale_above_timeout():
    m = SensorInterface.battery_temp(40.0, 1.0)
    assert m.is_stale(current_time_s=2.01, timeout_s=1.0) is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_stale_when_invalid():
    m = Measurement("pack_current_a", 10.0, "A", 1.0, valid=False, reason="dropout")
    assert m.is_stale(current_time_s=1.0, timeout_s=1.0) is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_invalid_timestamp_is_stale():
    m = SensorInterface.battery_temp(40.0, float("nan"))
    assert m.is_stale(current_time_s=1.0, timeout_s=1.0) is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_invalid_constructor_flags():
    m = SensorInterface.invalid("pack_voltage_v", 2.0, "sensor fault")
    assert m.valid is False
    assert m.reason == "sensor fault"
    assert not m.is_finite()
