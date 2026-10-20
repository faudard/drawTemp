"""R44.C — five regional journeys through canonical GameSession."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from drawtemp.export.r15 import preflight
from examples.r44_five_valleys import (
    VALLEYS, five_valleys_project, relic_flag, smoke_five_valleys,
    write_five_valleys,
)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.world_graph44 import EXTENSION, WorldGraph


class FiveValleys44Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = five_valleys_project()

    def test_world_has_five_regions_and_canonical_connections(self):
        document = self.project.extensions[EXTENSION]["data"]
        self.assertEqual(len(document["regions"]), 5)
        self.assertEqual(len(document["objects"]), 5)
        self.assertEqual(len(document["portals"]), 8)
        self.assertEqual(GameProject.from_dict(
            json.loads(json.dumps(self.project.to_dict())), self.content).to_dict(),
                         self.project.to_dict())

    def test_locked_gate_is_atomic_then_unlocked_by_real_interaction(self):
        session = GameSession.new(self.content, self.project, "main", seed=44)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_transition("to_grove")
        self.assertEqual(session.recording(), before)
        result = session.route_world_interact("relic")
        self.assertFalse(result["already_activated"])
        self.assertTrue(session.progress.story_flags[relic_flag("valley")])
        saved = session.recording()
        self.assertTrue(session.route_world_interact("relic")["already_activated"])
        self.assertEqual(session.recording(), saved)
        # R44 travel is spatially gated; direct R25 travel still exists for
        # compatibility but the R44 Player must use the hotspot-aware API.
        with self.assertRaises(RuleError):
            session.route_world_transition("to_grove")
        session.route_move(1, 0)
        session.route_move(1, 0)
        session.route_move(0, 1)
        self.assertEqual(session.route_world_transition("to_grove")["scene"], "grove")
        self.assertTrue(session.progress.story_flags[relic_flag("valley")])

    def test_proximity_and_invalid_object_fail_without_changes(self):
        session = GameSession.new(self.content, self.project, "main")
        session.route_move(0, 1)
        session.route_move(0, 1)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_world_interact("relic")
        with self.assertRaises(RuleError):
            session.route_world_interact("nonexistent")
        self.assertEqual(session.recording(), before)

    def test_complete_five_valleys_and_return_after_save(self):
        session, trace = smoke_five_valleys()
        self.assertEqual(trace["visited"], [row[0] for row in VALLEYS])
        self.assertEqual(session.route_scene, "ridge")
        self.assertEqual(len(trace["route_history"]), 5)
        self.assertTrue(all(trace["world_flags"].values()))
        with TemporaryDirectory() as temp:
            path = Path(temp) / "five-valleys-session.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())
            atlas = WorldGraph(self.project.extensions[EXTENSION]["data"],
                               self.content, self.project)
            self.assertTrue(atlas.object_states(restored.progress, "ridge")
                            ["relic"]["active"])
            restored.route_move(1, 0)
            restored.route_move(1, 0)
            restored.route_move(0, 1)
            restored.route_world_transition("back_marsh")
            self.assertTrue(atlas.object_states(restored.progress, "marsh")
                            ["relic"]["active"])
            restored.route_move(1, 0)
            restored.route_move(1, 0)
            restored.route_move(0, 1)
            restored.route_world_transition("back_grove")
            restored.route_move(1, 0)
            restored.route_move(1, 0)
            restored.route_move(0, 1)
            restored.route_world_transition("back_valley")
            self.assertTrue(atlas.object_states(restored.progress, "valley")
                            ["relic"]["active"])

    def test_forged_relic_flag_fails_save_integrity(self):
        session = GameSession.new(self.content, self.project, "main")
        session.route_world_interact("relic")
        data = session.recording()
        forged = deepcopy(data)
        forged["progress"]["story_flags"][relic_flag("valley")] = False
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, self.content, self.project)
        altered = deepcopy(data)
        altered["scene_route"]["current"] = "sanctuary"
        altered["digest"] = digest({k: v for k, v in altered.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(altered, self.content, self.project)

    def test_creator_documents_have_strict_preflight_and_no_asset_rights(self):
        with TemporaryDirectory() as temp:
            source, project_path = write_five_valleys(Path(temp) / "five")
            self.assertTrue(source.exists())
            self.assertTrue(project_path.exists())
            report = preflight(source, require_licenses=True)
            self.assertTrue(report["passed"], report["errors"])
            self.assertEqual(report["assets"], [])
            self.assertTrue(report["rights_attestations_checked"])
            with self.assertRaises(RuleError):
                write_five_valleys(Path(temp) / "five")


if __name__ == "__main__":
    unittest.main()
