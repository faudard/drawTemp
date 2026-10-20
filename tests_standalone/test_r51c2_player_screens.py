"""R51.C2 — actual R1 dialogue/inventory projection and fail-closed actions."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.player.r51_hud import hud_for_player
from drawtemp.player.r51_screens import (
    authored_screen, perform_dialogue_advance, perform_inventory_use,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r51_layout_draft import new_layout, check_layout, edit_layout
from sporebound.game_session import GameSession
from sporebound.ui_layout_r51 import (
    NAMESPACE, UiLayoutError, catalog_from_project, project_layout,
)


def make_project(content, project):
    hud = edit_layout(new_layout("HUD_CT"), "add", target="root", widget={
        "id": "inventory", "type": "button",
        "text": "Ouvrir le sac", "action": "combat.open_inventory",
    })
    project.extensions[NAMESPACE] = {
        "schema_version": 1,
        "data": {"version": 1, "layouts": {
            "dialogue": new_layout("DIALOGUE"),
            "inventory": new_layout("INVENTORY"),
            "hud_ct": hud,
        }},
    }
    project.validate(content)
    return project


class R51C2ScreenTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_new_screen_templates_have_real_bindings_and_intents(self):
        dialogue = check_layout(new_layout("DIALOGUE"))
        inventory = check_layout(new_layout("INVENTORY"))
        assert dialogue["kind"] == "DIALOGUE"
        names = {node["binding"]["path"] for node in
                 dialogue["root"]["children"] if "binding" in node}
        self.assertEqual(names, {"dialogue.title", "dialogue.speaker",
                                 "dialogue.text", "dialogue.progress"})
        self.assertEqual(inventory["root"]["children"][1]["binding"]["path"],
                         "inventory.item_count")
        self.assertEqual(inventory["root"]["children"][-1]["action"],
                         "inventory.close")

    def test_canonical_session_scalar_fail_closed(self):
        make_project(self.content, self.project)
        game = GameSession.new(self.content, self.project, "main")
        catalog = catalog_from_project(self.project)
        original = game.recording()
        with self.assertRaises(UiLayoutError):
            project_layout("dialogue", catalog, game, width=800)
        with self.assertRaises(UiLayoutError):
            project_layout("inventory", catalog, game, width=800)
        with self.assertRaises(UiLayoutError):
            project_layout("dialogue", catalog, game, width=800, dialogue_view={
                "title": "a", "speaker": "b", "text": "c", "progress": 42,
            })
        with self.assertRaises(UiLayoutError):
            project_layout("inventory", catalog, game, width=800,
                           inventory_view={"item_count": True})
        self.assertEqual(game.recording(), original)

    def test_real_reference_dialogue_is_read_only_and_choice_still_works(self):
        make_project(self.content, self.project)
        with TemporaryDirectory() as folder:
            player = PlayerController(self.content, self.project, "main", folder)
            self.assertFalse(authored_screen(player, "DIALOGUE", 800)["available"])
            player.new_game()
            self.assertEqual(player.state()["screen"], "dialogue")
            recording = player.session.recording()
            before = player.session.snapshot().revision
            screen = authored_screen(player, "DIALOGUE", 800)
            self.assertTrue(screen["available"], screen)
            self.assertEqual(screen["projection"]["kind"], "DIALOGUE")
            self.assertIn("À la lisière",
                          [node.get("value") for node in screen["projection"]
                           ["root"]["children"]])
            self.assertEqual(screen["permitted_actions"], [])
            self.assertEqual(player.session.snapshot().revision, before)
            self.assertEqual(player.session.recording(), recording)
            with self.assertRaises(UiLayoutError):
                perform_dialogue_advance(player)
            self.assertEqual(player.session.recording(), recording)
            screen["projection"]["root"]["children"][1]["value"] = "FALSIFIÉ"
            self.assertNotIn(
                "FALSIFIÉ",
                [node.get("value") for node in
                 authored_screen(player, "DIALOGUE", 800)["projection"]["root"]["children"]]
            )
            player.choose("enter")
            self.assertFalse(authored_screen(player, "DIALOGUE", 800)["available"])

    def test_real_battle_inventory_view_and_disallowed_item_do_not_commit(self):
        make_project(self.content, self.project)
        with TemporaryDirectory() as folder:
            player = PlayerController(self.content, self.project, "main", folder)
            player.new_game()
            player.choose("enter")
            player.start_mission(MISSION)
            self.assertEqual(player.state()["screen"], "battle")
            before_recording = player.session.recording()
            before_revision = player.session.snapshot().revision
            screen = authored_screen(player, "INVENTORY", 820)
            self.assertTrue(screen["available"], screen)
            self.assertEqual(screen["projection"]["kind"], "INVENTORY")
            self.assertEqual(screen["permitted_actions"], ["inventory.close"])
            self.assertTrue(screen["items"])
            self.assertEqual(screen["projection"]["root"]["children"][1]["value"],
                             sum(row["count"] for row in screen["items"]))
            self.assertEqual(player.session.recording(), before_recording)
            self.assertEqual(player.session.snapshot().revision, before_revision)
            for bad in ("nonexistent", "", "__class__"):
                with self.subTest(bad=bad), self.assertRaises(UiLayoutError):
                    perform_inventory_use(player, bad)
            self.assertEqual(player.session.recording(), before_recording)
            actual = authored_screen(player, "INVENTORY", 820)
            self.assertEqual(actual["items"], screen["items"])
            screen["items"][0]["count"] = -987
            self.assertNotEqual(
                authored_screen(player, "INVENTORY", 820)["items"][0]["count"],
                -987)
            ct = hud_for_player(player, 820)
            self.assertTrue(ct["available"])

    def test_missing_context_or_bad_inputs_deny_by_default(self):
        make_project(self.content, self.project)
        with TemporaryDirectory() as folder:
            player = PlayerController(self.content, self.project, "main", folder)
            for kind in ("MENU", "HUD_ACTION", "not-a-kind", None):
                with self.subTest(kind=kind), self.assertRaises(UiLayoutError):
                    authored_screen(player, kind, 800)
            for width in (-1, 0, True, 20000, "850"):
                with self.subTest(width=width), self.assertRaises(UiLayoutError):
                    authored_screen(player, "DIALOGUE", width)
            self.assertFalse(authored_screen(player, "INVENTORY", 800)["available"])
            with self.assertRaises(UiLayoutError):
                perform_inventory_use(player, "potion")


class R51C2QmlContractTests(unittest.TestCase):
    def test_qt_player_dialogue_inventory_routes_and_fallbacks(self):
        root = Path(__file__).parents[1]
        qml = (root / "drawtemp/player/Main.qml").read_text(encoding="utf-8")
        bridge = (root / "drawtemp/player/qt_app.py").read_text(encoding="utf-8")
        self.assertIn('objectName: "r51-player-dialogue"', qml)
        self.assertIn('objectName: "r51-inventory-overlay"', qml)
        self.assertIn('objectName: "r51-item-" + modelData.id', qml)
        self.assertIn('visible: root.authoredDialoguePayload.available !== true', qml)
        self.assertIn("root.authoredInventoryOpen = false", qml)
        self.assertIn('sequence: "Escape"', qml)
        self.assertIn("player.authoredDialogueAdvance()", qml)
        self.assertIn("player.authoredInventoryUse(modelData.id)", qml)
        self.assertIn("def authoredScreen(self, kind, width):", bridge)
        self.assertIn("def authoredInventoryUse(self, item_id):", bridge)


if __name__ == "__main__":
    unittest.main()
