"""R38.4: deterministic, read-only Creator Tools Pro preflight.

Uses canonical Content/GameProject validators, R49 typed-reference audit, R31
compiler and R15 asset/rights gate. No writes, implicit migration, inferred
copyright license, release certification or background job.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from sporebound.assets import AssetRegistry
from sporebound.studio_transaction import validate_pair
from drawtemp.sdk.logic_graph import NAMESPACE as LOGIC_NS, compile_r9_triggers
from drawtemp.studio.r49_inspector_integrity import reference_audit

SCHEMA = 1
KIND = "drawtemp-r38-creator-preflight"
MAX_ISSUES = 512
MAX_ASSET_FILES = 10000
MAX_GRAPHS = 128


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def inspect_project(snapshot, *, asset_root=None, require_licenses=False):
    """Inspect a detached session snapshot or pair. Never commit or write.

    A valid canonical pair is necessary but not sufficient for readiness:
    R49 typed refs, R31 graph-to-native synchronization, asset files and R17
    release attestations have independent diagnostics and honest evidence
    status. An incomplete scan blocks preview readiness.
    """
    if type(require_licenses) is not bool:
        raise TypeError("require_licenses must be boolean")
    raw = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    if type(raw) is not dict or not {"content", "project"} <= set(raw):
        raise ValueError("Expected a canonical Content/GameProject snapshot")
    content, project = raw["content"], raw["project"]
    if type(content) is not dict or type(project) is not dict:
        raise ValueError("Content/GameProject must be JSON dictionaries")
    revision = raw.get("revision")
    if revision is not None and (type(revision) is not int or revision < 0):
        raise ValueError("Invalid snapshot revision")
    report = {
        "schema": SCHEMA, "kind": KIND, "revision": revision,
        "content_sha256": None, "project_sha256": None,
        "passed": False, "ready_for_preview": False,
        "asset_integrity_verified": False, "rights_verified": False,
        "release_certified": False, "complete": True,
        "errors": [], "warnings": [], "issues": [], "counts": {
            "missions": 0, "graphs": 0, "assets": 0, "references_scanned": 0,
        },
    }

    def issue(severity, code, path, message):
        if len(report["issues"]) >= MAX_ISSUES:
            report["complete"] = False
            return
        item = {"severity": severity, "code": code, "path": path,
                "message": str(message)}
        report["issues"].append(item)
        target = "errors" if severity == "error" else "warnings"
        report[target].append(str(message))

    try:
        report["content_sha256"] = _hash(content)
        report["project_sha256"] = _hash(project)
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        issue("error", "invalid_json", "/", str(exc))
        report["complete"] = False
        return report

    # This validator owns authoritative game rules, including typed event
    # conditions, door links, physics triggers and most cross-doc IDs.
    try:
        canonical_content, canonical_project = validate_pair(content, project)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        issue("error", "canonical_invalid", "/content+project", str(exc))
        report["complete"] = False
        return report

    report["counts"]["missions"] = len(canonical_content["missions"])
    assets = AssetRegistry(canonical_project.get("assets") or None)
    physical = [row for row in assets.to_dict()["entries"]
                if row["kind"] != "animation"]
    report["counts"]["assets"] = len(physical)

    # R49 scanning is bounded; truncated results are never interpreted as clean.
    try:
        audit = reference_audit(
            {"content": canonical_content, "project": canonical_project},
            max_nodes=20000, max_problems=200)
        report["counts"]["references_scanned"] = audit.scanned_nodes
        for broken in audit.problems:
            issue("error", "reference_missing", broken.path, broken.summary)
        if audit.truncated:
            report["complete"] = False
            issue("error", "reference_incomplete", "/references",
                  "Typed-reference scan exceeded its safety budget")
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        report["complete"] = False
        issue("error", "reference_audit_failed", "/references", str(exc))

    # R31 visual nodes are authoring source. A native R9 trigger edited outside
    # the graph editor would be a valid Content document but a stale build.
    extension = canonical_project.get("extensions", {}).get(LOGIC_NS)
    if extension is not None:
        graphs = extension.get("data", {}).get("graphs", ())
        if type(graphs) is not list or len(graphs) > MAX_GRAPHS:
            report["complete"] = False
            issue("error", "graph_budget", "/extensions/" + LOGIC_NS,
                  "Visual graph preflight exceeds bounded graph limit")
        else:
            report["counts"]["graphs"] = len(graphs)
            for graph in graphs:
                graph_id = str(graph.get("id", "?"))
                mid = graph.get("mission_id")
                path = ("GameProject.extensions." + LOGIC_NS +
                        ".data.graphs[id=" + graph_id + "]")
                try:
                    compiled = compile_r9_triggers(graph)
                    mission = next((row for row in canonical_content["missions"]
                                    if row["id"] == mid), None)
                    if mission is None:
                        raise ValueError("Visual graph mission does not exist")
                    actual = {row["id"]: row for row in mission["triggers"]}
                    for expected in compiled:
                        if actual.get(expected["id"]) != expected:
                            issue("error", "graph_native_drift", path,
                                  "R31 graph " + graph_id +
                                  " differs from generated R9 event " + expected["id"])
                except (ValueError, TypeError, KeyError, RecursionError) as exc:
                    issue("error", "graph_invalid", path, str(exc))

    # Impassable surroundings are advisory: remote switches and scripted
    # opening may make an enclosed door intentional.
    for mission in canonical_content["missions"]:
        mpath = "Content.missions[id=" + mission["id"] + "]"
        width, height = mission["board"]["width"], mission["board"]["height"]
        blocked = {tuple(tile["pos"]) for tile in mission["board"]["tiles"]
                   if tile.get("blocked", False)}
        for row in mission.get("objects", ()):
            if row.get("kind") != "door":
                continue
            x, y = row["pos"]
            adjacent = ((x+1, y), (x-1, y), (x, y+1), (x, y-1))
            if not any(0 <= a < width and 0 <= b < height and
                       (a, b) not in blocked for a, b in adjacent):
                issue("warning", "door_sealed", mpath +
                      ".objects[id=" + row["id"] + "]",
                      "Door " + row["id"] +
                      " has no adjacent walkable tile (may be intentional)")

    if len(physical) > MAX_ASSET_FILES:
        report["complete"] = False
        issue("error", "asset_budget", "/assets",
              "Physical asset count exceeds preflight safety budget")
    elif asset_root is None:
        # A clean in-memory project does not prove on-disk asset integrity.
        if physical:
            issue("warning", "asset_unchecked", "GameProject.assets",
                  "Supply asset_root to verify asset files and license evidence")
        report["asset_integrity_verified"] = not physical
        report["rights_verified"] = not physical
        if require_licenses and physical:
            issue("error", "rights_unchecked", "asset-licenses.json",
                  "Strict rights check requires an asset root")
    else:
        # R15/R17 verifies file signatures, symlink escape, checksum-bound
        # attestations and actual evidence paths. It does *not* grant rights.
        root = Path(asset_root).expanduser()
        if not root.is_dir():
            issue("error", "asset_root_missing", str(root),
                  "Project asset directory does not exist")
        else:
            for problem in assets.diagnostics(root):
                issue("error", "asset_file", "GameProject.assets.entries[id=" +
                      problem["asset_id"] + "]", problem["message"])
            report["asset_integrity_verified"] = not any(
                item["code"] == "asset_file" for item in report["issues"])
            if physical:
                from drawtemp.export.r15 import _check_asset_rights
                gate = {"assets": sorted({row["path"] for row in physical}),
                        "errors": [], "warnings": [], "rights_evidence": [],
                        "rights_attestations_checked": False}
                _check_asset_rights(root, gate, require_licenses)
                for message in gate["errors"]:
                    issue("error", "asset_rights_invalid", "asset-licenses.json", message)
                for message in gate["warnings"]:
                    issue("warning", "asset_rights_warning", "asset-licenses.json", message)
                report["rights_verified"] = (
                    require_licenses and gate["rights_attestations_checked"]
                    and not gate["errors"] and not gate["warnings"])
            else:
                report["rights_verified"] = True

    report["passed"] = not report["errors"] and report["complete"]
    report["ready_for_preview"] = report["passed"] and report[
        "asset_integrity_verified"]
    if require_licenses:
        report["ready_for_preview"] &= report["rights_verified"]
    # No R14 native runtime, clean-machine release or legal verification here.
    return report
