"""R62.C: read-only Player village projection from canonical R35/R55/R62 state.

No gameplay counters, receipts or authoritative inventories live in this
adapter. Only fixed authored definitions and immutable Simulation views are
combined into scene-scoped button intents for Qt Quick.
"""
from __future__ import annotations

from drawtemp.sdk.simulation import thaw
from sporebound.farming_life import EXTENSION as FARM_EXTENSION
from sporebound.relationship_life import EXTENSION as SOCIAL_EXTENSION
from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION


def village_view(session, project, progress, exploration, revision):
    """Return a bounded, detached scene-specific farm/social/merchant HUD."""
    empty = {"enabled": False, "day": 0, "season": "", "weather": "",
             "plots": [], "animals": [], "people": [], "merchants": []}
    scene = exploration.get("scene_id") if exploration else None
    if not scene or exploration.get("completed", False):
        return empty
    extensions = project.extensions
    farm_envelope = extensions.get(FARM_EXTENSION)
    social_envelope = extensions.get(SOCIAL_EXTENSION)
    if farm_envelope is None and social_envelope is None:
        return empty
    inventory = progress.get("inventory", {})
    farm = (thaw(session.farming_state(scene, expected_revision=revision))
            if farm_envelope is not None else None)
    social = (thaw(session.relationship_state(expected_revision=revision))
              if social_envelope is not None else None)
    spec = farm_envelope["data"] if farm_envelope else None
    living = thaw(session.living_world_state(scene=scene))
    clock = thaw(session.living_world_state())
    state = dict(empty)
    state.update(enabled=True, day=clock["day"],
                 season=farm["season"] if farm else "",
                 weather=farm["weather"] if farm else "")
    if farm is not None:
        crops = spec["crops"]
        state["plots"] = [{
            "id": plot["id"], "soil": plot["soil"],
            "crop": farm["plots"][plot["id"]]["crop"] or "",
            "ready": farm["plots"][plot["id"]]["ready"],
            "can_harvest": farm["plots"][plot["id"]]["ready"],
            "planted_day": farm["plots"][plot["id"]]["planted_day"],
            "crops": [
                {"id": crop["id"], "seed": crop["seed_item"],
                 "product": crop["yield_item"], "yield": crop["yield_quantity"],
                 "days": crop["grow_days"],
                 "seed_owned": inventory.get(crop["seed_item"], 0),
                 "available": (farm["plots"][plot["id"]]["crop"] is None
                               and plot["soil"] in crop["soils"]
                               and farm["season"] in crop["seasons"]
                               and inventory.get(crop["seed_item"], 0) > 0)}
                for crop in crops
                if plot["soil"] in crop["soils"]
            ],
        } for plot in spec["plots"] if plot["id"] in farm["plots"]]
        animal_spec = {row["id"]: row for row in spec["animals"]}
        state["animals"] = [
            {"id": key, "hunger": value["hunger"],
             "ready": value["ready"],
             "feed_item": animal_spec[key]["feed_item"],
             "feed_owned": inventory.get(animal_spec[key]["feed_item"], 0),
             "product": animal_spec[key]["yield_item"],
             "can_feed": (value["hunger"] > 0 and
                          inventory.get(animal_spec[key]["feed_item"], 0) > 0)}
            for key, value in sorted(farm["animals"].items())]
    if social is not None:
        social_spec = {row["npc"]: row for row in
                       social_envelope["data"]["relationships"]}
        pose_by_npc = {row["id"]: row for row in living["npcs"]}
        position = exploration.get("position")
        for npc, details in sorted(social["relationships"].items()):
            pose = pose_by_npc.get(npc)
            if pose is None or pose["activity"] == "unavailable":
                continue
            npc_pos = pose.get("pos")
            nearby = (npc_pos is None or
                      (type(position) in (list, tuple) and len(position) == 2
                       and sum(abs(position[i] - npc_pos[i])
                               for i in range(2)) <= 1))
            row = social_spec[npc]
            state["people"].append({
                "id": npc, "activity": pose["activity"],
                "score": details["score"],
                "can_talk": (nearby and details["can_talk_today"] and
                             row["talk_activity"] in ("any", pose["activity"])),
                "talked_today": not details["can_talk_today"],
                "can_gift": nearby and details["can_gift_today"],
                "nearby": nearby,
                "gifts": [
                    {"item": gift["item"], "gain": gift["gain"],
                     "owned": inventory.get(gift["item"], 0),
                     "available": (nearby and details["can_gift_today"]
                                   and inventory.get(gift["item"], 0) > 0)}
                    for gift in row["gifts"]],
            })
    system_envelope = extensions.get(SYSTEMS_EXTENSION)
    if system_envelope:
        stocks = thaw(session.system_state(expected_revision=revision))["stocks"]
        limits = {row["id"]: row["capacity"] for row in
                  system_envelope["data"]["resources"]}
        state["merchants"] = [
            {"id": row["id"], "item": row["resource"],
             "sell_price": row["sell_price"],
             "owned": inventory.get(row["resource"], 0),
             "stock": stocks[row["resource"]],
             "can_sell": (inventory.get(row["resource"], 0) > 0
                          and stocks[row["resource"]] < limits[row["resource"]])}
            for row in system_envelope["data"]["merchants"]
            if row["scene"] == scene]
    return state


__all__ = ["village_view"]
