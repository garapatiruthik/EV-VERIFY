# EV-Verify

Python-based e-powertrain verification test bench. Simulation only — not a production BMS, digital twin, HIL system, or safety-certified system. See README.md and docs/assumptions_and_limitations.md.

## Commands

Create/activate a venv (PowerShell):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run tests with branch coverage:
```
pytest --cov=ev_verify --cov-branch --cov-report=term-missing --cov-report=xml
```

Run traceability checker:
```
python scripts/check_traceability.py
```

Run a scenario:
```
python -m ev_verify.cli list-scenarios
python -m ev_verify.cli run --scenario normal_city_drive --seed 42
python -m ev_verify.cli run-all --seed 42
```

Lint:
```
ruff check src tests scripts
ruff format --check src tests scripts
```

CI workflow: `.github/workflows/ci.yml` (push/PR, Python 3.11 & 3.12 matrix, ruff, pytest+branch coverage, traceability check).

## Notes

- Deterministic seeds: every scenario uses a fixed seed; no network, current time, or hardware dependencies.
- All defaults are illustrative simulation values, not manufacturer specifications.
- Sensor faults are injected at the sensor boundary and never mutate plant ground truth.
