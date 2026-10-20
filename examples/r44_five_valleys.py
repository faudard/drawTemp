"""R44.C 'La route des cinq vallées': an editable, validated headless slice.

Uses one canonical Content/GameProject pair. SceneRouter owns travel,
GameSession owns objects and saves. No new renderer or streaming/runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drawtemp.sdk.reference import reference_project
from sporebound.game_session import GameSession
from sporebound.model import require
from sporebound.storage import write_json
from sporebound.world_graph44 import EXTENSION, WorldGraph

# region ID, display title, exploration theme, atlas biome, projection
VALLEYS = (
    ("valley", "Le hameau du premier pont", "village", "village", "top_down"),
    ("grove", "Les vergers de la brume", "forest", "forest", "top_down"),
    ("marsh", "La lagune des roseaux", "fields", "swamp", "top_down"),
    ("ridge", "La crête des veilleurs", "stone", "mountain", "isometric"),
    ("sanctuary", "Le sanctuaire des cinq sources", "stone", "stone", "isometric"),
)


def relic_flag(scene_id):
    return "world44_" + scene_id + "_relic"


def five_valleys_project():
    """Return an original five-scene project without changing legacy Jeanne."""
    content, project = reference_project()
    project.title = "R44 — La route des cinq vallées"
    project.subtitle = "Aventure narrative à cinq régions"
    project.story = {
        "entry_scenes": {}, "after_mission": {},
        "scenes": [
            {"id": sid, "title": title, "speaker": "",
             "text": "Une région à découvrir. Le souvenir ouvre le passage suivant.",
             "choices": [{"id": "explore", "label": "Explorer la vallée"}]}
            for sid, title, _, _, _ in VALLEYS],
    }
    project.exploration = {
        sid: {
            "title": title, "theme": terrain, "width": 5, "height": 5,
            "start": [1, 1], "blocked": [],
            "interactions": [
                {"id": "relic", "title": "Souvenir", "text": "Le passage suivant est désormais ouvert.",
                 "pos": [2, 1], "required": False, "exit": False},
                {"id": "exit", "title": "Chemin", "text": "Vers les autres vallées.",
                 "pos": [3, 3], "required": False, "exit": True},
            ],
        } for sid, title, terrain, _, _ in VALLEYS
    }
    ids = [row[0] for row in VALLEYS]
    routes, portals = [], []
    for before, after in zip(ids, ids[1:]):
        forward = "to_" + after
        backward = "back_" + before
        routes.append({"id": forward, "source": before, "destination": after,
                       "spawn": [1, 1],
                       "when": {"flag": relic_flag(before), "eq": True}})
        routes.append({"id": backward, "source": after, "destination": before,
                       "spawn": [1, 1]})
        portals.extend([
            {"route": forward, "source": [3, 3], "travel_cost": 2},
            {"route": backward, "source": [3, 3], "travel_cost": 1},
        ])
    project.scene_routes = {"version": 1, "start": ids[0], "links": routes}
    project.game_modes = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {sid: {"preset": "narrative"} for sid in ids},
    }
    project.extensions[EXTENSION] = {
        "schema_version": 1,
        "data": {
            "version": 1,
            "regions": [
                {"id": sid, "title": title, "biome": biome,
                 "projection": projection, "palette": [],
                 "scenes": [{"id": sid, "origin": [12 + i * 18, 12 + (i % 2) * 15]}]}
                for i, (sid, title, _, biome, projection) in enumerate(VALLEYS)
            ],
            "portals": portals,
            "objects": [
                {"id": "relic", "scene": sid, "kind": "chest", "flag": relic_flag(sid)}
                for sid in ids
            ],
        },
    }
    project.validate(content)
    return content, project


def smoke_five_valleys(*, seed=44):
    """Run the whole five-region journey through actual GameSession APIs."""
    content, project = five_valleys_project()
    session = GameSession.new(content, project, "main", seed=seed)
    graph = WorldGraph(project.extensions[EXTENSION]["data"], content, project)
    visited = []
    ids = [row[0] for row in VALLEYS]
    for idx, sid in enumerate(ids):
        require(session.route_scene == sid, "R44: wrong scene in five-region trace")
        visited.append(sid)
        require(graph.object_states(session.progress, sid)["relic"]["active"] is False,
                "R44: unexplored relic unexpectedly active")
        result = session.route_world_interact("relic")
        require(result["already_activated"] is False, "R44: first relic is not new")
        require(session.route_world_interact("relic")["already_activated"] is True,
                "R44: second activation must be idempotent")
        if idx < len(ids) - 1:
            require(graph.shortest_path(sid, ids[idx+1], session.progress)["routes"]
                    == ["to_" + ids[idx+1]], "R44: canonical next route missing")
            # Walk to the authored exit instead of teleporting from spawn.
            session.route_move(1, 0)
            session.route_move(1, 0)
            session.route_move(0, 1)
            session.route_world_transition("to_" + ids[idx+1])
    # Explicit return to prior region and observe the original cache state.
    session.route_move(1, 0)
    session.route_move(1, 0)
    session.route_move(0, 1)
    session.route_world_transition("back_ridge")
    require(session.route_scene == "ridge"
            and graph.object_states(session.progress, "ridge")["relic"]["active"],
            "R44: returning erased a persistent object")
    return session, {"visited": visited, "route_history": list(session.route_history),
                     "world_flags": {sid: session.progress.story_flags[relic_flag(sid)]
                                     for sid in ids}}


def write_five_valleys(directory):
    """Emit the canonical Content + GameProject pair; refuse overwrite."""
    content, project = five_valleys_project()
    folder = Path(directory)
    require(not folder.exists(), "R44: destination already exists")
    folder.mkdir(parents=True)
    source = folder / "five_valleys.json"
    manifest = folder / "five_valleys.game.json"
    write_json(source, content.to_dict())
    write_json(manifest, project.to_dict())
    return source, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="R44.C — five valleys reference project")
    parser.add_argument("--output", type=Path,
                        help="Create canonical Content/Project JSON files in a new folder")
    parser.add_argument("--smoke", action="store_true",
                        help="Run the five-scene traversal in the real headless GameSession")
    args = parser.parse_args(argv)
    if not args.output and not args.smoke:
        parser.error("Specify --output and/or --smoke")
    if args.output:
        source, manifest = write_five_valleys(args.output)
        from drawtemp.export.r15 import preflight
        report = preflight(source, require_licenses=True)
        print(json.dumps({"content": str(source), "project": str(manifest),
                          "preflight": report}, ensure_ascii=False, indent=2))
        if not report["passed"]:
            return 1
    if args.smoke:
        _, result = smoke_five_valleys()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
