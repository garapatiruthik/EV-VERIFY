"""Traceability self-test.

Asserts that every implemented requirement in requirements/requirements.json
has at least one collected pytest item carrying its requirement marker.
The marker collection itself is written to reports/traceability.json by the
pytest_collection_finish hook in tests/conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _collected():
    requirements = json.loads(
        (REPO_ROOT / "requirements" / "requirements.json").read_text(encoding="utf-8")
    )
    report = json.loads((REPO_ROOT / "reports" / "traceability.json").read_text(encoding="utf-8"))
    return requirements, report.get("collected", {})


@pytest.mark.unit
@pytest.mark.requirement("REQ-VER-001")
def test_every_implemented_requirement_has_a_test():
    requirements, collected = _collected()
    marker_to_nodes: dict[str, set[str]] = {}
    for nodeid, reqs in collected.items():
        for req_id in reqs:
            marker_to_nodes.setdefault(req_id, set()).add(nodeid)
    uncovered = [
        req["id"]
        for req in requirements
        if req.get("implemented", False) and not marker_to_nodes.get(req["id"])
    ]
    assert not uncovered, f"implemented requirements without tests: {uncovered}"
