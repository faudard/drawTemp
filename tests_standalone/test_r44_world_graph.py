"""R44.A: headless WorldGraph contract, paths, flags and migration gates."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError
from sporebound.world_graph44 import EXTENSION, WorldGraph
from tests_standalone.test_r25_scene_router import scene_fixture


def authored_world():
    content, project = scene_fixture()
    hero = next(u for u in content.missions[MISSION].units if u.team == "player")
    project.assets = {"version": 1, "entries": [
        {"id": "forest_tiles", "kind": "sprite", "path": "forest.png"}],
        "bindings": {}}
    graph = {"version": 1, "regions": [
        {"id": "lowlands", "title": "Les basses terres", "biome": "village",
         "projection": "top_down", "palette": ["forest_tiles"],
         "scenes": [{"id": "arrival", "origin": [8, 12]}]},
        {"id": "arena", "title": "Les remparts", "biome": "stone",
         "projection": "isometric", "palette": [],
         "scenes": [{"id": MISSION, "origin": [30, 40]}]},
    ], "portals": [
        {"route": "to_arena", "source": [1, 2], "travel_cost": 7},
        {"route": "retreat", "source": list(hero.pos), "travel_cost": 3},
        {"route": "victory_return", "source": list(hero.pos), "travel_cost": 2},
    ], "objects": [
        {"id": "chest", "scene": "arrival", "kind": "chest",
         "flag": "world44_chest_open"},
        {"id": "door", "scene": "arrival", "kind": "door",
         "flag": "world44_gate_open"},
    ]}
    project.extensions[EXTENSION] = {"schema_version": 1, "data": graph}
    project.validate(content)
    return content, project


class WorldGraph44Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = authored_world()
        self.graph = WorldGraph(self.project.extensions[EXTENSION]["data"],
                                self.content, self.project)

    def test_roundtrip_keeps_canonical_routes_and_legacy_omission(self):
        manifest = self.project.to_dict()
        self.assertEqual(GameProject.from_dict(manifest, self.content).to_dict(),
                         manifest)
        self.assertEqual(self.graph.metrics()["regions"], 2)
        self.assertEqual(self.graph.metrics()["portals"], 3)
        content, old = reference_project()
        self.assertNotIn(EXTENSION, old.to_dict().get("extensions", {}))
        old_session = GameSession.new(content, old, "main")
        self.assertNotIn(EXTENSION, old_session.project.extensions)

    def test_conditions_shortest_path_and_returns(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        self.assertIsNone(self.graph.shortest_path("arrival", MISSION,
                                                   session.progress))
        with self.assertRaises(RuleError):
            self.graph.inspect_portal("arrival", "to_arena", session.progress)
        session.progress.story_flags["portal_open"] = True
        path = self.graph.shortest_path("arrival", MISSION, session.progress)
        self.assertEqual(path, {"routes": ["to_arena"], "travel_cost": 7})
        before = session.recording()
        inspected = self.graph.inspect_portal("arrival", "to_arena",
                                              session.progress)
        self.assertEqual(inspected["route"]["destination"], MISSION)
        self.assertEqual(session.recording(), before)
        self.assertEqual(self.graph.shortest_path(MISSION, "arrival",
                                                  session.progress)["travel_cost"], 3)
        # Travel still occurs only through the canonical GameSession.
        self.assertEqual(session.route_transition("to_arena")["scene"], MISSION)

    def test_coordinates_are_reversible_and_pick_rejects_half_cells(self):
        self.assertEqual(self.graph.atlas_position("arrival", [1, 2]), [9, 14])
        self.assertEqual(self.graph.scene_cell("arrival", [9, 14]), [1, 2])
        hero = next(u for u in self.content.missions[MISSION].units
                    if u.team == "player")
        p = list(hero.pos)
        self.assertEqual(self.graph.scene_cell(
            MISSION, self.graph.atlas_position(MISSION, p)), p)
        with self.assertRaises(RuleError):
            self.graph.scene_cell(MISSION, [31, 40])
        with self.assertRaises(RuleError):
            self.graph.atlas_position("arrival", [999, 0])

    def test_world_objects_reuse_campaign_flags_across_save_load(self):
        session = GameSession.new(self.content, self.project, "main", seed=5)
        self.assertFalse(self.graph.object_states(session.progress, "arrival")["chest"]["active"])
        session.progress.story_flags["world44_chest_open"] = True
        session.progress.story_flags["portal_open"] = True
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            loaded = GameSession.load(path, self.content, self.project)
            self.assertEqual(loaded.recording(), session.recording())
            self.assertTrue(self.graph.object_states(loaded.progress, "arrival")["chest"]["active"])
            self.assertFalse(self.graph.object_states(loaded.progress, "arrival")["door"]["active"])
        session.progress.story_flags["world44_chest_open"] = "yes"
        with self.assertRaises(RuleError):
            self.graph.object_states(session.progress, "arrival")

    def test_fail_closed_incorrect_authored_graph(self):
        invalid = [
            lambda g: g.update(version=2),
            lambda g: g["regions"][0].update(projection="3d"),
            lambda g: g["regions"][0].update(biome="unknown"),
            lambda g: g["regions"][0].update(palette=["unlicensed"]),
            lambda g: g["regions"][1]["scenes"][0].update(id="arrival"),
            lambda g: g["regions"][1]["scenes"][0].update(id="missing"),
            lambda g: g["regions"][0]["scenes"][0].update(origin=[True, 0]),
            lambda g: g["portals"][0].update(route="missing"),
            lambda g: g["portals"][0].update(source=[2, 1]),
            lambda g: g["portals"][0].update(travel_cost=True),
            lambda g: g["portals"].append(deepcopy(g["portals"][0])),
            lambda g: g["portals"].clear(),
            lambda g: g["objects"][1].update(flag="world44_chest_open"),
            lambda g: g["objects"][0].update(kind="code"),
            lambda g: g["objects"][0].update(flag="ex_external"),
            lambda g: g.update(untrusted="payload"),
        ]
        for change in invalid:
            project = deepcopy(self.project)
            change(project.extensions[EXTENSION]["data"])
            with self.subTest(change=change):
                with self.assertRaises(RuleError):
                    project.validate(self.content)
        project = deepcopy(self.project)
        project.extensions[EXTENSION]["schema_version"] = 2
        with self.assertRaises(RuleError):
            project.validate(self.content)

    def test_graph_snapshot_never_mutates_authored_data(self):
        original = deepcopy(self.project.extensions[EXTENSION]["data"])
        self.graph.raw["regions"][0]["title"] = "detached"
        self.assertEqual(self.project.extensions[EXTENSION]["data"], original)
        session = GameSession.new(self.content, self.project, "main")
        with self.assertRaises(RuleError):
            self.graph.inspect_portal("elsewhere", "to_arena", session.progress)


if __name__ == "__main__":
    unittest.main()
