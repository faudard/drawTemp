"""R51.A — opt-in, headless, declarative UI contract.

UI documents are stored only in GameProject.extensions[org.drawtemp.ui].
They do not own gameplay state, execute code, or change legacy project JSON.
Studio and Player consume the same resolved, read-only projection.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .model import RuleError

NAMESPACE = "org.drawtemp.ui"
VERSION = 1
_ID = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
KINDS = frozenset({"HUD_CT", "HUD_ACTION", "MENU", "DIALOGUE", "INVENTORY"})
INTENTS = frozenset({
    "menu.continue", "menu.new_game", "menu.options", "menu.quit",
    "combat.end_turn", "combat.open_inventory", "dialogue.advance",
    "inventory.close",
    "action.step_left", "action.step_right", "action.jump", "action.attack",
})
# Explicit, typed, read-only GameSession/BattleFrame projection. No getattr
# traversal, user expressions, QML/JS evaluation, or shadow player state.
FIELDS = {
    "session.campaign_id": "str",
    "session.scene_id": "str",
    "session.seed": "int",
    "combat.title": "str",
    "combat.objective": "str",
    "combat.phase": "str",
    "combat.focus": "str",
    "combat.selection": "str",
    "combat.active_hp": "int",
    "combat.active_max_hp": "int",
    # R51.C2: read-only values projected from the existing Player snapshot.
    "dialogue.title": "str",
    "dialogue.speaker": "str",
    "dialogue.text": "str",
    "dialogue.progress": "str",
    "inventory.item_count": "int",
    "action.scene_title": "str",
}


class UiLayoutError(RuleError):
    """A malformed or incompatible authored UI document was rejected."""


def _require(condition, message):
    if not condition:
        raise UiLayoutError("R51 UI: " + message)


def _id(value):
    _require(type(value) is str and _ID.fullmatch(value) is not None,
             "invalid identifier")


def _binding(spec, *, numeric=False):
    _require(type(spec) is dict and set(spec) == {"path", "type"},
             "binding needs path and type")
    path = spec["path"]
    _require(type(path) is str and path in FIELDS, "unknown binding path")
    _require(type(spec["type"]) is str and spec["type"] == FIELDS[path],
             "binding type mismatch")
    if numeric:
        _require(spec["type"] == "int", "gauge requires numeric binding")


def _node(node, ids, buttons, *, depth=0):
    _require(depth <= 8, "tree depth exceeds limit")
    _require(type(node) is dict, "node must be an object")
    kind = node.get("type")
    _require(kind in ("row", "column", "text", "button", "gauge"),
             "unknown widget type")
    _id(node.get("id"))
    _require(node["id"] not in ids, "duplicate widget identifier")
    ids.add(node["id"])
    keys = set(node)
    if kind in ("row", "column"):
        _require(keys == {"id", "type", "children"},
                 "container has unsupported fields")
        children = node["children"]
        _require(type(children) is list and 1 <= len(children) <= 32,
                 "container needs 1..32 children")
        for child in children:
            _node(child, ids, buttons, depth=depth + 1)
    elif kind == "text":
        _require(keys in ({"id", "type", "text"}, {"id", "type", "binding"}),
                 "text needs exactly one literal or binding")
        if "text" in node:
            _require(type(node["text"]) is str and len(node["text"]) <= 240,
                     "text length exceeds limit")
        else:
            _binding(node["binding"])
    elif kind == "button":
        _require(keys == {"id", "type", "text", "action"},
                 "button needs label and explicit action intent")
        _require(type(node["text"]) is str and 1 <= len(node["text"]) <= 120,
                 "invalid button label")
        _require(type(node["action"]) is str and node["action"] in INTENTS,
                 "unknown button intent")
        buttons.add(node["id"])
    else:
        _require(keys == {"id", "type", "binding", "max_binding"},
                 "gauge needs current and maximum bindings")
        _binding(node["binding"], numeric=True)
        _binding(node["max_binding"], numeric=True)
    _require(len(ids) <= 64, "more than 64 widgets in a layout")


def validate_ui_catalog(data):
    """Strictly validate schema v1 and return a detached, unmodified copy.

    Version changes are never migrated automatically on project load.
    """
    _require(type(data) is dict and set(data) == {"version", "layouts"},
             "catalog needs version and layouts")
    _require(type(data["version"]) is int and data["version"] == VERSION,
             "unsupported schema: explicit migration required")
    layouts = data["layouts"]
    _require(type(layouts) is dict and len(layouts) <= 12,
             "layouts must be a map of at most 12 screens")
    for layout_id, layout in layouts.items():
        _id(layout_id)
        _require(type(layout) is dict and
                 set(layout) == {"kind", "root", "breakpoints", "focus_order"},
                 "layout has missing or unknown properties")
        _require(type(layout["kind"]) is str and layout["kind"] in KINDS,
                 "unknown layout kind")
        points = layout["breakpoints"]
        _require(type(points) is list and 1 <= len(points) <= 8,
                 "layout requires 1..8 responsive breakpoints")
        previous = -1
        for point in points:
            _require(type(point) is dict and set(point) == {"min_width", "columns"},
                     "breakpoint needs min_width and columns")
            width = point["min_width"]
            columns = point["columns"]
            _require(type(width) is int and 0 <= width <= 16384 and width > previous,
                     "breakpoints must be strictly increasing")
            _require(type(columns) is int and 1 <= columns <= 4,
                     "invalid responsive column count")
            previous = width
        _require(points[0]["min_width"] == 0,
                 "first responsive breakpoint must start at width zero")
        ids, buttons = set(), set()
        _node(layout["root"], ids, buttons)
        focus = layout["focus_order"]
        _require(type(focus) is list and
                 all(type(i) is str for i in focus) and
                 len(focus) == len(set(focus)) and set(focus) == buttons,
                 "focus order must cover each actionable widget exactly once")
        if layout["kind"] == "MENU":
            _require(bool(buttons), "menu needs an accessible action")
    return deepcopy(data)


def catalog_from_project(project):
    """Read the only canonical location; absence does not opt in."""
    extensions = project.extensions if hasattr(project, "extensions") else project.get("extensions", {})
    spec = extensions.get(NAMESPACE)
    if spec is None:
        return {"version": VERSION, "layouts": {}}
    _require(type(spec) is dict and
             type(spec.get("schema_version")) is int and
             spec["schema_version"] == VERSION and
             type(spec.get("data")) is dict,
             "invalid project extension envelope")
    return validate_ui_catalog(spec["data"])


def _values(session, battle_frame=None, *, dialogue_view=None,
            inventory_view=None, action_view=None):
    from .game_session import GameSession
    _require(isinstance(session, GameSession), "canonical GameSession required")
    values = {
        "session.campaign_id": session.campaign_id,
        "session.scene_id": session.route_scene or "",
        "session.seed": session.seed,
    }
    if battle_frame is not None:
        from .player_hud_layout import combat_hud_sections
        hud = combat_hud_sections(battle_frame)
        values.update({
            "combat.title": hud.title,
            "combat.objective": hud.objective,
            "combat.phase": hud.phase,
            "combat.focus": hud.focus,
            "combat.selection": hud.selection,
        })
        active = next((actor for actor in battle_frame.actors
                       if actor.id == battle_frame.active_id), None)
        if active is not None:
            values["combat.active_hp"] = active.hp
            values["combat.active_max_hp"] = active.max_hp
    # No arbitrary mapping traversal or unknown fields: the Player must
    # project only the documented, already-authenticated view values.
    if dialogue_view is not None:
        _require(type(dialogue_view) is dict and
                 set(dialogue_view) == {"title", "speaker", "text", "progress"},
                 "invalid canonical dialogue projection")
        for field, value in dialogue_view.items():
            _require(type(value) is str and len(value) <= 10000,
                     "invalid dialogue scalar")
            values["dialogue." + field] = value
    if inventory_view is not None:
        _require(type(inventory_view) is dict and
                 set(inventory_view) == {"item_count"} and
                 type(inventory_view["item_count"]) is int and
                 0 <= inventory_view["item_count"] <= 1000000,
                 "invalid inventory scalar")
        values["inventory.item_count"] = inventory_view["item_count"]
    if action_view is not None:
        _require(type(action_view) is dict and
                 set(action_view) == {"scene_title"} and
                 type(action_view["scene_title"]) is str and
                 len(action_view["scene_title"]) <= 240,
                 "invalid R32 action presentation scalar")
        values["action.scene_title"] = action_view["scene_title"]
    return values


def project_layout(layout_id, catalog, session, *, width, battle_frame=None,
                   dialogue_view=None, inventory_view=None,
                   action_view=None):
    """Shared read-only Studio/Player projection; never submit commands.

    The output contains only declarative widgets, responsive columns, and
    resolved scalar data. Button actions remain inert intents for R51.B.
    """
    data = validate_ui_catalog(catalog)
    _id(layout_id)
    _require(layout_id in data["layouts"], "unknown layout")
    _require(type(width) is int and 1 <= width <= 16384,
             "viewport width must be a positive integer")
    layout = data["layouts"][layout_id]
    point = next(p for p in reversed(layout["breakpoints"])
                 if width >= p["min_width"])
    values = _values(session, battle_frame, dialogue_view=dialogue_view,
                     inventory_view=inventory_view, action_view=action_view)

    def resolve(node):
        result = deepcopy(node)
        if "binding" in result:
            spec = result["binding"]
            _require(spec["path"] in values, "binding unavailable in this scene")
            value = values[spec["path"]]
            _require(type(value) is (int if spec["type"] == "int" else str),
                     "runtime binding type mismatch")
            result["value"] = value
        if "max_binding" in result:
            spec = result["max_binding"]
            _require(spec["path"] in values, "maximum binding unavailable")
            value = values[spec["path"]]
            _require(type(value) is int and value >= 0,
                     "invalid maximum binding value")
            result["max_value"] = value
        if "children" in result:
            result["children"] = [resolve(child) for child in result["children"]]
        return result

    return {
        "id": layout_id,
        "kind": layout["kind"],
        "columns": point["columns"],
        "focus_order": deepcopy(layout["focus_order"]),
        "root": resolve(layout["root"]),
    }
