"""R44.D Player integration: R1 facade, Player slots and GUI-facing projection."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from examples.r44_five_valleys import VALLEYS, five_valleys_project, relic_flag


class WorldAtlasPlayerTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = five_valleys_project()

    def test_read_only_projection_and_revision_guard(self):
        sim = Simulation.new(self.content, self.project, "main", seed=44)
        snapshot = sim.snapshot()
        world = thaw(sim.world_atlas_state())
        self.assertTrue(world["enabled"])
        self.assertEqual(world["scene"], "valley")
        self.assertEqual(world["region_title"], "Le hameau du premier pont")
        self.assertEqual(world["object_ids"], ["relic"])
        self.assertFalse(next(x for x in world["portals"] if x["id"] == "to_grove")["unlocked"])
        self.assertEqual(sim.snapshot(), snapshot)
        with self.assertRaises(SimulationError):
            sim.world_transition("to_grove")
        self.assertEqual(sim.snapshot(), snapshot)
        sim.world_interact("relic", expected_revision=snapshot.revision)
        self.assertTrue(next(x for x in thaw(sim.world_atlas_state())["portals"]
                             if x["id"] == "to_grove")["unlocked"])
        with self.assertRaises(SimulationError) as stale:
            sim.world_transition("to_grove", expected_revision=snapshot.revision)
        self.assertEqual(stale.exception.code, "stale_revision")
        self.assertEqual(thaw(sim.world_atlas_state())["scene"], "valley")
        self.assertFalse(next(x for x in thaw(sim.world_atlas_state())["portals"]
                              if x["id"] == "to_grove")["in_reach"])
        sim.explore_move(1, 0)
        sim.explore_move(1, 0)
        sim.explore_move(0, 1)
        sim.world_transition("to_grove", expected_revision=sim.snapshot().revision)
        self.assertEqual(thaw(sim.world_atlas_state())["scene"], "grove")
        self.assertEqual(sim.snapshot().mode, "campaign")

    def test_atlas_exit_distance_is_checked_by_engine(self):
        sim = Simulation.new(self.content, self.project, "main", seed=44)
        sim.world_interact("relic")
        sim.explore_move(0, 1)
        sim.explore_move(0, 1)
        before = sim.recording()
        with self.assertRaises(SimulationError) as error:
            sim.world_transition("to_grove")
        self.assertEqual(error.exception.code, "invalid_action")
        self.assertEqual(sim.recording(), before)
        self.assertFalse(next(x for x in thaw(sim.world_atlas_state())["portals"]
                              if x["id"] == "to_grove")["in_reach"])

    def test_qt_player_controller_completes_and_recovers_all_five(self):
        with TemporaryDirectory() as tmp:
            controller = PlayerController(self.content, self.project, "main",
                                          Path(tmp), seed=44)
            state = controller.new_game()
            self.assertEqual(state["screen"], "exploration")
            self.assertTrue(state["world_atlas"]["enabled"])
            ids = [v[0] for v in VALLEYS]
            for idx, sid in enumerate(ids):
                self.assertEqual(controller.state()["world_atlas"]["scene"], sid)
                if idx > 0:
                    self.assertFalse(controller.state()["world_atlas"]["objects"][0]["active"])
                # Main.qml uses this command for r44Object-relic.
                controller.world_interact("relic")
                self.assertTrue(controller.state()["world_atlas"]["objects"][0]["active"])
                if idx < 4:
                    route = "to_" + ids[idx + 1]
                    row = next(x for x in controller.state()["world_atlas"]["portals"]
                               if x["id"] == route)
                    self.assertTrue(row["unlocked"])
                    controller.explore_move(1, 0)
                    controller.explore_move(1, 0)
                    controller.explore_move(0, 1)
                    self.assertTrue(next(x for x in controller.state()["world_atlas"]["portals"]
                                         if x["id"] == route)["in_reach"])
                    controller.world_transition(route)
                    if idx == 1:  # Real Player slot, not direct GameSession disk writing.
                        controller.save(1)
                        saved = controller.session.recording()
                        controller.title()
                        controller.load(1)
                        self.assertEqual(controller.session.recording(), saved)
                        self.assertEqual(controller.state()["world_atlas"]["scene"], "marsh")
            self.assertEqual(controller.state()["world_atlas"]["scene"], "sanctuary")
            controller.explore_move(1, 0)
            controller.explore_move(1, 0)
            controller.explore_move(0, 1)
            controller.world_transition("back_ridge")
            self.assertTrue(controller.state()["world_atlas"]["objects"][0]["active"])
            self.assertTrue(all(
                controller.session.recording()["progress"]["story_flags"][relic_flag(sid)]
                for sid in ids))

    def test_player_does_not_revalidate_graph_on_every_projection(self):
        sim = Simulation.new(self.content, self.project, "main", seed=44)
        # No recompilation/revalidation on projection, input or a route.
        # Canonical GameProject.validate has already done this at session start.
        with patch("sporebound.world_graph44.validate_world_graph",
                   side_effect=AssertionError("unexpected R44 revalidation")):
            before = sim.recording()
            self.assertEqual(thaw(sim.world_atlas_state())["scene"], "valley")
            self.assertEqual(sim.recording(), before)
            sim.world_interact("relic")
            sim.explore_move(1, 0)
            sim.explore_move(1, 0)
            sim.explore_move(0, 1)
            sim.world_transition("to_grove")
            self.assertEqual(thaw(sim.world_atlas_state())["scene"], "grove")

    def test_world_reachability_is_conditional_and_never_mutates_saves(self):
        sim = Simulation.new(self.content, self.project, "main", seed=44)
        original = sim.recording()
        initial = thaw(sim.world_atlas_state())
        self.assertEqual(initial["reachability"]["regions"], ["valley"])
        self.assertEqual(initial["reachability"]["blocked_routes"], ["to_grove"])
        self.assertEqual(initial["visited_regions"], ["valley"])
        self.assertEqual(initial["region_total"], 5)
        self.assertEqual(sim.recording(), original)
        sim.world_interact("relic")
        open_route = thaw(sim.world_atlas_state())
        self.assertEqual(open_route["reachability"]["regions"], ["grove", "valley"])
        self.assertEqual(open_route["reachability"]["blocked_routes"], ["to_marsh"])
        self.assertEqual(open_route["visited_regions"], ["valley"])
        sim.explore_move(1, 0)
        sim.explore_move(1, 0)
        sim.explore_move(0, 1)
        sim.world_transition("to_grove")
        visited = thaw(sim.world_atlas_state())
        self.assertEqual(visited["visited_regions"], ["grove", "valley"])
        self.assertEqual(visited["reachability"]["blocked_routes"], ["to_marsh"])

    def test_old_project_has_no_world_atlas(self):
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
        with TemporaryDirectory() as tmp:
            player = PlayerController(content, project, "main", Path(tmp))
            player.new_game()
            self.assertFalse(player.state()["world_atlas"]["enabled"])
            self.assertEqual(player.session.snapshot().revision, 0)


if __name__ == "__main__":
    unittest.main()
