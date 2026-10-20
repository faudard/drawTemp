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
    intent = "combat.end_turn" if kind == "HUD_CT" else "menu.continue"
    label = "Fin du tour" if kind == "HUD_CT" else "Continuer"
    buttons = [
        {"id": "main_action", "type": "button", "text": label,
         "action": intent},
    ]
    if kind == "MENU":
        buttons = [
            {"id": "main_action", "type": "button", "text": "Nouvelle partie",
             "action": "menu.new_game"},
            {"id": "continue_action", "type": "button", "text": "Continuer",
             "action": "menu.continue"},
        ]
    if kind == "DIALOGUE":
        buttons = [{"id": "main_action", "type": "button",
                    "text": "Suite de la conversation",
                    "action": "dialogue.advance"}]
    if kind == "INVENTORY":
        buttons = [{"id": "main_action", "type": "button",
                    "text": "Fermer le sac", "action": "inventory.close"}]
    if kind == "HUD_ACTION":
        buttons = [
            {"id": "step_left", "type": "button", "text": "← Pas gauche",
             "action": "action.step_left"},
            {"id": "step_right", "type": "button", "text": "Pas droit →",
             "action": "action.step_right"},
            {"id": "jump", "type": "button", "text": "Saut",
             "action": "action.jump"},
            {"id": "attack", "type": "button", "text": "Attaquer",
             "action": "action.attack"},
        ]
    extra = []
    if kind == "DIALOGUE":
        extra = [
            {"id": "dialogue_title", "type": "text",
             "binding": {"path": "dialogue.title", "type": "str"}},
            {"id": "dialogue_speaker", "type": "text",
             "binding": {"path": "dialogue.speaker", "type": "str"}},
            {"id": "dialogue_text", "type": "text",
             "binding": {"path": "dialogue.text", "type": "str"}},
            {"id": "dialogue_progress", "type": "text",
             "binding": {"path": "dialogue.progress", "type": "str"}},
        ]
    if kind == "INVENTORY":
        extra = [{"id": "inventory_count", "type": "text",
                  "binding": {"path": "inventory.item_count", "type": "int"}}]
    if kind == "HUD_ACTION":
        extra = [{"id": "action_scene", "type": "text",
                  "binding": {"path": "action.scene_title", "type": "str"}}]
    return {
        "kind": kind,
        "root": {
            "id": "root", "type": "column",
            "children": [
                {"id": "welcome", "type": "text", "text": "Interface personnalisable"},
                *extra, *buttons,
            ],
        },
        "breakpoints": [{"min_width": 0, "columns": 1},
                        {"min_width": 900, "columns": 2}],
        "focus_order": [button["id"] for button in buttons],
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


def edit_gauge_bindings(layout, widget_id, current_path, maximum_path):
    """Change two typed numeric read-only bindings as ONE validated edit."""
    if current_path not in FIELDS or FIELDS[current_path] != "int":
        raise UiLayoutError("R51: gauge current binding must be a known integer")
    if maximum_path not in FIELDS or FIELDS[maximum_path] != "int":
        raise UiLayoutError("R51: gauge maximum binding must be a known integer")
    draft = check_layout(layout)
    node, _parent = _locate(draft["root"], widget_id)
    if node is None or node["type"] != "gauge":
        raise UiLayoutError("R51: selected widget is not a gauge")
    node["binding"] = {"path": current_path, "type": "int"}
    node["max_binding"] = {"path": maximum_path, "type": "int"}
    return check_layout(draft)


def edit_focus_order(layout, focus_order):
    """Replace the keyboard order exactly; R51.A rejects missing/duplicate IDs."""
    draft = check_layout(layout)
    draft["focus_order"] = deepcopy(focus_order)
    return check_layout(draft)


def move_focus(layout, widget_id, direction):
    """Move one button within focus order, regardless of visual tree nesting."""
    if direction not in ("up", "down"):
        raise UiLayoutError("R51: unknown focus direction")
    draft = check_layout(layout)
    focus = draft["focus_order"]
    if widget_id not in focus:
        raise UiLayoutError("R51: selected widget is not a focusable button")
    index = focus.index(widget_id)
    target = index + (-1 if direction == "up" else 1)
    if not 0 <= target < len(focus):
        raise UiLayoutError("R51: button already at focus edge")
    focus[index], focus[target] = focus[target], focus[index]
    return check_layout(draft)


def next_focus(layout, current_id=None, *, reverse=False, enabled=None):
    """Deterministic focus successor, skipping actions disallowed by Player.

    Does not change gameplay or save state; Qt Quick applies the returned ID.
    """
    draft = check_layout(layout)
    order = draft["focus_order"]
    if enabled is not None:
        if type(enabled) not in (set, frozenset, tuple, list):
            raise UiLayoutError("R51: permitted focus IDs must be a collection")
        allowed = set(enabled)
        if any(type(k) is not str for k in allowed):
            raise UiLayoutError("R51: invalid permitted focus identifier")
        order = [key for key in order if key in allowed]
    if not order:
        return None
    if current_id not in order:
        return order[-1] if reverse else order[0]
    step = -1 if reverse else 1
    return order[(order.index(current_id) + step) % len(order)]


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
        "dialogue.title": "La rencontre",
        "dialogue.speaker": "Narrateur",
        "dialogue.text": "Un dialogue de démonstration.",
        "dialogue.progress": "Réplique 1 / 2",
        "inventory.item_count": 3,
        "action.scene_title": "Château — plateforme",
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
