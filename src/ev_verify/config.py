"""Configuration for the EV-Verify simulation.

All default values are illustrative simulation values only. They are not
manufacturer specifications, production limits, cell ratings, or safe
operating limits for any real vehicle or battery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BatteryConfig:
    """Illustrative battery pack parameters."""

    capacity_ah: float = 50.0
    nominal_voltage_v: float = 350.0
    voltage_min_v: float = 280.0
    voltage_max_v: float = 420.0
    # Piecewise-linear SOC -> open-circuit voltage table (SOC fraction, V).
    # Illustrative only: a roughly linear pack curve.
    soc_voltage_table_v: tuple[tuple[float, float], ...] = (
        (0.0, 280.0),
        (0.25, 320.0),
        (0.5, 350.0),
        (0.75, 380.0),
        (1.0, 410.0),
    )
    internal_resistance_ohm: float = 0.05
    max_discharge_current_a: float = 300.0
    max_charge_current_a: float = 100.0
    # Protective (hard) thresholds.
    over_voltage_v: float = 430.0
    under_voltage_v: float = 250.0
    over_temp_c: float = 65.0
    # Thermal model.
    thermal_capacity_j_per_c: float = 5000.0
    cooling_coefficient_w_per_c: float = 50.0
    ambient_temp_c: float = 25.0
    # Soft constraints / derating.
    soc_derate_start: float = 0.20
    soc_hard_min: float = 0.05
    temp_derate_start_c: float = 50.0


@dataclass(frozen=True)
class MotorConfig:
    """Illustrative motor parameters."""

    inertia_kgm2: float = 0.5
    viscous_friction_nm_per_rad_s: float = 0.2
    efficiency: float = 0.90
    max_torque_nm: float = 400.0
    # Hard stop: reverse rotation is not modelled; speed clamps at zero.
    min_speed_rad_s: float = 0.0


@dataclass(frozen=True)
class SupervisorConfig:
    """Illustrative supervisor / BMS thresholds and timing."""

    stale_sensor_timeout_s: float = 1.0
    # Hysteresis band (fraction of threshold) applied before re-tripping after
    # a soft constraint leaves the derating region.
    derate_hysteresis: float = 0.05


@dataclass(frozen=True)
class SimulationConfig:
    """Simulation timing and scenario defaults."""

    dt_s: float = 0.01
    default_seed: int = 42
    default_duration_s: float = 20.0


@dataclass(frozen=True)
class AppConfig:
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    motor: MotorConfig = field(default_factory=MotorConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        def get(section: str, key: str, default: Any) -> Any:
            return data.get(section, {}).get(key, default)

        def table(key: str) -> tuple[tuple[float, float], ...]:
            raw = data.get("battery", {}).get(key)
            if raw is None:
                return BatteryConfig.soc_voltage_table_v
            return tuple((float(row[0]), float(row[1])) for row in raw)

        return cls(
            battery=BatteryConfig(
                capacity_ah=float(get("battery", "capacity_ah", 50.0)),
                nominal_voltage_v=float(get("battery", "nominal_voltage_v", 350.0)),
                voltage_min_v=float(get("battery", "voltage_min_v", 280.0)),
                voltage_max_v=float(get("battery", "voltage_max_v", 420.0)),
                soc_voltage_table_v=table("soc_voltage_table_v"),
                internal_resistance_ohm=float(get("battery", "internal_resistance_ohm", 0.05)),
                max_discharge_current_a=float(get("battery", "max_discharge_current_a", 300.0)),
                max_charge_current_a=float(get("battery", "max_charge_current_a", 100.0)),
                over_voltage_v=float(get("battery", "over_voltage_v", 430.0)),
                under_voltage_v=float(get("battery", "under_voltage_v", 250.0)),
                over_temp_c=float(get("battery", "over_temp_c", 65.0)),
                thermal_capacity_j_per_c=float(get("battery", "thermal_capacity_j_per_c", 5000.0)),
                cooling_coefficient_w_per_c=float(
                    get("battery", "cooling_coefficient_w_per_c", 50.0)
                ),
                ambient_temp_c=float(get("battery", "ambient_temp_c", 25.0)),
                soc_derate_start=float(get("battery", "soc_derate_start", 0.20)),
                soc_hard_min=float(get("battery", "soc_hard_min", 0.05)),
                temp_derate_start_c=float(get("battery", "temp_derate_start_c", 50.0)),
            ),
            motor=MotorConfig(
                inertia_kgm2=float(get("motor", "inertia_kgm2", 0.5)),
                viscous_friction_nm_per_rad_s=float(
                    get("motor", "viscous_friction_nm_per_rad_s", 0.2)
                ),
                efficiency=float(get("motor", "efficiency", 0.90)),
                max_torque_nm=float(get("motor", "max_torque_nm", 400.0)),
                min_speed_rad_s=float(get("motor", "min_speed_rad_s", 0.0)),
            ),
            supervisor=SupervisorConfig(
                stale_sensor_timeout_s=float(get("supervisor", "stale_sensor_timeout_s", 1.0)),
                derate_hysteresis=float(get("supervisor", "derate_hysteresis", 0.05)),
            ),
            simulation=SimulationConfig(
                dt_s=float(get("simulation", "dt_s", 0.01)),
                default_seed=int(get("simulation", "default_seed", 42)),
                default_duration_s=float(get("simulation", "default_duration_s", 20.0)),
            ),
        )

    @classmethod
    def from_json(cls, path: str) -> "AppConfig":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data)

    @classmethod
    def default(cls) -> "AppConfig":
        return cls()

    def validate(self) -> None:
        """Validate configuration values. Raises ValueError on nonsense config."""
        bat = self.battery
        mot = self.motor
        sup = self.supervisor
        sim = self.simulation
        if not _is_finite(bat.capacity_ah) or bat.capacity_ah <= 0:
            raise ValueError("battery.capacity_ah must be positive and finite")
        if not _is_finite(bat.internal_resistance_ohm) or bat.internal_resistance_ohm < 0:
            raise ValueError("battery.internal_resistance_ohm must be non-negative and finite")
        if not _is_finite(bat.over_voltage_v) or not _is_finite(bat.under_voltage_v):
            raise ValueError("battery voltage thresholds must be finite")
        if bat.under_voltage_v >= bat.over_voltage_v:
            raise ValueError("battery.under_voltage_v must be below over_voltage_v")
        if not _is_finite(bat.over_temp_c) or bat.over_temp_c <= 0:
            raise ValueError("battery.over_temp_c must be positive and finite")
        if not _is_finite(bat.thermal_capacity_j_per_c) or bat.thermal_capacity_j_per_c <= 0:
            raise ValueError("battery.thermal_capacity_j_per_c must be positive and finite")
        if not _is_finite(bat.cooling_coefficient_w_per_c) or bat.cooling_coefficient_w_per_c < 0:
            raise ValueError("battery.cooling_coefficient_w_per_c must be non-negative and finite")
        if not (0.0 < bat.soc_hard_min < bat.soc_derate_start < 1.0):
            raise ValueError("require 0 < soc_hard_min < soc_derate_start < 1")
        if not _is_finite(mot.inertia_kgm2) or mot.inertia_kgm2 <= 0:
            raise ValueError("motor.inertia_kgm2 must be positive and finite")
        if not (0.0 < mot.efficiency <= 1.0):
            raise ValueError("motor.efficiency must be in (0, 1]")
        if not _is_finite(sup.stale_sensor_timeout_s) or sup.stale_sensor_timeout_s <= 0:
            raise ValueError("supervisor.stale_sensor_timeout_s must be positive and finite")
        if not _is_finite(sim.dt_s) or sim.dt_s <= 0:
            raise ValueError("simulation.dt_s must be positive and finite")


def _is_finite(value: float) -> bool:
    import math

    return math.isfinite(value)
