"""R51.B — Player read-only HUD and narrowly routed authoring intents.

Uses the pre-existing canonical GameSession inside R1 Simulation. Never
duplicates a save, simulates fake CT, or lets QML choose gameplay operations.
"""
from __future__ import annotations

from sporebound.presentation import battle_frame
from sporebound.ui_layout_r51 import (
    UiLayoutError, catalog_from_project, project_layout,
)


def hud_for_player(controller, width):
    """Read the authored HUD_CT for the current real battle, or report NO HUD."""
    if type(width) is not int or not 1 <= width <= 16384:
        raise UiLayoutError("R51: invalid Player viewport width")
    catalog = catalog_from_project(controller.project)
    matching = sorted(
        key for key, layout in catalog["layouts"].items()
        if layout["kind"] == "HUD_CT")
    if not matching or controller.session is None or controller.show_title:
        return {"available": False, "error": ""}
    # This is the same GameSession owned by R1 Simulation, not another copy.
    game = controller.session._session
    battle = game.active_battle
    if battle is None or battle.result:
        return {"available": False, "error": ""}
    try:
        projection = project_layout(
            matching[0], catalog, game, width=width,
            battle_frame=battle_frame(battle, tuple(controller.selected)))
    except UiLayoutError as exc:
        return {"available": False, "error": str(exc)}
    active = battle.active
    authorized = (
        active is not None and active.team == "player" and
        not battle.deploying and not battle.result
    )
    return {
        "available": True, "error": "",
        "projection": projection,
        # Only the already implemented PlayerController.command("end") can
        # be enabled. Remaining v1 authoring intents stay visibly inert.
        "permitted_actions": ["combat.end_turn"] if authorized else [],
    }


def perform_ui_intent(controller, intent):
    """Route only explicitly implemented and valid Player actions."""
    if intent != "combat.end_turn":
        raise UiLayoutError("R51: UI intent not implemented in Player")
    hud = hud_for_player(controller, 900)
    if not hud["available"] or intent not in hud["permitted_actions"]:
        raise UiLayoutError("R51: tactical action unavailable")
    # Existing R12/R1 command is the sole mutation/replay/save owner.
    return controller.command("end")



def menu_for_player(controller, width):
    """Strict, static authored title menu with a guaranteed New Game path.

    A title screen exists before GameSession does, so R51 v1 gameplay
    bindings are *not* resolved using synthetic session state.
    """
    from copy import deepcopy

    if type(width) is not int or not 1 <= width <= 16384:
        raise UiLayoutError("R51: invalid menu viewport width")
    catalog = catalog_from_project(controller.project)
    matches = sorted(k for k, v in catalog["layouts"].items()
                     if v["kind"] == "MENU")
    if not matches or not controller.show_title:
        return {"available": False, "error": ""}
    layout = catalog["layouts"][matches[0]]

    def inspect(node):
        if "binding" in node or "max_binding" in node:
            raise UiLayoutError("R51: title menus cannot use live GameSession bindings")
        return [node["action"]] if node["type"] == "button" else [
            action for child in node.get("children", []) for action in inspect(child)
        ]

    try:
        intents = inspect(layout["root"])
        # Never replace the existing title menu with an authored screen that
        # cannot launch a new game, even if the schema itself is valid.
        if "menu.new_game" not in intents:
            raise UiLayoutError("R51: title menu must offer New Game")
    except UiLayoutError as exc:
        return {"available": False, "error": str(exc)}

    bp = next(p for p in reversed(layout["breakpoints"])
              if width >= p["min_width"])
    permission = ["menu.new_game"]
    save_available = controller.state()["save_manager"]["continue_available"]
    if save_available:
        permission.append("menu.continue")
    permission.extend(("menu.options", "menu.quit"))
    return {
        "available": True, "error": "",
        "projection": {
            "id": matches[0], "kind": "MENU", "columns": bp["columns"],
            "focus_order": deepcopy(layout["focus_order"]),
            "root": deepcopy(layout["root"]),
        },
        # The Qt Quick component intersects this with authored button IDs.
        "permitted_actions": [k for k in permission if k in intents],
    }


def perform_menu_intent(controller, intent):
    """Use only existing R12 menu actions and recheck availability."""
    menu = menu_for_player(controller, 900)
    if not menu["available"] or intent not in menu["permitted_actions"]:
        raise UiLayoutError("R51: title menu action unavailable")
    if intent == "menu.new_game":
        return controller.new_game()
    if intent == "menu.continue":
        return controller.continue_game()
    # Settings and Quit remain local to Main.qml popup/window, never Core.
    raise UiLayoutError("R51: use native Qt shell for non-gameplay menu action")
