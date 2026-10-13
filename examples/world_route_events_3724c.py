"""Build a playable route-event campaign using the canonical road/story systems.

python -m examples.world_route_events_3724c --output /tmp/road_demo.json
python -m sporebound player --content /tmp/road_demo.json --project /tmp/road_demo.game.json
"""
import argparse
import json
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.storage import write_json
from sporebound.world_map import default_world


def build(output):
    content = Content.load(DEFAULT_CONTENT)
    project = GameProject.default(content)
    world = default_world(content, project.campaigns, theme="kingdom")
    project.world = world
    world["events"] = [{
        "id": "road_caravan", "from": "garden", "to": "escape",
        "scene": "scene_road_caravan",
        "when": {"completed_mission": "garden"},
    }]
    project.story = {
        "scenes": [{
            "id": "scene_road_caravan",
            "title": "La caravane sur la route",
            "speaker": "Marchande",
            "text": ("Une caravane est arretee par des brigands. La marchande "
                     "demande votre aide avant de reprendre la route."),
            "choices": [
                {"id": "escort", "label": "Proteger la caravane.",
                 "effects": [{"kind": "add_flag", "flag": "road_escort", "amount": 1}]},
                {"id": "bribe", "label": "Payer 20 pieces pour degager la route.",
                 "when": {"gold_gte": 20},
                 "effects": [{"kind": "gold", "amount": -20},
                             {"kind": "set_flag", "flag": "road_bribe", "value": True}]},
                {"id": "avoid", "label": "Contourner les brigands.",
                 "effects": [{"kind": "set_flag", "flag": "road_avoided", "value": True}]},
            ],
        }],
    }
    # Escorting the merchants changes the real next tactical battle.
    project.battle_support = [{
        "mission": "escape", "flag": "road_escort",
        "gte": 1, "potion_bonus": 2,
    }]
    project.validate(content)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, content.to_dict())
    manifest = target.with_suffix(".game.json")
    project.save(manifest, content)
    return {"content": str(target), "project": str(manifest),
            "road_events": len(world["events"]),
            "choice_ids": [row["id"] for row in project.story["scenes"][0]["choices"]]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="3.7.24C narrative route events")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
