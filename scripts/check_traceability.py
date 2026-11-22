"""Requirements-to-test traceability checker.

Compares reports/traceability.json (produced by the pytest collection hook)
with requirements/requirements.json. Prints covered and uncovered requirement
IDs and returns a non-zero exit status when an implemented requirement has no
collected test carrying its marker.

Requirements flagged ``planned`` and not ``implemented`` are excluded from the
mandatory denominator and listed separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check requirements-to-test traceability")
    parser.add_argument("--requirements", default="requirements/requirements.json")
    parser.add_argument("--report", default="reports/traceability.json")
    args = parser.parse_args(argv)

    req_path = REPO_ROOT / args.requirements
    report_path = REPO_ROOT / args.report

    if not req_path.exists():
        print(f"error: requirements file not found: {req_path}")
        return 2
    if not report_path.exists():
        print(f"error: traceability report not found: {report_path} (run pytest first)")
        return 2

    requirements = json.loads(req_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    collected = report.get("collected", {})

    # Map requirement id -> set of node ids carrying its marker.
    marker_to_nodes: dict[str, set[str]] = {}
    for nodeid, reqs in collected.items():
        for req_id in reqs:
            marker_to_nodes.setdefault(req_id, set()).add(nodeid)

    covered = []
    uncovered = []
    planned = []
    mandatory = 0

    for req in requirements:
        req_id = req["id"]
        implemented = bool(req.get("implemented", False))
        if not implemented:
            planned.append(req_id)
            continue
        mandatory += 1
        nodes = marker_to_nodes.get(req_id, set())
        if nodes:
            covered.append((req_id, sorted(nodes)))
        else:
            uncovered.append(req_id)

    print("Requirements traceability check")
    print(f"  implemented requirements: {mandatory}")
    print(f"  covered: {len(covered)}")
    print(f"  uncovered: {len(uncovered)}")
    print(f"  planned (excluded from denominator): {len(planned)}")

    if covered:
        print("\nCovered requirements:")
        for req_id, nodes in covered:
            print(f"  {req_id}: {len(nodes)} test(s)")
            for n in nodes:
                print(f"    - {n}")

    if uncovered:
        print("\nUncovered implemented requirements (FAIL):")
        for req_id in uncovered:
            print(f"  {req_id}")

    if planned:
        print("\nPlanned but not implemented (excluded):")
        for req_id in planned:
            print(f"  {req_id}")

    traceability_pct = (len(covered) / mandatory * 100) if mandatory else 100.0
    print(f"\nTraceability: {len(covered)}/{mandatory} = {traceability_pct:.1f}%")

    if uncovered:
        print("\nRESULT: FAIL - implemented requirements without test coverage remain.")
        return 1
    print("\nRESULT: PASS - every implemented requirement has at least one test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
