"""R9.B revision-bound interactive debugger for a disposable canonical Battle.

Not a second interpreter, GameSession save format, or authenticated replay.
A debug handle is invalid after any editor apply/undo/redo; a fresh handle
must be created to avoid explaining a different document revision.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError
from sporebound.event_debugger import EventDebugger, format_debug_report


class EventDebugController:
    """UI-safe debug commands with source-revision checks and detached reports."""

    def __init__(self, authoring, mission_id, event_id, *,
                 scenario="satisfied", tick=0):
        self._authoring = authoring
        self.source_revision = authoring.revision
        snapshot = authoring.snapshot().to_dict()
        content = snapshot["content"]
        project = GameProject.from_dict(snapshot["project"],
                                        Content.from_dict(content))
        self._engine = EventDebugger(content, mission_id, event_id,
                                     project=project, scenario=scenario, tick=tick)
        self.mission_id = mission_id
        self.event_id = event_id

    def _current(self):
        if self._authoring.revision != self.source_revision:
            raise AuthoringError(
                "stale_revision", "event_debug",
                "Le document a changé : redémarrer la session de diagnostic.")

    def _read(self, report):
        result = deepcopy(report)
        return {
            "source_revision": self.source_revision,
            "report": result,
            "lines": format_debug_report(result),
        }

    def report(self):
        self._current()
        return self._read(self._engine.report())

    def chain_ids(self):
        self._current()
        return tuple(event["id"] for event in self._engine.chain)

    def breakpoint(self, event_id, enabled=True):
        self._current()
        self._engine.set_breakpoint(event_id, enabled)
        return self.report()

    def step(self):
        self._current()
        return self._read(self._engine.step())

    def resume(self):
        self._current()
        return self._read(self._engine.continue_to_breakpoint())

    def inspect(self, event_id):
        self._current()
        result = deepcopy(self._engine.inspect(event_id))
        return {"source_revision": self.source_revision, **result}

    def restart(self, *, scenario="satisfied", tick=0):
        self._current()
        return type(self)(self._authoring, self.mission_id, self.event_id,
                          scenario=scenario, tick=tick)
