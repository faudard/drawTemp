"""R76.B2: rights-gated, pixel-checked optimized *preview* for R15 Creator.

No in-place mutation, new license grant, artistic approval or release certificate.
Only byte-identical assets are de-duplicated; strict R15 checks both projects.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from sporebound.assets import AssetRegistry
from drawtemp.export.r15 import export_game, preflight, project_path, verify_bundle

from drawtemp.assets.optimizer import (
    OptimizerError, _copy_verified, _digest, _json_bytes, _output_location,
    plan_optimization,
)
from drawtemp.assets.optimization_audit import _file_fingerprint

SCHEMA = 2
MAX_PIXELS = 16 * 1024 * 1024
MAX_PROJECT_FILES = 2048
MAX_PROJECT_BYTES = 512 * 1024 * 1024
RECEIPT = "r76b2-receipt.json"
SHA = re.compile(r"[a-f0-9]{64}\Z")


def _load_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise OptimizerError("Duplicate JSON key: " + str(key))
            obj[key] = value
        return obj
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique)


def _real_file(root, relative):
    """No symlink in any project-relative component, even if it points inside."""
    if (not isinstance(relative, str) or not relative or "\\" in relative or
            relative.startswith("/") or any(p in ("", ".", "..")
            for p in relative.split("/"))):
        raise OptimizerError("Nonportable project file path")
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise OptimizerError("Symlink in source path: " + relative)
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise OptimizerError("Missing/unsafe source file: " + relative)
    return resolved


def _fingerprints(root, paths):
    rows = []
    total = 0
    if len(paths) > MAX_PROJECT_FILES:
        raise OptimizerError("R76 preview source file count exceeds limit")
    folded = set()
    for rel in sorted(paths):
        if rel.casefold() in folded:
            raise OptimizerError("Case-colliding project file: " + rel)
        folded.add(rel.casefold())
        path = _real_file(root, rel)
        digest, count, _ = _file_fingerprint(path)
        total += count
        if total > MAX_PROJECT_BYTES:
            raise OptimizerError("R76 preview source exceeds 512 MiB limit")
        rows.append({"path": rel, "sha256": digest, "bytes": count})
    return rows


def _decoded_rgba(root, relative):
    """Decode for a real pixel comparison, bounded; no lossy conversion."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise OptimizerError("R76.B2 pixel gate needs Pillow (pip install '.[art]')") from exc
    path = _real_file(root, relative)
    try:
        with Image.open(path) as img:
            if img.format != "PNG":
                raise OptimizerError("Not a decodable PNG: " + relative)
            w, h = img.size
            if w <= 0 or h <= 0 or w * h > MAX_PIXELS:
                raise OptimizerError("PNG exceeds R76.B2 decoded pixel limit")
            img.load()
            raw = img.convert("RGBA").tobytes()
    except (OSError, SyntaxError, ValueError) as exc:
        raise OptimizerError("PNG decode failed: " + relative) from exc
    return {"width": w, "height": h,
            "rgba_sha256": sha256(raw).hexdigest()}


