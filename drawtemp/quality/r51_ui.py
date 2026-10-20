"""R51.C — inspect authored screens for real Player coverage before export.

This is a *capability* and rights preflight, not an R51 certification.
No implicit migration, simulator, scripts, filesystem traversal or Qt imports.
"""
from __future__ import annotations

from hashlib import sha256
import json

from sporebound.ui_layout_r51 import NAMESPACE, catalog_from_project

# Only capabilities actually implemented and guarded in Qt Player R51.B/B2.
_RUNTIME_INTENTS = {
    "MENU": frozenset({"menu.new_game", "menu.continue", "menu.options", "menu.quit"}),
    "HUD_CT": frozenset({"combat.end_turn"}),
}
# Authored layouts that only Studio can preview must not silently ship as
# functional screens. Future R51/52 may expand this mapping with E2E proof.
_SUPPORTED = frozenset(_RUNTIME_INTENTS)


def _walk(node):
    yield node
    for child in node.get("children", ()):
        yield from _walk(child)


def _canonical_hash(catalog):
    payload = json.dumps(catalog, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def ui_export_audit(project):
    """Evaluate capability parity; return deterministic evidence.

    This does *not* certify accessibility, licensing truth, GPU, native Player
    resources or clean-machine exports. Legacy projects remain unaffected.
    """
    extensions = (project.extensions if hasattr(project, "extensions")
                  else project.get("extensions", {}))
    if NAMESPACE not in extensions:
        return {"present": False, "sha256": "", "screens": [],
                "errors": [], "warnings": []}

    catalog = catalog_from_project(project)  # already validated by GameProject
    errors = []
    warnings = []
    screens = []
    counted_kinds = set()
    if not catalog["layouts"]:
        errors.append("R51: empty opt-in UI catalog cannot replace any Player screen")
    for layout_id, layout in sorted(catalog["layouts"].items()):
        kind = layout["kind"]
        widgets = tuple(_walk(layout["root"]))
        buttons = [w for w in widgets if w["type"] == "button"]
        actions = [w["action"] for w in buttons]
        bindings = [w["id"] for w in widgets
                    if "binding" in w or "max_binding" in w]
        if kind not in _SUPPORTED:
            errors.append(layout_id + ": Player screen kind " + kind +
                          " is Studio-preview only (not runtime implemented)")
        if kind in counted_kinds and kind in _SUPPORTED:
            errors.append(layout_id + ": duplicate runtime screen kind " + kind)
        counted_kinds.add(kind)
        allowed = _RUNTIME_INTENTS.get(kind, frozenset())
        for action in sorted(set(actions) - allowed):
            errors.append(layout_id + ": unsupported Player intent " + action)
        if kind == "MENU":
            if bindings:
                errors.append(layout_id + ": title MENU uses GameSession bindings: " +
                              ", ".join(sorted(bindings)))
            if "menu.new_game" not in actions:
                errors.append(layout_id + ": title MENU lacks menu.new_game")
        if kind == "HUD_CT" and "combat.end_turn" not in actions:
            warnings.append(layout_id + ": HUD_CT has no enabled command")
        screens.append({
            "id": layout_id, "kind": kind, "buttons": len(buttons),
            "widgets": len(widgets),
            "breakpoints": [p["min_width"] for p in layout["breakpoints"]],
        })
    return {
        "present": True, "sha256": _canonical_hash(catalog),
        "screens": screens, "errors": errors, "warnings": warnings,
    }


def assert_ui_bundle_identity(project, manifest_ui):
    """Verify the bundle attests to the exact authored schema and screens."""
    from drawtemp.export.r15 import ExportError

    audit = ui_export_audit(project)
    if not audit["present"]:
        if manifest_ui is not None:
            raise ExportError("R51 manifest declares UI absent from GameProject")
        return
    if type(manifest_ui) is not dict or set(manifest_ui) != {
        "schema", "sha256", "screens", "strict_asset_rights"
    }:
        raise ExportError("Missing or malformed R51 UI export manifest")
    if (manifest_ui["schema"] != 1 or
            manifest_ui["sha256"] != audit["sha256"] or
            manifest_ui["screens"] != audit["screens"] or
            manifest_ui["strict_asset_rights"] is not True):
        raise ExportError("R51 UI manifest / GameProject parity mismatch")
    if audit["errors"]:
        raise ExportError("R51 Player capabilities no longer supported: " +
                          "; ".join(audit["errors"]))



def main(argv=None):
    """Read-only audit for automation and author triage; no certification."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="DrawTemp R51 UI Player compatibility")
    parser.add_argument("--project", type=Path, required=True,
                        help="Canonical *.game.json file")
    args = parser.parse_args(argv)
    try:
        project = json.loads(args.project.read_text(encoding="utf-8"))
        result = ui_export_audit(project)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"present": False, "sha256": "", "screens": [],
                  "errors": [str(exc)], "warnings": []}
    print(json.dumps({"schema": 1, "kind": "r51-ui-capability-audit", **result},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
