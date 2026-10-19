"""R32 authored opt-in preview over canonical Jeanne Content/GameProject."""
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.physics_scenes import EXTENSION


def collider(name, rect, *, trigger=False, **extras):
    return {"id": name, "rect": rect, "layer": 1, "mask": 1,
            "trigger": trigger, "one_way": False, **extras}


def platform_demo_project():
    content, project = reference_project()
    project.story["entry_scenes"] = {}
    project.exploration["arrival"] = {
        "title": "R32 village", "theme": "village", "width": 12, "height": 6,
        "start": [1, 4], "blocked": [],
        "interactions": [{"id": "exit", "title": "Portail", "text": "Combat tactique",
                          "pos": [5, 4], "required": False, "exit": True}],
    }
    hero = next(u for u in content.missions[MISSION].units if u.team == "player")
    project.game_modes = {"version": 1, "default": {"preset": "srpg"},
                          "scenes": {"arrival": {"preset": "action"},
                                     MISSION: {"preset": "srpg"}}}
    project.scene_routes = {
        "version": 1, "start": "arrival",
        "links": [
            {"id": "to_arena", "source": "arrival", "destination": MISSION,
             "spawn": list(hero.pos)},
            {"id": "retreat", "source": MISSION, "destination": "arrival",
             "spawn": [1, 4]},
        ],
    }
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": {"scenes": {"arrival": {
            "id": "arrival", "width": 12000, "height": 6000, "gravity": 40,
            "hero": {"pos": [1000, 4200], "size": [500, 800],
                     "speed": 240, "jump": 520, "max_fall": 900, "coyote": 4},
            "colliders": [
                collider("floor", [0, 5000, 12000, 1000]),
                collider("gate", [3200, 3500, 100, 1500]),
                collider("lever", [1500, 4200, 500, 700],
                         trigger=True, opens="gate"),
                collider("arena_portal", [4700, 4200, 600, 700],
                         trigger=True, route="to_arena"),
                collider("moving_platform", [6500, 3800, 1400, 100],
                         one_way=True, velocity=65, travel=[6500, 8500]),
            ],
        }}}}
    project.validate(content)
    return content, project