def inspect_preview(content_path: Path) -> dict:
    """Review canonical Content + GameProject and file-bound redistribution."""
    source = Path(content_path)
    if source.is_symlink():
        raise OptimizerError("Symlinked Content input forbidden")
    source = source.resolve(strict=True)
    project_file = project_path(source)
    if project_file.is_symlink():
        raise OptimizerError("Symlinked GameProject input forbidden")
    initial = preflight(source, require_licenses=True)
    if not initial["passed"] or initial["rights_attestations_checked"] is not True:
        raise OptimizerError("Original R15 strict preflight blocked: " +
                             "; ".join(initial["errors"]))
    project = _load_json(project_file)
    if not isinstance(project, dict):
        raise OptimizerError("Invalid GameProject")
    registry = AssetRegistry(project.get("assets") or None)
    plan = plan_optimization(registry, source.parent)
    if not plan["proposals"]:
        raise OptimizerError("No measured byte-identical optimization available")
    license_file = source.parent / "asset-licenses.json"
    licenses = _load_json(_real_file(source.parent, "asset-licenses.json"))
    if (not isinstance(licenses, dict) or licenses.get("schema") != 1
            or not isinstance(licenses.get("assets"), dict)):
        raise OptimizerError("R15 rights manifest invalid")
    rights = licenses["assets"]
    equivalent = []
    for item in plan["proposals"]:
        redundant, canonical = item["source_path"], item["canonical_path"]
        # Equal bytes do not imply equal redistribution rights. Require the
        # *complete* file-bound attestation to match for merged paths.
        if rights.get(redundant) != rights.get(canonical) or not isinstance(rights.get(canonical), dict):
            raise OptimizerError("Incompatible rights/provenance for " + redundant)
        if rights[canonical].get("allow_modification") is not True:
            raise OptimizerError("Modification rights not approved for " + canonical)
        if redundant.endswith(".png"):
            left = _decoded_rgba(source.parent, redundant)
            right = _decoded_rgba(source.parent, canonical)
            if left != right:
                raise OptimizerError("Decoded RGBA differs for " + redundant)
            equivalent.append({"before": redundant, "after": canonical,
                               "kind": "png_rgba", **left, "identical": True})
        else:
            equivalent.append({"before": redundant, "after": canonical,
                               "kind": "byte_identical_audio_not_decoded",
                               "identical": True})
    all_source = set(initial["assets"]) | set(initial["rights_evidence"])
    all_source.update((source.name, project_file.name, license_file.name))
    fingerprints = _fingerprints(source.parent, all_source)
    return {
        "schema": SCHEMA,
        "kind": "drawtemp-r76b2-optimized-project-plan",
        "content_name": source.name,
        "project_name": project_file.name,
        "optimizer_plan": plan,
        "source_files": fingerprints,
        "visual_evidence": equivalent,
        "rights_gate": "r15_strict_preflight_passed",
        "manual_golden_approval": False,
        "gameplay_replay_parity": "not_assessed",
        "release_certified": False,
    }


def _inventory(root, *, exclude_receipt=False):
    result = []
    paths = []
    for node in root.rglob("*"):
        if node.is_symlink():
            raise OptimizerError("Symlink in derived preview")
        if node.is_file():
            relative = node.relative_to(root).as_posix()
            if exclude_receipt and relative == RECEIPT:
                continue
            paths.append(relative)
        elif not node.is_dir():
            raise OptimizerError("Unsupported node in derived preview")
    return _fingerprints(root, paths)


def _validate_receipt(directory, expected_sha):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise OptimizerError("Derived preview missing or symlinked")
    receipt_path = root / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise OptimizerError("Derived receipt missing")
    receipt = _load_json(receipt_path)
    if (not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA or
            receipt.get("kind") != "drawtemp-r76b2-optimized-project-preview" or
            receipt.get("release_certified") is not False or
            _digest(receipt) != expected_sha or
            receipt_path.read_bytes() != _json_bytes(receipt)):
        raise OptimizerError("Unexpected or tampered derived receipt")
    if _inventory(root, exclude_receipt=True) != receipt["files"]:
        raise OptimizerError("Derived preview contents changed; undo refused")
    content = root / receipt["content_name"]
    staged = preflight(content, require_licenses=True)
    if not staged["passed"] or staged["rights_attestations_checked"] is not True:
        raise OptimizerError("Derived project no longer passes strict R15 preflight")
    return receipt


