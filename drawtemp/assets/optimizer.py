"""R76.B1 — deterministic, non-destructive asset de-duplication review.

This creates an *asset-only derived preview*, not a playable bundle or release.
It never mutates the source registry, original files, rights attestations or saves.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile

from sporebound.assets import AssetRegistry

from .optimization_audit import (
    _check_physical_file, _file_fingerprint, audit_registry,
)

SCHEMA = 1


class OptimizerError(ValueError):
    pass


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _digest(value):
    return sha256(_json_bytes(value)).hexdigest()


def plan_optimization(registry: AssetRegistry, project_root: Path) -> dict:
    """Make a frozen review plan; no mutation and no conjectural compression."""
    report = audit_registry(registry, project_root)
    if report["integrity"] != "inspected":
        raise OptimizerError("Asset audit blocked; no optimization proposals available")
    manifest = registry.to_dict()
    files = sorted(report["files"], key=lambda item: item["path"])
    by_path = {item["path"]: item for item in files}
    aliases = {}
    savings = 0
    for group in report["duplicate_candidates"]:
        # Group only truly interchangeable physical media (same extension,
        # same kind, same bytes); do not alter logical asset IDs or bindings.
        by_compatibility = {}
        for path in group:
            item = by_path[path]
            compatibility = (tuple(item["kinds"]), item["media_type"],
                             Path(path).suffix.lower())
            by_compatibility.setdefault(compatibility, []).append(path)
        for paths in by_compatibility.values():
            if len(paths) < 2:
                continue
            canonical = min(paths)
            for redundant in sorted(p for p in paths if p != canonical):
                aliases[redundant] = canonical
                savings += by_path[redundant]["bytes"]
    proposal_rows = [
        {"source_path": path, "canonical_path": target,
         "bytes_saved_in_derived_assets": by_path[path]["bytes"],
         "sha256": by_path[path]["sha256"]}
        for path, target in sorted(aliases.items())
    ]
    projected = deepcopy(manifest)
    for entry in projected["entries"]:
        if entry["kind"] != "animation" and entry["path"] in aliases:
            entry["path"] = aliases[entry["path"]]
    AssetRegistry(projected)
    return {
        "schema": SCHEMA,
        "kind": "drawtemp-r76b-optimizer-plan",
        "input_registry_sha256": _digest(manifest),
        "input_asset_fingerprints": [
            {"path": f["path"], "sha256": f["sha256"], "bytes": f["bytes"]}
            for f in files
        ],
        "proposals": proposal_rows,
        "projected_registry": projected,
        "cost": {
            "source_bytes": report["summary"]["encoded_bytes_hashed"],
            "derived_bytes": report["summary"]["encoded_bytes_hashed"] - savings,
            "bytes_saved": savings,
            "candidate_count": len(proposal_rows),
        },
        "pixel_parity": "byte_identical_source_assets",
        "image_golden_approved": False,
        "rights": "not_assessed",
        "gameplay_parity": "not_assessed",
        "release_certified": False,
    }


def _output_location(project_root, destination):
    root = Path(project_root).resolve(strict=True)
    target = Path(destination)
    # Resolve *only* parent first: do not silently accept a symlinked target.
    if target.is_symlink():
        raise OptimizerError("Symlinked output target forbidden")
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        raise OptimizerError("Output parent must exist")
    if root == parent or root in parent.parents or parent == root.parent and target == root:
        raise OptimizerError("Output must be outside source project directory")
    candidate = parent / target.name
    if candidate.exists() or candidate.is_symlink() or not target.name or target.name in (".", ".."):
        raise OptimizerError("Output already exists or is invalid")
    if candidate == root:
        raise OptimizerError("Cannot overwrite original project")
    return root, candidate


def _verify_plan(registry, root, plan):
    current = plan_optimization(registry, root)
    if current != plan:
        raise OptimizerError("Stale or modified optimization plan; preview again")
    if not current["proposals"]:
        raise OptimizerError("No measurable asset de-duplication proposal")
    return current


def _copy_verified(source: Path, destination: Path, expected: dict):
    # No symlink following; byte hash is checked for both source and output.
    source_sha, source_size, _ = _file_fingerprint(source)
    if (source_sha, source_size) != (expected["sha256"], expected["bytes"]):
        raise OptimizerError("Input changed before copy: " + expected["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        digest = sha256()
        size = 0
        while True:
            data = reader.read(1024 * 1024)
            if not data:
                break
            digest.update(data)
            size += len(data)
            writer.write(data)
        writer.flush()
        os.fsync(writer.fileno())
    source_check, source_now, _ = _file_fingerprint(source)
    if (digest.hexdigest(), size) != (source_sha, source_size) or (
            source_check, source_now) != (source_sha, source_size):
        raise OptimizerError("Input changed during copy: " + expected["path"])
    copied_sha, copied_bytes, _ = _file_fingerprint(destination)
    if (copied_sha, copied_bytes) != (source_sha, source_size):
        raise OptimizerError("Staged copy differs from input: " + expected["path"])


def publish_derived_assets(registry: AssetRegistry, project_root: Path,
                           plan: dict, destination: Path, *, approved: bool) -> dict:
    """Explicit approval creates a standalone *non-releasable* artifact atomically.

    A failed stage is deleted; the original project is never rewritten.
    The destination must not exist; no silent replacement.
    """
    if approved is not True:
        raise OptimizerError("Explicit user approval required")
    root, target = _output_location(project_root, destination)
    current = _verify_plan(registry, root, plan)
    files = {item["path"]: item for item in current["input_asset_fingerprints"]}
    used_paths = sorted({entry["path"] for entry in current["projected_registry"]["entries"]
                         if entry["kind"] != "animation"})
    if len(used_paths) >= len(files):
        raise OptimizerError("No decrease in physical asset count")
    stage = Path(tempfile.mkdtemp(prefix=".r76b-stage-", dir=target.parent))
    published = False
    try:
        for rel in used_paths:
            entry = next(e for e in registry.to_dict()["entries"]
                         if e["kind"] != "animation" and e["path"] == rel)
            source = _check_physical_file(registry, root, rel, entry["id"])
            _copy_verified(source, stage / "assets" / rel, files[rel])
        manifest = current["projected_registry"]
        manifest_bytes = _json_bytes(manifest)
        (stage / "registry.json").write_bytes(manifest_bytes)
        receipt = {
            "schema": SCHEMA,
            "kind": "drawtemp-r76b-derived-assets-preview",
            "release_certified": False,
            "rights": "not_attested_for_derived_package",
            "gameplay_parity": "not_assessed",
            "source_registry_sha256": current["input_registry_sha256"],
            "plan_sha256": _digest(current),
            "registry_sha256": sha256(manifest_bytes).hexdigest(),
            "files": [files[path] for path in used_paths],
            "proposals": current["proposals"],
            "cost": current["cost"],
        }
        (stage / "receipt.json").write_bytes(_json_bytes(receipt))
        _verify_artifact(stage, receipt)
        if target.exists() or target.is_symlink():
            raise OptimizerError("Output appeared during staging")
        stage.rename(target)
        published = True
        return {"directory": str(target), "receipt_sha256": _digest(receipt),
                "cost": deepcopy(current["cost"]), "release_certified": False}
    finally:
        if not published and stage.exists():
            shutil.rmtree(stage)


def _verify_artifact(folder: Path, receipt: dict):
    if not folder.is_dir() or folder.is_symlink():
        raise OptimizerError("Invalid derived asset directory")
    if (receipt.get("schema") != SCHEMA or
            receipt.get("kind") != "drawtemp-r76b-derived-assets-preview" or
            receipt.get("release_certified") is not False):
        raise OptimizerError("Unrecognized optimizer receipt")
    wanted = {"registry.json", "receipt.json"}
    for item in receipt["files"]:
        wanted.add("assets/" + item["path"])
    actual = set()
    for node in folder.rglob("*"):
        if node.is_symlink():
            raise OptimizerError("Symlink in artifact")
        if node.is_file():
            actual.add(node.relative_to(folder).as_posix())
        elif not node.is_dir():
            raise OptimizerError("Unsupported artifact entry")
    if actual != wanted:
        raise OptimizerError("Unexpected or missing derived file")
    registry_bytes = (folder / "registry.json").read_bytes()
    if sha256(registry_bytes).hexdigest() != receipt["registry_sha256"]:
        raise OptimizerError("Derived registry altered")
    registry = AssetRegistry(json.loads(registry_bytes.decode("utf-8")))
    for item in receipt["files"]:
        file = folder / "assets" / item["path"]
        digest, size, _ = _file_fingerprint(file)
        if (digest, size) != (item["sha256"], item["bytes"]):
            raise OptimizerError("Derived asset altered: " + item["path"])
    if registry.diagnostics(folder / "assets"):
        raise OptimizerError("Derived asset registry invalid")
    return True


def undo_derived_assets(destination: Path, *, expected_receipt_sha256: str) -> bool:
    """Remove *only* an intact artifact produced by this feature.

    Reject unknown, tampered and symlinked trees. This does not affect
    any canonical Studio undo/redo history.
    """
    directory = Path(destination)
    if directory.is_symlink() or not directory.is_dir():
        raise OptimizerError("Derived directory absent or symlinked")
    file = directory / "receipt.json"
    if file.is_symlink() or not file.is_file():
        raise OptimizerError("Missing optimizer receipt")
    receipt = json.loads(file.read_text(encoding="utf-8"))
    if (_digest(receipt) != expected_receipt_sha256 or
            file.read_bytes() != _json_bytes(receipt)):
        raise OptimizerError("Receipt differs from approved optimization")
    _verify_artifact(directory, receipt)
    # Atomic move out of the published name before destruction.
    with tempfile.TemporaryDirectory(prefix=".r76b-undo-", dir=directory.parent) as holding:
        tomb = Path(holding) / "derived"
        directory.rename(tomb)
        try:
            _verify_artifact(tomb, receipt)
        except BaseException:
            tomb.rename(directory)
            raise
        shutil.rmtree(tomb)
    return True
