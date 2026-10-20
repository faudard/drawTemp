"""R66.A simulation trace contracts and non-destructive diagnostic projections.

This module ONLY observes versioned events supplied by a canonical simulation.
It neither advances GameSession nor defines new gameplay rules.  Its ledger is
an audit projection, not a save/replay authority. No UI, filesystem or clock.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

SCHEMA = 1
MAX_EVENTS = 20_000
MAX_SEEDS = 32
_KEY = re.compile(r"[a-z][a-z0-9_-]{0,55}\Z")


class SimulationLabError(ValueError):
    """Fail-closed, stable diagnostic for invalid or inconsistent trace data."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _reject(code, message):
    raise SimulationLabError(code, message)


def _shape(obj, keys, label):
    if type(obj) is not dict or set(obj) != keys:
        _reject("invalid_shape", label + " has unexpected or missing fields")


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        _reject("invalid_integer", f"{label} must be in {low}..{high}")


def _key(value, label):
    if type(value) is not str or _KEY.fullmatch(value) is None:
        _reject("invalid_id", label + " must be a lowercase ASCII identifier")


def _digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode("ascii")).hexdigest()


def validate_trace(trace):
    """Return a detached strict v1 trace; never coerce malformed input."""
    _shape(trace, {"schema", "seed", "days", "ticks_per_day", "accounts", "events"},
           "trace")
    if type(trace["schema"]) is not int or trace["schema"] != SCHEMA:
        _reject("unsupported_schema", "R66 supports trace schema 1 only")
    _integer(trace["seed"], 0, 2**32 - 1, "seed")
    _integer(trace["days"], 1, 365, "days")
    _integer(trace["ticks_per_day"], 1, 86400, "ticks_per_day")
    accounts = trace["accounts"]
    if type(accounts) is not dict or not 1 <= len(accounts) <= 64:
        _reject("budget", "Trace requires 1..64 accounts")
    resources = set()
    for owner, balances in accounts.items():
        _key(owner, "account")
        if type(balances) is not dict or not 1 <= len(balances) <= 16:
            _reject("invalid_shape", "Each account needs 1..16 resources")
        for resource, count in balances.items():
            _key(resource, "resource")
            _integer(count, 0, 10**12, "opening balance")
            resources.add(resource)
    if not 1 <= len(resources) <= 16 or any(set(b) != resources for b in accounts.values()):
        _reject("invalid_shape", "Each account must declare the same resources")
    events = trace["events"]
    if type(events) is not list or len(events) > MAX_EVENTS:
        _reject("budget", "At most 20,000 events per trace")
    ids, last_tick = set(), -1
    for i, event in enumerate(events):
        _shape(event, {"id", "tick", "kind", "resource", "quantity",
                       "source", "target", "depends_on", "cause"}, "event")
        _key(event["id"], "event id")
        if event["id"] in ids:
            _reject("duplicate_event", "Duplicate event id: " + event["id"])
        _integer(event["tick"], 0,
                 trace["days"] * trace["ticks_per_day"] - 1, "tick")
        if event["tick"] < last_tick:
            _reject("event_order", f"Event {i} is earlier than its predecessor")
        last_tick = event["tick"]
        if event["kind"] not in ("transfer", "produce", "consume"):
            _reject("invalid_kind", "Unsupported resource operation")
        if type(event["resource"]) is not str or event["resource"] not in resources:
            _reject("unknown_resource", "Resource is not declared")
        _integer(event["quantity"], 1, 10**12, "quantity")
        source, target = event["source"], event["target"]
        for endpoint in (source, target):
            if endpoint is not None and (type(endpoint) is not str or endpoint not in accounts):
                _reject("unknown_account", "Event account is not declared")
        if ((event["kind"] == "transfer" and (source is None or target is None or source == target))
                or (event["kind"] == "produce" and (source is not None or target is None))
                or (event["kind"] == "consume" and (source is None or target is not None))):
            _reject("invalid_endpoints", "Source/target incompatible with operation")
        deps = event["depends_on"]
        if type(deps) is not list or len(deps) > 16 or any(
                type(d) is not str or d not in ids for d in deps) or len(set(deps)) != len(deps):
            _reject("invalid_dependency", "Dependencies must be unique earlier event ids")
        if type(event["cause"]) is not str or not 1 <= len(event["cause"]) <= 160:
            _reject("invalid_cause", "Cause must be 1..160 characters")
        ids.add(event["id"])
    return deepcopy(trace)


