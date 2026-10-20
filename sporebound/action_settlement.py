"""R50.B action-combat settlement validation and replay evidence.

This is a deliberately *one-shot-per-authored-scene* prototype gate. Each
accepted settlement binds a genuine R26 victory to the canonical R25 route and
Campaign reward flags. No second save, scripts, or free-form loot conversion.
"""
from __future__ import annotations

from hashlib import sha256

from .action_runtime import ActionRuntime
from .action_scene_adapter import EXTENSION, authored_action_scene
from .model import require

MAX_SETTLEMENTS = 32


def settlement_keys(scene):
    require(type(scene) is str and bool(scene), "Invalid action settlement scene")
    slug = sha256(scene.encode("utf-8")).hexdigest()[:20]
    return "r50_action_done_" + slug, "r50_action_coin_" + slug


def victory_coins(runtime):
    """Only reward a living hero after ALL authored enemies are defeated."""
    snapshot = runtime.snapshot()
    require(runtime.tick > 0 and snapshot["hero"]["alive"] is True and
            snapshot["hero"]["hp"] > 0, "R26 action victory needs a living hero")
    enemies = snapshot["enemies"]
    require(bool(enemies) and all(type(e["hp"]) is int and e["hp"] == 0
                                   for e in enemies.values()),
            "R26 victory requires every enemy defeated")
    inv = snapshot["inventory"]
    # R26 chests/keys stay local until their own versioned settlement policy.
    require(set(inv) <= {"coin"} and
            type(inv.get("coin", 0)) is int and
            inv.get("coin", 0) == len(enemies) and
            1 <= len(enemies) <= 32,
            "Only replay-proven once-only R26 coins can transfer to Campaign")
    return inv["coin"]


def validate_settlements(rows, *, project, route_history, progress,
                         current_action=None):
    """Replay every award and match it to a real prior scene transition.

    The ledger and two flags belong to GameSession; Campaign.gold can be
    consumed later, so we never falsely equate gold with the lifetime award.
    """
    require(type(rows) is list and len(rows) <= MAX_SETTLEMENTS,
            "Action settlement history exceeds bound")
    routes = project.scene_routes
    known = {row["id"]: row for row in routes.get("links", [])}
    require(len(route_history) <= 4096, "Malformed action route history")
    visited = set()
    last_index = -1
    total = 0
    for item in rows:
        require(type(item) is dict and set(item) == {
            "version", "scene", "link", "route_index", "coin", "runtime"
        } and type(item["version"]) is int and item["version"] == 1,
                "Invalid R26 action settlement schema")
        scene, link, index, amount = (
            item["scene"], item["link"], item["route_index"], item["coin"])
        require(type(scene) is str and scene not in visited and
                type(link) is str and link in known and
                type(index) is int and last_index < index < len(route_history) and
                type(amount) is int and 1 <= amount <= 32,
                "Invalid or duplicated action reward identity")
        route = known[link]
        require(route_history[index] == link and route["source"] == scene,
                "R26 settled route does not match canonical history")
        # Verify there is no earlier visit to the same action scene at a
        # distinct history index. The terminal action visit must be real.
        cursor = routes["start"]
        source = None
        for historical in route_history[:index + 1]:
            edge = known[historical]
            require(edge["source"] == cursor, "Disconnected R26 route history")
            source = cursor
            cursor = edge["destination"]
        require(source == scene, "R26 action reward attached to wrong scene")
        runtime = ActionRuntime.from_recording(
            item["runtime"], expected_scene=authored_action_scene(project, scene))
        require(victory_coins(runtime) == amount,
                "R26 settled reward differs from validated combat replay")
        flag, coin_flag = settlement_keys(scene)
        require(progress.story_flags.get(flag) is True and
                type(progress.story_flags.get(coin_flag)) is int and
                progress.story_flags[coin_flag] == amount,
                "Campaign reward flags do not match verified R26 settlement")
        visited.add(scene)
        last_index = index
        total += amount
    # Reject phantom reward flags, including those injected into a legacy slot.
    for scene in project.extensions.get(EXTENSION, {}).get("data", {}).get(
            "scenes", {}):
        flag, coin_flag = settlement_keys(scene)
        require((flag in progress.story_flags) == (scene in visited) and
                (coin_flag in progress.story_flags) == (scene in visited),
                "R26 settlement evidence is missing or unexpected")
    if current_action is not None:
        require(current_action.scene["id"] not in visited,
                "Settled R26 scene cannot start another reward run")
    return total
