"""R60.B1 — original Creator showcase: real R53, R55, R51 integration."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.creator_examples.r53_hybrid import build_relais_hybride_r53
from drawtemp.creator_examples.r60_showcase import (
    CONTENT_REGIONS, ECONOMY_QUEST, MERCHANT, TITLE,
    author_showcase, build_sentinelles_ambre, systems_document,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.export.templates import TEMPLATES, create_template
from sporebound.game_session import GameSession, digest
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION
from sporebound.ui_layout_r51 import (
    NAMESPACE as UI_EXTENSION, catalog_from_project, project_layout,
)


def win_rpg(session, encounter):
    session.rpg_start(encounter)
    target = "loup" if encounter == "woods" else "gardien"
    session.rpg_action({
        "kind": "combo", "actor": session.rpg_state()["active"],
        "target": target, "combo": "lames_du_relais"})
    for _ in range(45):
        state = session.rpg_state()
        if state["result"] is not None:
            break
        session.rpg_action({
            "kind": "attack", "actor": state["active"], "target": target})
    if session.rpg_state()["result"] != "victory":
        raise AssertionError("Native RPG encounter did not end in victory")
    session.rpg_finish()


class R60HybridShowcaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content, cls.project = build_sentinelles_ambre()

    def test_native_factory_two_plus_regions_and_three_authoring_screens(self):
        self.assertEqual(self.project.title, TITLE)
        self.assertTrue(set(CONTENT_REGIONS) <= set(self.project.exploration))
        self.assertEqual(len(self.project.extensions[UI_EXTENSION]["data"]["layouts"]), 3)
        self.assertEqual(self.project.extensions[SYSTEMS_EXTENSION]["data"], systems_document())
        for scene in CONTENT_REGIONS:
            profile = self.project.game_modes["scenes"][scene]["profile"]
            self.assertEqual(profile["movement"], "FREE_REALTIME")
            self.assertEqual(profile["combat"], "RPG_TURN")
        self.assertEqual(self.project.game_modes["scenes"][
            "relais_ct_reference"], {"preset": "srpg"})
        self.assertEqual(self.content.to_dict()["version"], 1)
        self.assertEqual(self.project.to_dict()["version"], 1)
        self.assertEqual(
            GameProject.from_dict(self.project.to_dict(), self.content).to_dict(),
            self.project.to_dict())
        again_content, again_project = build_sentinelles_ambre()
        self.assertEqual(again_content.to_dict(), self.content.to_dict())
        self.assertEqual(again_project.to_dict(), self.project.to_dict())

    def test_studio_undo_redo_and_editable_creator_template(self):
        editor = author_showcase()
        final = editor.snapshot().to_dict()
        self.assertEqual(editor.revision, 4)  # one economy and three HUD transactions
        self.assertTrue(editor.snapshot().can_undo)
        editor.undo()
        self.assertNotIn("r60_inventory", editor.snapshot().to_dict()[
            "project"]["extensions"][UI_EXTENSION]["data"]["layouts"])
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict()["project"], final["project"])
        self.assertEqual(editor.snapshot().to_dict()["content"], final["content"])
        self.assertIn("hybrid_r60", TEMPLATES)
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "production"
            create_template("hybrid_r60", folder)
            opened = AuthoringSession.open(folder / "game.json")
            self.assertEqual(opened.snapshot().to_dict()["project"],
                             self.project.to_dict())
            self.assertEqual(opened.snapshot().to_dict()["content"],
                             self.content.to_dict())
            with self.assertRaises(Exception):
                create_template("hybrid_r60", folder)

    def test_declarative_hud_read_only_compact_and_wide(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        before = session.recording()
        catalog = catalog_from_project(self.project)
        compact = project_layout("r60_exploration", catalog, session, width=640)
        wide = project_layout("r60_exploration", catalog, session, width=1100)
        self.assertEqual((compact["columns"], wide["columns"]), (1, 2))
        self.assertEqual(compact["root"]["children"][1]["value"], "village")
        compact["root"]["children"][1]["value"] = "forged"
        self.assertEqual(project_layout(
            "r60_exploration", catalog, session, width=640)["root"][
                "children"][1]["value"], "village")
        self.assertEqual(session.recording(), before)
        bag = project_layout(
            "r60_inventory", catalog, session, width=640,
            inventory_view={"item_count": len(session.progress.inventory)})
        self.assertEqual(bag["root"]["children"][1]["value"],
                         len(session.progress.inventory))
        self.assertEqual(session.recording(), before)

    def test_economy_boutique_and_sidequest_save_reload_no_double_reward(self):
        for seed in (17, 31):
            with self.subTest(seed=seed):
                game = GameSession.new(self.content, self.project, "main", seed=seed)
                initial_gold = game.progress.gold
                for _ in range(4):
                    game.route_realtime_step(0, 0)
                self.assertEqual(game.system_state()["tick"], 4)
                self.assertEqual(game.system_state()["stocks"]["lantern"], 2)
                self.assertEqual(game.progress.inventory.get("lantern", 0), 0)
                game.route_transition("village_to_woods")
                with self.assertRaises(RuleError):
                    game.system_trade(MERCHANT, "buy", 1, "off_scene")
                win_rpg(game, "woods")
                self.assertEqual(game.progress.gold, initial_gold + 12)
                game.route_transition("woods_to_village")
                self.assertTrue(game.system_trade(MERCHANT, "buy", 2, "r60_buy_01"))
                self.assertEqual(game.progress.inventory["lantern"], 2)
                self.assertEqual(game.progress.gold, initial_gold + 2)
                self.assertEqual(game.system_state()["stocks"]["lantern"], 0)
                self.assertTrue(game.system_fulfill(ECONOMY_QUEST))
                self.assertEqual(game.progress.inventory["lantern"], 0)
                self.assertTrue(game.progress.story_flags["beacon_supplied"])
                receipt = game.recording()
                with TemporaryDirectory() as temp:
                    location = Path(temp) / "r60-save.json"
                    game.save(location)
                    loaded = GameSession.load(location, self.content, self.project)
                    self.assertEqual(loaded.recording(), receipt)
                    self.assertFalse(loaded.system_trade(
                        MERCHANT, "buy", 2, "r60_buy_01"))
                    self.assertFalse(loaded.system_fulfill(ECONOMY_QUEST))
                    self.assertEqual(loaded.recording(), receipt)
                    with self.assertRaises(RuleError):
                        loaded.system_trade(MERCHANT, "buy", 1, "r60_buy_01")
                    self.assertEqual(loaded.recording(), receipt)

    def test_rpg_to_ct_keeps_one_campaign_save_and_refuses_shop_in_combat(self):
        game = GameSession.new(self.content, self.project, "main", seed=17)
        game.route_transition("village_to_woods")
        win_rpg(game, "woods")
        game.route_transition("woods_to_crypt")
        win_rpg(game, "crypt")
        game.route_transition("crypt_to_ct")
        self.assertEqual(game.mode, "battle")
        self.assertEqual(game.party_hybrid_state()["phase"], "TACTICAL_CT")
        with self.assertRaises(RuleError):
            game.system_trade(MERCHANT, "buy", 1, "in_ct")
        checkpoint = game.recording()
        self.assertEqual(
            GameSession.from_recording(checkpoint, self.content, self.project).recording(),
            checkpoint)
        self.assertEqual(game.system_state()["tick"], 0)

    def test_modified_economy_with_recomputed_digest_rejected(self):
        game = GameSession.new(self.content, self.project, "main", seed=17)
        for _ in range(4):
            game.route_realtime_step(0, 0)
        authentic = game.recording()
        altered = deepcopy(authentic)
        altered["systems"]["stocks"]["lantern"] += 1
        altered["digest"] = digest({
            key: value for key, value in altered.items() if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(altered, self.content, self.project)
        self.assertEqual(game.recording(), authentic)

    def test_complete_headless_showcase_runs_native_ct(self):
        from examples.r60_production_showcase import run_showcase
        proof = run_showcase(seed=17)
        self.assertEqual(proof["slice"], "VS-60.B1")
        self.assertTrue(proof["ct_completed"])
        self.assertEqual(proof["gold_delta"], 60)
        self.assertTrue(proof["replay_roundtrip"])

    def test_r53_without_r60_additions_keeps_original_identity(self):
        old_content, old_project = build_relais_hybride_r53()
        self.assertNotIn(SYSTEMS_EXTENSION, old_project.extensions)
        self.assertNotIn(UI_EXTENSION, old_project.extensions)
        old_game = GameSession.new(old_content, old_project, "main", seed=17)
        self.assertNotIn("systems", old_game.recording())
        self.assertEqual(old_game.party_hybrid_state()["phase"], "EXPLORATION")


if __name__ == "__main__":
    unittest.main()