def _apply(balances, created, consumed, event):
    resource, amount = event["resource"], event["quantity"]
    source, target = event["source"], event["target"]
    if source is not None:
        if balances[source][resource] < amount:
            _reject("insufficient_resource", "Event " + event["id"] +
                    " overdraws " + source + "/" + resource)
        balances[source][resource] -= amount
    if target is not None:
        if balances[target][resource] + amount > 10**15:
            _reject("overflow", "Ledger balance exceeds audit budget")
        balances[target][resource] += amount
    if event["kind"] == "produce":
        created[resource] += amount
    elif event["kind"] == "consume":
        consumed[resource] += amount


class SimulationTraceLab:
    """Seek/step/rewind an audit projection without touching gameplay or trace."""

    def __init__(self, trace):
        self._trace = validate_trace(trace)
        self.trace_sha256 = _digest(self._trace)
        self._initial = deepcopy(self._trace["accounts"])
        self._balances = deepcopy(self._initial)
        self._created = {r: 0 for r in next(iter(self._initial.values()))}
        self._consumed = dict(self._created)
        self._position = 0
        self._cancelled = False

    @property
    def remaining(self):
        return len(self._trace["events"]) - self._position

    def cancel(self):
        self._cancelled = True

    def snapshot(self):
        """Detached projection, never a canonical GameSession checkpoint."""
        totals = {r: sum(a[r] for a in self._balances.values())
                  for r in self._created}
        for resource, total in totals.items():
            expected = (sum(a[resource] for a in self._initial.values()) +
                        self._created[resource] - self._consumed[resource])
            if total != expected:
                _reject("conservation", "Resource conservation failed: " + resource)
        return {"schema": SCHEMA, "trace_sha256": self.trace_sha256,
                "position": self._position, "remaining": self.remaining,
                "last_tick": self._trace["events"][self._position-1]["tick"]
                if self._position else None,
                "balances": deepcopy(self._balances), "created": dict(self._created),
                "consumed": dict(self._consumed), "totals": totals,
                "cancelled": self._cancelled}

    def seek(self, position):
        if self._cancelled:
            _reject("cancelled", "Cancelled lab cannot resume")
        _integer(position, 0, len(self._trace["events"]), "position")
        # Transactional projection: an invalid event cannot leave partial state.
        if position >= self._position:
            balances, created, consumed = (deepcopy(self._balances),
                                            dict(self._created), dict(self._consumed))
            start = self._position
        else:
            balances = deepcopy(self._initial)
            created = {r: 0 for r in self._created}
            consumed = dict(created)
            start = 0
        for event in self._trace["events"][start:position]:
            _apply(balances, created, consumed, event)
        self._balances, self._created, self._consumed = balances, created, consumed
        self._position = position
        return self.snapshot()

    def step(self, count=1):
        _integer(count, 1, MAX_EVENTS, "count")
        return self.seek(min(len(self._trace["events"]), self._position + count))

    def rewind(self, count=1):
        _integer(count, 1, MAX_EVENTS, "count")
        return self.seek(max(0, self._position - count))

    def run(self):
        return self.seek(len(self._trace["events"]))


