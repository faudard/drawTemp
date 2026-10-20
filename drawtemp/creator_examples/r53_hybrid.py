"""R53.C1 — authored three-companion RPG↔CT route using canonical engines.

No fake CT adapter: the native R41 RPG encounters and R25 SceneRouter/CT
Battle process every action in GameSession and persist in its existing slot.
"""
from __future__ import annotations

from drawtemp.creator_examples.classic_rpg import build_relais_du_village
from sporebound.classic_party import EXTENSION

CT_MISSION = "relais_ct_reference"
RPG_SCENES = ("woods", "crypt")
THREE_HEROES = ("elya", "oren", "mira")


def build_relais_hybride_r53():
    """A reusable 3-hero, 2-combat-mode extension of R41's village slice."""
    content, project = build_relais_du_village()
    mission = content.missions[CT_MISSION]
    # Enable the second ally's *native Content skill* to execute R53 combos.
    next(unit for unit in mission.units if unit.id == "oren").skills.append(
        "lame_claire")
    mission.reward = 9  # Settles once through Campaign.finish on CT victory.

    party = project.extensions[EXTENSION]["data"]
    roster = party["campaigns"]["main"]
    roster["initial"] = list(THREE_HEROES)
    roster["active"] = list(THREE_HEROES)
    roster["max_active"] = 3
    party["orchestration"] = {
        "version": 1, "pause_policy": "freeze_on_encounter",
        "combos": [{
            "id": "lames_du_relais",
            "members": ["elya", "oren"],
            "modes": ["RPG_TURN", "TACTICAL_CT"],
            "skills": {"elya": "lame_claire", "oren": "lame_claire"},
        }],
        "defaults": {"main": {
            "leader": "oren",
            "formation": ["front", "flank_left", "support"],
        }},
    }
    # The R25 authored mission portal *really* starts CT Battle; the return
    # requires victory. An explicit retreat supports a failed attempt, without
    # granting the CT reward or setting the completed mission flag.
    project.scene_routes["links"].extend([
        {"id": "crypt_to_ct", "source": "crypt",
         "destination": CT_MISSION, "spawn": [1, 1],
         "when": {"flag": "r41_crypt", "eq": True}},
        {"id": "ct_victory_to_village", "source": CT_MISSION,
         "destination": "village", "spawn": [1, 1],
         "when": {"completed_mission": CT_MISSION}},
        {"id": "ct_retreat_to_crypt", "source": CT_MISSION,
         "destination": "crypt", "spawn": [1, 1]},
    ])
    project.title = "Le relais hybride — R53"
    project.subtitle = "Trois compagnons, RPG classique et combat tactique CT."
    content.validate()
    project.validate(content)
    return content, project


__all__ = ["build_relais_hybride_r53", "CT_MISSION",
           "RPG_SCENES", "THREE_HEROES"]
