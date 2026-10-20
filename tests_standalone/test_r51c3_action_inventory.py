"""R51.C3: real R32 HUD and campaign equipment; no new simulation owner."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.player.r51_action import (
    action_hud_for_player, perform_action_intent, ACTION_FRAMES)
from drawtemp.player.r51_screens import (
    authored_screen, perform_campaign_equip, perform_campaign_unequip)
from drawtemp.sdk.r40_starters import create_starter_pair
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r51_layout_draft import new_layout, check_layout
from sporebound.ui_layout_r51 import (
    NAMESPACE, UiLayoutError, catalog_from_project, project_layout)


def with_layouts(content, project):
    project.extensions[NAMESPACE] = {
        "schema_version": 1,
        "data": {"version": 1, "layouts": {
            "platform_hud": new_layout("HUD_ACTION"),
            "player_inventory": new_layout("INVENTORY"),
        }}
    }
    project.validate(content)
    return project


class R51C3PlayerTests(unittest.TestCase):
    def test_studio_action_template_has_only_fixed_r32_intents(self):
        layout = check_layout(new_layout("HUD_ACTION"))
        actions = [row["action"] for row in layout["root"]["children"]
                   if row["type"] == "button"]
        self.assertEqual(set(actions), set(ACTION_FRAMES))
        self.assertIn("action.scene_title",
                      [row["binding"]["path"]
                       for row in layout["root"]["children"]
                       if "binding" in row])

    def test_real_platform_frame_is_canonical_and_nonduplicating(self):
        content, project = create_starter_pair("r40-metroidvania")
        with_layouts(content, project)
        with TemporaryDirectory() as folder:
            player = PlayerController(content, project, "main",
                                      Path(folder) / "save", seed=31)
            self.assertFalse(action_hud_for_player(player, 800)["available"])
            player.new_game()
            self.assertEqual(player.state()["screen"], "platform")
            before = player.session.recording()
            before_revision = player.session.snapshot().revision
            hud = action_hud_for_player(player, 850)
            self.assertTrue(hud["available"], hud)
            self.assertTrue(hud["single_frame"])
            self.assertEqual(hud["projection"]["kind"], "HUD_ACTION")
            self.assertIn("action.step_right", hud["permitted_actions"])
            self.assertNotIn("action.attack", hud["permitted_actions"])
            self.assertEqual(player.session.recording(), before)
            with self.assertRaises(UiLayoutError):
                perform_action_intent(player, "action.attack")
            for bad in ("__import__", "action.travel", True, ""):
                with self.subTest(intent=bad), self.assertRaises(UiLayoutError):
                    perform_action_intent(player, bad)
            self.assertEqual(player.session.recording(), before)
            perform_action_intent(player, "action.step_right")
            self.assertEqual(player.session.snapshot().revision,
                             before_revision + 1)
            self.assertEqual(player.state()["platform"]["state"]["tick"], 1)
            self.assertNotEqual(player.session.recording(), before)
            previous = player.session.recording()
            action_hud_for_player(player, 850)
            self.assertEqual(player.session.recording(), previous)

    def test_campaign_inventory_equip_and_unequip_use_r1(self):
        content, project = reference_project()
        with_layouts(content, project)
        with TemporaryDirectory() as folder:
            player = PlayerController(content, project, "main",
                                      Path(folder) / "save", seed=18)
            player.new_game()
            self.assertEqual(player.state()["screen"], "dialogue")
            self.assertFalse(authored_screen(player, "INVENTORY", 800)["available"])
            player.choose("enter")
            self.assertEqual(player.state()["screen"], "campaign")
            before = player.session.recording()
            inventory = authored_screen(player, "INVENTORY", 800)
            self.assertTrue(inventory["available"], inventory)
            self.assertEqual(inventory["context"], "campaign")
            self.assertFalse(inventory["can_use"])
            self.assertTrue(inventory["can_equip"])
            self.assertEqual(inventory["projection"]["kind"], "INVENTORY")
            self.assertEqual(player.session.recording(), before)
            for bad in ("unknown", "", "__dict__", True):
                with self.subTest(item=bad), self.assertRaises(UiLayoutError):
                    perform_campaign_equip(player, bad)
            for bad in ("helmet", "", "__dict__", True):
                with self.subTest(slot=bad), self.assertRaises(UiLayoutError):
                    perform_campaign_unequip(player, bad)
            self.assertEqual(player.session.recording(), before)
            if inventory["items"]:
                item = inventory["items"][0]
                before_revision = player.session.snapshot().revision
                perform_campaign_equip(player, item["id"])
                self.assertEqual(player.session.snapshot().revision,
                                 before_revision + 1)
                updated = authored_screen(player, "INVENTORY", 800)
                self.assertEqual(updated["context"], "campaign")
                if updated["equipped"].get(item["slot"]) == item["id"]:
                    perform_campaign_unequip(player, item["slot"])
                    self.assertEqual(player.session.snapshot().revision,
                                     before_revision + 2)
            self.assertFalse(action_hud_for_player(player, 800)["available"])

    def test_malformed_action_layout_falls_back_and_replay_unchanged(self):
        content, project = create_starter_pair("r40-metroidvania")
        with_layouts(content, project)
        layout = project.extensions[NAMESPACE]["data"]["layouts"]["platform_hud"]
        layout["root"]["children"][-1]["action"] = "menu.quit"
        project.validate(content)
        with TemporaryDirectory() as folder:
            player = PlayerController(content, project, "main", folder)
            player.new_game()
            before = player.session.recording()
            self.assertFalse(action_hud_for_player(player, 800)["available"])
            with self.assertRaises(UiLayoutError):
                perform_action_intent(player, "action.step_right")
            self.assertEqual(player.session.recording(), before)

    def test_typed_r32_binding_rejects_invalid_injection(self):
        content, project = create_starter_pair("r40-metroidvania")
        with_layouts(content, project)
        player = PlayerController(content, project, "main", "/tmp/r51-c3-unused")
        # No file is written because we only use the project schema and a GameSession.
        from sporebound.game_session import GameSession
        game = GameSession.new(content, project, "main", seed=3)
        layouts = catalog_from_project(project)
        with self.assertRaises(UiLayoutError):
            project_layout("platform_hud", layouts, game, width=800)
        with self.assertRaises(UiLayoutError):
            project_layout("platform_hud", layouts, game, width=800,
                           action_view={"scene_title": True})


class R51C3QtContractTests(unittest.TestCase):
    def test_main_qml_displays_real_buttons_with_legacy_fallback(self):
        src = (Path(__file__).parents[1] /
               "drawtemp/player/Main.qml").read_text(encoding="utf-8")
        bridge = (Path(__file__).parents[1] /
                  "drawtemp/player/qt_app.py").read_text(encoding="utf-8")
        self.assertIn('objectName: "r51-player-action-hud"', src)
        self.assertIn('objectName: "r51-action-hud-toggle"', src)
        self.assertIn("player.authoredActionIntent(action)", src)
        self.assertIn('objectName: "r51-equip-" + modelData.id', src)
        self.assertIn('objectName: "r51-unequip-" + modelData', src)
        self.assertIn("player.authoredCampaignEquip(modelData.id)", src)
        self.assertIn("player.authoredCampaignUnequip(modelData)", src)
        self.assertIn("player.platformPulse(move, jump, attack)", src)
        self.assertIn("def authoredActionHud(self, width):", bridge)
        self.assertIn("def authoredCampaignUnequip(self, slot):", bridge)


if __name__ == "__main__":
    unittest.main()
