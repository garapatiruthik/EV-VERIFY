"""Electric motor model (simplified forward-rotating).

Model: first-order rotational dynamics
    alpha = (applied_torque - load_torque - friction * omega) / inertia
    omega += alpha * dt

Reverse rotation is not modelled: motor speed clamps at zero (no reverse
operation unless deliberately modelled and tested).

Sign convention:
  positive applied torque  = traction, draws energy from the pack
  negative applied torque  = regenerative braking, returns energy to the pack
  (regeneration only while rotating; zero speed -> zero regen energy)

All default parameters are illustrative simulation values only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import MotorConfig


@dataclass(frozen=True)
class MotorState:
    """Immutable snapshot of motor plant ground truth."""

    speed_rad_s: float
    speed_rpm: float
    applied_torque_nm: float
    load_torque_nm: float
    mechanical_power_w: float
    electrical_power_w: float  # positive = draw from pack, negative = return
    dc_current_a: float  # positive = discharge from pack


@dataclass
class Motor:
    """Simplified forward-rotating motor model."""

    config: MotorConfig
    speed_rad_s: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.speed_rad_s) or self.speed_rad_s < self.config.min_speed_rad_s:
            raise ValueError("initial motor speed must be finite and not below min_speed_rad_s")

    def step(
        self,
        applied_torque_nm: float,
        load_torque_nm: float,
        dt_s: float,
        pack_voltage_v: float,
    ) -> MotorState:
        """Advance the motor model by one time step.

        Args:
            applied_torque_nm: torque applied to the rotor (supervisor-limited).
            load_torque_nm: opposing load torque.
            dt_s: time step (positive, finite).
            pack_voltage_v: pack terminal voltage used to convert electrical
                power to DC current (must be positive and finite).

        Returns:
            MotorState snapshot after the step.
        """
        if not math.isfinite(applied_torque_nm):
            raise ValueError(f"applied torque must be finite, got {applied_torque_nm}")
        if not math.isfinite(load_torque_nm):
            raise ValueError(f"load torque must be finite, got {load_torque_nm}")
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError(f"dt must be positive and finite, got {dt_s}")
        if not math.isfinite(pack_voltage_v) or pack_voltage_v <= 0:
            raise ValueError(f"pack voltage must be positive and finite, got {pack_voltage_v}")

        friction_nm = self.config.viscous_friction_nm_per_rad_s * self.speed_rad_s
        net_torque_nm = applied_torque_nm - load_torque_nm - friction_nm
        alpha_rad_s2 = net_torque_nm / self.config.inertia_kgm2
        speed_next = self.speed_rad_s + alpha_rad_s2 * dt_s

        # Prevent invalid reverse rotation; forward-only model clamps at zero.
        if speed_next < self.config.min_speed_rad_s:
            speed_next = self.config.min_speed_rad_s

        self.speed_rad_s = speed_next
        speed_rpm = speed_next * 60.0 / (2.0 * math.pi)

        mechanical_power_w = applied_torque_nm * speed_next
        # Efficiency estimate: traction draws electrical/mech, regen returns mech*eff.
        if mechanical_power_w >= 0:
            electrical_power_w = mechanical_power_w / self.config.efficiency
        else:
            electrical_power_w = mechanical_power_w * self.config.efficiency

        dc_current_a = electrical_power_w / pack_voltage_v

        return MotorState(
            speed_rad_s=speed_next,
            speed_rpm=speed_rpm,
            applied_torque_nm=applied_torque_nm,
            load_torque_nm=load_torque_nm,
            mechanical_power_w=mechanical_power_w,
            electrical_power_w=electrical_power_w,
            dc_current_a=dc_current_a,
        )
