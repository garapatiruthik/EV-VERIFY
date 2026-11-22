# Architecture

EV-Verify is a discrete-time, deterministic simulation of an e-powertrain
(battery + motor) with a supervisor protection layer and sensor fault
injection at the measurement boundary.

## Data flow

```
scenario -> Simulation loop -> BatteryModel/MotorModel (plant ground truth)
                                   |
                                   v
                          SensorInterface (measurements)
                                   |
                                   v
                          FaultInjector (mutates measurements only)
                                   |
                                   v
                          Supervisor (state machine, fault codes, derating)
                                   |
                                   v
                          Telemetry (step records, fault log, CSV/JSON output)
```

The plant's hidden ground-truth state is never mutated by faults. Faults
mutate only the measurement seen by the supervisor.

## Modules

- `config.py` — `SimulationConfig`: duration, time step, seeds, limits, fault
  schedule parameters. Single source of simulation constants.
- `battery.py` — `BatteryModel`: SOC clamping, coulomb counting, open-circuit
  voltage interpolation, terminal voltage (`OCV - I*R`), temperature rise under
  load and cooling toward ambient.
- `motor.py` — `MotorModel`: motor speed response to applied torque under load.
- `sensors.py` — `Measurement` (value, unit, timestamp, validity, reason) and
  `SensorInterface`: constructors for battery temp, pack voltage, current, etc.
- `fault_injection.py` — `FaultSchedule` (timed `FaultEvent` list), `FaultInjector`
  (applies dropout/stale/spike/bias/noise; stale freezes the timestamp
  persistently).
- `supervisor.py` — state machine (`INITIALISING`, `READY`, `ACTIVE`,
  `DERATED`, `FAULT_LATCHED`, `FAULT_CLEARED`), fault-code evaluation, torque
  derating, latch/clear behaviour.
- `simulation.py` — `Simulation`: ties plant, injector, and supervisor together
  over fixed time steps; tracks previous time so each scheduled fault fires once
  in `(prev_t, current_t]`.
- `scenarios.py` — built-in scenario definitions (normal city drive, steady
  cruise, hard acceleration, low SOC, regenerative braking, thermal stress,
  sensor bias/dropout/spike/stale).
- `telemetry.py` — `Telemetry`: per-step `StepRecord`, state-transition counting,
  critical fault-code dedup (logged once at onset), torque-derating step count,
  CSV/JSON report writing.
- `cli.py` — `list-scenarios`, `run` (one scenario), `run-all` (all scenarios).

## Supervisor states

`INITIALISING` -> `READY` -> `ACTIVE`; `ACTIVE` -> `DERATED` when limits are
approached; critical faults latch into `FAULT_LATCHED`; `FAULT_CLEARED` on
recovery.

## Determinism

Every scenario uses a fixed seed. There are no network, current-time, or
hardware dependencies. Runs are reproducible given the same seed and version.
