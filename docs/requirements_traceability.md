# Requirements Traceability

EV-Verify defines 20 requirements in `requirements/requirements.json`. Each
implemented requirement (`implemented: true`) must be linked to at least one
collected test via the `@pytest.mark.requirement("REQ-...")` marker.

Traceability is enforced by `scripts/check_traceability.py`, which compares
pytest-collected markers (written to `reports/traceability.json` by
`tests/conftest.py`) against `requirements/requirements.json`. CI fails when an
implemented requirement has no covering test.

## Requirement index

| ID | Description | Severity | Implemented | Tests |
|---|---|---|---|---|
| REQ-BAT-001 | SOC remains within `[0, 1]` under charge and discharge | high | yes | `test_battery.py`, `test_invariants.py` |
| REQ-BAT-002 | Positive current decreases SOC; negative current increases SOC | high | yes | `test_battery.py` |
| REQ-BAT-003 | Terminal voltage responds to current and internal resistance | high | yes | `test_battery.py` |
| REQ-BAT-004 | Temperature rises under load and cools toward ambient | medium | yes | `test_battery.py` |
| REQ-MOT-001 | Positive torque increases motor speed | high | yes | `test_motor.py` |
| REQ-MOT-002 | Applied torque never exceeds supervisor limit | high | yes | `test_supervisor.py`, `test_normal_drive.py` |
| REQ-MOT-003 | Regenerative torque produces negative pack current | high | yes | `test_regenerative_braking.py` |
| REQ-SEN-001 | Invalid/missing/non-finite measurements are rejected | high | yes | `test_sensors.py`, `test_supervisor.py` |
| REQ-SEN-002 | Stale measurements detected via timestamps | high | yes | `test_sensors.py` |
| REQ-BMS-001 | Critical over-voltage latches fault, zero torque | high | yes | `test_supervisor.py`, `test_fault_transitions.py` |
| REQ-BMS-002 | Critical under-voltage latches fault, zero torque | high | yes | `test_supervisor.py`, `test_fault_transitions.py` |
| REQ-BMS-003 | Discharge over-current protective fault | high | yes | `test_supervisor.py` |
| REQ-BMS-004 | Regenerative charge current constrained by charge limit | medium | yes | `test_supervisor.py`, `test_regenerative_braking.py` |
| REQ-BMS-005 | Critical battery temperature protective fault | high | yes | `test_supervisor.py`, `test_fault_transitions.py` |
| REQ-BMS-006 | Sensor dropout/invalid safety-critical data -> safe response | high | yes | `test_fault_transitions.py`, `test_fault_recovery.py` |
| REQ-BMS-007 | Soft constraints cause torque derating before critical threshold | medium | yes | `test_supervisor.py`, `test_low_soc.py` |
| REQ-BMS-008 | Fault latched until reset and safe recovery | high | yes | `test_fault_recovery.py` |
| REQ-SIM-001 | Identical scenario+seed -> identical traces | high | yes | `test_normal_drive.py` |
| REQ-LOG-001 | Each step records time, scenario, torque, SOC, voltage, current, temp, speed, state, faults | medium | yes | `test_normal_drive.py`, `test_telemetry.py` |
| REQ-VER-001 | Each implemented requirement linked to >=1 automated test | high | yes | `scripts/check_traceability.py` |

## Verification

Run the traceability checker:

```powershell
python scripts/check_traceability.py
```

Expected result: `20/20 covered, PASS`. Requirements flagged `planned` but not
`implemented` are excluded from the mandatory denominator (none currently).

## Adding a new requirement

1. Add an entry to `requirements/requirements.json` with `id`, `description`,
   `severity`, `priority`, `implemented`, `planned`, and `test_names`.
2. Add `@pytest.mark.requirement("<id>")` to the covering test(s).
3. Run `python scripts/check_traceability.py` to confirm coverage.
