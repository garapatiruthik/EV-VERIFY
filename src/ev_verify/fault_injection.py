"""Sensor fault injection at the measurement boundary.

Faults mutate only the measurement seen by the controller, never the plant's
hidden ground-truth state. A "stale" fault persists: once triggered, the
signal's timestamp is frozen for the rest of the run, modelling a sensor that
stops advancing its clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sensors import Measurement


@dataclass(frozen=True)
class FaultEvent:
    """A scheduled or detected fault event."""

    time_s: float
    signal: str
    kind: str  # dropout, stale, spike, bias, noise
    description: str
    value: float | None = None


@dataclass
class FaultSchedule:
    """List of fault events scheduled by simulation time."""

    events: list[FaultEvent] = field(default_factory=list)

    def add(
        self, time_s: float, signal: str, kind: str, description: str, value: float | None = None
    ) -> None:
        self.events.append(FaultEvent(time_s, signal, kind, description, value))

    def due(self, prev_time_s: float, current_time_s: float) -> list[FaultEvent]:
        """Return events scheduled in (prev_time, current_time]; each fires once."""
        return [e for e in self.events if prev_time_s < e.time_s <= current_time_s]


@dataclass
class FaultInjector:
    """Applies scheduled sensor faults to measurements."""

    schedule: FaultSchedule
    _stale: dict[str, float] = field(default_factory=dict)

    @staticmethod
    def _original(measurements: dict[str, Measurement], signal: str) -> Measurement | None:
        return measurements.get(signal)

    def apply(
        self,
        measurements: dict[str, Measurement],
        prev_time_s: float,
        current_time_s: float,
    ) -> tuple[dict[str, Measurement], list[FaultEvent]]:
        """Return (mutated measurements, fault events fired at this step).

        The input measurement dict is not mutated; a new dict is returned.
        Faults mutate only the measurement layer, never the plant ground truth.
        """
        fired = self.schedule.due(prev_time_s, current_time_s)
        result = dict(measurements)
        for event in fired:
            original = self._original(result, event.signal)
            if event.kind == "dropout":
                result[event.signal] = Measurement(
                    event.signal,
                    float("nan"),
                    "",
                    current_time_s,
                    valid=False,
                    reason=event.description,
                )
            elif event.kind == "stale":
                self._stale[event.signal] = current_time_s
                result[event.signal] = self._stale_measurement(
                    event.signal, current_time_s, original
                )
            elif event.kind == "spike":
                spike_value = event.value if event.value is not None else float("inf")
                result[event.signal] = Measurement(
                    event.signal,
                    spike_value,
                    original.unit if original else "",
                    current_time_s,
                    valid=False,
                    reason=event.description,
                )
            elif event.kind == "bias":
                offset = event.value if event.value is not None else 0.0
                base = original.value if (original is not None and original.is_finite()) else 0.0
                result[event.signal] = Measurement(
                    event.signal,
                    base + offset,
                    original.unit if original else "",
                    current_time_s,
                    valid=True,
                    reason=event.description,
                )
            elif event.kind == "noise":
                magnitude = event.value if event.value is not None else 0.0
                base = original.value if (original is not None and original.is_finite()) else 0.0
                result[event.signal] = Measurement(
                    event.signal,
                    base + magnitude,
                    original.unit if original else "",
                    current_time_s,
                    valid=True,
                    reason=event.description,
                )
        # Persistent stale override: the timestamp stays frozen from here on.
        for signal, frozen_ts in self._stale.items():
            original = self._original(result, signal)
            result[signal] = self._stale_measurement(signal, frozen_ts, original)
        return result, fired

    @staticmethod
    def _stale_measurement(
        signal: str, frozen_ts: float, original: Measurement | None
    ) -> Measurement:
        if original is None:
            return Measurement(
                signal,
                float("nan"),
                "",
                frozen_ts,
                valid=True,
                reason="stale sensor: nominal value unavailable",
            )
        return Measurement(
            signal,
            original.value,
            original.unit,
            frozen_ts,
            valid=True,
            reason="stale sensor: timestamp not advancing",
        )
