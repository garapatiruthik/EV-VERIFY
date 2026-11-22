"""Run all built-in scenarios and write CSV/JSON reports."""

from __future__ import annotations

from ev_verify.cli import _run_scenario
from ev_verify.scenarios import list_scenario_names


def main() -> int:
    overall = 0
    for name in list_scenario_names():
        print(f"=== {name} ===")
        code = _run_scenario(name, 42, "reports/generated", None)
        if code != 0:
            overall = code
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
