"""Typed sensor measurements and the nominal sensor interface.

Measurements are what the controller sees. Plant ground truth is kept
separate so a test can compare what the controller observed against what the
simulated plant actually contained.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Measurement:
    """A single typed sensor measurement."""

    signal: str
    value: float
    unit: str
    timestamp_s: float
    valid: bool = True
    reason: str | None = None

    def is_finite(self) -> bool:
        return math.isfinite(self.value)

    def is_stale(self, current_time_s: float, timeout_s: float) -> bool:
        if not self.valid:
            return True
        if not math.isfinite(self.timestamp_s) or not math.isfinite(current_time_s):
            return True
        if timeout_s <= 0:
            return False
        return (current_time_s - self.timestamp_s) > timeout_s


class SensorSignal:
    """Signal names used by the supervisor (constants, not magic strings)."""

    PACK_VOLTAGE: Final = "pack_voltage_v"
    PACK_CURRENT: Final = "pack_current_a"
    BATTERY_TEMP: Final = "battery_temp_c"
    MOTOR_SPEED: Final = "motor_speed_rpm"
    SOC: Final = "soc"


class SensorInterface:
    """Converts plant state into nominal sensor measurements.

    The supervisor must only consume these measurements; it never reads plant
    ground truth directly.
    """

    @staticmethod
    def pack_voltage(value: float, timestamp_s: float) -> Measurement:
        return Measurement(SensorSignal.PACK_VOLTAGE, value, "V", timestamp_s)

    @staticmethod
    def pack_current(value: float, timestamp_s: float) -> Measurement:
        return Measurement(SensorSignal.PACK_CURRENT, value, "A", timestamp_s)

    @staticmethod
    def battery_temp(value: float, timestamp_s: float) -> Measurement:
        return Measurement(SensorSignal.BATTERY_TEMP, value, "°C", timestamp_s)

    @staticmethod
    def motor_speed(value: float, timestamp_s: float) -> Measurement:
        return Measurement(SensorSignal.MOTOR_SPEED, value, "RPM", timestamp_s)

    @staticmethod
    def soc(value: float, timestamp_s: float) -> Measurement:
        return Measurement(SensorSignal.SOC, value, "1", timestamp_s)

    @staticmethod
    def invalid(signal: str, timestamp_s: float, reason: str) -> Measurement:
        return Measurement(signal, float("nan"), "", timestamp_s, valid=False, reason=reason)

    @staticmethod
    def from_battery_state(state, timestamp_s: float) -> dict[str, Measurement]:
        return {
            SensorSignal.PACK_VOLTAGE: SensorInterface.pack_voltage(
                state.terminal_voltage_v, timestamp_s
            ),
            SensorSignal.PACK_CURRENT: SensorInterface.pack_current(state.current_a, timestamp_s),
            SensorSignal.BATTERY_TEMP: SensorInterface.battery_temp(
                state.temperature_c, timestamp_s
            ),
            SensorSignal.SOC: SensorInterface.soc(state.soc, timestamp_s),
        }

    @staticmethod
    def from_motor_state(state, timestamp_s: float) -> dict[str, Measurement]:
        return {
            SensorSignal.MOTOR_SPEED: SensorInterface.motor_speed(state.speed_rpm, timestamp_s),
        }
