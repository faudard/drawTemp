"""R56.A replayable gameplay QA on the authoritative GameSession.

This is bounded headless source evidence, not release certification.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from drawtemp.core import GameSession

KIND = "drawtemp-r56-gameplay-scenario"
SCHEMA = 1
MAX_STEPS = 256
MAX_BYTES = 262144
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
KEY = re.compile(r"[A-Za-z_][A-Za-z_0-9-]{0,79}\Z")
# No dynamic dispatch except after exact operation validation.
OPERATIONS = {
    "choose_story_option": 1, "choose_tactical_story_option": 1,
    "start_mission": 1, "execute": 1, "return_to_campaign": 0,
    "ai_turn": 0, "route_realtime_step": 2, "route_interact": 1,
    "route_transition": 1, "route_platform_step": 4,
    "route_platform_travel": 1, "explore_move": 2,
    "explore_interact": 1, "system_advance": 1, "system_trade": 4,
    "system_fulfill": 1,
}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def validate_scenario(doc):
    try:
        raw = canonical(doc)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Scenario must be finite JSON") from exc
    if len(raw) > MAX_BYTES or type(doc) is not dict or set(doc) != {
        "kind", "schema", "id", "starter", "revision", "campaign",
        "seed", "content_digest", "project_digest", "steps"
    }:
        raise ValueError("Oversized or unknown scenario contract")
    if doc["kind"] != KIND or type(doc["schema"]) is not int or doc["schema"] != SCHEMA:
        raise ValueError("Unsupported scenario version")
    if any(type(doc[k]) is not str or not IDENT.fullmatch(doc[k])
           for k in ("id", "starter", "campaign")):
        raise ValueError("Invalid identity")
    if type(doc["revision"]) is not str or not SHA40.fullmatch(doc["revision"]):
        raise ValueError("Expected exact Git SHA")
    if any(type(doc[k]) is not str or not SHA64.fullmatch(doc[k])
           for k in ("content_digest", "project_digest")):
        raise ValueError("Expected pinned content and project digests")
    if type(doc["seed"]) is not int or not 0 <= doc["seed"] <= 2**31 - 1:
        raise ValueError("Invalid seed")
    steps = doc["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError("Expected 1..256 steps")
    for i, step in enumerate(steps, 1):
        if type(step) is not dict or set(step) != {"operation", "args", "expect"}:
            raise ValueError("Invalid step %d" % i)
        operation = step["operation"]
        if (type(operation) is not str or operation not in OPERATIONS or
                type(step["args"]) is not list or
                len(step["args"]) != OPERATIONS[operation]):
            raise ValueError("Disallowed operation or arity at step %d" % i)
        if type(step["expect"]) is not list or len(step["expect"]) > 16:
            raise ValueError("Too many expectations")
        for check in step["expect"]:
            if type(check) is not dict or set(check) != {"path", "equals"}:
                raise ValueError("Invalid expectation")
            path = check["path"]
            if (type(path) is not list or not 1 <= len(path) <= 8 or
                    any(type(key) is not str or not KEY.fullmatch(key)
                        for key in path)):
                raise ValueError("Invalid expectation path")
    return deepcopy(doc)


def build_scenario(content, project, *, identifier, starter, revision,
                   steps, campaign="main", seed=17):
    """Construct pinned data, without stepping the game or editing inputs."""
    initial = GameSession.new(content, project, campaign, seed=seed).recording()
    return validate_scenario({
        "kind": KIND, "schema": SCHEMA, "id": identifier, "starter": starter,
        "revision": revision, "campaign": campaign, "seed": seed,
        "content_digest": initial["content_digest"],
        "project_digest": initial["project_digest"], "steps": steps,
    })


class ScenarioFailure(Exception):
    def __init__(self, step, category, message):
        self.step = step
        self.category = category
        super().__init__(str(message)[:500])


def _expect(recording, checks, index):
    for check in checks:
        value = recording
        for key in check["path"]:
            if not isinstance(value, dict) or key not in value:
                raise ScenarioFailure(index, "missing_state",
                                      "Missing " + ".".join(check["path"]))
            value = value[key]
        if type(value) is not type(check["equals"]) or value != check["equals"]:
            raise ScenarioFailure(index, "invariant",
                                  "Unexpected " + ".".join(check["path"]))


def _execute(doc, content, project, rules, interval):
    try:
        session = GameSession.new(content, project, doc["campaign"],
                                  seed=doc["seed"], rules=rules)
        record = session.recording()
    except Exception as exc:
        raise ScenarioFailure(0, "initialization",
                              "%s: %s" % (type(exc).__name__, exc)) from exc
    if (record["content_digest"] != doc["content_digest"] or
            record["project_digest"] != doc["project_digest"]):
        raise ScenarioFailure(0, "source_drift", "Content/GameProject changed")
    trace = [{"step": 0, "operation": "initial", "digest": record["digest"],
              "mode": record["mode"], "checkpoint": True}]
    for i, step in enumerate(doc["steps"], 1):
        try:
            getattr(session, step["operation"])(*deepcopy(step["args"]))
            record = session.recording()
            _expect(record, step["expect"], i)
            checkpoint = i % interval == 0 or i == len(doc["steps"])
            if checkpoint:
                restored = GameSession.from_recording(
                    deepcopy(record), content, project, rules=rules)
                if restored.recording() != record:
                    raise ScenarioFailure(i, "checkpoint", "Restored state diverged")
                session = restored
            trace.append({"step": i, "operation": step["operation"],
                          "digest": record["digest"], "mode": record["mode"],
                          "checkpoint": checkpoint})
        except ScenarioFailure as exc:
            exc.trace = deepcopy(trace)
            raise
        except Exception as exc:
            failure = ScenarioFailure(i, "runtime", "%s: %s" %
                                      (type(exc).__name__, exc))
            failure.trace = deepcopy(trace)
            raise failure from exc
    return trace


def run_scenario(document, content, project, *, revision, rules=None,
                 checkpoint_every=1):
    """Compare two fresh replay runs and authoritative save/reload checkpoints."""
    doc = validate_scenario(document)
    if type(revision) is not str or not SHA40.fullmatch(revision):
        raise ValueError("Expected exact invocation revision")
    if (type(checkpoint_every) is not int or
            not 1 <= checkpoint_every <= 64):
        raise ValueError("Checkpoint interval must be 1..64")
    report = {
        "kind": "drawtemp-r56a-qa-report", "schema": 1,
        "scenario": doc["id"], "starter": doc["starter"],
        "declared_revision": doc["revision"],
        "scenario_sha256": sha256(canonical(doc)).hexdigest(),
        "content_digest": doc["content_digest"],
        "project_digest": doc["project_digest"],
        "revision_independently_attested": False,
        "release_certified": False, "replay_verified": False,
        "status": "blocked", "steps_executed": 0,
        "trace": [], "counterexample": None,
    }
    if revision != doc["revision"]:
        report["counterexample"] = {
            "step": 0, "category": "revision_drift",
            "message": "Scenario revision differs from invocation", "prefix": [],
        }
        return report
    try:
        first = _execute(doc, content, project, rules, checkpoint_every)
        second = _execute(doc, content, project, rules, checkpoint_every)
        for a, b in zip(first, second):
            if a != b:
                failure = ScenarioFailure(a["step"], "nondeterministic",
                                          "Independent replay digests differ")
                failure.trace = deepcopy(first[:a["step"] + 1])
                raise failure
        report.update(status="passed", replay_verified=True,
                      steps_executed=len(doc["steps"]), trace=first)
    except ScenarioFailure as exc:
        report["trace"] = deepcopy(getattr(exc, "trace", []))
        report["status"] = "blocked" if exc.step == 0 else "failed"
        report["steps_executed"] = max(0, exc.step - 1)
        report["counterexample"] = {
            "step": exc.step, "category": exc.category, "message": str(exc),
            "prefix": deepcopy(doc["steps"][:exc.step]),
        }
    return report


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _load(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Missing, symlinked or oversized scenario")
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_no_duplicate_keys,
                      parse_constant=lambda x: (_ for _ in ()).throw(
                          ValueError("Invalid numeric constant " + x)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="R56.A gameplay replay")
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        doc = validate_scenario(_load(args.scenario))
        from drawtemp.sdk.r40_starters import STARTER_KINDS, create_starter_pair
        if doc["starter"] not in STARTER_KINDS:
            raise ValueError("CLI supports only canonical R40 starters")
        content, project = create_starter_pair(doc["starter"])
        report = run_scenario(doc, content, project, revision=args.revision,
                              checkpoint_every=args.checkpoint_every)
        output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            if args.output.resolve() == args.scenario.resolve():
                raise ValueError("Cannot overwrite input scenario")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0 if report["status"] == "passed" else 2
    except (ValueError, OSError, UnicodeError) as exc:
        print("R56.A blocked: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
