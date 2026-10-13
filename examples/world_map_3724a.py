"""Produce a playable World Map demo using the project's canonical Content.

Usage:
    python -m examples.world_map_3724a --output /tmp/world_demo.json
    python -m sporebound player --content /tmp/world_demo.json \
        --project /tmp/world_demo.game.json
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
    regions = ("Valcroix", "Forêt du Nord", "Campagne", "Fortifications")
    for index, node in enumerate(world["nodes"]):
        node["region"] = regions[min(index // 3, len(regions) - 1)]
    project.world = world
    project.validate(content)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, content.to_dict())
    project_path = target.with_suffix(".game.json")
    project.save(project_path, content)
    return {
        "content": str(target),
        "project": str(project_path),
        "missions": len(content.missions),
        "world_locations": len(world["nodes"]),
        "routes": sum(len(m.next_missions) for m in content.missions.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build 3.7.24A World Map demo")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
