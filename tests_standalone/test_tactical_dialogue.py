"""3.7.21E: tactical StoryBook decisions across battle checkpoint / resume."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError
from sporebound import story_authoring


def authored_fixture():
    data = Content.load(DEFAULT_CONTENT).to_dict()
    mission = next(row for row in data["missions"] if row["id"] == "garden")
    original = next(row for row in mission["triggers"]
                    if row["id"] == "spore_pulse")
    original["value"] = 0
    mission["triggers"].append({
        "id": "arrival", "condition": "tick", "value": 0,
        "actions": [{"kind": "message", "text": "A new threat approaches"}],
    })
    content = Content.from_dict(data)
    project = GameProject.default(content)
    project_data = project.to_dict()
    project_data["story"] = {
        "scenes": [
            {"id": "lever_question", "title": "Le choix du village",
             "speaker": "Jeanne", "text": "Préserver le village ?",
             "choices": [
                 {"id": "help", "label": "Protéger",
                  "effects": [{"kind": "set_flag",
                               "flag": "village_saved", "value": True},
                              {"kind": "gold", "amount": 12}],
                  "next_scene": "confirmation"},
                 {"id": "ignore", "label": "Ignorer",
                  "effects": [{"kind": "set_flag",
                               "flag": "village_saved", "value": False}]},
             ]},
            {"id": "confirmation", "title": "Résolution",
             "speaker": "Jeanne", "text": "En avant.",
             "choices": [
                 {"id": "continue", "label": "Reprendre",
                  "effects": [{"kind": "add_flag", "flag": "reputation",
                               "amount": 1}]},
             ]},
            {"id": "second_event", "title": "Des renforts ?",
             "speaker": "Officier", "text": "Nos ordres ?",
             "choices": [{"id": "wait", "label": "Attendre"}]},
        ],
        "during_tactical_event": {
            "garden/spore_pulse": "lever_question",
            "garden/arrival": "second_event",
        },
    }
    project = GameProject.from_dict(project_data, content)
    return content, project


class TacticalDialogueTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = authored_fixture()

    def test_link_validation_rejects_dangling_trigger_or_scene(self):
        original = self.project.to_dict()
        with self.assertRaises(RuleError):
            story_authoring.set_tactical_scene(
                self.project, self.content, "garden", "nonexistent",
                "lever_question")
        with self.assertRaises(RuleError):
            story_authoring.set_tactical_scene(
                self.project, self.content, "garden", "spore_pulse",
                "nonexistent")
        self.assertEqual(self.project.to_dict(), original)
        changed = story_authoring.set_tactical_scene(
            self.project, self.content, "garden", "spore_pulse", "")
        self.assertNotIn("garden/spore_pulse",
                         changed.story.get("during_tactical_event", {}))
        self.assertIn("garden/spore_pulse",
                      self.project.story["during_tactical_event"])

    def test_two_trigger_dialogues_are_queued_in_engine_order(self):
        session = GameSession.new(self.content, self.project, "main")
        battle = session.start_mission("garden")
        self.assertEqual(battle.fired[:2], ["spore_pulse", "arrival"])
        self.assertEqual(session.tactical_story_pending, "lever_question")
        self.assertEqual(session.tactical_story_queue, ["second_event"])
        self.assertEqual(session.tactical_scene()["speaker"], "Jeanne")
        self.assertEqual([c["id"] for c in session.tactical_choices()],
                         ["help", "ignore"])
        self.assertFalse(session.finalized)

        with self.assertRaises(RuleError):
            session.execute({"kind": "end", "facing": [0, 1]})
        with self.assertRaises(RuleError):
            session.choose_tactical_story_option("unavailable")
        self.assertEqual(session.progress.story_flags.get("village_saved"), None)

        session.choose_tactical_story_option("help")
        self.assertEqual(session.tactical_story_pending, "confirmation")
        self.assertEqual(session.tactical_story_queue, ["second_event"])
        self.assertTrue(session.progress.story_flags["village_saved"])
        self.assertEqual(session.progress.gold, 12)
        self.assertEqual(session.progress.story_pending, "")
        session.choose_tactical_story_option("continue")
        self.assertEqual(session.tactical_story_pending, "second_event")
        self.assertEqual(session.progress.story_flags["reputation"], 1)
        session.choose_tactical_story_option("wait")
        self.assertEqual(session.tactical_story_pending, "")
        self.assertEqual(session.tactical_story_queue, [])
        self.assertEqual(session.progress.story_history[-3:], [
            {"scene": "lever_question", "choice": "help"},
            {"scene": "confirmation", "choice": "continue"},
            {"scene": "second_event", "choice": "wait"}])
        session.execute({"kind": "end", "facing": [0, 1]})
        self.assertEqual(session.tactical_story_pending, "")

    def test_unresolved_dialogue_survives_replay_and_choice_applies_once(self):
        session = GameSession.new(self.content, self.project, "main")
        session.start_mission("garden")
        before = session.recording()
        self.assertIn("tactical_story_pending", before)
        self.assertEqual(before["tactical_story_queue"], ["second_event"])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "battle_save.json"
            session.save(path)
            loaded = GameSession.load(path, self.content, self.project)
        self.assertEqual(loaded.recording(), before)
        self.assertEqual(loaded.battle.digest(), session.battle.digest())
        loaded.choose_tactical_story_option("ignore")
        self.assertEqual(loaded.progress.story_flags["village_saved"], False)
        loaded.choose_tactical_story_option("wait")
        self.assertEqual(loaded.tactical_story_pending, "")
        self.assertFalse(loaded.progress.story_flags["village_saved"])
        self.assertEqual(loaded.progress.story_history.count(
            {"scene": "lever_question", "choice": "ignore"}), 1)
        restored = GameSession.from_recording(
            loaded.recording(), self.content, self.project)
        self.assertEqual(restored.recording(), loaded.recording())
        self.assertEqual(restored.tactical_story_pending, "")

    def test_pending_tactical_story_defers_battle_settlement(self):
        session = GameSession.new(self.content, self.project, "main")
        session.start_mission("garden")
        session.battle.result = "victory"  # a synthetic settlement boundary
        session._settle()
        self.assertFalse(session.finalized)
        self.assertEqual(session.progress.completed, [])
        session.choose_tactical_story_option("ignore")
        session.choose_tactical_story_option("wait")
        self.assertTrue(session.finalized)
        self.assertEqual(session.progress.completed, ["garden"])

    def test_corrupt_pending_checkpoint_is_rejected(self):
        session = GameSession.new(self.content, self.project, "main")
        session.start_mission("garden")
        original = session.recording()
        for corruption in (
            {"tactical_story_pending": "unknown"},
            {"tactical_story_queue": ["unknown"]},
            {"mode": "campaign"},
        ):
            with self.subTest(corruption=corruption):
                data = deepcopy(original)
                data.update(corruption)
                data["digest"] = digest({k: v for k, v in data.items()
                                         if k != "digest"})
                with self.assertRaises(RuleError):
                    GameSession.from_recording(data, self.content, self.project)


if __name__ == "__main__":
    unittest.main()
