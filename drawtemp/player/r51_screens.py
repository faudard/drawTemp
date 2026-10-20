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
    layout = catalog["layouts"][matches[0]]

    def nodes(root):
        yield root
        for child in root.get("children", []):
            yield from nodes(child)

    authored = tuple(nodes(layout["root"]))
    actions = {row["action"] for row in authored if row["type"] == "button"}
    permitted = ({"dialogue.advance"} if kind == "DIALOGUE"
                 else {"inventory.close"})
    # Without a visible narrative text and advance action the designer could
    # hide a canonical story and soft-lock the player. Prefer the legacy UI.
    required_bindings = ({"dialogue.text"} if kind == "DIALOGUE"
                         else set())
    bindings = {row["binding"]["path"] for row in authored
                if "binding" in row}
    if not permitted <= actions or not actions <= permitted or not (
            required_bindings <= bindings):
        return {"available": False, "error":
                "R51: authored screen lacks mandatory text/action or has "
                "unsupported intents; classic Player retained"}
    state = controller.state()
    expected = ("dialogue",) if kind == "DIALOGUE" else ("battle", "campaign")
    if state["screen"] not in expected:
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

    if state["screen"] == "campaign":
        # R8 campaign equipment is the authoritative inventory projection,
        # *not* the battle stock. No free-form owner/hero IDs are accepted.
        gear = state.get("gear") or {}
        stock = gear.get("inventory") or []
        equipped = gear.get("equipped") or {}
        if type(stock) is not list or type(equipped) is not dict or any(
            type(row) is not dict or
            type(row.get("id")) is not str or
            type(row.get("count")) is not int or
            row["count"] < 0 or
            type(row.get("slot")) is not str or
            type(row.get("name")) is not str
            for row in stock
        ):
            return {"available": False, "error": "Invalid campaign inventory"}
        if len(stock) > 128 or any(
            type(key) is not str or type(value) is not str
            for key, value in equipped.items()
        ):
            return {"available": False, "error": "Invalid equipped items"}
        stock_rows = sorted(
            ({"id": row["id"], "name": row["name"],
              "slot": row["slot"], "count": row["count"]}
             for row in stock if row["count"] > 0),
            key=lambda row: row["id"])
        total = sum(row["count"] for row in stock_rows)
        try:
            projection = project_layout(
                matches[0], catalog, game, width=width,
                inventory_view={"item_count": total})
        except UiLayoutError as exc:
            return {"available": False, "error": str(exc)}
        return {
            "available": True, "error": "", "projection": projection,
            "permitted_actions": ["inventory.close"],
            "context": "campaign", "items": stock_rows,
            "equipped": dict(equipped), "can_use": False,
            "can_equip": True,
        }

    # Tactical inventory is intentionally separate from the campaign gear.
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
        "context": "battle", "items": items, "can_use": can_use,
        "can_equip": False, "equipped": {},
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



def perform_campaign_equip(controller, item_id):
    """Apply R8 equipment only when the canonical campaign owns the item."""
    if type(item_id) is not str or len(item_id) > 120:
        raise UiLayoutError("R51: invalid campaign equipment ID")
    screen = authored_screen(controller, "INVENTORY", 800)
    if not screen["available"] or screen.get("context") != "campaign":
        raise UiLayoutError("R51: campaign equipment screen unavailable")
    if item_id not in {row["id"] for row in screen["items"]}:
        raise UiLayoutError("R51: equipment not in the real campaign stock")
    return controller.equip_hero("jeanne", item_id)


def perform_campaign_unequip(controller, slot):
    """Never let authored UI select an arbitrary actor or inventory slot."""
    if slot not in ("weapon", "armor", "accessory") or type(slot) is not str:
        raise UiLayoutError("R51: invalid campaign equipment slot")
    screen = authored_screen(controller, "INVENTORY", 800)
    if not screen["available"] or screen.get("context") != "campaign":
        raise UiLayoutError("R51: campaign equipment screen unavailable")
    if not screen["equipped"].get(slot):
        raise UiLayoutError("R51: equipment slot is already empty")
    return controller.unequip_hero("jeanne", slot)
