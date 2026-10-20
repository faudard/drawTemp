"""R41.C — original, asset-free classic RPG vertical-slice starter.

Generate two canonical objects (Content + GameProject), no sidecar saves, Python
rules or copied Jeanne story. The fallback CT mission is pinned to srpg, while
all three explorable regions use the R25 classic_rpg profile.
"""
from __future__ import annotations

from drawtemp.core import Content, GameProject
from sporebound.classic_party import EXTENSION


def _scene(scene_id, label, text):
    return {"id": scene_id, "title": label, "speaker": "Narrateur",
            "text": text,
            "choices": [{"id": "continue", "label": "Continuer"}]}


def _stage(label, theme):
    return {"title": label, "theme": theme, "width": 6, "height": 6,
            "start": [1, 1], "blocked": [],
            "interactions": [{
                "id": "exit", "title": "Sentier", "text": "Voyager",
                "pos": [4, 2], "required": False, "exit": True,
            }]}


def _hero(uid, name, pos, *, hp, attack, magic=5, speed=12, skills=None):
    return {"id": uid, "name": name, "team": "player", "pos": pos,
            "max_hp": hp, "hp": hp, "max_mp": 18, "mp": 18,
            "attack": attack, "magic": magic, "speed": speed,
            "weapon_power": 2, "skills": list(skills or []),
            "reaction": "none"}


def _enemy(uid, name, pos, *, hp, attack, speed):
    return {"id": uid, "name": name, "team": "enemy", "pos": pos,
            "max_hp": hp, "hp": hp, "attack": attack,
            "speed": speed, "weapon_power": 1,
            "skills": [], "reaction": "none"}


def build_relais_du_village():
    """Create an original 3-hero / 2-encounter playable R41 slice.

    This is a *template*; no data is written until the existing Creator's
    two-file atomic staging and preflight validate the complete authored pair.
    """
    data = {
        "version": 1,
        "skills": [
            {"id": "lame_claire", "name": "Lame claire",
             "cost": 0, "range": 1, "target": "enemy",
             "effects": [{"kind": "damage", "power": 4}]},
            {"id": "soin_du_relais", "name": "Soin du relais",
             "cost": 3, "range": 3, "target": "ally",
             "effects": [{"kind": "heal", "power": 14}]},
        ],
        "missions": [{
            # Historical tactical schema requires a mission; R41 gameplay
            # never changes this CT mission's engine or makes it RPG_TURN.
            "id": "relais_ct_reference",
            "name": "Scène tactique optionnelle — référence du moteur CT",
            "board": {"width": 8, "height": 6, "tiles": []},
            "units": [
                _hero("elya", "Elya, garde du relais", [1, 1],
                      hp=74, attack=12, speed=16, skills=["lame_claire"]),
                _hero("oren", "Oren, éclaireur", [1, 2],
                      hp=68, attack=11, speed=14),
                _hero("mira", "Mira, soigneuse", [2, 1],
                      hp=58, attack=6, magic=10, speed=13,
                      skills=["soin_du_relais"]),
                _enemy("loup", "Loup des bois", [6, 1],
                       hp=24, attack=4, speed=8),
                _enemy("gardien", "Gardien des ruines", [6, 3],
                       hp=48, attack=6, speed=10),
            ],
            "objective": "eliminate", "reward": 0,
            "next_missions": [], "triggers": [],
        }],
        "jobs": {}, "equipment": {},
        "tactic_unlocks": [],
    }
    content = Content.from_dict(data)
    project = GameProject.default(content)
    project.title = "Le relais du village"
    project.subtitle = "Trois compagnons, deux rencontres et un retour au village."
    project.campaigns[0].update(
        name="La lumière du relais",
        description="Recrutez Oren et Mira. Libérez le bois puis les ruines.")
    project.story = {
        "scenes": [
            _scene("village", "Le relais", "Au relais, Elya attend ses compagnons."),
            _scene("woods", "Le bois des Brumes",
                   "Des traces de loups coupent le sentier des marchands."),
            _scene("crypt", "La crypte des Veilleurs",
                   "Un gardien solitaire veille sur l'ancienne lanterne."),
        ],
        "entry_scenes": {}, "after_mission": {},
    }
    project.exploration = {
        "village": _stage("Village du relais", "village"),
        "woods": _stage("Bois des Brumes", "forest"),
        "crypt": _stage("Crypte des Veilleurs", "stone"),
    }
    project.game_modes = {
        "version": 1, "default": {"preset": "classic_rpg"},
        "scenes": {"relais_ct_reference": {"preset": "srpg"}},
    }
    project.scene_routes = {
        "version": 1, "start": "village",
        "links": [
            {"id": "village_to_woods", "source": "village",
             "destination": "woods", "spawn": [1, 1]},
            {"id": "woods_to_village", "source": "woods",
             "destination": "village", "spawn": [1, 1]},
            {"id": "woods_to_crypt", "source": "woods",
             "destination": "crypt", "spawn": [1, 1],
             "when": {"flag": "r41_woods", "eq": True}},
            {"id": "crypt_to_woods", "source": "crypt",
             "destination": "woods", "spawn": [1, 1]},
            {"id": "crypt_to_village", "source": "crypt",
             "destination": "village", "spawn": [1, 1],
             "when": {"flag": "r41_crypt", "eq": True}},
        ],
    }
    project.extensions[EXTENSION] = {
        "schema_version": 1,
        "data": {
            "version": 1,
            "campaigns": {"main": {
                "recruitable": ["elya", "oren", "mira"],
                "initial": ["elya"], "active": ["elya"], "max_active": 3,
            }},
            "encounters": {
                "woods": {"scene": "woods", "enemies": ["loup"],
                          "reward_gold": 12},
                "crypt": {"scene": "crypt", "enemies": ["gardien"],
                          "reward_gold": 24},
            },
            "quest": {
                "title": "Rallumer la lanterne du relais",
                "encounters": ["woods", "crypt"],
                "return_scene": "village",
                "reward_gold": 25, "reward_item": "potion",
                "reward_quantity": 2,
            },
        },
    }
    project.validate(content)
    return content, project


__all__ = ["build_relais_du_village"]
