"""R20.A — static production-contract audit for the existing Jeanne Act I pack.

This checks authored Content/GameProject data, not tactical wins, Qt, replay,
user experience or export certification. No extra project schema is introduced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.game_project import GameProject
from sporebound.model import Content

ROOT = Path(__file__).resolve().parents[1]
CONTENT_PATH = ROOT / "sporebound/content/jeanne.json"
PROJECT_PATH = ROOT / "sporebound/content/jeanne.game.json"

# Explicit acceptance expectations, NOT a second runtime mission graph.
AFTER_MISSION = {
    "p0_01_lame": "sc_p0_apres_lecon",
    "p0_02_incendie": "sc_p0_cendres",
    "p0_03a_secours": "sc_p0_apres_branche",
    "p0_03b_poursuite": "sc_p0_apres_branche",
    "p0_04_fuite": "sc_p0_au_revoir",
    "a1_01_route": "sc_a1_pont",
    "a1_02_pont": "sc_a1_hospice",
    "a1_03_hospice": "sc_a1_dilemme",
    "a1_04a_archives": "sc_a1_debrief",
    "a1_04b_otages": "sc_a1_debrief",
    "a1_05_vaucouleurs": "sc_a1_fin",
}
BRANCHES = {
    "sc_p0_cendres": {
        "secourir": ("prologue_path", "secours", "p0_03a_secours"),
        "poursuivre": ("prologue_path", "poursuite", "p0_03b_poursuite"),
    },
    "sc_a1_dilemme": {
        "prendre_archives": ("acte1_choix", "archives", "a1_04a_archives"),
        "liberer_otages": ("acte1_choix", "otages", "a1_04b_otages"),
    },
}
RECRUITS = {
    "engager_etienne": ("etienne", "gambison_ecuyer"),
    "engager_agnes": ("agnes", "baton_hospice"),
}
ENDINGS = {
    "preuve_officielle": ("archives", "archives"),
    "parole_otages": ("otages", "temoins"),
    "appel_de_jeanne": (None, "foi"),
}


def audit_pack(content, project):
    """Return violations of the authored R20.A contract; never mutate inputs."""
    errors = []
    def check(ok, description):
        if not ok:
            errors.append(description)

    try:
        project.validate(content)
    except Exception as exc:
        return {"scope": "authoring-only", "ok": False,
                "errors": ["canonical validation: " + str(exc)]}

    campaign = project.campaign("jeanne")
    check(campaign is not None and campaign["start_mission"] == "p0_01_lame",
          "Jeanne campaign must start with the playable sword lesson")
    story = project.story
    check(story.get("entry_scenes", {}).get("jeanne") == "sc_p0_champs",
          "Prologue must start in Domremy exploration")

    after = story.get("after_mission", {})
    for mission, scene in AFTER_MISSION.items():
        check(mission in content.missions, "Missing canonical mission " + mission)
        check(after.get(mission) == scene,
              "Incorrect after_mission link for " + mission)

    scenes = {scene["id"]: scene for scene in story.get("scenes", [])}
    def choices(scene_id):
        if scene_id not in scenes:
            errors.append("Missing scene " + scene_id)
            return {}
        return {choice["id"]: choice for choice in scenes[scene_id]["choices"]}

    for scene_id, expected_choices in BRANCHES.items():
        actual = choices(scene_id)
        for choice_id, (flag, value, destination) in expected_choices.items():
            choice = actual.get(choice_id, {})
            effects = choice.get("effects", [])
            check({"kind": "set_flag", "flag": flag, "value": value} in effects,
                  "Missing persistent decision " + scene_id + "/" + choice_id)
            check({"kind": "unlock_mission", "mission": destination} in effects,
                  "Branch does not unlock expected mission " + destination)

    for choice_id, (hero, item) in RECRUITS.items():
        choice = choices("sc_a1_camp").get(choice_id, {})
        effects = choice.get("effects", [])
        check({"kind": "recruit_hero", "hero": hero} in effects,
              "Recruitment lost for " + hero)
        check({"kind": "grant_item", "item": item, "quantity": 1} in effects,
              "Recruit equipment grant lost for " + hero)
        check({"kind": "equip_hero", "hero": hero, "item": item} in effects,
              "Recruit equipment assignment lost for " + hero)
        check({"kind": "unlock_mission", "mission": "a1_01_route"} in effects,
              "Recruit choice must open the first Act I mission")

    for scene_id, choice_id, destination in (
        ("sc_p0_apres_lecon", "courir", "p0_02_incendie"),
        ("sc_p0_apres_branche", "partir", "p0_04_fuite"),
        ("sc_a1_pont", "tenir_passage", "a1_02_pont"),
        ("sc_a1_pont", "contourner", "a1_02_pont"),
        ("sc_a1_hospice", "ravitailler", "a1_03_hospice"),
        ("sc_a1_hospice", "proteger_dossiers", "a1_03_hospice"),
        ("sc_a1_debrief", "avancer_vaucouleurs", "a1_05_vaucouleurs"),
    ):
        effects = choices(scene_id).get(choice_id, {}).get("effects", [])
        check({"kind": "unlock_mission", "mission": destination} in effects,
              "Missing continuation " + scene_id + "/" + choice_id)

    finish = choices("sc_a1_fin")
    for choice_id, (route, support) in ENDINGS.items():
        choice = finish.get(choice_id, {})
        if route is not None:
            check(choice.get("when") == {"flag": "acte1_choix", "eq": route},
                  "Ending must respect the authored branch: " + choice_id)
        else:
            check("when" not in choice, "Fallback ending must remain available")
        effects = choice.get("effects", [])
        for effect in (
            {"kind": "set_flag", "flag": "acte1_complete", "value": True},
            {"kind": "set_flag", "flag": "acte2_route_ouverte", "value": True},
            {"kind": "set_flag", "flag": "acte2_appui", "value": support},
        ):
            check(effect in effects, "Missing handoff effect for " + choice_id)

    # Three distinct objectives and alternative branch outcomes are preserved
    # in content; this is only an authoring assertion, NOT playtest evidence.
    check(len(set(AFTER_MISSION) & set(content.missions)) == len(AFTER_MISSION),
          "The scripted Act I chain has missing tactical missions")
    return {"scope": "authoring-only", "ok": not errors,
            "missions": len(AFTER_MISSION), "scenes": len(scenes),
            "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, default=CONTENT_PATH)
    parser.add_argument("--project", type=Path, default=PROJECT_PATH)
    args = parser.parse_args(argv)
    try:
        content = Content.load(args.content)
        project = GameProject.load(args.project, content)
        result = audit_pack(content, project)
    except Exception as exc:
        result = {"scope": "authoring-only", "ok": False,
                  "errors": ["Cannot load validated source pair: " + str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