def prepare_preview(content_path, review, destination, *, approved=False):
    """Publish only a new, strict-R15-checked project copy outside the source."""
    if approved is not True:
        raise OptimizerError("Explicit author approval required")
    source = Path(content_path).resolve(strict=True)
    root, target = _output_location(source.parent, destination)
    current = inspect_preview(source)
    if current != review:
        raise OptimizerError("Stale source, rights, pixels or plan; inspect again")
    projected = deepcopy(current["optimizer_plan"]["projected_registry"])
    aliases = {i["source_path"]: i["canonical_path"]
               for i in current["optimizer_plan"]["proposals"]}
    source_rows = {r["path"]: r for r in current["source_files"]}
    stage = Path(tempfile.mkdtemp(prefix=".r76b2-stage-", dir=target.parent))
    published = False
    try:
        for relative, expected in sorted(source_rows.items()):
            if relative in aliases or relative in (current["project_name"], "asset-licenses.json"):
                continue
            _copy_verified(_real_file(root, relative), stage / relative, expected)
        project = _load_json(_real_file(root, current["project_name"]))
        project["assets"] = projected
        (stage / current["project_name"]).write_bytes(_json_bytes(project))
        licenses = _load_json(_real_file(root, "asset-licenses.json"))
        for redundant in aliases:
            del licenses["assets"][redundant]
        (stage / "asset-licenses.json").write_bytes(_json_bytes(licenses))
        # The original source remains intact; only the detached project uses
        # new paths. R15 verifies those paths, provenance and other extensions.
        checked = preflight(stage / current["content_name"], require_licenses=True)
        if (not checked["passed"] or checked["rights_attestations_checked"] is not True
                or set(checked["assets"]) !=
                    {i["path"] for i in current["optimizer_plan"]["input_asset_fingerprints"]}
                    - set(aliases)):
            raise OptimizerError("Optimized staged R15 preflight blocked: " +
                                 "; ".join(checked["errors"]))
        # Catch any change in source files after staging, including attestation
        # evidence and the Content/Project documents.
        if _fingerprints(root, source_rows) != current["source_files"]:
            raise OptimizerError("Original project changed during staging")
        receipt = {
            "schema": SCHEMA,
            "kind": "drawtemp-r76b2-optimized-project-preview",
            "content_name": current["content_name"],
            "project_name": current["project_name"],
            "files": _inventory(stage),
            "source_plan_sha256": _digest(current),
            "rights_gate": "r15_strict_preflight_passed",
            "visual_evidence": current["visual_evidence"],
            "manual_golden_approval": False,
            "gameplay_replay_parity": "not_assessed",
            "release_certified": False,
        }
        (stage / RECEIPT).write_bytes(_json_bytes(receipt))
        expected_sha = _digest(receipt)
        _validate_receipt(stage, expected_sha)
        if target.exists() or target.is_symlink():
            raise OptimizerError("Output appeared during staging")
        stage.rename(target)
        published = True
        return {"directory": str(target), "receipt_sha256": expected_sha,
                "content": str(target / current["content_name"]),
                "rights_checked": True, "release_certified": False}
    finally:
        if not published and stage.exists():
            shutil.rmtree(stage)


def export_native_preview(directory, receipt_sha256, runtime_dir, bundle):
    """Call existing R15 export only on verified optimized preview, not source."""
    receipt = _validate_receipt(directory, receipt_sha256)
    result = export_game(
        Path(directory) / receipt["content_name"],
        Path(runtime_dir), Path(bundle),
        require_licenses=True, release=False,
    )
    verify_bundle(bundle, require_release=False)
    return {"bundle": str(bundle), "result": str(result),
            "release_certified": False}


def undo_preview(directory, *, expected_receipt_sha256):
    """Reversibly discard only a byte-verified R76.B2 generated copy."""
    root = Path(directory)
    _validate_receipt(root, expected_receipt_sha256)
    with tempfile.TemporaryDirectory(prefix=".r76b2-undo-", dir=root.parent) as work:
        tomb = Path(work) / "project"
        root.rename(tomb)
        try:
            _validate_receipt(tomb, expected_receipt_sha256)
        except BaseException:
            tomb.rename(root)
            raise
        shutil.rmtree(tomb)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="R76.B2 optimized R15 preview (not release)")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan")
    plan_cmd.add_argument("--content", required=True, type=Path)
    stage = commands.add_parser("stage")
    stage.add_argument("--content", required=True, type=Path)
    stage.add_argument("--output", required=True, type=Path)
    stage.add_argument("--expected-plan-sha256", required=True)
    stage.add_argument("--approve", action="store_true")
    exp = commands.add_parser("export")
    exp.add_argument("--stage", required=True, type=Path)
    exp.add_argument("--receipt-sha256", required=True)
    exp.add_argument("--runtime-dir", required=True, type=Path)
    exp.add_argument("--bundle", required=True, type=Path)
    undo = commands.add_parser("undo")
    undo.add_argument("--stage", required=True, type=Path)
    undo.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            plan = inspect_preview(args.content)
            print(json.dumps({"plan_sha256": _digest(plan), "review": plan},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "stage":
            plan = inspect_preview(args.content)
            if not SHA.fullmatch(args.expected_plan_sha256) or (
                    args.expected_plan_sha256 != _digest(plan)):
                raise OptimizerError("Plan checksum changed; run plan again")
            result = prepare_preview(args.content, plan, args.output, approved=args.approve)
        elif args.command == "export":
            result = export_native_preview(args.stage, args.receipt_sha256,
                                           args.runtime_dir, args.bundle)
        else:
            result = {"undone": undo_preview(
                args.stage, expected_receipt_sha256=args.receipt_sha256)}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("R76.B2 NO-GO: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
