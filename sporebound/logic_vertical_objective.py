"""R31.H — opt-in all-objectives gate for the reference Player journey.

This is an ordinary immutable RuleSet objective. It requires the real Battle
state to show an enemy defeated, a chest opened and a player on the extraction
cell. Never activate it for legacy missions, and never drive outcomes from UI.
"""
from __future__ import annotations

from .rules.registry import ObjectiveRule

OBJECTIVE = "r31h_quest_extract"
CHEST = "r31h_chest"


def validate_slice_mission(mission):
    from .model import require
    matching = [obj for obj in mission.objects
                if obj["id"] == CHEST and obj["kind"] == "chest"]
    require(len(matching) == 1,
            "R31.H extraction requires one authored native chest")
    require(not matching[0].get("used", False),
            "R31.H authored chest must begin unopened")
    require(bool(mission.goal), "R31.H extraction requires a goal cell")


def achieved(battle):
    chest = next((obj for obj in battle.mission.objects
                  if obj["id"] == CHEST and obj["kind"] == "chest"), None)
    return bool(chest and chest.get("used", False) and
                not any(actor.alive and actor.team == "enemy"
                        for actor in battle.units) and
                any(actor.alive and actor.team == "player" and
                    actor.pos in battle.mission.goal for actor in battle.units))


def has_slice_objective(data):
    return any(row.get("objective") == OBJECTIVE
               for row in data.get("missions", ()))


def install_slice_objective(rules):
    if OBJECTIVE in rules.objectives:
        return rules
    return rules.with_family(
        "objectives",
        rules.objectives.with_rule(
            OBJECTIVE, ObjectiveRule(achieved, needs_goal=True,
                                     version="5.0-r31h")))
