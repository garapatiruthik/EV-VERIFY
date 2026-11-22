"""Command-line interface for EV-Verify.

Usage:
    python -m ev_verify.cli list-scenarios
    python -m ev_verify.cli run --scenario normal_city_drive --seed 42
    python -m ev_verify.cli run-all --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import AppConfig
from .scenarios import all_scenarios, list_scenario_names
from .simulation import Simulation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ev_verify", description="EV-Verify simulation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-scenarios", help="list built-in deterministic scenarios")

    run_p = sub.add_parser("run", help="run a single deterministic scenario")
    run_p.add_argument("--scenario", required=True, help="scenario name")
    run_p.add_argument("--seed", type=int, default=42, help="deterministic seed")
    run_p.add_argument("--duration", type=float, default=None, help="override duration in seconds")
    run_p.add_argument(
        "--output", default="reports/generated", help="output directory for CSV/JSON"
    )

    runall = sub.add_parser("run-all", help="run all built-in scenarios")
    runall.add_argument("--seed", type=int, default=42, help="deterministic seed")
    runall.add_argument(
        "--output", default="reports/generated", help="output directory for CSV/JSON"
    )

    return parser


def _write_outputs(logger, summary: dict, output_dir: str, scenario: str, seed: int) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{scenario}_seed{seed}.csv"
    json_path = out / f"{scenario}_seed{seed}.json"
    logger.write_csv(str(csv_path))
    duration = summary.get("duration_s", 0.0)
    dt = summary.get("dt_s", 0.0)
    logger.write_summary_json(str(json_path), duration, dt)
    print(f"  wrote {csv_path}")
    print(f"  wrote {json_path}")


def _run_scenario(name: str, seed: int, output_dir: str, duration: float | None) -> int:
    scenarios = all_scenarios()
    if name not in scenarios:
        print(f"error: unknown scenario '{name}'. Available: {', '.join(sorted(scenarios))}")
        return 2
    scenario = scenarios[name]
    config = AppConfig.default()
    sim = Simulation(config)
    dur = duration if duration is not None else scenario.duration_s
    result = sim.run(
        scenario=scenario.name,
        seed=seed,
        request_fn=scenario.request_fn,
        duration_s=dur,
        fault_injector=scenario.fault_injector,
        reset_requested_at=scenario.reset_requested_at,
        initial_soc=scenario.initial_soc,
        initial_temp_c=scenario.initial_temp_c,
    )
    summary = result.summary.to_dict()
    print(f"scenario: {scenario.name} (seed {seed}, duration {dur}s)")
    print(f"  final state: {summary['final_state']}")
    print(f"  steps: {summary['steps']}")
    print(f"  state transitions: {summary['state_transitions']}")
    print(f"  detected faults: {len(summary['detected_faults'])}")
    print(f"  max battery temp: {summary['max_battery_temp_c']:.2f} C")
    print(f"  min SOC: {summary['min_soc']:.4f}")
    print(f"  max |pack current|: {summary['max_pack_current_a']:.2f} A")
    _write_outputs(result.logger, summary, output_dir, scenario.name, seed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-scenarios":
        print("Built-in scenarios:")
        for name in list_scenario_names():
            print(f"  - {name}")
        return 0

    if args.command == "run":
        return _run_scenario(args.scenario, args.seed, args.output, args.duration)

    if args.command == "run-all":
        overall = 0
        for name in list_scenario_names():
            print(f"=== {name} ===")
            code = _run_scenario(name, args.seed, args.output, None)
            if code != 0:
                overall = code
        return overall

    print(f"error: unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
