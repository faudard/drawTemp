"""R51.C2 — project real dialogue and tactical inventory into authored Qt UI.

Never stages an independent GameSession, edits saves, or synthesizes gameplay.
The canonical controller owns all narrative and item commands. Layouts without
an implemented runtime context always fall back to the existing Player view.
"""
from __future__ import annotations

from sporebound.ui_layout_r51 import (
    UiLayoutError, catalog_from_project, project_layout,
)


def authored_screen(controller, kind, width):
    """Detached presentation model for one real Player screen."""
    if kind not in ("DIALOGUE", "INVENTORY"):
        raise UiLayoutError("R51: unsupported runtime screen")
    if type(width) is not int or not 1 <= width <= 16384:
        raise UiLayoutError("R51: viewport width must be 1..16384")
    catalog = catalog_from_project(controller.project)
    matches = sorted(
        ident for ident, spec in catalog["layouts"].items()
        if spec["kind"] == kind
    )
    if len(matches) != 1 or controller.session is None or controller.show_title:
        return {"available": False, "error": ""}
    state = controller.state()
    expected = "dialogue" if kind == "DIALOGUE" else "battle"
    if state["screen"] != expected:
        return {"available": False, "error": ""}
    game = controller.session._session  # Same authoritative Simulation owner.
    if kind == "DIALOGUE":
        scene = state.get("scene") or {}
        line = state.get("dialogue_line") or {}
        if not scene:
            return {"available": False, "error": ""}
        count = line.get("count", 0)
        index = line.get("index", 0)
        if type(count) is not int or type(index) is not int:
            return {"available": False, "error": "Invalid dialogue line"}
        projection_values = {
            "title": str(scene.get("title") or ""),
            "speaker": str(scene.get("speaker") or ""),
            "text": str(scene.get("text") or ""),
            "progress": (f"Réplique {index + 1} / {count}" if count > 1 else ""),
        }
        try:
            projection = project_layout(
                matches[0], catalog, game, width=width,
                dialogue_view=projection_values)
        except UiLayoutError as exc:
            return {"available": False, "error": str(exc)}
        can_advance = (count > 1 and index < count - 1 and
                       line.get("complete") is False and
                       not bool(state.get("cinematic", {}).get("id")))
        return {
            "available": True, "error": "", "projection": projection,
            "permitted_actions": ["dialogue.advance"] if can_advance else [],
        }

    # Tactical inventory is not the campaign equipment editor, nor a new store.
    battle = game.active_battle
    if battle is None or battle.result:
        return {"available": False, "error": ""}
    stock = state.get("battle", {}).get("inventory", {}).get("player", {})
    if type(stock) is not dict or any(
        type(key) is not str or type(quantity) is not int or quantity < 0
        for key, quantity in stock.items()
    ):
        return {"available": False, "error": "Invalid authoritative inventory"}
    items = [{"id": key, "count": count}
             for key, count in sorted(stock.items()) if count > 0]
    if len(items) > 128:
        return {"available": False, "error": "Inventory display limit exceeded"}
    active = battle.active
    can_use = (active is not None and active.team == "player" and
               not battle.deploying and not battle.result)
    try:
        projection = project_layout(
            matches[0], catalog, game, width=width,
            inventory_view={"item_count": sum(row["count"] for row in items)})
    except UiLayoutError as exc:
        return {"available": False, "error": str(exc)}
    return {
        "available": True, "error": "", "projection": projection,
        "permitted_actions": ["inventory.close"],
        "items": items, "can_use": can_use,
    }


def perform_dialogue_advance(controller):
    """Guard a real R1 narrative advance; authored text never chooses a branch."""
    screen = authored_screen(controller, "DIALOGUE", 800)
    if not screen["available"] or "dialogue.advance" not in screen["permitted_actions"]:
        raise UiLayoutError("R51: dialogue advance unavailable")
    return controller.next_dialogue_line()


def perform_inventory_use(controller, item_id):
    """Reject stale/unknown items and recheck the human CT turn."""
    if type(item_id) is not str or len(item_id) > 120:
        raise UiLayoutError("R51: invalid inventory item ID")
    screen = authored_screen(controller, "INVENTORY", 800)
    if not screen["available"] or not screen["can_use"]:
        raise UiLayoutError("R51: inventory usage unavailable")
    if item_id not in {row["id"] for row in screen["items"]}:
        raise UiLayoutError("R51: item absent from canonical inventory")
    return controller.use_item(item_id)
