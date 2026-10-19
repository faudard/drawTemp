"""R17.13: fail-closed release evidence index, not a certification authority."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from drawtemp.quality.r14 import verify_report
from drawtemp.export.r15 import preflight, project_path, verify_bundle

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")

REQUIRED_CHECKS = (
    "Headless R17 / Python 3.10",
    "Headless R17 / Python 3.12",
    "Combined R7/R9/Player/Renderer / ubuntu-latest",
    "Combined R7/R9/Player/Renderer / windows-latest",
    "Combined R7/R9/Player/Renderer / macos-latest",
    "R17.12 author / save / export contract",
    "R17.12 freeze / authored export / ubuntu-latest",
    "R17.12 freeze / authored export / windows-latest",
    "R17.12 freeze / authored export / macos-latest",
    "R17.12 authored Player / isolated ubuntu-latest",
    "R17.12 authored Player / isolated windows-latest",
    "R17.12 authored Player / isolated macos-latest",
)
RELEASE_GATES = {
    "R17.1": "Merge inventory and master ancestry",
    "R17.2": "Canonical runtime and Studio",
    "R17.3": "Event pages and replay persistence",
    "R17.4": "One AuthoringSession across workshops",
    "R17.5": "Human-reviewed renderer equivalence",
    "R17.6": "Redistribution and modification rights",
    "R17.7": "Crash-safe saves and deterministic replay",
    "R17.8": "Native export on physically clean machine",
    "R17.9": "Real hardware GPU profiles and goldens",
    "R17.10": "Legacy migration and rollback",
    "R17.11": "Player and Studio error recovery UX",
    "R17.12": "Cross-workshop native Player user journey",
    "R17.13": "Evidence inventory and external release review",
}
OPEN_RISKS = (
    "Real art redistribution rights and legal provenance not independently verified",
    "Hardware GPU frame times, human goldens and DPI review not independently approved",
    "Isolated CI runner does not equal a clean consumer installation",
    "Offscreen Qt smoke is not an interactive test across all GUI workshops",
    "PR stack changes must be present in final master tree and checked commit",
    "Executable signing, notarization and independent final approval are pending",
)


class EvidenceError(ValueError):
    pass


def _hash_file(path):
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file(location):
    p = Path(location)
    if p.is_symlink() or not p.is_file():
        raise EvidenceError("Missing or symlinked evidence: " + str(p))
    return p


def index_artifacts(artifacts):
    """Compute hashes from real files, never accept claimed digests."""
    if not isinstance(artifacts, dict):
        raise EvidenceError("Named artifacts must be a mapping")
    result = {}
    for name, location in sorted(artifacts.items()):
        if not isinstance(name, str) or not ARTIFACT_NAME.fullmatch(name):
            raise EvidenceError("Invalid artifact name")
        p = _file(location)
        result[name] = {"path": str(p), "sha256": _hash_file(p),
                        "size_bytes": p.stat().st_size}
    return result


def _json(location):
    p = _file(location)
    if p.stat().st_size > 8 * 1024 * 1024:
        raise EvidenceError("Evidence JSON exceeds 8 MiB")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise EvidenceError("Invalid evidence JSON: " + str(exc)) from exc


def inspect_checks(payload, revision):
    """Check-run snapshot must be complete and anchored to exact commit.

    Downloaded JSON is a self-supplied snapshot, not authenticated GitHub API
    provenance. A CI success can never imply independent release approval.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("check_runs"), list):
        raise EvidenceError("Expected GitHub check-runs API JSON")
    runs = payload["check_runs"]
    if type(payload.get("total_count")) is not int or payload["total_count"] != len(runs):
        return {"complete": False, "all_required_success": False,
                "reason": "Check-run pagination incomplete", "required": {},
                "missing": list(REQUIRED_CHECKS)}
    named = {}
    for run in runs:
        if not isinstance(run, dict):
            raise EvidenceError("Malformed GitHub check run")
        name = run.get("name")
        if name not in REQUIRED_CHECKS:
            continue
        if run.get("head_sha") != revision:
            raise EvidenceError("Check belongs to another commit: " + str(name))
        named.setdefault(name, []).append(run)
    required = {}
    missing = []
    for name in REQUIRED_CHECKS:
        choices = named.get(name, [])
        if not choices:
            missing.append(name)
            required[name] = {"status": "missing", "conclusion": None}
            continue
        current = max(choices, key=lambda row: (
            row.get("run_attempt") if type(row.get("run_attempt")) is int else 0,
            row.get("started_at") or "",
            row.get("id") if type(row.get("id")) is int else 0))
        required[name] = {"status": current.get("status"),
                          "conclusion": current.get("conclusion"),
                          "url": current.get("html_url") or ""}
    complete_green = not missing and all(
        x["status"] == "completed" and x["conclusion"] == "success"
        for x in required.values())
    return {"complete": True, "all_required_success": complete_green,
            "reason": "" if complete_green else "Missing, queued or failing checks",
            "required": required, "missing": missing}


