"""EV-Verify: Python-based E-powertrain verification test bench.

Simulation only — not a production BMS, digital twin, HIL system, or
safety-certified system. See docs/assumptions_and_limitations.md.
"""

from .config import AppConfig
from .scenarios import Scenario, all_scenarios, list_scenario_names
from .simulation import ScenarioRequest, Simulation

__all__ = [
    "AppConfig",
    "Simulation",
    "ScenarioRequest",
    "all_scenarios",
    "list_scenario_names",
    "Scenario",
]
