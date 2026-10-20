"""R51.C3 — read-only authored HUD for the canonical R32 platform runtime.

Each authored button invokes exactly one pre-existing R32 simulation frame;
hold-to-move, physics, input polling, and autosave remain in PlatformViewport /
PlayerController. No author text becomes Python, QML, or a dynamic command.
"""
from __future__ import annotations

from sporebound.ui_layout_r51 import (
    UiLayoutError, catalog_from_project, project_layout,
)

ACTION_FRAMES = {
    "action.step_left": (-1, False, False),
    "action.step_right": (1, False, False),
    "action.jump": (0, True, False),
    "action.attack": (0, False, True),
}


def action_hud_for_player(controller, width):
    if type(width) is not int or not 1 <= width <= 16384:
        raise UiLayoutError("R51: invalid action HUD viewport width")
    catalog = catalog_from_project(controller.project)
    matches = sorted(k for k, v in catalog["layouts"].items()
                     if v["kind"] == "HUD_ACTION")
    if len(matches) != 1 or controller.session is None or controller.show_title:
        return {"available": False, "error": ""}
    snapshot = controller.state()
    platform = snapshot.get("platform") or {}
    if snapshot["screen"] != "platform" or platform.get("enabled") is not True:
        return {"available": False, "error": ""}
    layout = catalog["layouts"][matches[0]]
    def walk(node):
        yield node
        for child in node.get("children", ()):
            yield from walk(child)
    nodes = tuple(walk(layout["root"]))
    actions = {w["action"] for w in nodes if w["type"] == "button"}
    if not actions or not actions <= ACTION_FRAMES.keys():
        return {"available": False, "error":
                "R51: unsupported authored R32 button; native viewport retained"}
    scene = snapshot.get("exploration") or {}
    title = scene.get("title") or "Plateformes"
    if type(title) is not str or len(title) > 240:
        return {"available": False, "error": "Invalid native action scene title"}
    try:
        projected = project_layout(
            matches[0], catalog, controller.session._session, width=width,
            action_view={"scene_title": title})
    except UiLayoutError as exc:
        return {"available": False, "error": str(exc)}
    boss = (platform.get("state") or {}).get("boss") or {}
    # Terminal, paused or cinematic scenes cannot dispatch game actions.
    enabled = not (
        boss.get("defeated") or boss.get("player_defeated") or
        bool((snapshot.get("cinematic") or {}).get("id"))
    )
    return {
        "available": True, "error": "", "projection": projected,
        "permitted_actions": sorted(actions) if enabled else [],
        "single_frame": True,
    }


def perform_action_intent(controller, intent):
    """Recheck actual R32 view immediately before the canonical action."""
    if type(intent) is not str or intent not in ACTION_FRAMES:
        raise UiLayoutError("R51: unknown action command")
    hud = action_hud_for_player(controller, 800)
    if not hud["available"] or intent not in hud["permitted_actions"]:
        raise UiLayoutError("R51: action command is unavailable")
    move, jump, attack = ACTION_FRAMES[intent]
    return controller.platform_step(move, jump, attack)
