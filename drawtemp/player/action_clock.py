"""R26.C wall-clock adapter. The action simulation remains integer-tick only.

Wall-clock time controls how many simulation steps are requested; neither
elapsed time nor render FPS is passed into the deterministic action rules.
"""
from __future__ import annotations

SECOND_NS = 1_000_000_000


class ActionStepClock:
    def __init__(self, *, hz=60, max_catchup=6):
        if type(hz) is not int or hz not in (30, 60, 120):
            raise ValueError("Unsupported fixed action tick rate")
        if type(max_catchup) is not int or not 1 <= max_catchup <= 16:
            raise ValueError("Invalid catch-up budget")
        self.hz = hz
        self.max_catchup = max_catchup
        self._credit = 0

    def reset(self):
        """Discard stale time after pause, load, respawn or a device stall."""
        self._credit = 0

    def advance(self, elapsed_ns):
        """Return a bounded integer number of 1/hz logical steps.

        The remainder is accumulated with exact integer arithmetic. A stall
        beyond the catch-up budget is explicitly dropped rather than issuing
        hundreds of commands in a single UI frame.
        """
        if type(elapsed_ns) is not int or elapsed_ns < 0:
            raise ValueError("Elapsed monotonic delta must be a nonnegative int")
        self._credit = min(self._credit + elapsed_ns * self.hz,
                           self.max_catchup * SECOND_NS)
        steps, self._credit = divmod(self._credit, SECOND_NS)
        return int(steps)


__all__ = ["ActionStepClock"]
