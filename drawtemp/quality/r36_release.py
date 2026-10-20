"""R36.C2 animation asset provenance audit, reusing R4 and strict R15 rights.

The report is a preflight: verifying signatures, hashes, license evidence and
metadata consistency is NOT a legal determination of redistribution rights.
Never auto-approve human-reviewed rights or pixel goldens.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from drawtemp.assets.atlas import load_annotations, png_dimensions
from drawtemp.quality.r14 import safe_asset_path
from sporebound.animation_graph import controllers_from_project
from sporebound.assets import AssetRegistry

UNKNOWN_LICENSES = frozenset(("UNVERIFIED", "UNKNOWN", "TODO", "NONE"))
MAX_SPRITES = 256


def audit_r36_rights(project, asset_root, *, require_licenses=False):
    """Validate every R36-referenced sprite and shared physical atlas (R4/R15).

    Existing R15 rights rules are the only authority for license evidence.
    Optional R4 pivot metadata must not contradict those attestations. With
    strict rights, a mismatch blocks the already-existing R15 export gate.
    """
    if type(require_licenses) is not bool:
        raise ValueError("require_licenses must be a boolean")
    document = project.to_dict() if hasattr(project, "to_dict") else project
    if type(document) is not dict:
        raise ValueError("Expected a validated GameProject dictionary")
    root = Path(asset_root).resolve()
    graph_rows = controllers_from_project(document)
    result = {
        "schema": 1, "kind": "r36-animation-rights",
        "enabled": bool(graph_rows), "strict": require_licenses,
        "controllers": sorted(row["id"] for row in graph_rows),
        "sprites": [], "files": [], "errors": [], "warnings": [],
        "rights_attestations_checked": False,
        "release_ready": False,
    }
    if not graph_rows:
        result["release_ready"] = True  # No R36-specific work; generic R15 still applies.
        return result

    registry = AssetRegistry(document.get("assets") or None)
    ids = set()
    for graph in graph_rows:
        for state in graph["states"]:
            animation = registry.require_reference(state["animation"], "animation")
            ids.update(frame["sprite"] for frame in animation["frames"])
    if len(ids) > MAX_SPRITES:
        result["errors"].append("R36 exceeds 256 distinct referenced sprite IDs")
        return result
    result["sprites"] = sorted(ids)
    file_hashes = {}
    for sprite_id in sorted(ids):
        try:
            descriptor = registry.require_reference(sprite_id, "sprite")
            relative = descriptor["path"]
            path = safe_asset_path(root, relative)
            resolved = registry.resolve(sprite_id, root)
            if path != resolved:
                raise ValueError("R28 sprite file path does not match canonical registry")
            raw = resolved.read_bytes()
            width, height = png_dimensions(raw)
            if "region" in descriptor:
                x, y, w, h = descriptor["region"]
                if x + w > width or y + h > height:
                    raise ValueError("Sprite atlas region exceeds verified PNG")
            digest = sha256(raw).hexdigest()
            previous = file_hashes.get(relative)
            if previous is not None and previous != digest:
                raise ValueError("Referenced atlas changed during audit")
            file_hashes[relative] = digest
        except (OSError, TypeError, ValueError) as exc:
            result["errors"].append(sprite_id + ": " + str(exc))

    result["files"] = [
        {"path": relative, "sha256": digest}
        for relative, digest in sorted(file_hashes.items())
    ]
    try:
        annotation = load_annotations(
            root / ".drawtemp" / "r4-annotations.json", registry)["sprites"]
    except (OSError, TypeError, ValueError) as exc:
        result["errors"].append("R4 annotation file invalid: " + str(exc))
        annotation = {}
    for sprite_id in sorted(ids):
        metadata = annotation.get(sprite_id)
        if metadata is None:
            continue  # Annotations are optional for plain R28 PNG files.
        relative = registry.require_reference(sprite_id, "sprite")["path"]
        digest = file_hashes.get(relative)
        if digest and metadata["source_sha256"] != digest:
            result["errors"].append(sprite_id + ": R4 annotation source hash differs from PNG")
        if metadata["license"].upper() in UNKNOWN_LICENSES:
            message = sprite_id + ": R4 annotation license remains unverified"
            (result["errors"] if require_licenses else result["warnings"]).append(message)

    # Reuse R15's existing, evidence-backed attestation validator verbatim.
    from drawtemp.export.r15 import _check_asset_rights
    rights_report = {
        "errors": [], "warnings": [], "assets": sorted(file_hashes),
        "rights_evidence": [], "rights_attestations_checked": False,
    }
    if file_hashes:
        _check_asset_rights(root, rights_report, require_licenses)
    else:
        rights_report["rights_attestations_checked"] = True
    result["errors"].extend(rights_report["errors"])
    result["warnings"].extend(rights_report["warnings"])
    result["rights_attestations_checked"] = rights_report["rights_attestations_checked"]
    result["rights_evidence"] = rights_report["rights_evidence"]
    result["release_ready"] = (
        require_licenses and not result["errors"] and
        result["rights_attestations_checked"]
    )
    return result
