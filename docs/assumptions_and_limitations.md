# Assumptions and Limitations

EV-Verify is a Python-based e-powertrain verification test bench. It is a
simulation tool only.

## Not a production system

This project is **not**:
- a production Battery Management System (BMS),
- a digital twin,
- a Hardware-in-the-Loop (HIL) system, or
- a safety-certified system.

Do not use it for real vehicle control, functional safety certification, or
production powertrain verification without appropriate engineering review.

## Simulation assumptions

- All default values are illustrative simulation values, not manufacturer
  specifications.
- Every scenario uses a fixed seed. There are no network, current-time, or
  hardware dependencies, so runs are deterministic given the same seed.
- Sensor faults are injected at the sensor boundary (measurement layer) and
  never mutate the plant's hidden ground-truth state.
- The supervisor evaluates derived limits against filtered measurements; it is
  a simplified model of a real BMS/motor-controller protection strategy.
- Time advances in fixed discrete steps; there is no variable-step or
  real-time execution.

## Coverage and traceability

- Branch coverage is measured with `pytest --cov-branch`. Some modules
  (CLI, config, scenarios, telemetry) have branches exercised only by
  integration/scenario paths rather than unit tests.
- Requirements traceability is enforced by `scripts/check_traceability.py`,
  which compares pytest requirement markers against `requirements/requirements.json`.
- Requirements flagged `planned` but not `implemented` are excluded from the
  mandatory traceability denominator.

## Local environment notes

- Hypothesis's native extension and the coverage C tracer may be blocked by
  host Application Control policy on some Windows machines. Work around by
  running pytest with `-p no:hypothesispytest`; GitHub Actions CI runs
  Hypothesis normally.
