"""R27.D: an additive four-stage tactical dungeon journey using R1/R5/R27.

This is a *campaign* journey, not a real-time SceneRouter: each gateway is
an ordinary, verified mission settlement. The builder works on a detached
AuthoringSession and commits the entire Content/Project pair as ONE R1 edit.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.dungeon_authoring import DungeonStudio
from drawtemp.studio.map_authoring import MapStudio


def _prefix(value):
    if (type(value) is not str or not 1 <= len(value) <= 20
            or not value.isascii() or not value[0].isalpha()
            or not all(ch.isalnum() or ch == "_" for ch in value)):
        raise RuleError("Journey prefix must be a safe 1..20 character ID")
    return value


def build_dungeon_journey(maps: MapStudio, *, prefix="r27"):
    """Add one playable four-mission campaign without replacing existing games.

    Village -> key-locked dungeon -> boss -> return uses:
      * real R27.A dungeon room,
      * real R27.B key and locked door,
      * Content.next_missions and CampaignFlow gates/outcomes,
      * Player's existing GameSession save/return_to_campaign.
    """
    if not isinstance(maps, MapStudio):
        raise TypeError("Journey needs the open MapStudio")
    prefix = _prefix(prefix)
    ids = {
        "village": prefix + "_village",
        "dungeon": prefix + "_dungeon",
        "boss": prefix + "_boss",
        "return": prefix + "_return",
    }
    campaign_id = prefix + "_journey"
    source = maps.snapshot()
    occupied = {m["id"] for m in source["content"]["missions"]}
    if occupied.intersection(ids.values()):
        raise RuleError("Journey missions already exist")
    if any(c["id"] == campaign_id for c in source["project"]["campaigns"]):
        raise RuleError("Journey campaign already exists")
    # Sandbox retains the active project's original missions and release
    # metadata; none of these interim edits can touch the live history.
    sandbox = MapStudio(AuthoringSession.new(
        source["content"], source["project"]))
    dungeon = DungeonStudio(sandbox)
    sandbox.create(ids["village"], "Village · le départ", 16, 16)
    sandbox.set_objective("extract")
    sandbox.paint([(2, 14)], "goal")

    dungeon.create_dungeon(ids["dungeon"], "Temple · la clé d'ambre",
                           width=16, height=16, from_map=ids["village"])
    dungeon.build_room((3, 3), (12, 12), entrance=(7, 3))
    dungeon.place_puzzle(prefix + "_amber_key", "key", (7, 2),
                         door_id="room_door")
    sandbox.paint([(8, 5)], "goal")
    sandbox.set_objective("extract")

    dungeon.create_dungeon(ids["boss"], "Crypte · le gardien",
                           width=12, height=12, from_map=ids["dungeon"])
    dungeon.create_dungeon(ids["return"], "Village · le retour",
                           width=16, height=16, from_map=ids["boss"])
    sandbox.set_objective("extract")
    sandbox.paint([(2, 14)], "goal")

    candidate = sandbox.snapshot()
    content, project = candidate["content"], candidate["project"]
    missions = {row["id"]: row for row in content["missions"]}
    # Localized combat difficulty and spawn markers, never a new data schema.
    for stage, coords in {
        "village": ([1, 14], [14, 1]),
        "dungeon": ([7, 1], [14, 1]),
        "boss": ([5, 8], [7, 8]),
        "return": ([1, 14], [14, 1]),
    }.items():
        mission = missions[ids[stage]]
        hero = next(u for u in mission["units"] if u["team"] == "player")
        opponent = next(u for u in mission["units"] if u["team"] == "enemy")
        hero["pos"] = coords[0]
        opponent["pos"] = coords[1]
        # Village and dungeon encounters remain tactical for R27.D; low
        # enemy speed simply leaves time for the intended navigation/puzzle.
        if stage != "boss":
            opponent["speed"] = 1
            opponent["name"] = "Sentinelle lointaine"
        else:
            opponent["name"] = "Gardien du sanctuaire"
            opponent["max_hp"] = 24
            opponent["hp"] = 24
            opponent["attack"] = 5
            opponent["speed"] = 7
        mission["reward"] = {"village": 0, "dungeon": 40,
                             "boss": 120, "return": 0}[stage]
        mission["objective"] = (
            "eliminate" if stage == "boss" else "extract")
    project["campaigns"].append({
        "id": campaign_id,
        "name": "Le sanctuaire de l'ambre",
        "description": "Quatre missions liées : village, énigme, boss, retour",
        "start_mission": ids["village"],
    })
    # The new campaign intentionally has no forced narrative entry scene:
    # an existing main/Jeanne story must remain exactly as it was.
    flow = deepcopy(project.get("campaign_flow", {}))
    gates = flow.setdefault("gates", {})
    outcomes = flow.setdefault("outcomes", {})
    endings = flow.setdefault("endings", {})
    flags = {stage: prefix + "_" + stage + "_cleared"
             for stage in ("village", "dungeon", "boss", "return")}
    gates[ids["dungeon"]] = {"completed_mission": ids["village"]}
    gates[ids["boss"]] = {
        "all": [{"completed_mission": ids["dungeon"]},
                {"flag": flags["dungeon"], "eq": True}]}
    gates[ids["return"]] = {
        "all": [{"completed_mission": ids["boss"]},
                {"flag": flags["boss"], "eq": True}]}
    for stage in ("village", "dungeon", "boss", "return"):
        outcomes[ids[stage]] = {"victory": [
            {"kind": "set_flag", "flag": flags[stage], "value": True}]}
    endings[prefix + "_homecoming"] = {
        "all": [{"completed_mission": ids["return"]},
                {"flag": flags["return"], "eq": True}]}
    project["campaign_flow"] = flow

    # All references, rule registries, cross-object links and project flow
    # are checked by the SAME transactional AuthoringSession validator.
    # An unrelated live edit invalidates this optimistic revision plan.
    plan = maps.authoring.preview_pair(
        lambda _content, _project: (deepcopy(content), deepcopy(project)),
        kind="r27-journey-create")
    result = maps.authoring.apply(plan)
    maps.mission_id = ids["village"]
    return {
        "campaign_id": campaign_id,
        "missions": ids,
        "flags": flags,
        "revision": result.snapshot.revision,
    }


def journey_status(session, campaign_id, *, prefix="r27"):
    """Detached canonical campaign progress; no separate journey checkpoint."""
    prefix = _prefix(prefix)
    if session.campaign_id != campaign_id:
        raise RuleError("Journey does not belong to this campaign")
    progress = session.campaign_inspector()
    by_stage = {}
    for stage in ("village", "dungeon", "boss", "return"):
        mission = prefix + "_" + stage
        by_stage[stage] = {
            "id": mission,
            "completed": mission in progress["missions"]["completed"],
            "available": mission in progress["missions"]["available"],
            "unlocked": mission in progress["missions"]["unlocked"],
        }
    return {
        "campaign_id": campaign_id,
        "stages": by_stage,
        "completed": prefix + "_homecoming" in progress["endings"],
        "consequences": list(progress["consequences"]),
    }
