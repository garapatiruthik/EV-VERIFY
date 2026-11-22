"""Pytest configuration: fixtures and requirement traceability collection.

On collection finish, records each collected test node ID together with its
@ pytest.mark.requirement("REQ-...") markers into reports/traceability.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


@pytest.hookimpl(hookwrapper=True)
def pytest_collection_finish(session):
    outcome = yield
    outcome.get_result()
    report = {}
    for item in session.items:
        reqs = []
        for mark in item.iter_markers(name="requirement"):
            if mark.args:
                reqs.append(str(mark.args[0]))
        report[item.nodeid] = reqs
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "traceability.json", "w", encoding="utf-8") as handle:
        json.dump({"collected": report}, handle, indent=2)
