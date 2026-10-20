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
from sporebound.physics_scenes import EXTENSION as PHYSICS_EXTENSION


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


def _collider(ident: str, rect: list[int], *,
              trigger: bool = False, one_way: bool = False, route=None) -> dict:
    row = {"id": ident, "rect": rect, "layer": 1, "mask": 1,
           "trigger": trigger, "one_way": one_way}
    if route is not None:
        row["route"] = route
    return row


def _platform_room(identifier: str, *, ruin: bool = False,
                   citadel: bool = False) -> dict:
    """R32 physics with original simple geometry, fixed 60 Hz stepping.

    The high ledge in the village is too high for one jump (250, gravity 40).
    A real midair double jump can reach it after the feather is collected.
    """
    colliders = [_collider("floor", [0, 4000, 6000, 1000])]
    if identifier == "arrival":
        colliders.extend([
            _collider("waystone", [1800, 3200, 400, 700], trigger=True),
            _collider("ruins_portal", [2400, 3200, 500, 700],
                      trigger=True, route="to_ruins"),
            _collider("upper_ledge", [3400, 2850, 2350, 100], one_way=True),
            _collider("high_portal", [4400, 2070, 600, 650],
                      trigger=True, route="high_gate"),
        ])
    if ruin:
        colliders.extend([
            _collider("feather", [1550, 3200, 400, 700], trigger=True),
            _collider("return_portal", [2400, 3200, 500, 700],
                      trigger=True, route="back_to_village"),
        ])
    scene = {
        "id": identifier, "width": 6000, "height": 5000, "gravity": 40,
        "hero": {"pos": [1000, 3200], "size": [500, 800],
                 "speed": 180, "jump": 250, "max_fall": 800,
                 "coyote": 4},
        "colliders": colliders,
    }
    if citadel:
        scene["boss"] = {
            "id": "r40_warden", "rect": [2850, 3100, 900, 900],
            "attack_rect": [2050, 3150, 1700, 850],
            "hp": 4, "phase_at": 2, "hero_hp": 6,
            "telegraph": [18, 10], "strike": [5, 6],
            "recover": [20, 16],
        }
    return scene


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
        # R40.B.4 removes the former direct ruins->citadel shortcut.
        # The ONLY path into the guardian's chamber now returns to the
        # village, collects the feather, and reaches the physical high gate.
        project.scene_routes["links"] = [
            row for row in project.scene_routes["links"]
            if row["id"] in ("to_ruins", "back_to_village")
        ]
        project.scene_routes["links"].append({
            "id": "high_gate", "source": "arrival",
            "destination": "r40_citadel", "spawn": [1, 1],
            "when": {"flag": "r33_pickup_feather", "eq": True},
        })
        project.extensions[PHYSICS_EXTENSION] = {
            "schema_version": 1,
            "data": {"scenes": {
                "arrival": _platform_room("arrival"),
                "r40_ruins": _platform_room("r40_ruins", ruin=True),
                "r40_citadel": _platform_room("r40_citadel", citadel=True),
            }},
        }
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
