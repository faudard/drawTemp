"""R26.B opt-in Player and canonical campaign action handoff safety gates."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.player.action_controller import ActionPlayerController, demo_scene
from drawtemp.sdk.action_encounter import ActionEncounter
from drawtemp.sdk.reference import reference_project
from sporebound.action_runtime import ActionRuntime, ActionError
from sporebound.game_session import GameSession
from sporebound.model import RuleError


def action_scene():
    return {
        "id": "arrival", "width": 7, "height": 7, "walls": [],
        "hero": {"pos": [1, 1], "hp": 12},
        "enemies": [{"id": "wolf", "pos": [2, 1], "hp": 1, "patrol": []}],
        "objects": [
            {"id": "supply", "kind": "chest", "pos": [1, 2],
             "item": "key", "requires": ""},
            {"id": "gate", "kind": "door", "pos": [2, 2],
             "item": "", "requires": "key"},
        ],
    }


def action_profile(self, scene_id):
    assert scene_id == "arrival"
    return {"movement": "FREE_REALTIME", "combat": "ACTION_REALTIME",
            "camera": "TOP_DOWN", "interaction": "CONTEXTUAL", "ui": "ACTION"}


class R26BPlayerTests(unittest.TestCase):
    def test_headless_controller_state_detachment_tick_pause_and_resume(self):
        controller = ActionPlayerController(demo_scene())
        snapshot = controller.state()
        snapshot["hero"]["hp"] = -100
        snapshot["items"].clear()
        self.assertEqual(controller.runtime.hero["hp"], 8)
        self.assertEqual(len(controller.scene["objects"]), 3)
        controller.step(dx=0, dy=1, interact=True)
        self.assertEqual(controller.runtime.inventory["gate_key"], 1)
        tick = controller.runtime.tick
        controller.toggle_pause()
        self.assertEqual(controller.step(dx=1), [])
        self.assertEqual(controller.runtime.tick, tick)
        controller.toggle_pause()
        controller.step(dx=1)
        self.assertEqual(controller.runtime.tick, tick + 1)

    def test_controller_save_and_fail_closed_corrupted_checkpoint(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "action.json"
            controller = ActionPlayerController(demo_scene(), save_path=path)
            controller.step(dx=1)
            original = controller.runtime.digest()
            controller.save()
            controller.step(dy=1)
            self.assertNotEqual(original, controller.runtime.digest())
            controller.load()
            self.assertEqual(original, controller.runtime.digest())
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["commands"][0]["dx"] = -1
            path.write_text(json.dumps(raw), encoding="utf-8")
            before = controller.runtime.digest()
            with self.assertRaises(ActionError):
                controller.load()
            self.assertEqual(before, controller.runtime.digest())

    def test_action_inventory_can_start_from_legacy_campaign_without_replay_change(self):
        scene = action_scene()
        original = ActionRuntime(scene)
        self.assertNotIn("initial_inventory", original.recording())
        runner = ActionRuntime(scene, initial_inventory={"potion": 2, "key": 1})
        self.assertEqual(runner.inventory["potion"], 2)
        runner.step({"tick": 1, "interact": "gate"})
        self.assertEqual(runner.inventory["key"], 0)
        restored = ActionRuntime.from_recording(runner.recording(), expected_scene=scene)
        self.assertEqual(restored.digest(), runner.digest())
        self.assertEqual(restored.initial_inventory, {"potion": 2, "key": 1})
        for bad in ({"potion": -1}, {"potion": True}, {"bad": 1.1}):
            with self.subTest(bad=bad), self.assertRaises(ActionError):
                ActionRuntime(scene, initial_inventory=bad)


class R26BCampaignTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = GameSession.new(self.content, self.project, "main", seed=17)
        self.session.choose_story_option("enter")
        self.session.progress.inventory["potion"] = 2
        self.original = self.session.recording()

    def test_rejected_without_r25_or_with_non_action_profile(self):
        with self.assertRaises(RuleError):
            ActionEncounter(self.session, action_scene())
        with patch.object(GameSession, "scene_profile",
                          return_value={"movement": "GRID_CT",
                                        "combat": "TACTICAL_CT"}, create=True):
            with self.assertRaises(RuleError):
                ActionEncounter(self.session, action_scene())
        self.assertEqual(self.session.recording(), self.original)

    def test_complete_action_commits_once_and_preserves_tactical_v1(self):
        with patch.object(GameSession, "scene_profile", action_profile, create=True):
            encounter = ActionEncounter(self.session, action_scene())
            encounter.step({"tick": 1, "dx": 1, "attack": True})
            encounter.step({"tick": 2, "interact": "supply"})
            self.assertEqual(self.session.recording(), self.original)
            self.assertFalse(encounter.can_complete())
            encounter.step({"tick": 3, "interact": "gate"})
            self.assertTrue(encounter.can_complete())
            checkpoint = encounter.commit()
            self.assertEqual(checkpoint["mode"], "campaign")
            self.assertNotIn("action", checkpoint)
            self.assertEqual(self.session.progress.inventory["potion"], 2)
            self.assertEqual(self.session.progress.inventory["coin"], 1)
            self.assertEqual(self.session.progress.inventory["key"], 0)
            self.assertTrue(self.session.progress.story_flags["r26:arrival"])
            restored = GameSession.from_recording(
                checkpoint, self.content, self.project)
            self.assertEqual(restored.recording(), checkpoint)
            with self.assertRaises(RuleError):
                encounter.commit()
            with self.assertRaises(RuleError):
                ActionEncounter(self.session, action_scene())

    def test_mid_action_checkpoint_verifies_both_ledgers_and_restores(self):
        with patch.object(GameSession, "scene_profile", action_profile, create=True):
            encounter = ActionEncounter(self.session, action_scene())
            encounter.step({"tick": 1, "dx": 1, "attack": True})
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "compound.json"
                encounter.save(path)
                restore = ActionEncounter.load(
                    path, self.content, self.project, action_scene())
                self.assertEqual(restore.runtime.digest(), encounter.runtime.digest())
                self.assertEqual(restore.session.recording(), self.original)
                restore.step({"tick": 2, "interact": "supply"})
                restore.step({"tick": 3, "interact": "gate"})
                restored_campaign = restore.commit()
                self.assertEqual(restored_campaign["mode"], "campaign")
                # A corrupted recorded input must fail, not mutate the campaign.
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["action"]["commands"][0]["dx"] = -1
                payload["digest"] = __import__(
                    "sporebound.game_session", fromlist=["digest"]).digest(
                    {k: v for k, v in payload.items() if k != "digest"})
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(RuleError):
                    ActionEncounter.load(path, self.content, self.project, action_scene())
                self.assertEqual(self.session.recording(), self.original)

    def test_external_campaign_modification_is_rejected_before_commit(self):
        with patch.object(GameSession, "scene_profile", action_profile, create=True):
            encounter = ActionEncounter(self.session, action_scene())
            self.session.progress.gold += 10
            # The tick continues, but no checkpoint/reward may be
            # published after a concurrent change to canonical progress.
            encounter.step({"tick": 1})
            with self.assertRaises(RuleError):
                encounter.recording()
            with self.assertRaises(RuleError):
                encounter.commit()
            self.assertEqual(self.session.progress.inventory, {"potion": 2})


if __name__ == "__main__":
    unittest.main()
