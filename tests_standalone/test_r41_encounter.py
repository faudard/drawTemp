"""R41.B2 — deterministic RPG_TURN actions, GameSession replay and authoring tests."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from drawtemp.studio.encounter_authoring import (
    apply_encounter_edit, available_rpg_enemies, available_rpg_scenes,
    encounter_definitions, preview_encounter_edit,
)
from sporebound.classic_party import EXTENSION
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r41_classic_party import party_fixture


def encounter_fixture():
    content, project = party_fixture()
    project.story = {
        "scenes": [{"id": "inn", "title": "Village", "speaker": "",
                    "text": "À l'auberge", "choices": [
                        {"id": "continue", "label": "Continuer"}]}],
        "entry_scenes": {}, "after_mission": {},
    }
    project.exploration["inn"] = {
        "title": "Village", "theme": "village",
        "width": 4, "height": 4, "start": [0, 1], "blocked": [],
        "interactions": [{
            "id": "exit", "title": "Place du village",
            "text": "Sortir de l'auberge", "pos": [1, 2],
            "required": False, "exit": True,
        }],
    }
    project.extensions[EXTENSION]["data"]["encounters"] = {
        "sparring": {
            "scene": "inn",
            "enemies": ["renaud_mentor"],
            "reward_gold": 17,
        },
    }
    project.validate(content)
    return content, project


class R41EncounterTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = encounter_fixture()
        self.session = GameSession.new(self.content, self.project, "main", seed=29)

    def test_attack_auto_enemy_victory_and_reward_once(self):
        self.assertEqual(self.session.rpg_available(), ["sparring"])
        self.session.rpg_start("sparring")
        self.assertEqual(self.session.mode, "rpg")
        view = self.session.rpg_state()
        self.assertEqual(view["active"], "jeanne")
        self.assertEqual(self.session.progress.gold, 0)
        for _ in range(10):
            view = self.session.rpg_state()
            if view["result"]:
                break
            self.session.rpg_action(
                {"kind": "attack", "actor": view["active"],
                 "target": "renaud_mentor"})
        self.assertEqual(self.session.rpg_state()["result"], "victory")
        gold_before = self.session.progress.gold
        self.assertEqual(gold_before, 0)
        outcome = self.session.rpg_finish()
        self.assertEqual(outcome["result"], "victory")
        self.assertEqual(self.session.progress.gold, 17)
        self.assertEqual(self.session.progress.heroes["jeanne"].xp, 50)
        self.assertEqual(self.session.rpg_available(), [])
        with self.assertRaises(RuleError):
            self.session.rpg_start("sparring")
        with self.assertRaises(RuleError):
            self.session.rpg_finish()
        self.assertEqual(self.session.progress.gold, 17)

    def test_save_load_mid_battle_replay_and_checkpoint_tampering(self):
        self.session.progress.inventory["potion"] = 1
        self.session.rpg_start("sparring")
        first = self.session.rpg_state()
        self.session.rpg_action(
            {"kind": "attack", "actor": first["active"], "target": "renaud_mentor"})
        original = self.session.recording()
        with TemporaryDirectory() as path:
            save = Path(path) / "r41-middle.json"
            self.session.save(save)
            restored = GameSession.load(save, self.content, self.project)
            self.assertEqual(restored.recording(), original)
            self.assertEqual(restored.rpg_state(), self.session.rpg_state())
        broken = deepcopy(original)
        broken["rpg_encounter"]["view"]["actors"][0]["hp"] = 1
        broken["digest"] = digest({k: v for k, v in broken.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(broken, self.content, self.project)
        broken = deepcopy(original)
        broken["rpg_encounter"]["commands"][0]["target"] = "unknown"
        broken["digest"] = digest({k: v for k, v in broken.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(broken, self.content, self.project)
        broken = deepcopy(original)
        broken.pop("rpg_encounter")
        broken["digest"] = digest({k: v for k, v in broken.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(broken, self.content, self.project)
        broken = deepcopy(original)
        broken["rpg_encounter"] = []
        broken["digest"] = digest({k: v for k, v in broken.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(broken, self.content, self.project)

    def test_guard_potion_and_wrong_turn_rollback(self):
        self.session.progress.inventory["potion"] = 1
        self.session.rpg_start("sparring")
        before = self.session.recording()
        for invalid in (
            {"kind": "attack", "actor": "renaud_mentor", "target": "jeanne"},
            {"kind": "item", "actor": "jeanne", "target": "renaud_mentor", "item": "potion"},
            {"kind": "skill", "actor": "jeanne", "target": "renaud_mentor",
             "skill": "unknown"},
            {"kind": "magic", "actor": "jeanne", "target": "renaud_mentor"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                self.session.rpg_action(invalid)
            self.assertEqual(self.session.recording(), before)
        self.session.rpg_action({"kind": "guard", "actor": "jeanne"})
        self.assertEqual(self.session.rpg_state()["active"], "jeanne")
        hero = next(a for a in self.session.rpg_state()["actors"]
                    if a["id"] == "jeanne")
        self.assertLess(hero["hp"], hero["max_hp"])
        self.session.rpg_action(
            {"kind": "item", "actor": "jeanne", "target": "jeanne", "item": "potion"})
        self.assertEqual(self.session.progress.inventory["potion"], 0)
        self.assertEqual(self.session.rpg_state()["inventory"]["potion"], 0)
        with self.assertRaises(RuleError):
            self.session.party_set_active(["jeanne"])
        saved = self.session.recording()
        self.assertEqual(GameSession.from_recording(
            saved, self.content, self.project).recording(), saved)

    def test_reuse_existing_content_skill_and_flee_without_reward(self):
        self.session.rpg_start("sparring")
        before = self.session.rpg_state()
        self.session.rpg_action({"kind": "skill", "actor": "jeanne",
                                 "target": "renaud_mentor", "skill": "estoc"})
        after = self.session.rpg_state()
        previous = next(a for a in before["actors"] if a["id"] == "renaud_mentor")
        changed = next(a for a in after["actors"] if a["id"] == "renaud_mentor")
        self.assertLess(changed["hp"], previous["hp"])
        self.session.rpg_action({"kind": "flee", "actor": "jeanne"})
        self.assertEqual(self.session.rpg_state()["result"], "fled")
        self.session.rpg_finish()
        self.assertEqual(self.session.progress.gold, 0)
        self.assertFalse(self.session.progress.story_flags.get("r41:sparring"))
        self.assertEqual(self.session.rpg_available(), ["sparring"])

    def test_guard_until_ko_defeat_never_grants_victory_reward(self):
        self.session.rpg_start("sparring")
        for _ in range(100):
            view = self.session.rpg_state()
            if view["result"]:
                break
            self.assertEqual(view["active"], "jeanne")
            self.session.rpg_action({"kind": "guard", "actor": "jeanne"})
        self.assertEqual(self.session.rpg_state()["result"], "defeat")
        hero = next(a for a in self.session.rpg_state()["actors"]
                    if a["id"] == "jeanne")
        self.assertEqual(hero["hp"], 0)
        self.session.rpg_finish()
        self.assertEqual(self.session.progress.gold, 0)
        self.assertEqual(self.session.progress.heroes["jeanne"].xp, 0)
        self.assertEqual(self.session.rpg_available(), ["sparring"])

    def test_invalid_encounter_contract_fails_closed(self):
        modifiers = [
            lambda d: d.update(enemies=["unknown"]),
            lambda d: d.update(enemies=["renaud_mentor", "renaud_mentor"]),
            lambda d: d.update(scene="unknown"),
            lambda d: d.update(reward_gold=True),
            lambda d: d.update(extra=1),
        ]
        for modifier in modifiers:
            project = deepcopy(self.project)
            modifier(project.extensions[EXTENSION]["data"]["encounters"]["sparring"])
            with self.subTest(modifier=modifier), self.assertRaises(RuleError):
                project.validate(self.content)
        project = deepcopy(self.project)
        project.game_modes["scenes"]["inn"] = {"preset": "srpg"}
        with self.assertRaises(RuleError):
            project.validate(self.content)

    def test_encounter_editor_preview_apply_undo_and_stale(self):
        editor = AuthoringSession.new(self.content, self.project)
        self.assertIn("inn", available_rpg_scenes(editor.snapshot()))
        self.assertIn("renaud_mentor", dict(available_rpg_enemies(editor.snapshot())))
        original = editor.snapshot().to_dict()
        draft = preview_encounter_edit(
            editor, "sparring", scene="inn", enemies=["renaud_mentor"],
            reward_gold=50, expected_revision=editor.revision)
        self.assertEqual(editor.snapshot().to_dict(), original)
        self.assertEqual(draft.before["reward_gold"], 17)
        applied = apply_encounter_edit(editor, draft)
        self.assertEqual(applied.snapshot.revision, 1)
        self.assertEqual(encounter_definitions(editor.snapshot())["sparring"][
            "reward_gold"], 50)
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["project"],
                         original["project"])
        with self.assertRaises(RuleError):
            preview_encounter_edit(editor, "new_encounter", scene="inn",
                                   enemies=["renaud_mentor"], reward_gold=20,
                                   expected_revision=0)

    def test_simulation_and_player_roundtrip(self):
        with TemporaryDirectory() as path:
            player = PlayerController(self.content, self.project,
                                      "main", Path(path), seed=29)
            state = player.new_game()
            self.assertEqual(state["rpg_available"], ["sparring"])
            player.start_rpg_encounter("sparring")
            self.assertEqual(player.state()["screen"], "rpg_battle")
            rev = player.session.snapshot().revision
            with self.assertRaises(SimulationError):
                player.session.rpg_action(
                    {"kind": "guard", "actor": "jeanne"},
                    expected_revision=rev - 1)
            player.rpg_action("guard")
            player.save(1)
            other = PlayerController(self.content, self.project,
                                     "main", Path(path), seed=29)
            other.load(1)
            self.assertEqual(other.state()["screen"], "rpg_battle")
            self.assertEqual(other.state()["rpg"], player.state()["rpg"])
            other.rpg_action("flee")
            other.finish_rpg_encounter()
            self.assertEqual(other.state()["screen"], "campaign")


if __name__ == "__main__":
    unittest.main()