def inspect_cross(payload):
    if not isinstance(payload, dict):
        raise EvidenceError("Expected cross-workshop JSON object")
    player = payload.get("player")
    valid = (
        isinstance(player, dict) and player.get("replay_verified") is True
        and player.get("trigger_count") == 1
        and isinstance(payload.get("preflight"), dict)
        and payload["preflight"].get("passed") is True
        and all(isinstance(payload.get(key), str) and SHA64.fullmatch(payload[key])
                for key in ("content_sha256", "project_sha256", "asset_sha256"))
        and payload.get("r17_12_certified") is False)
    return {"contract_valid": bool(valid),
            "scope": "self-reported cross-workshop preview",
            "release_certified": False}


def inspect_r14(payload):
    try:
        complete = verify_report(payload, require_complete=False)
    except (TypeError, KeyError, ValueError) as exc:
        return {"contract_valid": False, "claimed_p0_complete": False,
                "reason": str(exc)}
    return {"contract_valid": True, "claimed_p0_complete": bool(complete),
            "hardware_independently_attested": False}


def _gate(key, status="blocked", detail="Independent proof is missing"):
    return {"name": RELEASE_GATES[key], "status": status, "detail": detail}


def build_dossier(*, revision, artifacts=None, checks=None, cross=None, r14=None,
                  content_path=None, bundle_path=None, review=None,
                  generated_utc=None):
    """Collect evidence without elevating a self-reported result into release."""
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise EvidenceError("Exact lowercase 40-digit commit SHA required")
    paths = dict(artifacts or {})
    for name, value in (("github-checks", checks),
                        ("r17-12-cross-workshop", cross),
                        ("r14-hardware-report", r14),
                        ("release-review", review)):
        if value is not None:
            if name in paths:
                raise EvidenceError("Reserved artifact name: " + name)
            paths[name] = value
    if content_path is not None:
        if "authored-content" in paths or "authored-project" in paths:
            raise EvidenceError("Reserved authored artifact names")
        paths["authored-content"] = content_path
        paths["authored-project"] = project_path(content_path)
    if bundle_path is not None:
        if "bundle-manifest" in paths:
            raise EvidenceError("Reserved bundle artifact name")
        paths["bundle-manifest"] = Path(bundle_path) / "manifest.json"
    indexed = index_artifacts(paths)
    gates = {key: _gate(key) for key in RELEASE_GATES}
    ci = (inspect_checks(_json(checks), revision) if checks is not None
          else {"complete": False, "all_required_success": False,
                "reason": "No check-run snapshot", "required": {},
                "missing": list(REQUIRED_CHECKS)})
    components = {"checks": ci}
    if ci["all_required_success"]:
        gates["R17.2"] = _gate("R17.2", "partial",
                              "Integration CI for this commit reports success")
        gates["R17.8"] = _gate(
            "R17.8", "partial",
            "Native+isolated CI checks passed; physical installation not verified")
    else:
        gates["R17.8"]["detail"] = ci["reason"]

    if cross is not None:
        result = inspect_cross(_json(cross))
        components["cross_workshop"] = result
        if result["contract_valid"]:
            for gate, reason in (
                ("R17.3", "Event page preview reported, not independently attested"),
                ("R17.4", "Shared canonical adapters used, GUI clicks unverified"),
                ("R17.7", "Save/replay reported; fault matrix not independently reviewed"),
                ("R17.12", "Cross-workshop preview; full native GUI journey pending"),
            ):
                gates[gate] = _gate(gate, "partial", reason)
        else:
            gates["R17.12"]["detail"] = "R17.12 evidence invalid or incomplete"
    if bundle_path is not None:
        try:
            manifest = verify_bundle(bundle_path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            components["bundle"] = {"verified": False, "reason": str(exc)}
        else:
            matched = True
            if content_path is not None:
                expected = Path(content_path)
                source_pair = project_path(expected)
                exported_pair = (Path(bundle_path) / "game" / source_pair.name)
                matched = (
                    manifest["content"] == "game/" + expected.name
                    and exported_pair.is_file()
                    and not exported_pair.is_symlink()
                    and _hash_file(expected) ==
                        _hash_file(Path(bundle_path) / manifest["content"])
                    and _hash_file(source_pair) == _hash_file(exported_pair))
            components["bundle"] = {
                "verified": bool(matched), "content": manifest["content"],
                "file_count": len(manifest["files"]),
                "authored_pair_identical": matched if content_path is not None else None,
                "certification": manifest.get("certification", "unknown")}
            if not matched:
                components["bundle"]["reason"] = (
                    "R15 bundle does not match the exact authored Content/GameProject pair")
                gates["R17.8"]["detail"] = "Export belongs to another authored project"
            elif gates["R17.8"]["status"] == "blocked":
                gates["R17.8"] = _gate(
                    "R17.8", "partial",
                    "Local R15 manifest verified; native installation unproven")
    if r14 is not None:
        info = inspect_r14(_json(r14))
        components["r14"] = info
        if info["contract_valid"]:
            gates["R17.5"] = _gate(
                "R17.5", "partial",
                "R14 report structure checked; human visual approval still needed")
            if info["claimed_p0_complete"]:
                gates["R17.9"] = _gate(
                    "R17.9", "partial",
                    "R14 report claims P0 complete; real GPU provenance unauthenticated")
    if content_path is not None:
        report = preflight(content_path, require_licenses=True)
        structured = report.get("rights_attestations_checked") is True
        components["asset_rights"] = {
            "strict_preflight_passed": report["passed"],
            "structured_attestations_checked": structured,
            "independent_legal_review": False,
            "errors": report["errors"], "warnings": report["warnings"]}
        if report["passed"] and structured:
            gates["R17.6"] = _gate(
                "R17.6", "partial",
                "R17.6 rights file hashes checked; licensor authority not reviewed")
        else:
            gates["R17.6"]["detail"] = "Rights approval incomplete; release blocked"
    if review is not None:
        submitted = _json(review)
        components["external_review"] = {
            "recorded": isinstance(submitted, dict),
            "authenticated": False,
            "reason": "Standalone JSON cannot authenticate a reviewer"}
    if indexed:
        gates["R17.13"] = _gate(
            "R17.13", "partial",
            "Local SHA-256 evidence index exists; external review remains pending")
    blocking = [
        key + ": " + gate["detail"] for key, gate in gates.items()
        if gate["status"] != "pass"]
    return {
        "schema": 1, "kind": "drawtemp5-r17-release-evidence",
        "revision": revision,
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
        "status": "blocked", "release_ready": False,
        "independent_release_approval": False,
        "artifacts": indexed, "components": components,
        "gates": gates, "blocking_reasons": blocking,
        "open_risks": list(OPEN_RISKS),
        "release_notes_status": "DRAFT - NOT CERTIFIED"}


def release_notes(dossier):
    if dossier.get("kind") != "drawtemp5-r17-release-evidence":
        raise EvidenceError("Expected an R17 release dossier")
    lines = [
        "# DrawTemp 5.0 - Draft release notes (NOT CERTIFIED)", "",
        "Commit: " + dossier["revision"], "",
        "**Release status: BLOCKED.** No publishing approval is implied.", "",
        "## Features awaiting release review", "",
        "- Canonical SDK and Studio workshops for maps, RPG data and events",
        "- Qt Player, persistence and recovery, R15 native export preview",
        "- R17.12 cross-workshop E2E scenario and native relocation", "",
        "## Unmet release gates", ""]
    lines.extend("- **" + key + "**: " + row["detail"]
                 for key, row in dossier["gates"].items()
                 if row["status"] != "pass")
    lines += ["", "## Artifact SHA-256 digests", ""]
    lines.extend("- " + name + ": " + row["sha256"] +
                 " (" + str(row["size_bytes"]) + " bytes)"
                 for name, row in dossier["artifacts"].items())
    lines += ["", "Hashes prove bytes, not legal rights, human approvals or real GPU provenance.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="R17.13 fail-closed release dossier")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--artifact", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--checks-json", type=Path)
    parser.add_argument("--cross-json", type=Path)
    parser.add_argument("--r14-json", type=Path)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--review-json", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    artifacts = {}
    for spec in args.artifact:
        name, equal, location = spec.partition("=")
        if not equal or name in artifacts:
            parser.error("Expected unique --artifact NAME=PATH")
        artifacts[name] = Path(location)
    try:
        dossier = build_dossier(
            revision=args.revision, artifacts=artifacts, checks=args.checks_json,
            cross=args.cross_json, r14=args.r14_json,
            content_path=args.content, bundle_path=args.bundle,
            review=args.review_json)
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    for path, data in (
        (args.report, json.dumps(dossier, ensure_ascii=False,
                                 sort_keys=True, indent=2) + "\n"),
        (args.notes, release_notes(dossier))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    print("R17.13 BLOCKED: " + str(len(dossier["blocking_reasons"])) +
          " gates pending, report=" + str(args.report))
    return 1 if args.require_ready and not dossier["release_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
