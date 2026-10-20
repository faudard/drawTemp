"""R63.A: contract validation, deterministic replay and survival vertical slice."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from sporebound.model import RuleError
from sporebound.survival import EXTENSION, SurvivalRuntime, validate_survival


def survival_spec():
    return {
        "version": 1,
        "needs": {"energy": 80, "hunger": 65, "temperature": 80,
                  "energy_drain": 1, "hunger_drain": 1, "cold_drain": 1},
        "items": ["axe", "wood", "stone", "berries", "camp", "ration"],
        "tools": [{"id": "axe", "durability": 2}],
        "nodes": [
            {"id": "forest", "scene": "arrival", "item": "wood",
             "stock": 3, "yield": 1, "tool": "axe", "wear": 1,
             "energy_cost": 5, "cold": 15},
            {"id": "rocks", "scene": "arrival", "item": "stone",
             "stock": 2, "yield": 1, "tool": None, "wear": 0,
             "energy_cost": 4, "cold": 0},
            {"id": "berry_bush", "scene": "arrival", "item": "berries",
             "stock": 4, "yield": 2, "tool": None, "wear": 0,
             "energy_cost": 2, "cold": 0},
        ],
        "recipes": [
            {"id": "make_camp", "inputs": {"wood": 1, "stone": 1},
             "outputs": {"camp": 1}, "energy_cost": 4},
            {"id": "make_ration", "inputs": {"berries": 2},
             "outputs": {"ration": 1}, "energy_cost": 3},
        ],
        "foods": [{"item": "ration", "nutrition": 25}],
        "shelters": [
            {"id": "home", "scene": "arrival", "fuel": {"camp": 1},
             "energy_restore": 35, "warmth": 40},
        ],
    }


def fresh():
    return SurvivalRuntime(survival_spec(), {"arrival"}), SimpleNamespace(
        inventory={"axe": 1})


class R63SurvivalTests(unittest.TestCase):
    def test_schema_closed_and_noninteger_counts_rejected(self):
        config = survival_spec()
        self.assertEqual(validate_survival(config, {"arrival"}), config)
        for edit in (
            lambda x: x["needs"].update(energy_drain=True),
            lambda x: x.update(version=2),
            lambda x: x["nodes"][0].update(scene="other"),
            lambda x: x["nodes"][0].update(tool=[]),
            lambda x: x["tools"][0].update(durability=-1),
            lambda x: x["recipes"][0]["outputs"].update(wood=1),
            lambda x: x["foods"].append({"item": "ration", "nutrition": 2}),
            lambda x: x.update(executable_script="eval()"),
        ):
            document = deepcopy(config)
            edit(document)
            with self.subTest(document=document), self.assertRaises(RuleError):
                validate_survival(document, {"arrival"})

    def test_vertical_slice_two_recipes_environment_and_recovery(self):
        runtime, progress = fresh()
        runtime.advance(3)
        runtime.gather(progress, "arrival", "forest", "harvest1")
        self.assertEqual(progress.inventory["wood"], 1)
        self.assertEqual(runtime.needs["temperature"], 62)
        self.assertFalse(runtime.gather(progress, "arrival", "forest", "harvest1"))
        runtime.gather(progress, "arrival", "rocks", "stone1")
        runtime.gather(progress, "arrival", "berry_bush", "berries1")
        runtime.craft(progress, "arrival", "make_camp", "craft1")
        runtime.craft(progress, "arrival", "make_ration", "craft2")
        self.assertEqual(progress.inventory["camp"], 1)
        self.assertEqual(progress.inventory["ration"], 1)
        runtime.eat(progress, "arrival", "ration", "eat1")
        runtime.rest(progress, "arrival", "home", "rest1")
        self.assertEqual(progress.inventory["camp"], 0)
        self.assertGreater(runtime.needs["energy"], 70)
        self.assertGreater(runtime.needs["temperature"], 80)
        copied = SurvivalRuntime(survival_spec(), {"arrival"})
        copied.restore(runtime.snapshot())
        self.assertEqual(copied.snapshot(), runtime.snapshot())
        self.assertFalse(copied.craft(progress, "arrival", "make_camp", "craft1"))
        with self.assertRaises(RuleError):
            copied.craft(progress, "arrival", "make_ration", "craft1")

    def test_rejected_actions_do_not_mutate_inventory_or_journal(self):
        runtime, progress = fresh()
        before = (runtime.snapshot(), deepcopy(progress.inventory))
        for cmd in (
            lambda: runtime.gather(progress, "other", "forest", "bad1"),
            lambda: runtime.craft(progress, "arrival", "make_camp", "bad2"),
            lambda: runtime.rest(progress, "arrival", "home", "bad3"),
            lambda: runtime.advance(True),
        ):
            with self.assertRaises(RuleError):
                cmd()
            self.assertEqual((runtime.snapshot(), progress.inventory), before)
        for i in range(2):
            runtime.gather(progress, "arrival", "forest", f"wood{i}")
        old = (runtime.snapshot(), deepcopy(progress.inventory))
        with self.assertRaises(RuleError):
            runtime.gather(progress, "arrival", "forest", "worn_tool")
        self.assertEqual((runtime.snapshot(), progress.inventory), old)

    def test_replay_rejects_tampering_and_duplicate_receipts(self):
        runtime, progress = fresh()
        runtime.gather(progress, "arrival", "forest", "receipt")
        checkpoint = runtime.snapshot()
        for mutation in (
            lambda x: x["stock"].update(forest=3),
            lambda x: x["needs"].update(temperature=100),
            lambda x: x["durability"].update(axe=100),
            lambda x: x.update(tick=9),
            lambda x: x["journal"].append(deepcopy(x["journal"][0])),
            lambda x: x["journal"].append({"kind": "advance", "ticks": True}),
        ):
            tampered = deepcopy(checkpoint)
            mutation(tampered)
            with self.subTest(tampered=tampered), self.assertRaises(RuleError):
                runtime.restore(tampered)
            self.assertEqual(runtime.snapshot(), checkpoint)

    def test_tick_compaction_and_replay_determinism(self):
        a, _ = fresh()
        b, _ = fresh()
        a.advance(120)
        for _ in range(120):
            b.advance(1)
        self.assertEqual(a.snapshot(), b.snapshot())
        self.assertEqual(a.snapshot()["journal"], [{"kind": "advance", "ticks": 120}])
        restored = SurvivalRuntime(survival_spec(), {"arrival"})
        restored.restore(a.snapshot())
        self.assertEqual(restored.snapshot(), a.snapshot())

    def test_cold_exposure_is_hazardous_and_frame_independent(self):
        spec = survival_spec()
        spec["needs"].update(
            energy_drain=0, hunger_drain=0, cold_drain=10)
        fast = SurvivalRuntime(spec, {"arrival"})
        frames = SurvivalRuntime(spec, {"arrival"})
        fast.advance(12)
        for _ in range(12):
            frames.advance(1)
        self.assertEqual(fast.snapshot(), frames.snapshot())
        self.assertEqual(fast.needs["temperature"], 0)
        self.assertEqual(fast.needs["energy"], 73)
        restored = SurvivalRuntime(spec, {"arrival"})
        restored.restore(fast.snapshot())
        self.assertEqual(restored.snapshot(), fast.snapshot())

    def test_authored_map_placement_is_bounded_and_reach_checked(self):
        from sporebound.game_session import GameSession
        from tests_standalone.test_r25_scene_router import scene_fixture
        content, project = scene_fixture()
        spec = survival_spec()
        spec["nodes"][0]["pos"] = [2, 1]  # blocked
        project.extensions[EXTENSION] = {
            "schema_version": 1, "data": spec, "references": []}
        with self.assertRaises(RuleError):
            project.validate(content)
        spec["nodes"][0]["pos"] = [3, 3]  # valid, far away
        project.validate(content)
        session = GameSession.new(content, project, "main")
        session.progress.inventory["axe"] = 1
        before = session.recording()
        with self.assertRaises(RuleError):
            session.survival_gather("forest", "far")
        self.assertEqual(session.recording(), before)
        self.assertEqual(session.survival_state()["stock"]["forest"], 3)

    def test_crafting_cycles_are_rejected(self):
        spec = survival_spec()
        spec["recipes"].append({
            "id": "unmake_camp", "inputs": {"camp": 1},
            "outputs": {"wood": 1}, "energy_cost": 1})
        with self.assertRaises(RuleError):
            validate_survival(spec, {"arrival"})

    def test_authoring_preview_undo_redo_and_stale_revision(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.studio.survival_authoring import (
            apply_survival_design, preview_survival_design)
        from tests_standalone.test_r25_scene_router import scene_fixture
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        before = session.snapshot().to_dict()
        preview = preview_survival_design(
            session, survival_spec(), expected_revision=before["revision"])
        self.assertEqual(preview.report["recipes"], 2)
        self.assertEqual(preview.report["hazards"], 1)
        self.assertEqual(session.snapshot().to_dict()["project"], before["project"])
        apply_survival_design(session, preview)
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        with self.assertRaises(ValueError):
            preview_survival_design(
                session, survival_spec(), expected_revision=before["revision"])
        session.undo()
        self.assertNotIn(EXTENSION,
                         session.snapshot().to_dict()["project"].get("extensions", {}))
        session.redo()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])

    def test_movement_uses_atomic_fixed_survival_ticks(self):
        from sporebound.game_session import GameSession
        from tests_standalone.test_r25_scene_router import scene_fixture
        content, project = scene_fixture()
        project.extensions[EXTENSION] = {
            "schema_version": 1, "data": survival_spec(), "references": []}
        project.validate(content)
        session = GameSession.new(content, project, "main")
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_realtime_step(9, 0)
        self.assertEqual(session.recording(), before)
        session.route_realtime_step(0, 0)
        self.assertEqual(session.survival_state()["tick"], 1)
        recording = session.recording()
        self.assertEqual(GameSession.from_recording(
            recording, content, project).recording(), recording)

    def test_gamesession_opt_in_checkpoint_and_sdk_revision(self):
        from drawtemp.sdk.simulation import Simulation, SimulationError
        from sporebound.game_session import GameSession, digest
        from tests_standalone.test_r25_scene_router import scene_fixture
        content, project = scene_fixture()
        legacy = GameSession.new(content, project, "main")
        self.assertNotIn("survival", legacy.recording())
        project.extensions[EXTENSION] = {
            "schema_version": 1, "data": survival_spec(), "references": []}
        project.validate(content)
        session = GameSession.new(content, project, "main")
        self.assertEqual(session.survival_state()["tick"], 0)
        session.progress.inventory["axe"] = 1
        self.assertTrue(session.survival_gather("forest", "first"))
        self.assertEqual(session.progress.inventory["wood"], 1)
        self.assertFalse(session.survival_gather("forest", "first"))
        with self.assertRaises(RuleError):
            session.survival_gather("rocks", "first")
        recording = session.recording()
        resumed = GameSession.from_recording(recording, content, project)
        self.assertEqual(resumed.recording(), recording)
        self.assertEqual(resumed.survival_state(), session.survival_state())
        bad = deepcopy(recording)
        bad["survival"]["stock"]["forest"] += 1
        bad["digest"] = digest({k: v for k, v in bad.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, content, project)

        sdk = Simulation.new(content, project, "main")
        self.assertEqual(sdk.survival_state()["tick"], 0)
        rev = sdk.snapshot().revision
        update = sdk.survival_advance(expected_revision=rev)
        self.assertEqual(update.snapshot.revision, rev + 1)
        with self.assertRaises(SimulationError):
            sdk.survival_advance(expected_revision=rev)

    def test_legacy_save_rejects_unexpected_survival(self):
        from sporebound.game_session import GameSession, digest
        from tests_standalone.test_r25_scene_router import scene_fixture
        content, project = scene_fixture()
        session = GameSession.new(content, project, "main")
        bad = session.recording()
        bad["survival"] = {}
        bad["digest"] = digest({k: v for k, v in bad.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, content, project)


if __name__ == "__main__":
    unittest.main()
