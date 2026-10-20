"""R51.B2 — typed gauges, keyboard focus order and authentic title menu."""
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r51_layout_draft import (
    new_layout, check_layout, edit_layout, edit_gauge_bindings,
    edit_focus_order, move_focus, next_focus,
)
from drawtemp.player.controller import PlayerController
from drawtemp.player.r51_hud import menu_for_player, perform_menu_intent
from sporebound.ui_layout_r51 import UiLayoutError


def authored_project(project, layout, layout_id="title"):
    project.extensions["org.drawtemp.ui"] = {
        "schema_version": 1,
        "data": {"version": 1, "layouts": {layout_id: layout}},
    }
    return project


class GaugeFocusTests(unittest.TestCase):
    def test_gauge_binding_is_typed_and_does_not_mutate_original(self):
        layout = edit_layout(new_layout(), "add", target="root", widget={
            "id": "health", "type": "gauge",
            "binding": {"path": "combat.active_hp", "type": "int"},
            "max_binding": {"path": "combat.active_max_hp", "type": "int"},
        })
        original = deepcopy(layout)
        updated = edit_gauge_bindings(
            layout, "health", "session.seed", "combat.active_max_hp")
        self.assertEqual(layout, original)
        self.assertEqual(updated["root"]["children"][-1]["binding"],
                         {"path": "session.seed", "type": "int"})
        for path in ("combat.focus", "__class__", "", None, True):
            with self.subTest(path=path), self.assertRaises(UiLayoutError):
                edit_gauge_bindings(layout, "health", path,
                                    "combat.active_max_hp")
        with self.assertRaises(UiLayoutError):
            edit_gauge_bindings(layout, "welcome", "session.seed",
                                "combat.active_max_hp")
        self.assertEqual(layout, original)

    def test_explicit_keyboard_order_reordering_and_skip(self):
        layout = edit_layout(new_layout(), "add", target="root", widget={
            "id": "extra", "type": "button", "text": "Inventaire",
            "action": "combat.open_inventory"})
        before = deepcopy(layout)
        custom = edit_focus_order(layout, ["extra", "main_action"])
        self.assertEqual(custom["focus_order"], ["extra", "main_action"])
        moved = move_focus(custom, "main_action", "up")
        self.assertEqual(moved["focus_order"], ["main_action", "extra"])
        self.assertEqual(next_focus(moved), "main_action")
        self.assertEqual(next_focus(moved, "main_action"), "extra")
        self.assertEqual(next_focus(moved, "extra"), "main_action")
        self.assertEqual(next_focus(moved, reverse=True), "extra")
        self.assertEqual(next_focus(moved, "extra", enabled={"main_action"}),
                         "main_action")
        self.assertIsNone(next_focus(moved, enabled=set()))
        self.assertEqual(layout, before)
        for invalid in (
            ["main_action"], ["main_action", "extra", "extra"],
            ["wrong", "extra"], ["main_action", "welcome"],
        ):
            with self.subTest(order=invalid), self.assertRaises(UiLayoutError):
                edit_focus_order(layout, invalid)
        with self.assertRaises(UiLayoutError):
            move_focus(layout, "welcome", "up")
        with self.assertRaises(UiLayoutError):
            move_focus(layout, "main_action", "up")
        self.assertEqual(layout, before)

    def test_new_menu_template_always_has_new_game(self):
        layout = new_layout("MENU")
        self.assertEqual(check_layout(layout), layout)
        self.assertIn("menu.new_game",
                      [node["action"] for node in layout["root"]["children"]
                       if node["type"] == "button"])
        self.assertEqual(len(layout["focus_order"]), 2)


class AuthoredMenuTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_legacy_title_falls_back_without_mutating_state(self):
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            before = player.state()
            self.assertEqual(menu_for_player(player, 800),
                             {"available": False, "error": ""})
            with self.assertRaises(UiLayoutError):
                perform_menu_intent(player, "menu.new_game")
            self.assertEqual(player.state(), before)

    def test_menu_read_only_and_new_game_through_existing_controller(self):
        layout = new_layout("MENU")
        authored_project(self.project, layout)
        self.project.validate(self.content)
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            before = player.state()
            narrow = menu_for_player(player, 560)
            wide = menu_for_player(player, 1240)
            self.assertTrue(narrow["available"])
            self.assertEqual(narrow["projection"]["columns"], 1)
            self.assertEqual(wide["projection"]["columns"], 2)
            self.assertEqual(narrow["permitted_actions"], ["menu.new_game"])
            self.assertEqual(player.state(), before)
            narrow["projection"]["root"]["children"][1]["text"] = "tampered"
            self.assertNotEqual(
                menu_for_player(player, 560)["projection"]["root"]
                ["children"][1]["text"], "tampered")
            for bad in ("menu.continue", "menu.quit", "menu.options",
                        "combat.end_turn", "__import__", ""):
                with self.subTest(intent=bad), self.assertRaises(UiLayoutError):
                    perform_menu_intent(player, bad)
            self.assertEqual(player.state(), before)
            perform_menu_intent(player, "menu.new_game")
            self.assertNotEqual(player.state()["screen"], "title")
            self.assertFalse(menu_for_player(player, 560)["available"])

    def test_static_title_menu_fails_closed_on_bindings_or_missing_new_game(self):
        layout = new_layout("MENU")
        layout["root"]["children"][0] = {
            "id": "main_action", "type": "text",
            "binding": {"path": "session.campaign_id", "type": "str"}}
        layout["focus_order"] = ["continue_action"]
        self.assertEqual(check_layout(layout), layout)
        authored_project(self.project, layout)
        self.project.validate(self.content)
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            result = menu_for_player(player, 800)
            self.assertFalse(result["available"])
            self.assertIn("cannot use live", result["error"])
        layout = new_layout("MENU")
        layout["root"]["children"][0]["action"] = "menu.quit"
        self.assertEqual(check_layout(layout), layout)
        authored_project(self.project, layout)
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            result = menu_for_player(player, 800)
            self.assertFalse(result["available"])
            self.assertIn("must offer New Game", result["error"])

    def test_bad_width_rejected_before_looking_at_title(self):
        authored_project(self.project, new_layout("MENU"))
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            for width in (-1, 0, True, 20000, "800"):
                with self.subTest(width=width), self.assertRaises(UiLayoutError):
                    menu_for_player(player, width)


if __name__ == "__main__":
    unittest.main()
