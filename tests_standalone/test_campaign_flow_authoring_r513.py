"""R5.13 visual authoring model, runtime parity and global undo/redo gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.campaign_flow import audit_campaign, inspect_campaign, settle
from sporebound.campaign_flow_authoring import (
    build_effect, change_condition, change_effect, condition_for,
    effect_fields, outcome_effects, preview_condition)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.studio_transaction import StudioHistory


class VisualCampaignAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.initial = deepcopy(self.project.to_dict())

    def test_author_nested_tree_and_endings_without_json(self):
        p = change_condition(self.project, self.content, "gate", "hold",
                             "replace", kind="completed_mission", key="garden")
        p = change_condition(p, self.content, "gate", "hold", "wrap", operator="all")
        p = change_condition(p, self.content, "gate", "hold", "append",
                             kind="flag_gte", key="trust_village", value="2")
        p = change_condition(p, self.content, "gate", "hold", "wrap",
                             path=(("all", 1),), operator="any")
        p = change_condition(p, self.content, "gate", "hold", "append",
                             path=(("all", 1),), kind="gold_gte", value="250")
        p = change_condition(p, self.content, "gate", "hold", "wrap",
                             path=(("all", 1), ("any", 1)), operator="not")
        self.assertEqual(condition_for(p, "gate", "hold"), {
            "all": [
                {"completed_mission": "garden"},
                {"any": [
                    {"flag": "trust_village", "gte": 2},
                    {"not": {"gold_gte": 250}},
                ]},
            ],
        })
        q = change_condition(p, self.content, "ending", "peace", "replace",
                             kind="flag_eq", key="truce_signed", value="true")
        self.assertEqual(condition_for(q, "ending", "peace"),
                         {"flag": "truce_signed", "eq": True})
        session = GameSession.new(self.content, q, "main")
        session.progress.unlocked.append("hold")
        self.assertEqual(session.available_missions(), ["garden"])
        session.progress.completed.append("garden")
        self.assertIn("hold", session.available_missions())
        self.assertFalse(preview_condition(q, "ending", "peace",
                                           session.progress)["matches"])
        session.progress.story_flags["truce_signed"] = True
        self.assertIn("peace", session.campaign_inspector()["endings"])
        self.assertEqual(self.project.to_dict(), self.initial)

    def test_reorder_effects_and_idempotent_runtime_consequences(self):
        p = change_effect(
            self.project, self.content, "garden", "victory", "add",
            effect=build_effect("add_flag", "supplies_player", "3",
                                content=self.content))
        p = change_effect(
            p, self.content, "garden", "victory", "add",
            effect=build_effect("set_flag", "fortification_gate", "open",
                                content=self.content))
        p = change_effect(
            p, self.content, "garden", "victory", "add",
            effect=build_effect("gold", value="25", content=self.content))
        self.assertEqual(len(outcome_effects(p, "garden", "victory")), 3)
        p = change_effect(p, self.content, "garden", "victory",
                          "move", index=2, destination=0)
        self.assertEqual([effect["kind"] for effect in
                          outcome_effects(p, "garden", "victory")],
                         ["gold", "add_flag", "set_flag"])
        p = change_effect(p, self.content, "garden", "victory",
                          "replace", index=1,
                          effect=build_effect("add_flag", "supplies_player", "5",
                                              content=self.content))
        p = change_effect(p, self.content, "garden", "victory", "delete", index=2)
        progress = p.new_game("main", self.content)
        original = deepcopy(progress)
        rewarded = settle(progress, p.campaign_flow, "garden", "victory",
                          content=self.content)
        self.assertEqual(progress, original)
        self.assertEqual(rewarded.gold, 25)
        self.assertEqual(rewarded.story_flags["supplies_player"], 5)
        self.assertEqual(settle(rewarded, p.campaign_flow, "garden", "victory",
                                content=self.content), rewarded)
        self.assertEqual(rewarded.flow_ledger, ["garden:victory"])

    def test_effect_form_roundtrips_supported_kinds(self):
        hero = next(unit.id for unit in self.content.missions["garden"].units
                    if unit.team == "player")
        equipment = next(iter(self.content.equipment))
        examples = [
            ("set_flag", "fortification_gate", "open"),
            ("set_flag", "allies_won", "true"),
            ("add_flag", "supplies_player", "-2"),
            ("unlock_mission", "escape", ""),
            ("recruit_hero", hero, ""),
            ("grant_item", equipment, "2"),
            ("equip_hero", hero, equipment),
            ("gold", "", "-5"),
            ("wound", hero, "arm_injury"),
            ("heal_wound", hero, "leg_injury"),
        ]
        for kind, a, b in examples:
            with self.subTest(kind=kind):
                effect = build_effect(kind, a, b, content=self.content)
                self.assertEqual(effect_fields(effect), (kind, a, b))

    def test_invalid_actions_do_not_mutate_editor_or_create_history(self):
        history = StudioHistory(self.content.to_dict(), self.project)
        for invalid in (
            lambda: change_condition(self.project, self.content, "gate", "ghost",
                                     "replace", kind="gold_gte", value="1"),
            lambda: change_condition(self.project, self.content, "ending", "bad space",
                                     "replace", kind="gold_gte", value="1"),
            lambda: change_condition(self.project, self.content, "gate", "hold",
                                     "append", kind="flag_eq", key="trust", value="1"),
            lambda: change_effect(self.project, self.content, "garden", "victory",
                                  "delete", index=0),
            lambda: build_effect("grant_item", "ghost", "2", content=self.content),
            lambda: build_effect("wound", "ghost", "arm_injury",
                                 content=self.content),
            lambda: build_effect("gold", value="not_int", content=self.content),
        ):
            with self.assertRaises(RuleError):
                invalid()
        self.assertFalse(history.record(self.content.to_dict(), self.project))
        self.assertEqual(self.project.to_dict(), self.initial)

    def test_global_history_save_and_restore_matches_player(self):
        history = StudioHistory(self.content.to_dict(), self.project)
        p = change_condition(self.project, self.content, "gate", "hold",
                             "replace", kind="completed_mission", key="garden")
        self.assertTrue(history.record(self.content.to_dict(), p))
        p = change_effect(p, self.content, "garden", "victory", "add",
                          effect=build_effect("gold", value="20",
                                              content=self.content))
        self.assertTrue(history.record(self.content.to_dict(), p))
        first_doc, back = history.undo()
        self.assertEqual(outcome_effects(back, "garden", "victory"), [])
        self.assertEqual(condition_for(back, "gate", "hold"),
                         {"completed_mission": "garden"})
        self.assertTrue(history.can_redo)
        second_doc, restored = history.redo()
        self.assertEqual(outcome_effects(restored, "garden", "victory"),
                         [{"kind": "gold", "amount": 20}])
        self.assertEqual(first_doc, second_doc)
        self.assertEqual(restored.to_dict(), p.to_dict())
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.game.json"
            restored.save(path, self.content)
            reloaded = GameProject.load(path, self.content)
            self.assertEqual(reloaded.to_dict(), restored.to_dict())
            session = GameSession.new(self.content, reloaded, "main")
            self.assertEqual(session.available_missions(), ["garden"])
            report = audit_campaign(self.content, reloaded, "main")
            self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
