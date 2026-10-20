"""R51.B — pure UI tree editing and explicit sample preview for the Studio.

All changes are local drafts until R51.A's AuthoringSession preview/apply.
No toolkit dependency, arbitrary scripts, sidecar state, or gameplay mutation.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.ui_layout_r51 import FIELDS, INTENTS, KINDS, UiLayoutError, validate_ui_catalog


def new_layout(kind="HUD_CT"):
    if kind not in KINDS:
        raise UiLayoutError("R51: unknown screen kind")
    return {
        "kind": kind,
        "root": {
            "id": "root", "type": "column",
            "children": [
                {"id": "welcome", "type": "text", "text": "Interface personnalisable"},
                {"id": "main_action", "type": "button", "text": "Continuer",
                 "action": "menu.continue"},
            ],
        },
        "breakpoints": [{"min_width": 0, "columns": 1},
                        {"min_width": 900, "columns": 2}],
        "focus_order": ["main_action"],
    }


def check_layout(layout):
    validate_ui_catalog({"version": 1, "layouts": {"design": layout}})
    return deepcopy(layout)


def _walk(node, parent=None):
    yield node, parent
    for child in node.get("children", []):
        yield from _walk(child, node)


def _locate(root, identifier):
    return next(((node, parent) for node, parent in _walk(root)
                 if node["id"] == identifier), (None, None))


def _button_ids(root):
    return [node["id"] for node, _ in _walk(root) if node["type"] == "button"]


def _normalize_focus(layout):
    buttons = _button_ids(layout["root"])
    layout["focus_order"] = [
        key for key in layout["focus_order"] if key in buttons
    ] + [key for key in buttons if key not in layout["focus_order"]]


def edit_layout(layout, command, *, target=None, widget=None, changes=None, direction=None):
    """Return a NEW validated tree; invalid commands leave the original intact.

    Operations: add child; update properties; remove node; move sibling up/down.
    The root cannot be removed/reparented. Structural edits are deterministic.
    """
    draft = check_layout(layout)
    root = draft["root"]
    node, parent = _locate(root, target)
    if command == "add":
        if node is None or node["type"] not in ("column", "row"):
            raise UiLayoutError("R51: select a container before adding")
        if type(widget) is not dict:
            raise UiLayoutError("R51: widget object required")
        if _locate(root, widget.get("id"))[0] is not None:
            raise UiLayoutError("R51: widget ID already exists")
        node["children"].append(deepcopy(widget))
    elif command == "update":
        if node is None or type(changes) is not dict or not changes:
            raise UiLayoutError("R51: existing widget and properties required")
        if "children" in changes or "type" in changes:
            raise UiLayoutError("R51: changing node type/children is not supported")
        old_id = node["id"]
        new_id = changes.get("id", old_id)
        if new_id != old_id and _locate(root, new_id)[0] is not None:
            raise UiLayoutError("R51: widget ID already exists")
        node.update(deepcopy(changes))
        draft["focus_order"] = [new_id if key == old_id else key
                                for key in draft["focus_order"]]
    elif command == "remove":
        if node is None or parent is None:
            raise UiLayoutError("R51: cannot remove root or unknown widget")
        if len(parent["children"]) <= 1:
            raise UiLayoutError("R51: container must keep one child")
        parent["children"] = [row for row in parent["children"]
                              if row["id"] != target]
    elif command == "move":
        if node is None or parent is None or direction not in ("up", "down"):
            raise UiLayoutError("R51: move requires a non-root node and direction")
        siblings = parent["children"]
        current = next(i for i, row in enumerate(siblings) if row["id"] == target)
        next_index = current + (-1 if direction == "up" else 1)
        if not 0 <= next_index < len(siblings):
            raise UiLayoutError("R51: widget already at edge")
        siblings[current], siblings[next_index] = siblings[next_index], siblings[current]
    else:
        raise UiLayoutError("R51: unknown edit command")
    _normalize_focus(draft)
    return check_layout(draft)


def edit_breakpoints(layout, breakpoints):
    draft = check_layout(layout)
    draft["breakpoints"] = deepcopy(breakpoints)
    return check_layout(draft)


def editor_sample(layout, width):
    """Deterministic, visibly labelled DESIGN SAMPLE, never a GameSession.

    The Player never uses this function; runtime binding projection exclusively
    uses project_layout() with the canonical GameSession and BattleFrame.
    """
    draft = check_layout(layout)
    if type(width) is not int or not 1 <= width <= 16384:
        raise UiLayoutError("R51: invalid preview width")
    point = next(p for p in reversed(draft["breakpoints"]) if width >= p["min_width"])
    sample = {
        "session.campaign_id": "demo",
        "session.scene_id": "scene_preview",
        "session.seed": 17,
        "combat.title": "Combat de démonstration",
        "combat.objective": "Défendre le village",
        "combat.phase": "Tour du joueur",
        "combat.focus": "Héros · PV 24/30",
        "combat.selection": "Case 2,3",
        "combat.active_hp": 24,
        "combat.active_max_hp": 30,
    }

    def resolve(node):
        out = deepcopy(node)
        if "binding" in out:
            spec = out["binding"]
            out["value"] = sample[spec["path"]]
        if "max_binding" in out:
            out["max_value"] = sample[out["max_binding"]["path"]]
        if "children" in out:
            out["children"] = [resolve(child) for child in out["children"]]
        return out

    return {"id": "design", "kind": draft["kind"],
            "columns": point["columns"],
            "focus_order": deepcopy(draft["focus_order"]),
            "root": resolve(draft["root"]), "sample": True}
