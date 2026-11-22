# EV-Verify

EV-Verify is a deterministic e-powertrain verification test bench. It simulates a battery and motor under drive-cycle scenarios, evaluates them through a supervisor protection layer, injects sensor faults at the measurement boundary, and records structured telemetry for every step. The project is designed to verify that protection logic, fault detection, torque derating, and latch/recovery behavior operate correctly across a range of simulated operating conditions.

## Purpose

The goal of EV-Verify is to provide a repeatable, self-contained environment for validating e-powertrain supervisory behavior. Every scenario uses a fixed seed with no dependence on network, wall-clock time, or hardware, so results are identical across runs. This makes the test bench suitable for regression checking, requirements traceability, and demonstrating that safety-relevant functions such as over-voltage, under-voltage, over-current, over-temperature, sensor dropout, and stale-sensor detection behave as specified.

## What was built

EV-Verify consists of a simulation core, a scenario library, a test suite, and a command-line interface.

**Simulation core (`src/ev_verify/`)**
- `config.py` — `AppConfig`: single source of all simulation constants (battery, motor, supervisor, simulation timing).
- `battery.py` — `BatteryPack`: low-order equivalent-circuit model tracking SOC, open-circuit voltage, terminal voltage (`OCV - I·R`), resistive heating, and first-order thermal response.
- `motor.py` — `Motor`: first-order rotational dynamics converting applied and load torque into speed, mechanical power, and DC current.
- `sensors.py` — `Measurement` and `SensorInterface`: converts plant ground truth into typed sensor measurements the supervisor consumes.
- `fault_injection.py` — `FaultSchedule` and `FaultInjector`: applies dropout, stale, spike, bias, and noise faults at the measurement boundary only; plant ground truth is never mutated.
- `supervisor.py` — deterministic state machine (`INITIALISING`, `READY`, `DERATED`, `FAULT_LATCHED`) evaluating critical thresholds, soft derating with hysteresis, and latch/reset behavior.
- `simulation.py` — `Simulation`: fixed-time-step loop advancing plant, sensors, faults, supervisor, and telemetry together.
- `scenarios.py` — ten built-in deterministic scenarios covering normal drive, steady cruise, hard acceleration, regenerative braking, low SOC, thermal stress, sensor dropout, sensor spike, sensor bias, and stale sensor.
- `telemetry.py` — `TelemetryLogger`: per-step records plus aggregated run summary written to CSV and JSON.
- `cli.py` — `list-scenarios`, `run`, and `run-all` commands.

**Tests (`tests/`)**
- `tests/unit/` — unit tests for battery, motor, sensors, fault injection, supervisor, and telemetry.
- `tests/integration/` — scenario-level and fault-transition tests.
- `tests/property/` — property-based invariants (for example, SOC remains within `[0, 1]`).
- `tests/conftest.py` — collects `@pytest.mark.requirement` markers into a traceability report.
- `tests/test_traceability.py` — verifies every implemented requirement has a covering test.

**Supporting tooling**
- `scripts/check_traceability.py` — compares collected requirement markers against `requirements/requirements.json` and fails on any uncovered implemented requirement.
- `.github/workflows/ci.yml` — CI running ruff lint/format, pytest with branch coverage, and the traceability checker on Python 3.11 and 3.12.
- `docs/` — architecture, requirements traceability, test strategy, and assumptions and limitations.

## Results

The current state of the repository is verified as follows:

| Check | Result |
|---|---|
| Tests | 86 passed |
| Lint (ruff check) | Pass |
| Format (ruff format --check) | Pass |
| Branch coverage | 79% |
| Requirements traceability | 20 / 20 covered (100%) |
| Scenarios executed | 10 / 10 complete, no hangs |

Across all ten scenarios run with seed 42, every scenario reaches a final state within its step budget. Protective scenarios (`hard_acceleration`, `low_soc`, `regenerative_braking`, `sensor_spike`, `stale_sensor`, `thermal_stress`) correctly latch into `FAULT_LATCHED` with zero commanded torque. Nominal scenarios (`normal_city_drive`, `steady_cruise`, `sensor_bias`) remain `READY` or `DERATED` without spurious trips. The `sensor_dropout` scenario detects the fault, latches, and recovers after an explicit reset at t = 9 s.

## Requirements

EV-Verify traces 20 requirements (IDs `REQ-BAT-001` through `REQ-VER-001`), each implemented and linked to at least one automated test. The traceability checker confirms 100% coverage of implemented requirements.

## How to run

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the full test suite with branch coverage:

```powershell
pytest --cov=ev_verify --cov-branch --cov-report=term-missing --cov-report=xml
```

Verify requirements traceability:

```powershell
python scripts/check_traceability.py
```

Run lint and format checks:

```powershell
ruff check src tests scripts
ruff format --check src tests scripts
```

Run a single scenario:

```powershell
python -m ev_verify.cli run --scenario normal_city_drive --seed 42
```

Run all scenarios:

```powershell
python -m ev_verify.cli run-all --seed 42
```

List available scenarios:

```powershell
python -m ev_verify.cli list-scenarios
```

Scenario outputs (CSV and JSON) are written to `reports/generated/`.

## Repository contents

```
EV-VERIFY/
├── .github/workflows/ci.yml      # CI: ruff, pytest+branch coverage, traceability
├── README.md
├── AGENTS.md                     # commands and project notes
├── pyproject.toml                # packaging, pytest, and ruff configuration
├── src/ev_verify/                # simulation core and CLI
├── tests/                        # unit, integration, and property tests
├── config/                       # simulation configuration
├── requirements/requirements.json# 20 traced requirements
├── scripts/check_traceability.py # requirements-to-tests traceability checker
├── reports/                      # traceability report and scenario outputs
└── docs/                         # architecture, traceability, test strategy, limitations
```

## License

MIT.