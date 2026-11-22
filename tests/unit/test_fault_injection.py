"""Unit tests for the sensor fault injector (boundary injection only)."""

from __future__ import annotations

import math

import pytest

from ev_verify.fault_injection import FaultInjector, FaultSchedule
from ev_verify.sensors import SensorInterface


def _measurements():
    return {
        "pack_voltage_v": SensorInterface.pack_voltage(350.0, 1.0),
        "pack_current_a": SensorInterface.pack_current(10.0, 1.0),
        "battery_temp_c": SensorInterface.battery_temp(40.0, 1.0),
    }


PREV = -math.inf


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_dropout_marks_measurement_invalid():
    schedule = FaultSchedule()
    schedule.add(3.0, "pack_voltage_v", "dropout", "voltage sensor dropout")
    injector = FaultInjector(schedule)
    mutated, fired = injector.apply(_measurements(), PREV, 3.0)
    assert len(fired) == 1
    assert mutated["pack_voltage_v"].valid is False
    assert mutated["pack_voltage_v"].reason == "voltage sensor dropout"
    assert mutated["pack_current_a"].valid is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-001")
def test_spike_marks_invalid():
    schedule = FaultSchedule()
    schedule.add(5.0, "pack_voltage_v", "spike", "voltage spike", 500.0)
    injector = FaultInjector(schedule)
    mutated, fired = injector.apply(_measurements(), PREV, 5.0)
    assert mutated["pack_voltage_v"].valid is False
    assert mutated["pack_voltage_v"].value == 500.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-007")
def test_bias_shifts_value_but_remains_valid():
    schedule = FaultSchedule()
    schedule.add(4.0, "pack_current_a", "bias", "current bias", -80.0)
    injector = FaultInjector(schedule)
    mutated, fired = injector.apply(_measurements(), PREV, 4.0)
    assert mutated["pack_current_a"].valid is True
    assert mutated["pack_current_a"].value == pytest.approx(-70.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_each_fault_fires_only_once():
    schedule = FaultSchedule()
    schedule.add(3.0, "pack_voltage_v", "dropout", "voltage sensor dropout")
    injector = FaultInjector(schedule)
    original = _measurements()
    mutated, _ = injector.apply(original, PREV, 3.0)
    again, _ = injector.apply(_measurements(), 3.0, 4.0)
    assert original["pack_voltage_v"].valid is True
    assert mutated["pack_voltage_v"].valid is False
    # After firing once, the dropout is not reapplied; nominal value returns.
    assert again["pack_voltage_v"].valid is True


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_injector_does_not_mutate_input_dict():
    schedule = FaultSchedule()
    schedule.add(3.0, "pack_voltage_v", "dropout", "dropout")
    injector = FaultInjector(schedule)
    original = _measurements()
    injector.apply(original, PREV, 3.0)
    assert original["pack_voltage_v"].valid is True
    assert original["pack_voltage_v"].value == 350.0


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
def test_stale_on_missing_signal():
    schedule = FaultSchedule()
    schedule.add(2.0, "nonexistent_signal", "stale", "stale missing sensor")
    injector = FaultInjector(schedule)
    result, fired = injector.apply(_measurements(), PREV, 2.0)
    assert len(fired) == 1
    assert result["nonexistent_signal"].valid is True
    assert math.isnan(result["nonexistent_signal"].value)


@pytest.mark.unit
@pytest.mark.requirement("REQ-BMS-006")
@pytest.mark.requirement("REQ-SEN-001")
def test_bias_and_noise_without_values_use_zero():
    schedule = FaultSchedule()
    schedule.add(4.0, "pack_current_a", "bias", "bias no value", None)
    schedule.add(4.5, "pack_current_a", "noise", "noise no value", None)
    injector = FaultInjector(schedule)
    result, _ = injector.apply(_measurements(), PREV, 4.5)
    assert result["pack_current_a"].valid is True
    assert result["pack_current_a"].value == pytest.approx(10.0)


@pytest.mark.unit
@pytest.mark.requirement("REQ-SEN-002")
def test_stale_timestamp_freezes_persistently():
    schedule = FaultSchedule()
    schedule.add(4.0, "battery_temp_c", "stale", "temp timestamp frozen")
    injector = FaultInjector(schedule)
    mutated, _ = injector.apply(
        {"battery_temp_c": SensorInterface.battery_temp(40.0, 4.0)}, PREV, 4.0
    )
    assert mutated["battery_temp_c"].timestamp_s == 4.0
    assert mutated["battery_temp_c"].valid is True
    # The frozen timestamp persists on later steps with fresh nominal data.
    later, _ = injector.apply({"battery_temp_c": SensorInterface.battery_temp(40.0, 5.5)}, 4.0, 5.5)
    assert later["battery_temp_c"].timestamp_s == 4.0
    assert later["battery_temp_c"].valid is True
    assert later["battery_temp_c"].value == 40.0