def _percentile(values, fraction):
    if not values:
        return 0
    ordered = sorted(values)
    # nearest-rank percentile, integer-only deterministic and JSON-safe
    return ordered[((len(ordered) * fraction + 99) // 100) - 1]


def analyze_batch(traces, *, idle_days=3, cancel_after=None):
    """R66.C headless analytics over supplied traces, never synthetic gameplay.

    p95/p99 measure events/day, *not* host CPU or FPS. Each seed and source
    trace SHA is included for reproduction. Failures are reported per seed.
    """
    _integer(idle_days, 1, 30, "idle_days")
    if type(traces) not in (tuple, list) or not 1 <= len(traces) <= MAX_SEEDS:
        _reject("budget", "Batch requires 1..32 traces")
    if cancel_after is not None:
        _integer(cancel_after, 0, len(traces), "cancel_after")
    validated = [validate_trace(trace) for trace in traces]
    seeds = [t["seed"] for t in validated]
    if len(set(seeds)) != len(seeds):
        _reject("duplicate_seed", "Each trace seed must be unique")
    common = (validated[0]["days"], validated[0]["ticks_per_day"],
              tuple(sorted(next(iter(validated[0]["accounts"].values())).keys())))
    if any((t["days"], t["ticks_per_day"],
            tuple(sorted(next(iter(t["accounts"].values())).keys()))) != common
           for t in validated):
        _reject("incompatible_trace", "Batch horizon and resource schema must match")
    samples = []
    limit = len(validated) if cancel_after is None else cancel_after
    for trace in validated[:limit]:
        lab = SimulationTraceLab(trace)
        counts = [0] * trace["days"]
        for event in trace["events"]:
            counts[event["tick"] // trace["ticks_per_day"]] += 1
        gaps, longest, current = [], 0, 0
        for day, value in enumerate(counts):
            current = current + 1 if value == 0 else 0
            longest = max(longest, current)
            if current == idle_days:
                gaps.append(day - idle_days + 1)
        try:
            snapshot = lab.run()
            status = "warning" if gaps else "ok"
            diagnostic = None
        except SimulationLabError as exc:
            snapshot = lab.snapshot()
            status, diagnostic = "failed", {"code": exc.code, "message": str(exc)}
        samples.append({"seed": trace["seed"], "trace_sha256": lab.trace_sha256,
                        "status": status, "diagnostic": diagnostic,
                        "completed_events": snapshot["position"],
                        "total_events": len(trace["events"]),
                        "events_per_day": counts, "events_p95": _percentile(counts, 95),
                        "events_p99": _percentile(counts, 99),
                        "longest_idle_days": longest, "idle_windows": gaps,
                        "closing_balances": snapshot["balances"] if status != "failed" else None,
                        "closing_totals": snapshot["totals"] if status != "failed" else None})
    return {"schema": SCHEMA, "kind": "r66-observational-trace-batch",
            "days": common[0], "ticks_per_day": common[1], "resources": list(common[2]),
            "seeds_requested": seeds, "idle_days": idle_days,
            "status": "cancelled" if limit < len(validated) else (
                "failed" if any(s["status"] == "failed" for s in samples) else "completed"),
            "samples": samples,
            "deterministic_sha256": _digest({"days": common[0], "samples": samples,
                                               "seeds": seeds, "idle_days": idle_days})}


def compare_batches(baseline, candidate):
    """Compare matched seeds/horizon, exposing resource drift without mutation."""
    required = {"schema", "kind", "days", "ticks_per_day", "resources",
                "seeds_requested", "idle_days", "status", "samples", "deterministic_sha256"}
    for report in (baseline, candidate):
        _shape(report, required, "batch report")
        if (report["kind"] != "r66-observational-trace-batch" or
                report["schema"] != SCHEMA or report["status"] != "completed" or
                len(report["samples"]) != len(report["seeds_requested"]) or
                any(s["status"] == "failed" for s in report["samples"])):
            _reject("incomplete_report", "Only completed successful batch reports compare")
        try:
            expected = _digest({"days": report["days"], "samples": report["samples"],
                                "seeds": report["seeds_requested"],
                                "idle_days": report["idle_days"]})
        except (TypeError, ValueError, OverflowError):
            _reject("invalid_report", "Report cannot be encoded as canonical JSON")
        if expected != report["deterministic_sha256"]:
            _reject("report_modified", "Report contents do not match its digest")
    for key in ("days", "ticks_per_day", "resources", "seeds_requested", "idle_days"):
        if baseline[key] != candidate[key]:
            _reject("incompatible_report", "Report mismatch: " + key)
    deltas = []
    for before, after in zip(baseline["samples"], candidate["samples"]):
        if before["seed"] != after["seed"]:
            _reject("incompatible_report", "Seed order mismatch")
        resources = baseline["resources"]
        change = {r: after["closing_totals"][r] - before["closing_totals"][r]
                  for r in resources}
        deltas.append({"seed": before["seed"], "resource_deltas": change,
                       "events_p99_delta": after["events_p99"] - before["events_p99"],
                       "idle_windows_delta": len(after["idle_windows"]) - len(before["idle_windows"])})
    return {"schema": SCHEMA, "same_deterministic_report":
            baseline["deterministic_sha256"] == candidate["deterministic_sha256"],
            "per_seed": deltas}
