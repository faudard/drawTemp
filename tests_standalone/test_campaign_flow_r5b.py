"""R5.B gate: conditional campaign, persisted effects, audit and portable export."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.campaign import Campaign
from sporebound.campaign_flow import (audit_campaign, available_missions,
                                     inspect_campaign, settle, verify_save)
from sporebound.game_export4 import export_game
from sporebound.game_project import GameProject, load_slot, save_slot
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_session import PlayerSession


class CampaignFlowR5BTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.hero = next(unit.id for unit in self.content.missions["garden"].units
                         if unit.team == "player")
        self.project.campaign_flow = {
            "gates": {
                "hold": {"all": [
                    {"completed_mission": "garden"},
                    {"flag": "reputation_village", "gte": 2},
                ]},
            },
            "outcomes": {
                "garden": {"victory": [
                    {"kind": "add_flag", "flag": "reputation_village", "amount": 2},
                    {"kind": "set_flag", "flag": "fortification_gate", "value": "damaged"},
                    {"kind": "set_flag", "flag": "enemy_garrison", "value": "weakened"},
                    {"kind": "wound", "hero": self.hero, "wound": "arm_injury"},
                    {"kind": "gold", "amount": 25},
                ]},
            },
            "endings": {"retreat": {"flag": "reputation_village", "gte": 2}},
        }
        self.project.validate(self.content)

    def test_gate_and_outcome_in_unified_session_are_idempotent(self):
        session = GameSession.new(self.content, self.project, "main")
        session.progress.unlocked.append("hold")
        self.assertEqual(session.available_missions(), ["garden"])
        battle = session.progress.prepare(self.content, "garden")
        # Isolate the authenticated victory settlement boundary; do not store
        # this handcrafted result as a Battle replay.
        battle.result = "victory"
        session._commit(battle)
        self.assertIn("garden", session.progress.completed)
        self.assertIn("hold", session.available_missions())
        self.assertEqual(session.progress.story_flags["reputation_village"], 2)
        self.assertEqual(session.progress.story_flags["fortification_gate"], "damaged")
        self.assertEqual(session.progress.story_flags["enemy_garrison"], "weakened")
        self.assertIn("arm_injury", session.progress.heroes[self.hero].wounds)
        self.assertEqual(session.progress.flow_ledger, ["garden:victory"])
        report = session.campaign_inspector()
        self.assertIn("retreat", report["endings"])
        self.assertIn("reputation_village", report["reputation"])
        self.assertIn("fortification_gate", report["fortifications"])
        gold = session.progress.gold
        session._commit(battle)
        self.assertEqual(session.progress.gold, gold)
        self.assertEqual(session.progress.flow_ledger, ["garden:victory"])

    def test_saves_and_project_identity_must_match(self):
        session = GameSession.new(self.content, self.project, "main")
        progress = session.progress
        self.assertEqual(Campaign.from_dict({"version": 1, **asdict(progress)}), progress)
        with TemporaryDirectory() as dirname:
            path = Path(dirname) / "session.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())
            changed = deepcopy(self.project)
            changed.campaign_flow["gates"]["garden"] = {
                "flag": "reputation_village", "gte": 1}
            changed.validate(self.content)
            with self.assertRaisesRegex(RuleError, "incompatible"):
                GameSession.load(path, self.content, changed)
            profile = Path(dirname) / "profile.json"
            save_slot(profile, self.project, self.content, "main", 1, progress)
            self.assertEqual(load_slot(profile, self.project, self.content, "main", 1),
                             progress)
            with self.assertRaisesRegex(RuleError, "explicit migration"):
                load_slot(profile, changed, self.content, "main", 1)

    def test_atomic_outcomes_and_no_repeatable_rewards(self):
        progress = self.project.new_game("main", self.content)
        original = deepcopy(progress)
        changed = settle(progress, self.project.campaign_flow, "garden", "victory",
                         content=self.content)
        self.assertEqual(progress, original)
        self.assertEqual(changed.gold, 25)
        self.assertEqual(changed.flow_ledger, ["garden:victory"])
        again = settle(changed, self.project.campaign_flow, "garden", "victory",
                       content=self.content)
        self.assertEqual(again, changed)
        with self.assertRaises(RuleError):
            settle(progress, self.project.campaign_flow, "garden", "pending",
                   content=self.content)
        malformed = deepcopy(changed)
        malformed.flow_ledger.append("garden:victory")
        with self.assertRaises(RuleError):
            Campaign.from_dict({"version": 1, **asdict(malformed)})

    def test_legacy_saves_accept_only_legacy_project(self):
        legacy_project = GameProject.default(self.content)
        legacy = legacy_project.new_game("main", self.content)
        self.assertEqual(legacy.flow_digest, "")
        verify_save(legacy, legacy_project.campaign_flow)
        with self.assertRaisesRegex(RuleError, "explicit migration"):
            verify_save(legacy, self.project.campaign_flow)
        progress = self.project.new_game("main", self.content)
        progress.unlocked.append("hold")
        self.assertEqual(available_missions(progress, self.project.campaign_flow),
                         ["garden"])
        self.assertEqual(inspect_campaign(progress, self.project.campaign_flow)
                         ["missions"]["blocked"], ["hold"])

    def test_portable_export_contains_verified_qa_and_playable_runtime(self):
        report = audit_campaign(self.content, self.project, "main")
        self.assertEqual(report["errors"], [])
        with TemporaryDirectory() as dirname:
            root = Path(dirname)
            archive = export_game(self.content, self.project, root, root / "game.zip")
            with ZipFile(archive) as bundle:
                self.assertIn("game/campaign_qa.json", bundle.namelist())
                qa = json.loads(bundle.read("game/campaign_qa.json"))
                self.assertEqual(qa["reports"][0]["errors"], [])
                bundle.extractall(root / "isolated")
            script = (
                "from sporebound.model import Content;"
                "from sporebound.game_project import GameProject;"
                "from sporebound.game_session import GameSession;"
                "import json;"
                "c=Content.load('game/content.json');"
                "p=GameProject.load('game/project.game.json',c);"
                "s=GameSession.new(c,p,'main');"
                "assert s.available_missions()==['garden'];"
                "assert s.campaign_inspector()['missions']['available']==['garden']"
            )
            proc = subprocess.run([sys.executable, "-c", script],
                                  cwd=root / "isolated", capture_output=True,
                                  text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
