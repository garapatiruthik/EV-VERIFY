"""Battery pack model (low-order equivalent circuit).

Sign convention (used everywhere in this project):
  positive battery current  = discharge from the pack
  negative battery current  = regenerative charging into the pack

All default parameters are illustrative simulation values only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import BatteryConfig


@dataclass(frozen=True)
class BatteryState:
    """Immutable snapshot of battery plant ground truth."""

    soc: float
    terminal_voltage_v: float
    current_a: float
    temperature_c: float
    ambient_temperature_c: float
    open_circuit_voltage_v: float
    soc_clamped: bool
    heat_w: float


@dataclass
class BatteryPack:
    """Simple equivalent-circuit battery pack model."""

    config: BatteryConfig
    soc: float = 1.0
    temperature_c: float = 25.0

    def __post_init__(self) -> None:
        if not self._valid_soc(self.soc):
            raise ValueError(f"initial SOC out of range [0, 1]: {self.soc}")
        if not math.isfinite(self.temperature_c):
            raise ValueError("initial temperature must be finite")

    @staticmethod
    def _valid_soc(soc: float) -> bool:
        return math.isfinite(soc) and 0.0 <= soc <= 1.0

    def open_circuit_voltage(self, soc: float) -> float:
        """Open-circuit voltage via piecewise-linear interpolation of the table."""
        table = self.config.soc_voltage_table_v
        if soc <= table[0][0]:
            return table[0][1]
        if soc >= table[-1][0]:
            return table[-1][1]
        for (soc_low, volt_low), (soc_high, volt_high) in zip(table, table[1:], strict=False):
            if soc_low <= soc <= soc_high:
                span = soc_high - soc_low
                if span <= 0:
                    return volt_low
                frac = (soc - soc_low) / span
                return volt_low + frac * (volt_high - volt_low)
        return table[-1][1]

    def _clamp_soc(self, soc: float) -> tuple[float, bool]:
        if soc > 1.0:
            return 1.0, True
        if soc < 0.0:
            return 0.0, True
        return soc, False

    def step(self, current_a: float, dt_s: float, ambient_temp_c: float) -> BatteryState:
        """Advance the battery model by one time step.

        Args:
            current_a: pack current in amperes (positive = discharge).
            dt_s: time step in seconds (must be positive and finite).
            ambient_temp_c: ambient temperature in degrees C.

        Returns:
            BatteryState snapshot after the step.
        """
        if not math.isfinite(current_a):
            raise ValueError(f"current must be finite, got {current_a}")
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError(f"dt must be positive and finite, got {dt_s}")
        if not math.isfinite(ambient_temp_c):
            raise ValueError("ambient temperature must be finite")
        if not math.isfinite(self.config.capacity_ah) or self.config.capacity_ah <= 0:
            raise ValueError("battery capacity must be positive and finite")

        ocv_before = self.open_circuit_voltage(self.soc)
        # Terminal voltage: OCV minus IR drop (positive discharge current lowers V).
        terminal_voltage_v = ocv_before - current_a * self.config.internal_resistance_ohm
        if not math.isfinite(terminal_voltage_v):
            raise ValueError("computed terminal voltage is non-finite")

        # Coulomb counting: positive discharge current reduces SOC.
        charge_removed_ah = current_a * dt_s / 3600.0
        soc_next = self.soc - charge_removed_ah / self.config.capacity_ah
        soc_next, soc_clamped = self._clamp_soc(soc_next)

        ocv_after = self.open_circuit_voltage(soc_next)

        # Resistive heating; heat toward ambient via first-order thermal model.
        heat_w = current_a**2 * self.config.internal_resistance_ohm
        if not math.isfinite(heat_w):
            raise ValueError("computed heat is non-finite")
        dt_over_cap = dt_s / self.config.thermal_capacity_j_per_c
        temp_next = self.temperature_c + dt_over_cap * (
            heat_w - self.config.cooling_coefficient_w_per_c * (self.temperature_c - ambient_temp_c)
        )
        if not math.isfinite(temp_next):
            raise ValueError("computed temperature is non-finite")

        self.soc = soc_next
        self.temperature_c = temp_next

        return BatteryState(
            soc=soc_next,
            terminal_voltage_v=terminal_voltage_v,
            current_a=current_a,
            temperature_c=temp_next,
            ambient_temperature_c=ambient_temp_c,
            open_circuit_voltage_v=ocv_after,
            soc_clamped=soc_clamped,
            heat_w=heat_w,
        )
