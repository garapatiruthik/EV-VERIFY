# Test Strategy

## Test directories

- `tests/unit/` — unit tests for battery, motor, sensors, fault injection,
  supervisor, and simulation components.
- `tests/integration/` — end-to-end simulation and scenario-level tests.
- `tests/property/` — property-based tests (Hypothesis) checking invariants such
  as SOC always in `[0, 1]`.

## Markers

Tests are marked with:

- `@pytest.mark.requirement("REQ-...")` — links a test to a requirement ID in
  `requirements/requirements.json`. Collected by `tests/conftest.py` into
  `reports/traceability.json` and verified by `scripts/check_traceability.py`.
- `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.property` —
  test category.
- `@pytest.mark.fault_injection`, `@pytest.mark.scenario` — domain tags.

Run by category:

```powershell
pytest -m unit
pytest -m integration
pytest -m property
```

## Property-based testing

Hypothesis is used in `tests/property/` to assert invariants across many
generated inputs (e.g. SOC stays in `[0, 1]` under arbitrary current profiles).

Locally, Hypothesis's native extension may be blocked by host Application
Control policy. Work around with:

```powershell
pytest -p no:hypothesispytest
```

GitHub Actions CI runs Hypothesis normally (no workaround flag).

## Traceability

Every implemented requirement must have at least one collected test carrying
its `@pytest.mark.requirement` marker. `scripts/check_traceability.py` fails CI
when an implemented requirement is uncovered. Requirements flagged `planned`
but not `implemented` are excluded from the mandatory denominator.

## Coverage

Branch coverage is required:

```powershell
pytest --cov=ev_verify --cov-branch --cov-report=term-missing --cov-report=xml
```

Some modules (CLI, config, scenarios, telemetry) are primarily exercised
through scenario integration runs rather than isolated unit tests.
