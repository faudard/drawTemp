"""R34.C headless run/meta integration, replay, corruption and legacy isolation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.procgen_prefabs import demo_library
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError
from sporebound.roguelite import EXTENSION, validate_roguelite_spec


def configured():
    content = Content.load(DEFAULT_CONTENT)
    project = GameProject.default(content)
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": {
            "version": 1,
            "recipe": {"seed": 81, "rooms": 10, "branches": 3,
                       "locked_goal": True, "encounter_budget": 7, "loot_budget": 80},
            "library": demo_library(), "biome": "ruins", "meta_reward": 7,
        }}
    project.validate(content)
    return content, project


class RogueliteSessionTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = configured()
        self.session = GameSession.new(self.content, self.project, "main", seed=19)

    @staticmethod
    def finish(session):
        for room_id in session.roguelite_state()["layout"]["route"][1:]:
            session.roguelite_move(room_id)
        return session.roguelite_state()

    def test_win_once_and_meta_survives_restart_without_run_inventory(self):
        state = self.session.roguelite_state()
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["meta"], {"coins": 0, "wins": 0, "deaths": 0})
        original_gold = self.session.progress.gold
        self.session.roguelite_checkpoint()
        self.assertEqual(self.session.roguelite_state()["checkpoint"]["room"], 0)
        first = self.finish(self.session)
        self.assertEqual(first["status"], "won")
        self.assertEqual(first["meta"], {"coins": 7, "wins": 1, "deaths": 0})
        with self.assertRaises(RuleError):
            self.session.roguelite_move(0)
        with self.assertRaises(RuleError):
            self.session.roguelite_die()
        self.assertEqual(self.session.roguelite_state(), first)
        next_run = self.session.roguelite_restart()
        self.assertEqual(next_run["seed"], 82)
        self.assertEqual(next_run["meta"]["coins"], 7)
        self.assertEqual(next_run["inventory"]["loot"], 0)
        self.assertEqual(next_run["claimed"], [])
        self.assertEqual(next_run["checkpoint"], None)
        self.assertNotEqual(next_run["layout_digest"], first["layout_digest"])
        second = self.finish(self.session)
        self.assertEqual(second["meta"]["coins"], 14)
        self.assertEqual(second["meta"]["wins"], 2)
        self.assertEqual(self.session.progress.gold, original_gold)

    def test_death_discards_run_inventory_but_preserves_meta(self):
        run = self.session.roguelite_state()
        # Find loot anywhere using the valid route; claim once, then die.
        for room_id in run["layout"]["route"][1:]:
            self.session.roguelite_move(room_id)
            state = self.session.roguelite_state()
            row = state["layout"]["rooms"][room_id]
            if row["loot"]:
                claimed = self.session.roguelite_claim()
                self.assertGreater(claimed["inventory"]["loot"], 0)
                with self.assertRaises(RuleError):
                    self.session.roguelite_claim()
                break
        else:
            self.fail("Recipe with 80 loot placements must put loot on a route room")
        before = self.session.roguelite_state()["inventory"]["loot"]
        self.session.roguelite_checkpoint()
        self.session.roguelite_die()
        dead = self.session.roguelite_state()
        self.assertEqual(dead["inventory"]["loot"], before)
        self.assertEqual(dead["meta"]["deaths"], 1)
        with self.assertRaises(RuleError):
            self.session.roguelite_claim()
        self.session.roguelite_restart()
        after = self.session.roguelite_state()
        self.assertEqual(after["inventory"]["loot"], 0)
        self.assertEqual(after["meta"]["deaths"], 1)
        self.assertEqual(after["checkpoint"], None)

    def test_save_load_replays_commands_and_preserves_legacy_session_format(self):
        self.session.roguelite_checkpoint()
        route = self.session.roguelite_state()["layout"]["route"]
        self.session.roguelite_move(route[1])
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "roguelite.json"
            self.session.save(checkpoint)
            loaded = GameSession.load(checkpoint, self.content, self.project)
            self.assertEqual(loaded.recording(), self.session.recording())
            self.assertEqual(loaded.roguelite_state(), self.session.roguelite_state())
            for room_id in loaded.roguelite_state()["layout"]["route"][2:]:
                loaded.roguelite_move(room_id)
            self.assertEqual(loaded.roguelite_state()["meta"]["wins"], 1)
            self.assertEqual(self.session.roguelite_state()["meta"]["wins"], 0)
        vanilla = GameProject.default(self.content)
        legacy = GameSession.new(self.content, vanilla, "main", seed=19)
        self.assertNotIn("roguelite", legacy.recording())
        restored = GameSession.from_recording(
            legacy.recording(), self.content, vanilla)
        self.assertEqual(restored.recording(), legacy.recording())
        with self.assertRaises(RuleError):
            GameSession.from_recording(legacy.recording(), self.content, self.project)

    def test_corruption_and_forged_snapshot_even_with_recomputed_digest(self):
        self.finish(self.session)
        original = self.session.recording()
        tampered = deepcopy(original)
        tampered["roguelite"]["state"]["meta"]["coins"] += 900
        tampered["roguelite"]["digest"] = digest(
            {k: v for k, v in tampered["roguelite"].items() if k != "digest"})
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(tampered, self.content, self.project)
        tampered = deepcopy(original)
        tampered["roguelite"]["commands"][0] = {"kind": "move", "value": 500}
        tampered["roguelite"]["digest"] = digest(
            {k: v for k, v in tampered["roguelite"].items() if k != "digest"})
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(tampered, self.content, self.project)

    def test_rejected_action_rolls_back_and_ct_isolation(self):
        before = self.session.recording()
        for operation in (
            lambda: self.session.roguelite_move(True),
            lambda: self.session.roguelite_move(100),
            lambda: self.session.roguelite_claim(),
            lambda: self.session.roguelite_restart(),
        ):
            with self.assertRaises(RuleError):
                operation()
            self.assertEqual(self.session.recording(), before)
        self.session.start_mission(next(iter(self.content.missions)))
        with self.assertRaises(RuleError):
            self.session.roguelite_die()
        self.assertEqual(self.session.roguelite_state()["meta"]["deaths"], 0)

    def test_100_seeds_replay_to_same_meta_rewards(self):
        from sporebound.roguelite import RogueliteRun
        source = self.project.extensions[EXTENSION]["data"]
        for seed in range(100):
            with self.subTest(seed=seed):
                spec = deepcopy(source)
                spec["recipe"]["seed"] = seed
                run = RogueliteRun(spec, content=self.content, project=self.project)
                layout = run.snapshot()["layout"]
                for room_id in layout["route"][1:]:
                    run.action("move", room_id)
                self.assertEqual(run.snapshot()["status"], "won")
                self.assertEqual(run.snapshot()["meta"]["coins"], 7)
                restored = RogueliteRun.from_recording(
                    spec, run.recording(), content=self.content, project=self.project)
                self.assertEqual(restored.snapshot(), run.snapshot())

    def test_revision_checked_sdk_and_stale_actions(self):
        from drawtemp.sdk.simulation import Simulation, SimulationError
        sim = Simulation.new(self.content, self.project, "main", seed=19)
        first = sim.roguelite_state(expected_revision=0)
        next_room = first["layout"]["route"][1]
        result = sim.roguelite_move(next_room, expected_revision=0)
        self.assertEqual(result.snapshot.revision, 1)
        with self.assertRaises(SimulationError) as exc:
            sim.roguelite_move(next_room, expected_revision=0)
        self.assertEqual(exc.exception.code, "stale_revision")
        self.assertEqual(sim.roguelite_state(expected_revision=1)["position"],
                         next_room)

    def test_authoring_validation_fails_closed(self):
        extension = self.project.extensions[EXTENSION]["data"]
        for mutated in (
            {**extension, "meta_reward": True},
            {**extension, "version": 2},
            {**extension, "biome": "unknown"},
            {**extension, "recipe": {**extension["recipe"], "branches": 0}},
        ):
            with self.subTest(mutated=mutated), self.assertRaises(RuleError):
                validate_roguelite_spec(mutated, content=self.content, project=self.project)
        original = self.project.to_dict()
        editor = AuthoringSession.new(self.content, self.project)
        plan = editor.preview_project(
            lambda p: {**p, "extensions": {
                **p["extensions"], EXTENSION: {
                    **p["extensions"][EXTENSION],
                    "data": {**p["extensions"][EXTENSION]["data"],
                             "meta_reward": 12}}}},
            kind="roguelite-reward")
        self.assertEqual(editor.snapshot().project["extensions"][EXTENSION]["data"]
                         ["meta_reward"], 7)
        editor.apply(plan)
        self.assertEqual(editor.snapshot().project["extensions"][EXTENSION]["data"]
                         ["meta_reward"], 12)
        editor.undo()
        self.assertEqual(editor.snapshot().project["extensions"][EXTENSION]["data"]
                         ["meta_reward"], 7)
        self.assertEqual(self.project.to_dict(), original)


if __name__ == "__main__":
    unittest.main()
