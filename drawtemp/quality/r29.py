"""R29.A multi-genre quality evidence contracts (headless, fail-closed).

A successful bounded regression is PARTIAL evidence, never a certified
multi-genre Player, approved visual baseline, real GPU, or clean-machine export.
The report is deliberately computed from known probes, not caller-set statuses.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re

CHECKS = tuple(f"R29.{index}" for index in range(1, 11))
P0 = ("R29.1", "R29.2", "R29.3", "R29.4", "R29.5",
      "R29.7", "R29.9", "R29.10")
MODES = ("tactical_ct", "action_realtime", "rpg_turn")
RUNNERS = ("Linux", "Windows", "macOS")
# Each probe exercises EXISTING functionality only. None covers a complete R29 lot.
PROBES = {
    "tactical_replay": "R29.1",
    "visual_contract": "R29.2",
    "save_recovery": "R29.3",
    "export_contract": "R29.4",
    "asset_contract": "R29.5",
    "replay_diagnostics": "R29.8",
    "path_coverage": "R29.9",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _status(probe):
    if probe is None:
        return "blocked"
    if not isinstance(probe, dict) or probe.get("status") not in ("pass", "fail"):
        raise ValueError("Invalid probe status")
    return "partial" if probe["status"] == "pass" else "fail"


def _check(status, detail, probes=()):
    return {"status": status, "detail": detail, "probes": list(probes)}


def create_report(probes, *, revision, runner):
    """Compute a conservative report; no external input can grant 'pass'."""
    if not isinstance(probes, dict) or set(probes) != set(PROBES):
        raise ValueError("R29 requires every declared probe")
    if not isinstance(revision, str) or not revision:
        raise ValueError("Revision required")
    if runner not in (*RUNNERS, "local"):
        raise ValueError("Unrecognized runner")
    checks = {}
    for name, check_id in PROBES.items():
        status = _status(probes[name])
        scope = {
            "tactical_replay": "CT/Jeanne recording, checkpoint and replay only",
            "visual_contract": "Pixel comparator contract only; no approved multi-genre captures",
            "save_recovery": "Existing tactical fault tests; no action/RPG fault matrix",
            "export_contract": "R15 packaging tests; no clean-machine tri-OS proof",
            "asset_contract": "R4/INT-03 contracts; redistribution grant not certified",
            "replay_diagnostics": "Existing tactical diagnosis; no action AI replay explorer",
            "path_coverage": "Tactical campaign routes; no authored puzzle state-space corpus",
        }[name]
        checks[check_id] = _check(
            status, scope if status == "partial" else
            ("Probe failed; inspect log" if status == "fail" else "Probe not run"),
            (name,))
    checks["R29.6"] = _check(
        "blocked", "Real GPU/CPU frame time and memory samples by game mode missing")
    checks["R29.7"] = _check(
        "blocked", "Comparable human creator-to-export tests per genre missing")
    checks["R29.10"] = _check(
        "partial", "SHA-bound no-go evidence report only; signed-off release not certified")
    modes = {
        "tactical_ct": _check(_status(probes["tactical_replay"]),
                              "Bounded canonical Jeanne CT replay", ("tactical_replay",)),
        "action_realtime": _check(
            "blocked", "R25/R26 fixed-tick action runtime replay not yet integrated"),
        "rpg_turn": _check(
            "blocked", "R28 turn-based RPG replay not yet integrated"),
    }
    # All P0 checks AND all real gameplay modes must pass before release; since
    # no available probe proves a complete item, this automatically remains NO-GO.
    ready = (all(checks[key]["status"] == "pass" for key in P0)
             and all(mode["status"] == "pass" for mode in modes.values()))
    reasons = [key + ": " + checks[key]["status"]
               for key in P0 if checks[key]["status"] != "pass"]
    reasons += [key + ": " + modes[key]["status"]
                for key in MODES if modes[key]["status"] != "pass"]
    return {
        "schema": 1, "kind": "drawtemp-r29-evidence", "revision": revision,
        "runner": runner, "probes": probes, "checks": checks, "modes": modes,
        "release_ready": ready, "decision": "go" if ready else "no-go",
        "no_go_reasons": reasons,
        "scope": "bounded, headless QA infrastructure; not release certification",
    }


def verify_report(report, directory, *, require_release=False):
    """Verify log bytes, scope and derived status, rejecting forged 'pass'."""
    if not isinstance(report, dict) or report.get("schema") != 1 or (
            report.get("kind") != "drawtemp-r29-evidence"):
        raise ValueError("Invalid R29 evidence format")
    revision, runner = report.get("revision"), report.get("runner")
    if type(revision) is not str or not revision:
        raise ValueError("R29 revision missing")
    probes = report.get("probes")
    if not isinstance(probes, dict) or set(probes) != set(PROBES):
        raise ValueError("R29 probe matrix incomplete")
    root = Path(directory).resolve(strict=True)
    for name, entry in probes.items():
        if not isinstance(entry, dict) or entry.get("status") not in ("pass", "fail"):
            raise ValueError(f"{name}: invalid result")
        code = entry.get("exit_code")
        if type(code) is not int or (entry["status"] == "pass") != (code == 0):
            raise ValueError(f"{name}: exit code disagrees with status")
        if not isinstance(entry.get("command"), list) or not entry["command"] or not all(
                isinstance(part, str) and part for part in entry["command"]):
            raise ValueError(f"{name}: command missing")
        log, digest = entry.get("log"), entry.get("sha256")
        if (not isinstance(log, str) or log != name + ".log"
                or not isinstance(digest, str) or not SHA.fullmatch(digest)):
            raise ValueError(f"{name}: unsafe log or digest")
        path = (root / log).resolve(strict=True)
        if path.parent != root or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"{name}: missing, empty or external log")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{name}: log integrity mismatch")
    expected = create_report(probes, revision=revision, runner=runner)
    if report != expected:
        raise ValueError("R29 evidence derived checks or release status modified")
    if require_release and not report["release_ready"]:
        raise ValueError("R29 release gate NO-GO: missing multi-genre certification")
    return report["release_ready"]


def aggregate_matrix(sources, *, expected_revision=None):
    """Require independent tri-OS reports with identical immutable revision."""
    found, errors, revisions = {}, [], set()
    for path, report in sources:
        path = Path(path)
        try:
            verify_report(report, path.parent)
            runner, revision = report["runner"], report["revision"]
            if runner not in RUNNERS:
                raise ValueError("CI runner must be Linux, Windows or macOS")
            if runner in found:
                raise ValueError("Duplicate runner " + runner)
            if not COMMIT.fullmatch(revision):
                raise ValueError("Expected 40-hex immutable source revision")
            found[runner] = report
            revisions.add(revision)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(path) + ": " + str(exc))
    missing = sorted(set(RUNNERS) - set(found))
    if missing:
        errors.append("Missing runners: " + ", ".join(missing))
    if len(revisions) != 1:
        errors.append("All runners must report the same source SHA")
    if expected_revision is not None and revisions != {expected_revision}:
        errors.append("Runner SHA disagrees with aggregation SHA")
    failed = {runner: [name for name, item in report["probes"].items()
                       if item["status"] == "fail"]
              for runner, report in found.items()}
    if any(failed.values()):
        errors.append("Failed probes on one or more runners")
    return {
        "schema": 1, "kind": "drawtemp-r29-matrix",
        "revision": next(iter(revisions)) if len(revisions) == 1 else None,
        "runners": sorted(found), "failed_probes": failed,
        "matrix_verified": not errors,
        "release_ready": False, "decision": "no-go",
        "errors": errors,
        "scope": "Tri-OS bounded CI evidence, not clean-machine/GPU/user certification",
    }


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")
