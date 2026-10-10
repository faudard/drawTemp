"""2.8.3 story decisions are real StoryBook choices, tied to tactical replay."""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from examples.siege_scenarios import siege_content
from sporebound import siege_authoring as edit
from sporebound.authored_siege_player import AuthoredSiegeController
from sporebound.game_project import GameProject
from sporebound.game_session import digest
from sporebound.model import Content, RuleError


def authored_story():
    return {
        "scenes": [
            {"id": "intro", "title": "Le serment", "speaker": "Jeanne",
             "text": "Comment commencer l'assaut ?",
             "choices": [
                 {"id": "honor", "label": "Jurer fidélité",
                  "effects": [{"kind": "set_flag", "flag": "honor", "value": True},
                              {"kind": "gold", "amount": 3}],
                  "next_scene": "orders"},
                 {"id": "secret", "label": "Marcher sans bannière",
                  "effects": [{"kind": "set_flag", "flag": "honor", "value": False}],
                  "next_scene": "orders"}]},
            {"id": "orders", "title": "Les ordres", "speaker": "Écuyer",
             "text": "Payer les éclaireurs ?",
             "choices": [
                 {"id": "pay", "label": "Payer 2 pièces",
                  "when": {"gold_gte": 2},
                  "effects": [{"kind": "gold", "amount": -2},
                              {"kind": "set_flag", "flag": "spies", "value": True}]},
                 {"id": "free", "label": "Continuer sans éclaireur"}]},
            {"id": "after", "title": "Le bastion sécurisé", "speaker": "Jeanne",
             "text": "Les gardes se rendent.",
             "choices": [
                 {"id": "mercy", "label": "Faire grâce",
                  "effects": [{"kind": "set_flag", "flag": "mercy", "value": True}]},
                 {"id": "justice", "label": "Arrêter les défenseurs",
                  "effects": [{"kind": "set_flag", "flag": "mercy", "value": False}]}]},
        ],
        "entry_scenes": {"main": "intro"},
        "after_mission": {"castle_tunnels": "after"},
    }


def fixtures():
    raw = siege_content().to_dict()
    for mission in raw["missions"]:
        if mission["id"] == "castle_tunnels":
            for actor in mission["units"]:
                if actor["team"] == "enemy":
                    actor["hp"] = actor["max_hp"] = 1
    content = Content.from_dict(raw)
    bp = edit.new_blueprint("story_siege", "main", "castle_tunnels", front="sewers")
    bp = edit.add_front(bp, "gate", "castle_ram")
    project = edit.replace_siege(GameProject.default(content), content, bp)
    project.story = authored_story()
    project.validate(content)
    return content, bp, project


class SiegeStoryTests(unittest.TestCase):
    def test_conditional_choices_flags_gold_and_restart(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.game.json"
            a = AuthoredSiegeController(content, bp, path,
                                        project=project)
            a.new_game()
            self.assertEqual(a.active_scene()["id"], "intro")
            with self.assertRaises(RuleError):
                a.execute({"kind": "end"})
            a.choose_story_option("secret")
            self.assertEqual(a.active_scene()["id"], "orders")
            self.assertEqual([choice["id"] for choice in a.available_choices()],
                             ["free"])
            with self.assertRaises(RuleError):
                a.choose_story_option("pay")
            a.choose_story_option("free")
            self.assertIsNone(a.active_scene())
            self.assertIs(a.story.progress.story_flags["honor"], False)
            # Old Command Center saves must never erase the new choice journal.
            with self.assertRaises(RuleError):
                edit.save_siege_slot(path, bp, 1, a.session.fronts)
            b = AuthoredSiegeController(content, bp, path,
                                        project=project)
            b.continue_game()
            self.assertEqual(b.story.recording(), a.story.recording())
            self.assertIsNone(b.active_scene())
            self.assertEqual(b.session.fronts.digest(), a.session.fronts.digest())

    def test_branching_reward_and_atomic_choice_rollback(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            a = AuthoredSiegeController(content, bp, Path(tmp) / "project.game.json",
                                        project=project)
            a.new_game()
            a.choose_story_option("honor")
            self.assertIn("pay", [r["id"] for r in a.available_choices()])
            saved = a.story.recording()
            with patch.object(a, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    a.choose_story_option("pay")
            self.assertEqual(a.story.recording(), saved)
            a.choose_story_option("pay")
            self.assertEqual(a.story.progress.gold, 1)
            self.assertEqual(a.story.progress.story_flags,
                             {"honor": True, "spies": True})
            reloaded = AuthoredSiegeController(
                content, bp, a.project_path, project=project)
            reloaded.continue_game()
            self.assertEqual(reloaded.story.recording(), a.story.recording())

    def test_verified_victory_triggers_authored_epilogue(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            a = AuthoredSiegeController(content, bp, Path(tmp) / "project.game.json",
                                        project=project)
            a.new_game()
            a.choose_story_option("secret")
            a.choose_story_option("free")
            # The tunnel fixture is a real eliminate battle. Its ranged sapper
            # shoots the weak guards; no synthetic victory is injected.
            for _ in range(120):
                battle = a.current_battle()
                if battle.result is not None:
                    break
                if (battle.active is not None
                        and battle.active.id == "tunnel_sapper"
                        and not battle.active.acted):
                    enemy = next((u for u in battle.units
                                  if u.team == "enemy" and u.alive), None)
                    if enemy:
                        a.execute({"kind": "act", "skill": "attack",
                                   "cell": list(enemy.pos)})
                        continue
                a.execute({"kind": "end"})
            self.assertEqual(a.session.fronts.active.result, "victory")
            self.assertEqual(a.active_scene()["id"], "after")
            self.assertIn("castle_tunnels", a.story.progress.completed)
            self.assertEqual([e["kind"] for e in a.story.events][-1], "victory")
            with self.assertRaises(RuleError):
                a.switch("gate")
            a.choose_story_option("mercy")
            self.assertTrue(a.story.progress.story_flags["mercy"])
            b = AuthoredSiegeController(content, bp, a.project_path,
                                        project=project)
            b.continue_game()
            self.assertEqual(b.story.recording(), a.story.recording())

    def test_modified_story_or_forged_narrative_journal_is_rejected(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            a = AuthoredSiegeController(content, bp, Path(tmp) / "project.game.json",
                                        project=project)
            a.new_game()
            a.choose_story_option("honor")
            altered_project = deepcopy(project)
            altered_project.story["scenes"][0]["text"] = "Altered prologue"
            with self.assertRaises(RuleError):
                AuthoredSiegeController(
                    content, bp, a.project_path, project=altered_project).continue_game()
            file = a.save_path
            data = json.loads(file.read_text(encoding="utf-8"))
            data["narrative"]["events"][0]["choice"] = "not_a_choice"
            body = {k: v for k, v in data["narrative"].items() if k != "digest"}
            data["narrative"]["digest"] = digest(body)
            file.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(RuleError):
                AuthoredSiegeController(
                    content, bp, a.project_path, project=project).continue_game()

    def test_legacy_siege_slot_without_story_is_still_readable(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.game.json"
            legacy = AuthoredSiegeController(content, bp, path)
            legacy.new_game()
            legacy.execute({"kind": "end"})
            a = AuthoredSiegeController(content, bp, path, project=project)
            a.continue_game()
            self.assertIsNone(a.active_scene())  # Intro isn't repeated mid-combat.
            a.save()
            b = AuthoredSiegeController(content, bp, path, project=project)
            b.continue_game()
            self.assertEqual(a.story.recording(), b.story.recording())
            self.assertIn("narrative", json.loads(a.save_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
