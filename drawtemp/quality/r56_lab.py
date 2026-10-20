"""R56.B QA Lab: bounded capture, batch replay and drill-down projections.

This layer contains no gameplay engine, Qt objects or persistence of the
authoritative AuthoringSession. All execution delegates to R56.A GameSession QA.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

from drawtemp.core import GameSession
from drawtemp.quality.r56_scenarios import (
    SHA40, canonical, build_scenario, run_scenario, validate_scenario,
    _no_duplicate_keys,
)

KIND = "drawtemp-r56b-suite"
REPORT_KIND = "drawtemp-r56b-batch-report"
SCHEMA = 1
MAX_CASES = 12
MAX_SUITE_BYTES = 2 * 1024 * 1024
MAX_LINKS = 256
FAMILIES = frozenset({
    "project", "maps", "actors", "objects", "events",
    "campaigns", "scenes", "cinematics",
})


def _validate_link(item, step_count):
    if type(item) is not dict or set(item) != {"step", "resource"}:
        raise ValueError("R56.B link requires step and resource")
    step = item["step"]
    if type(step) is not int or not 1 <= step <= step_count:
        raise ValueError("Resource link step is out of range")
    resource = item["resource"]
    if (type(resource) is not list or len(resource) != 3 or
            any(type(v) is not str or len(v) > 100 for v in resource) or
            resource[0] not in FAMILIES or not resource[2]):
        raise ValueError("Resource link must be [family, mission, ID]")
    if resource[0] not in ("actors", "objects", "events") and resource[1]:
        raise ValueError("Unscoped resource has a mission ID")
    return deepcopy(item)


def validate_case(case):
    """Immutable sidecar links; R56.A JSON contract is deliberately unchanged."""
    if type(case) is not dict or set(case) != {"scenario", "links"}:
        raise ValueError("Case must contain scenario and links")
    scenario = validate_scenario(case["scenario"])
    links = case["links"]
    if type(links) is not list or len(links) > MAX_LINKS:
        raise ValueError("Too many case source links")
    checked, steps = [], set()
    for item in links:
        link = _validate_link(item, len(scenario["steps"]))
        if link["step"] in steps:
            raise ValueError("One source link per step")
        steps.add(link["step"])
        checked.append(link)
    return {"scenario": scenario, "links": checked}


def validate_suite(document):
    try:
        size = len(canonical(document))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Suite must be finite JSON") from exc
    if size > MAX_SUITE_BYTES:
        raise ValueError("Suite exceeds 2 MiB")
    if (type(document) is not dict or set(document) !=
            {"kind", "schema", "cases"} or document["kind"] != KIND or
            type(document["schema"]) is not int or document["schema"] != SCHEMA):
        raise ValueError("Unknown R56.B suite schema")
    cases = document["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("Suite requires 1..12 cases")
    selected = [validate_case(item) for item in cases]
    ids = [item["scenario"]["id"] for item in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate scenario identity")
    return {"kind": KIND, "schema": SCHEMA, "cases": selected}


def build_suite(cases):
    return validate_suite({"kind": KIND, "schema": SCHEMA, "cases": cases})


def capture_case(content, project, *, identifier, starter, revision, steps,
                 links=(), campaign="main", seed=17):
    """Construct a reviewable draft from explicitly captured UI action rows.

    Not passive Player input recording. Linked resource IDs are advisory and
    validated when navigating through the live Studio resource index.
    """
    scenario = build_scenario(
        content, project, identifier=identifier, starter=starter,
        revision=revision, steps=steps, campaign=campaign, seed=seed)
    return validate_case({"scenario": scenario, "links": list(links)})


def run_batch(document, content, project, *, revision, checkpoint_every=1):
    suite = validate_suite(document)
    if type(revision) is not str or not SHA40.fullmatch(revision):
        raise ValueError("Expected exact Git SHA for batch invocation")
    if type(checkpoint_every) is not int or not 1 <= checkpoint_every <= 64:
        raise ValueError("Checkpoint budget must be 1..64")
    cases = []
    for item in suite["cases"]:
        report = run_scenario(
            item["scenario"], content, project, revision=revision,
            checkpoint_every=checkpoint_every)
        cases.append({
            "id": item["scenario"]["id"], "status": report["status"],
            "links": deepcopy(item["links"]), "report": report,
        })
    counts = {status: sum(case["status"] == status for case in cases)
              for status in ("passed", "failed", "blocked")}
    return {
        "kind": REPORT_KIND, "schema": SCHEMA, "revision": revision,
        "suite_sha256": sha256(canonical(suite)).hexdigest(),
        "counts": counts, "cases": cases,
        "status": ("headless-passed" if counts["passed"] == len(cases)
                   else "no-go"),
        "release_certified": False,
        "revision_independently_attested": False,
    }


def inspect_case(result, case, step):
    """Project the selected trace row and typed Studio navigation hint."""
    validated = validate_case(case)
    if type(result) is not dict or result.get("scenario") != validated["scenario"]["id"]:
        raise ValueError("Report and scenario do not match")
    if result.get("scenario_sha256") != sha256(
            canonical(validated["scenario"])).hexdigest():
        raise ValueError("Report is from a different scenario version")
    if type(step) is not int or not 0 <= step <= len(validated["scenario"]["steps"]):
        raise ValueError("Invalid requested step")
    traces = [row for row in result.get("trace", [])
              if type(row) is dict and row.get("step") == step]
    failure = result.get("counterexample")
    if failure is not None and (type(failure) is not dict or
                                 type(failure.get("step")) is not int):
        raise ValueError("Invalid failure evidence")
    command = (deepcopy(validated["scenario"]["steps"][step - 1])
               if step else None)
    matching = [row["resource"] for row in validated["links"]
                if row["step"] == step]
    return {
        "step": step, "command": command,
        "trace": deepcopy(traces[0]) if traces else None,
        "failure": deepcopy(failure) if failure and failure["step"] == step else None,
        "resource": deepcopy(matching[0]) if matching else None,
        "reproduced_through_step": bool(traces),
        "description": ("Initial authoritative checkpoint" if step == 0 else
                        "Command step; fixed game tick only for tick operations"),
    }


def replay_to_step(case, content, project, *, revision, step, report=None):
    """Reproduce the exact command prefix using the canonical GameSession.

    This is an on-demand, bounded state observation of selected invariants,
    NOT a state-changing Studio or Player command. A failing invariant is
    reported with its actual observed value, not silently marked as passed.
    """
    item = validate_case(case)
    doc = item["scenario"]
    if type(step) is not int or not 0 <= step <= len(doc["steps"]):
        raise ValueError("Requested step out of bounds")
    if revision != doc["revision"] or type(revision) is not str:
        raise ValueError("Revision drift before replay")
    expected_trace = {}
    if report is not None:
        if (type(report) is not dict or
                report.get("scenario") != doc["id"] or
                report.get("scenario_sha256") != sha256(canonical(doc)).hexdigest()):
            raise ValueError("Report does not match replayed scenario")
        trace = report.get("trace")
        if type(trace) is not list or len(trace) > 257:
            raise ValueError("Invalid trace for on-demand replay")
        for row in trace:
            if (type(row) is not dict or type(row.get("step")) is not int or
                    not 0 <= row["step"] <= len(doc["steps"]) or
                    type(row.get("digest")) is not str or
                    row["step"] in expected_trace):
                raise ValueError("Invalid or duplicate replay trace index")
            expected_trace[row["step"]] = row["digest"]

    session = GameSession.new(content, project, doc["campaign"], seed=doc["seed"])
    state = session.recording()
    if (state["content_digest"] != doc["content_digest"] or
            state["project_digest"] != doc["project_digest"]):
        raise ValueError("Content or GameProject drift before replay")
    if 0 in expected_trace and expected_trace[0] != state["digest"]:
        raise ValueError("Initial checkpoint diverged")
    error = None
    for index, command in enumerate(doc["steps"][:step], 1):
        try:
            getattr(session, command["operation"])(*deepcopy(command["args"]))
            state = session.recording()
            if index in expected_trace and state["digest"] != expected_trace[index]:
                raise ValueError("Checkpoint diverged at step " + str(index))
            # The preceding prefix must restore exactly before proceeding.
            if index < step:
                session = GameSession.from_recording(
                    deepcopy(state), content, project)
                if session.recording() != state:
                    raise ValueError("Checkpoint restoration diverged")
        except Exception as exc:
            error = {"step": index, "type": type(exc).__name__,
                     "message": str(exc)[:500]}
            break

    observations = []
    if error is None and step:
        for check in doc["steps"][step - 1]["expect"]:
            actual = state
            present = True
            for key in check["path"]:
                if type(actual) is not dict or key not in actual:
                    present = False
                    break
                actual = actual[key]
            observation = {
                "path": deepcopy(check["path"]),
                "expected": deepcopy(check["equals"]),
                "present": present,
                "matches": present and type(actual) is type(check["equals"])
                           and actual == check["equals"],
            }
            if present:
                encoded = canonical(actual)
                if len(encoded) <= 4096:
                    observation["actual"] = deepcopy(actual)
                else:
                    observation["actual_sha256"] = sha256(encoded).hexdigest()
                    observation["actual_truncated"] = True
            observations.append(observation)
    return {
        "kind": "drawtemp-r56b-replay-point", "schema": 1,
        "scenario": doc["id"], "revision": revision, "step": step,
        "status": ("runtime-failed" if error else "invariant-failed"
                   if any(not row["matches"] for row in observations)
                   else "reproduced"),
        "mode": state["mode"], "digest": state["digest"],
        "observations": observations, "error": error,
        "release_certified": False,
        "revision_independently_attested": False,
    }


def diff_batches(baseline, current):
    """Compare bounded, same-suite reports without treating green as certified."""
    for source in (baseline, current):
        if (type(source) is not dict or source.get("kind") != REPORT_KIND or
                source.get("schema") != SCHEMA or
                type(source.get("cases")) is not list or
                len(source["cases"]) > MAX_CASES):
            raise ValueError("Invalid baseline/current QA report")
    if baseline["suite_sha256"] != current["suite_sha256"]:
        raise ValueError("Cannot compare different suite versions")
    if len(baseline["cases"]) != len(current["cases"]):
        raise ValueError("Case count differs")
    changes = []
    for old, new in zip(baseline["cases"], current["cases"]):
        if old.get("id") != new.get("id"):
            raise ValueError("Case identities differ")
        old_trace = {r["step"]: r for r in old["report"]["trace"]}
        new_trace = {r["step"]: r for r in new["report"]["trace"]}
        ticks = []
        for index in sorted(set(old_trace) | set(new_trace)):
            a, b = old_trace.get(index), new_trace.get(index)
            if a != b:
                ticks.append({
                    "step": index,
                    "before": None if a is None else a["digest"],
                    "after": None if b is None else b["digest"],
                })
        if old["status"] != new["status"] or ticks:
            changes.append({
                "scenario": new["id"], "before_status": old["status"],
                "after_status": new["status"], "step_diffs": ticks,
            })
    return {
        "kind": "drawtemp-r56b-batch-diff", "schema": 1,
        "baseline_revision": baseline["revision"],
        "current_revision": current["revision"],
        "changes": changes, "equal": not changes,
        "release_certified": False,
    }


def read_suite(path):
    path = Path(path)
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size > MAX_SUITE_BYTES):
        raise ValueError("Missing, linked or oversized suite")
    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_no_duplicate_keys,
        parse_constant=lambda text: (_ for _ in ()).throw(
            ValueError("Non-finite JSON constant: " + text)))
    return validate_suite(data)


def read_report(path):
    path = Path(path)
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size > MAX_SUITE_BYTES * 4):
        raise ValueError("Missing or oversized report")
    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_no_duplicate_keys,
        parse_constant=lambda text: (_ for _ in ()).throw(
            ValueError("Non-finite JSON constant: " + text)))
    if (type(data) is not dict or data.get("kind") != REPORT_KIND or
            data.get("schema") != SCHEMA or
            type(data.get("cases")) is not list or
            not 1 <= len(data["cases"]) <= MAX_CASES):
        raise ValueError("Unknown report schema")
    return data


def save_json(path, value, *, forbidden=()):
    """Never overwrite a source file; no hidden authoring or save writes."""
    path = Path(path)
    if any(path.resolve() == Path(item).resolve() for item in forbidden):
        raise ValueError("Cannot overwrite an input")
    data = canonical(value)
    if len(data) > MAX_SUITE_BYTES * 4:
        raise ValueError("Export exceeds bounded report size")
    if path.is_symlink():
        raise ValueError("Refusing to overwrite symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2,
                                sort_keys=True, allow_nan=False).encode("utf-8") + b"\n")
    return path


def main(argv=None):
    """CLI uses exactly the same batch runner and evidence as the Qt Lab."""
    parser = argparse.ArgumentParser(description="R56.B QA Lab batch replay")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        suite = read_suite(args.suite)
        from drawtemp.sdk.r40_starters import STARTER_KINDS, create_starter_pair
        starters = {item["scenario"]["starter"] for item in suite["cases"]}
        if len(starters) != 1 or next(iter(starters)) not in STARTER_KINDS:
            raise ValueError("CLI requires one canonical R40 starter per suite")
        content, project = create_starter_pair(next(iter(starters)))
        batch = run_batch(
            suite, content, project, revision=args.revision,
            checkpoint_every=args.checkpoint_every)
        if args.report is not None:
            save_json(args.report, batch, forbidden=[args.suite])
        else:
            print(json.dumps(batch, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if batch["status"] == "headless-passed" else 2
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print("R56.B blocked: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
