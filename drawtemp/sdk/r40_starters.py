"""R40.A reference starters, built from one canonical Content/GameProject pair.

These are editable vertical-slice *starting points*, not four certified games.
The default tactical mission stays CT; other capabilities are explicitly opt-in.
No second schema, interpreter, runtime or asset registry is created here.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.procgen_prefabs import demo_library
from drawtemp.sdk.reference import reference_project
from sporebound.exploration import _key
from sporebound.metroidvania import analyze_metroidvania
from sporebound.roguelite import EXTENSION as ROGUELITE_EXTENSION


# Order is meaningful in the Studio's existing project-creation dialog.
STARTER_INFO = {
    "r40-srpg": {
        "genre": "srpg", "title": "Jeanne — La porte de la lisière",
        "scope": "One canonical tactical mission, lever and branching story",
    },
    "r40-adventure": {
        "genre": "action-adventure", "title": "La Gardienne des ruines",
        "scope": "Authored top-down exploration scenes and action mode profiles",
    },
    "r40-metroidvania": {
        "genre": "metroidvania", "title": "Les Jardins suspendus",
        "scope": "Three authored scenes, a gated ability and reachability proof",
    },
    "r40-roguelite": {
        "genre": "roguelite", "title": "Le Labyrinthe des veilleurs",
        "scope": "Versioned seeded rooms and a real GameSession run/meta state",
    },
}
STARTER_KINDS = tuple(STARTER_INFO)


def _stage(title: str, theme: str) -> dict:
    """Small original exploration map; no undisclosed/licensed art."""
    return {
        "title": title, "theme": theme, "width": 6, "height": 5,
        "start": [1, 1], "blocked": [[3, 2]],
        "interactions": [
            {"id": "waystone", "title": "Pierre gravée",
             "text": "Une inscription indique l'ancien passage.",
             "pos": [2, 2], "required": False, "exit": False},
            {"id": "exit", "title": "Continuer l'exploration",
             "text": "Le chemin reste ouvert.",
             "pos": [4, 3], "required": False, "exit": True},
        ],
    }


def _story_scene(identifier: str, title: str) -> dict:
    return {
        "id": identifier, "title": title, "speaker": "Gardienne",
        "text": "Ce sanctuaire a ses propres secrets. Choisis ta route.",
        "choices": [{"id": "continue", "label": "Explorer les environs"}],
    }


def create_starter_pair(kind: str):
    """Construct and validate a detached canonical pair without disk writes.

    Returns a real Content and GameProject, never an alternative gameplay
    representation. All four intentionally reuse the legacy tactical sample:
    CT and old checkpoints cannot be silently converted to action combat.
    """
    if type(kind) is not str or kind not in STARTER_INFO:
        raise ValueError("Unknown R40 reference starter")
    content, project = reference_project()
    project.title = STARTER_INFO[kind]["title"]
    project.subtitle = STARTER_INFO[kind]["scope"]

    if kind in ("r40-adventure", "r40-metroidvania"):
        # The action examples have an original standalone narrative; the
        # historical Jeanne story remains exclusive to the SRPG starter.
        project.story = {
            "entry_scenes": {}, "after_mission": {},
            "scenes": [
                _story_scene("arrival", "Le départ du village"),
                _story_scene("r40_ruins", "La cour des ruines"),
                _story_scene("r40_citadel", "La chambre des gardiens"),
            ],
        }
        project.exploration = {
            "arrival": _stage("Village des lisières", "village"),
            "r40_ruins": _stage("Ruines envahies", "forest"),
            "r40_citadel": _stage("Citadelle oubliée", "stone"),
        }
        # Real GameSession scene routing (not a second game or save schema).
        # Conditions use flags written by Exploration.interact(), and can
        # therefore be checked after save/restore without special scripting.
        project.scene_routes = {
            "version": 1, "start": "arrival",
            "links": [
                {"id": "to_ruins", "source": "arrival",
                 "destination": "r40_ruins", "spawn": [1, 1],
                 "when": {"flag": _key("arrival", "waystone"), "eq": True}},
                {"id": "back_to_village", "source": "r40_ruins",
                 "destination": "arrival", "spawn": [1, 1]},
                {"id": "to_citadel", "source": "r40_ruins",
                 "destination": "r40_citadel", "spawn": [1, 1],
                 "when": {"flag": _key("r40_ruins", "waystone"), "eq": True}},
                {"id": "back_to_ruins", "source": "r40_citadel",
                 "destination": "r40_ruins", "spawn": [1, 1]},
            ],
        }
        # These are narrative waystone routes. The separate R33 ability
        # graph is still a preflight proof, NOT integrated platform physics.
        # The existing Content tactical mission stays GRID_CT/TACTICAL_CT.
        # Only these *exploration* scenes opt into real-time profiles.
        project.game_modes = {
            "version": 1, "default": {"preset": "srpg"},
            "scenes": {
                sid: {"preset": "action"}
                for sid in ("arrival", "r40_ruins", "r40_citadel")
            },
        }

    if kind == "r40-metroidvania":
        graph = {
            "version": 1,
            "rooms": ["arrival", "r40_ruins", "r40_citadel"],
            "start": "arrival", "goal": "r40_citadel",
            "starting_capabilities": [],
            "pickups": [
                {"id": "feather", "room": "r40_ruins",
                 "grants": ["double_jump"]},
            ],
            "links": [
                {"id": "to_ruins", "source": "arrival",
                 "destination": "r40_ruins", "requires": []},
                {"id": "return", "source": "r40_ruins",
                 "destination": "arrival", "requires": []},
                {"id": "high_gate", "source": "arrival",
                 "destination": "r40_citadel", "requires": ["double_jump"]},
            ],
        }
        result = analyze_metroidvania(graph, scene_ids=project.exploration)
        if not (result["complete"] and result["safe"]
                and result["goal_reachable"]):
            raise ValueError("Reference progression failed bounded analysis")
        project.extensions["drawtemp.metroidvania"] = {
            "schema_version": 1, "data": deepcopy(graph),
        }

    if kind == "r40-roguelite":
        project.extensions[ROGUELITE_EXTENSION] = {
            "schema_version": 1,
            "data": {
                "version": 1,
                "recipe": {
                    "seed": 81, "rooms": 10, "branches": 3,
                    "locked_goal": True, "encounter_budget": 7,
                    "loot_budget": 80,
                },
                "library": demo_library(), "biome": "ruins",
                "meta_reward": 7,
            },
        }
    project.validate(content)
    return content, project


def starter_catalog() -> tuple[dict, ...]:
    """Report what is implemented, without pretending to satisfy R40.12."""
    return tuple({
        "id": kind,
        **deepcopy(info),
        "canonical_pair": True,
        "source_prototype": True,
        "player_export_certified": False,
        "human_ux_certified": False,
        "release_8_0_certified": False,
    } for kind, info in STARTER_INFO.items())
