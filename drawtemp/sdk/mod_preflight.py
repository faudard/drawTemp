"""R47.F — opt-in, read-only project/mod preflight before Player launch.

This is an evidence check, not a second project or replay format. A caller
supplies a separately trusted registry and SHA-256 pins. Unknown namespaces
owned by other DrawTemp features are kept inert, never deleted or executed.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from drawtemp.export.r15 import preflight, project_path
from drawtemp.sdk.modding import ModError, ModRegistry
from sporebound.studio_transaction import validate_pair

MAX_DOCUMENT_BYTES = 32 * 1024 * 1024


def _no_duplicates(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON key: " + name)
        result[name] = value
    return result


def _read_bounded(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("A regular Content/GameProject document is required")
    with path.open("rb") as handle:
        raw = handle.read(MAX_DOCUMENT_BYTES + 1)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Content/GameProject exceeds 32 MiB preview budget")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                      parse_constant=lambda _value: (_ for _ in ()).throw(
                          ValueError("Non-finite JSON number")))
    if type(data) is not dict:
        raise ValueError("Content/GameProject must be a JSON object")
    return data, sha256(raw).hexdigest()


def inspect_modded_project(content_path, registry, *, expected_pins,
                           managed_namespaces=()):
    """Read-only R15 + R47 gate for an authored Content/GameProject pair.

    A game can continue to load unknown *inert* canonical extensions normally.
    Only a host-specified managed scope is subject to orphan detection.
    This function never enables mods, executes code, exports, or grants rights.
    """
    if not isinstance(registry, ModRegistry):
        raise ModError("invalid_registry", "A host-owned ModRegistry is required")
    source = Path(content_path).expanduser()
    result = {
        "schema": 1, "kind": "r47-modded-project-preflight",
        "ready_for_player_preview": False, "errors": [], "warnings": [],
        "content_sha256": None, "project_sha256": None,
        "mod_audit": None, "r15_passed": False,
        "rights_verified": False, "native_player_verified": False,
        "release_certified": False,
    }
    try:
        manifest = project_path(source)
        content, initial_content_hash = _read_bounded(source)
        project, initial_project_hash = _read_bounded(manifest)
        result["content_sha256"] = initial_content_hash
        result["project_sha256"] = initial_project_hash
        _content, canonical_project = validate_pair(content, project)
        mod_report = registry.audit_project(
            canonical_project, expected_pins=expected_pins,
            managed_namespaces=managed_namespaces)
        result["mod_audit"] = mod_report
        result["errors"].extend(mod_report["errors"])
        assets = preflight(source)
        result["r15_passed"] = assets["passed"]
        result["errors"].extend(assets["errors"])
        result["warnings"].extend(assets["warnings"])
        # Detect normal concurrent editor saves between the inspected snapshot
        # and the final preflight. This is NOT an atomic filesystem snapshot.
        _final_content, final_content_hash = _read_bounded(source)
        _final_project, final_project_hash = _read_bounded(manifest)
        if ((final_content_hash, final_project_hash) !=
                (initial_content_hash, initial_project_hash)):
            result["errors"].append("changed_during_preflight")
    except ModError:
        raise  # Bad caller contracts (pin schema) must never look like success.
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        result["errors"].append("invalid_project_files: " + str(exc))
    result["ready_for_player_preview"] = not result["errors"] and result["r15_passed"]
    return result
