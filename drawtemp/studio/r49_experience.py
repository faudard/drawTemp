"""R49.A: local, non-persistent Creator Studio command and latency contracts.

This is deliberately Qt-free. The registry audit verifies the shell wiring
surface, NOT successful execution of all commands. Timings are observed on the
current process only; they are not hardware/UX certification evidence.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from math import ceil
from time import perf_counter_ns
from typing import Mapping


CORE_COMMANDS = (
    "new_project", "open", "save", "undo", "redo", "playtest", "export",
    "palette", "guide", "focus_resources", "focus_inspector",
)

# Only fixed, non-identifying operation names are accepted. Never store paths,
# resource names, project titles, user input or document content in metrics.
OPERATION_IDS = frozenset({
    "studio.refresh", "studio.navigate", "studio.open",
    "studio.workspace_init",
})


@dataclass(frozen=True)
class ShortcutCollision:
    key: str
    owner: str
    shortcut: str


@dataclass(frozen=True)
class CommandIssue:
    key: str
    code: str


@dataclass(frozen=True)
class CommandAudit:
    registered: int
    issues: tuple[CommandIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def resolve_shortcuts(requested: Mapping[str, str]):
    """Keep the first registered binding for a duplicate accelerator.

    Caller is responsible for parsing valid shortcuts with QKeySequence first.
    This function detects equivalent whitespace/case variations and does not
    change the source mapping or mutate the user's saved settings.
    """
    effective = {}
    owners = {}
    conflicts = []
    for key, shortcut in requested.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Shortcut command key must be a nonempty string")
        if not isinstance(shortcut, str):
            raise ValueError("Shortcut must be a string")
        normalized = "".join(shortcut.split()).casefold()
        if normalized and normalized in owners:
            effective[key] = ""
            conflicts.append(ShortcutCollision(key, owners[normalized], shortcut))
        else:
            effective[key] = shortcut
            if normalized:
                owners[normalized] = key
    return effective, tuple(conflicts)


def audit_command_bindings(commands: Mapping[str, object], *, workspaces=()):
    """Report absent/unlabelled/untriggerable registered Qt actions.

    QAction.signal connections and runtime behavior are explicitly outside
    this static audit; integration tests must activate those commands.
    """
    required = CORE_COMMANDS + tuple("go_" + key for key in workspaces)
    issues = []
    for key in required:
        if key not in commands:
            issues.append(CommandIssue(key, "missing"))
    for key, action in commands.items():
        if not isinstance(key, str) or not key:
            issues.append(CommandIssue(str(key), "invalid_key"))
            continue
        label = getattr(action, "text", None)
        trigger = getattr(action, "trigger", None)
        if not callable(label) or not str(label()).strip():
            issues.append(CommandIssue(key, "missing_label"))
        if not callable(trigger):
            issues.append(CommandIssue(key, "not_triggerable"))
    return CommandAudit(len(commands), tuple(issues))


def _percentile(values, fraction):
    sorted_values = sorted(values)
    return sorted_values[max(0, ceil(len(sorted_values) * fraction) - 1)]


class OperationTimings:
    """Bounded monotonic observations; not exported, tracked or persisted."""

    def __init__(self, *, max_samples=256):
        if type(max_samples) is not int or not 1 <= max_samples <= 4096:
            raise ValueError("max_samples must be between 1 and 4096")
        self._max_samples = max_samples
        self._samples = {}
        self._failures = {}

    def record(self, operation: str, elapsed_ns: int, *, failed=False):
        if operation not in OPERATION_IDS:
            raise ValueError("Unknown timing operation")
        if type(elapsed_ns) is not int or elapsed_ns < 0:
            raise ValueError("Duration must be a nonnegative integer in ns")
        if type(failed) is not bool:
            raise ValueError("Failed flag must be boolean")
        series = self._samples.setdefault(operation, deque(maxlen=self._max_samples))
        series.append(elapsed_ns / 1_000_000)
        if failed:
            self._failures[operation] = self._failures.get(operation, 0) + 1

    @contextmanager
    def track(self, operation: str):
        if operation not in OPERATION_IDS:
            raise ValueError("Unknown timing operation")
        start = perf_counter_ns()
        try:
            yield
        except BaseException:
            self.record(operation, max(0, perf_counter_ns() - start), failed=True)
            raise
        else:
            self.record(operation, max(0, perf_counter_ns() - start))

    def summary(self):
        """Per-operation p50/p95/p99 in ms; sample count is the bounded window."""
        result = {}
        for operation, series in sorted(self._samples.items()):
            if not series:
                continue
            result[operation] = {
                "count": len(series),
                "failures_observed": self._failures.get(operation, 0),
                "p50_ms": round(_percentile(series, .50), 3),
                "p95_ms": round(_percentile(series, .95), 3),
                "p99_ms": round(_percentile(series, .99), 3),
                "max_ms": round(max(series), 3),
                "evidence": "local_process_observation_not_hardware_gate",
            }
        return result


def measure_studio(operation: str):
    """Instrument a synchronous Studio method without modifying its results."""
    if operation not in OPERATION_IDS:
        raise ValueError("Unknown timing operation")

    def decorate(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            with self.r49_timings.track(operation):
                return method(self, *args, **kwargs)
        return wrapper
    return decorate
