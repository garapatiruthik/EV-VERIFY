"""Deterministic synthetic drive-cycle scenarios.

All data is simulated; no measured vehicle data is used. Each scenario is
reproducible given its name and seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .config import AppConfig
from .fault_injection import FaultInjector, FaultSchedule
from .simulation import ScenarioRequest


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    duration_s: float
    request_fn: Callable[[float], ScenarioRequest]
    fault_injector: FaultInjector | None = None
    reset_requested_at: float | None = None
    initial_soc: float | None = None
    initial_temp_c: float | None = None
    description: str = ""


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normal_city_drive(seed: int = 42, duration_s: float = 20.0) -> Scenario:
    """Variable traction torque, stops and low-speed operation.

    Expected: remain READY or enter only documented temporary derating.
    """

    def request_fn(t: float) -> ScenarioRequest:
        # Piecewise torque profile: accelerate, cruise, stop, repeat.
        phase = t % 8.0
        if phase < 2.0:
            torque = 150.0 * (phase / 2.0)  # ramp up
        elif phase < 4.0:
            torque = 150.0  # hold
        elif phase < 5.0:
            torque = 150.0 * (1.0 - (phase - 4.0))  # ramp down
        else:
            torque = 0.0  # stop
        load = 20.0 + 10.0 * math.sin(t)
        return ScenarioRequest(t, torque, load, 25.0)

    return Scenario(
        name="normal_city_drive",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        description="Variable traction with stops; expect READY or brief derating.",
    )


def steady_cruise(seed: int = 42, duration_s: float = 20.0) -> Scenario:
    """Stable moderate torque and load; expected stable operation."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 100.0, 30.0, 25.0)

    return Scenario(
        name="steady_cruise",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        description="Constant moderate torque; stable operation expected.",
    )


def hard_acceleration(seed: int = 42, duration_s: float = 10.0) -> Scenario:
    """High positive torque/current; torque limiting or over-current response."""

    def request_fn(t: float) -> ScenarioRequest:
        torque = 600.0 if t < 5.0 else 0.0  # exceeds motor max torque
        return ScenarioRequest(t, torque, 10.0, 25.0)

    return Scenario(
        name="hard_acceleration",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        description="High torque demand; supervisor torque limiting expected.",
    )


def regenerative_braking(seed: int = 42, duration_s: float = 15.0) -> Scenario:
    """Negative torque while moving; negative pack current and charge limits."""

    def request_fn(t: float) -> ScenarioRequest:
        # Spin up first, then brake regeneratively.
        torque = 200.0 if t < 5.0 else -150.0
        load = 10.0
        return ScenarioRequest(t, torque, load, 25.0)

    return Scenario(
        name="regenerative_braking",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        description="Negative torque while rotating; expect negative pack current.",
    )


def low_soc(seed: int = 42, duration_s: float = 20.0) -> Scenario:
    """Start near the soft SOC threshold; torque derating near hard limit."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 200.0, 20.0, 25.0)

    return Scenario(
        name="low_soc",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        initial_soc=0.22,
        description="Starts near SOC derate threshold; expect derating then hard-limit behavior.",
    )


def thermal_stress(seed: int = 42, duration_s: float = 60.0) -> Scenario:
    """Sustained load in warm ambient; temperature rise, derating, hard protection."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 250.0, 30.0, 40.0)

    return Scenario(
        name="thermal_stress",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        initial_temp_c=40.0,
        description="Warm ambient + sustained load; expect temp rise, derating, possible hard trip.",
    )


def sensor_dropout(seed: int = 42, duration_s: float = 15.0) -> Scenario:
    """Remove a safety-critical measurement for a defined interval."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 100.0, 20.0, 25.0)

    schedule = FaultSchedule()
    # Single dropout onset at t=3.0. The nominal valid measurement naturally
    # returns afterward, but the fault stays latched until an explicit reset.
    schedule.add(3.0, "pack_voltage_v", "dropout", "sensor dropout: pack voltage unavailable")

    return Scenario(
        name="sensor_dropout",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        fault_injector=FaultInjector(schedule),
        reset_requested_at=9.0,
        description="Pack voltage dropout; expect detection, zero torque, latching, then reset recovery.",
    )


def sensor_spike(seed: int = 42, duration_s: float = 15.0) -> Scenario:
    """Sudden implausible measurement (over-voltage spike)."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 50.0, 10.0, 25.0)

    schedule = FaultSchedule()
    schedule.add(5.0, "pack_voltage_v", "spike", "voltage spike: implausible over-voltage", 500.0)

    return Scenario(
        name="sensor_spike",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        fault_injector=FaultInjector(schedule),
        description="Voltage spike; expect validity/range policy response.",
    )


def sensor_bias(seed: int = 42, duration_s: float = 15.0) -> Scenario:
    """Persistent offset on a measurement."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 100.0, 20.0, 25.0)

    schedule = FaultSchedule()
    schedule.add(4.0, "pack_current_a", "bias", "current sensor bias offset", -80.0)

    return Scenario(
        name="sensor_bias",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        fault_injector=FaultInjector(schedule),
        description="Persistent current offset; simplified model reports the biased measurement.",
    )


def stale_sensor(seed: int = 42, duration_s: float = 15.0) -> Scenario:
    """Stop advancing one sensor timestamp; verify stale-data detection."""

    def request_fn(t: float) -> ScenarioRequest:
        return ScenarioRequest(t, 100.0, 20.0, 25.0)

    schedule = FaultSchedule()
    schedule.add(4.0, "battery_temp_c", "stale", "temperature sensor timestamp frozen")

    return Scenario(
        name="stale_sensor",
        seed=seed,
        duration_s=duration_s,
        request_fn=request_fn,
        fault_injector=FaultInjector(schedule),
        description="Frozen temperature timestamp; expect stale detection at timeout boundary.",
    )


def all_scenarios() -> dict[str, Scenario]:
    return {
        s.name: s
        for s in (
            normal_city_drive(),
            steady_cruise(),
            hard_acceleration(),
            regenerative_braking(),
            low_soc(),
            thermal_stress(),
            sensor_dropout(),
            sensor_spike(),
            sensor_bias(),
            stale_sensor(),
        )
    }


def list_scenario_names() -> list[str]:
    return sorted(all_scenarios().keys())


def build_config_overrides(scenario: Scenario) -> AppConfig:
    """Scenario-specific config overrides (defaults remain illustrative)."""
    config = AppConfig.default()
    if scenario.name == "low_soc":
        # Start SOC near the derate threshold by discharging the pack first.
        pass
    if scenario.name == "thermal_stress":
        config = AppConfig(
            battery=config.battery,
            motor=config.motor,
            supervisor=config.supervisor,
            simulation=config.simulation,
        )
    return config
