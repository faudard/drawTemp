"""R32.D vertical slice: switch -> door -> portal -> real CT -> back.

This is GameSession + canonical GameProject, not an independent game save.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import MISSION
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r25_scene_router import scene_fixture

from sporebound.physics_scenes import EXTENSION
from sporebound.platform_physics import PlatformPhysics


def block(ident, rect, *, trigger=False, opens=None, route=None):
    row = {"id": ident, "rect": rect, "layer": 1, "mask": 1,
           "trigger": trigger, "one_way": False}
    if opens is not None:
        row["opens"] = opens
    if route is not None:
        row["route"] = route
    return row


def platform_fixture():
    content, project = scene_fixture()
    # This route was originally locked by a story flag; R32 uses an authored
    # physical door/trigger instead. Other R25 CT transitions are unchanged.
    project.scene_routes["links"][0].pop("when")
    authored = {
        "id": "arrival", "width": 12000, "height": 6000, "gravity": 40,
        "hero": {"pos": [1000, 4200], "size": [500, 800],
                 "speed": 240, "jump": 520, "max_fall": 900, "coyote": 4},
        "colliders": [
            block("floor", [0, 5000, 12000, 1000]),
            block("door", [3200, 3500, 100, 1500]),
            block("lever", [1500, 4200, 500, 700],
                  trigger=True, opens="door"),
            block("portal", [4700, 4200, 600, 750],
                  trigger=True, route="to_arena"),
        ],
    }
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": {"scenes": {"arrival": authored}}
    }
    project.validate(content)
    return content, project


class PlatformJourneyR32Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = platform_fixture()
        self.game = GameSession.new(self.content, self.project, "main", seed=17)

    def move(self, n, *, game=None, move=1, jump=False, interact=False):
        game = game or self.game
        events = []
        for index in range(n):
            events.extend(game.route_platform_step(
                move=move, jump=jump if index == 0 else False,
                interact=interact if index == 0 else False)["events"])
        return events

    def test_real_switch_door_persists_through_load_and_round_trip_to_ct(self):
        game = self.game
        self.assertEqual(game.route_platform_state()["scene"], "arrival")
        self.assertNotIn("scene_platform", GameSession.new(
            self.content, self.project, "main").recording())
        self.move(1)
        events = self.move(1, move=0, interact=True)
        self.assertEqual([e["kind"] for e in events], ["door_open"])
        flag = game._platform_flag("door")
        self.assertTrue(game.progress.story_flags[flag])
        self.assertEqual(game.route_platform_state()["disabled_colliders"], ["door"])
        self.move(12)
        self.assertGreater(game.route_platform_state()["actor"]["x"], 3200)
        with TemporaryDirectory() as temp:
            save_path = Path(temp) / "game.json"
            game.save(save_path)
            restored = GameSession.load(save_path, self.content, self.project)
            self.assertEqual(restored.recording(), game.recording())
            self.assertEqual(restored.route_platform_state(),
                             game.route_platform_state())
            self.move(2, game=restored)
            self.assertIn("to_arena", restored.route_platform_state()["available_routes"])
            traveled = restored.route_platform_travel("to_arena")
            self.assertEqual(traveled["scene"], MISSION)
            self.assertEqual(restored.mode, "battle")
            self.assertEqual(restored.route_history, ["to_arena"])
            restored.abandon_encounter()
            self.assertEqual(restored.route_transition("retreat")["scene"], "arrival")
            self.assertTrue(restored.progress.story_flags[flag])
            self.assertIn("door", restored.route_platform_state()["disabled_colliders"])
            restored.save(save_path)
            final = GameSession.load(save_path, self.content, self.project)
            self.assertEqual(final.recording(), restored.recording())

    def test_cannot_bypass_portal_and_rejects_unconfigured_scene(self):
        game = self.game
        with self.assertRaises(RuleError):
            game.route_platform_travel("to_arena")
        before = game.recording()
        with self.assertRaises(RuleError):
            game.route_platform_step(move=True)
        with self.assertRaises(RuleError):
            game.route_realtime_step(1, 0)
        self.assertEqual(game.recording(), before)
        self.move(1)
        with self.assertRaises(RuleError):
            game.route_platform_travel("to_arena")

    def test_replay_detects_tamper_even_after_outer_checksum_forged(self):
        self.move(1)
        self.move(1, move=0, interact=True)
        record = self.game.recording()
        self.assertEqual(GameSession.from_recording(
            record, self.content, self.project).recording(), record)
        broken = deepcopy(record)
        broken["scene_platform"]["physics"]["commands"][1]["interact"] = False
        body = broken["scene_platform"]["physics"]
        from sporebound.platform_physics import _hash
        body["digest"] = _hash({k: v for k, v in body.items() if k != "digest"})
        broken["digest"] = digest({k: v for k, v in broken.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(broken, self.content, self.project)
        mismatch = deepcopy(record)
        flag = self.game._platform_flag("door")
        mismatch["progress"]["story_flags"].pop(flag)
        mismatch["digest"] = digest({k: v for k, v in mismatch.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(mismatch, self.content, self.project)

    def test_invalid_route_references_and_switch_geometry_fail_validation(self):
        for transform in (
            lambda p: p.extensions[EXTENSION]["data"]["scenes"]["arrival"]["colliders"][3].update(route="unknown"),
            lambda p: p.extensions[EXTENSION]["data"]["scenes"]["arrival"]["colliders"][2].update(opens="absent"),
            lambda p: p.extensions[EXTENSION]["data"]["scenes"]["arrival"]["colliders"][2].update(opens=True),
        ):
            project = deepcopy(self.project)
            transform(project)
            with self.assertRaises(RuleError):
                GameProject.from_dict(project.to_dict(), self.content)

    def test_old_unrouted_game_session_has_no_physics_extension(self):
        from drawtemp.sdk.reference import reference_project
        c, p = reference_project()
        game = GameSession.new(c, p, "main", seed=17)
        self.assertNotIn("scene_platform", game.recording())
        with self.assertRaises(RuleError):
            game.route_platform_state()
        self.assertEqual(GameSession.from_recording(game.recording(), c, p).recording(),
                         game.recording())


if __name__ == "__main__":
    unittest.main()
