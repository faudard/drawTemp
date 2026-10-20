"""R51.B: widget editing, responsive preview and Player command safety."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r51_layout_authoring import LayoutAuthoring
from drawtemp.studio.r51_layout_draft import (
    new_layout, check_layout, edit_layout, edit_breakpoints, editor_sample,
)
from drawtemp.player.controller import PlayerController
from drawtemp.player.r51_hud import hud_for_player, perform_ui_intent
from sporebound.ui_layout_r51 import UiLayoutError


class LayoutDraftTests(unittest.TestCase):
    def test_template_and_responsive_preview_are_non_executable(self):
        layout = new_layout()
        self.assertEqual(check_layout(layout), layout)
        original = deepcopy(layout)
        small = editor_sample(layout, 400)
        wide = editor_sample(layout, 1250)
        self.assertTrue(small["sample"])
        self.assertEqual(small["columns"], 1)
        self.assertEqual(wide["columns"], 2)
        self.assertEqual(layout, original)
        self.assertEqual(small["root"]["children"][0]["text"], "Interface personnalisable")

    def test_add_edit_reorder_remove_and_focus_are_atomic(self):
        original = new_layout()
        added = edit_layout(original, "add", target="root", widget={
            "id": "second_action", "type": "button", "text": "Terminer",
            "action": "combat.end_turn"})
        self.assertEqual(original["focus_order"], ["main_action"])
        self.assertEqual(added["focus_order"], ["main_action", "second_action"])
        modified = edit_layout(added, "update", target="second_action", changes={
            "id": "finish", "text": "Terminer le tour",
            "action": "combat.end_turn"})
        self.assertEqual(modified["focus_order"], ["main_action", "finish"])
        moved = edit_layout(modified, "move", target="finish", direction="up")
        self.assertEqual(moved["root"]["children"][1]["id"], "finish")
        removed = edit_layout(moved, "remove", target="main_action")
        self.assertEqual(removed["focus_order"], ["finish"])
        self.assertEqual(check_layout(removed), removed)

    def test_invalid_operations_do_not_mutate_source(self):
        document = new_layout()
        snapshot = deepcopy(document)
        cases = [
            ("remove", {"target": "root"}),
            ("remove", {"target": "missing"}),
            ("move", {"target": "welcome", "direction": "up"}),
            ("update", {"target": "welcome", "changes": {"type": "evil"}}),
            ("update", {"target": "main_action",
                        "changes": {"action": "eval('game')"}}),
            ("add", {"target": "welcome", "widget": {
                "id": "bad", "type": "text", "text": "bad"}}),
            ("add", {"target": "root", "widget": {
                "id": "welcome", "type": "text", "text": "dup"}}),
        ]
        for operation, kwargs in cases:
            with self.subTest(operation=operation, kwargs=kwargs):
                with self.assertRaises(UiLayoutError):
                    edit_layout(document, operation, **kwargs)
                self.assertEqual(document, snapshot)
        with self.assertRaises(UiLayoutError):
            edit_breakpoints(document, [{"min_width": 500, "columns": 2}])
        self.assertEqual(document, snapshot)

    def test_all_authored_widget_types_and_explicit_breakpoints(self):
        layout = new_layout()
        gauge = {"id": "health", "type": "gauge",
                 "binding": {"path": "combat.active_hp", "type": "int"},
                 "max_binding": {"path": "combat.active_max_hp", "type": "int"}}
        result = edit_layout(layout, "add", target="root", widget=gauge)
        result = edit_layout(result, "add", target="root", widget={
            "id": "sidebar", "type": "row", "children": [
                {"id": "side_label", "type": "text",
                 "binding": {"path": "session.scene_id", "type": "str"}}
            ]})
        result = edit_breakpoints(result, [
            {"min_width": 0, "columns": 1},
            {"min_width": 750, "columns": 2},
            {"min_width": 1200, "columns": 3},
        ])
        self.assertEqual(editor_sample(result, 1500)["columns"], 3)
        self.assertEqual(editor_sample(result, 800)["root"]["children"][2]["value"], 24)
        self.assertEqual(editor_sample(result, 800)["root"]["children"][3]
                         ["children"][0]["value"], "scene_preview")

    def test_authoring_preview_never_commits_without_apply(self):
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        author = LayoutAuthoring(session)
        before = session.snapshot().to_dict()
        draft = edit_layout(new_layout(), "update",
                            target="main_action",
                            changes={"action": "combat.end_turn"})
        plan = author.preview_replace("my_hud", draft)
        self.assertEqual(before, session.snapshot().to_dict())
        author.apply(plan)
        self.assertEqual(session.revision, 1)
        with self.assertRaises(AuthoringError):
            author.apply(plan)
        session.undo()
        self.assertEqual(before["project"], session.snapshot().to_dict()["project"])
        session.redo()
        self.assertIn("org.drawtemp.ui", session.snapshot().to_dict()["project"]["extensions"])


class PlayerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_legacy_player_no_custom_hud_no_side_effects(self):
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            self.assertEqual(hud_for_player(player, 900), {"available": False, "error": ""})
            with self.assertRaises(UiLayoutError):
                perform_ui_intent(player, "combat.end_turn")

    def test_hud_is_opt_in_and_invalid_intents_are_rejected(self):
        layout = edit_layout(new_layout(), "update", target="main_action",
                             changes={"action": "combat.end_turn"})
        self.project.extensions["org.drawtemp.ui"] = {
            "schema_version": 1, "data": {
                "version": 1, "layouts": {"custom_ct": layout}}}
        self.project.validate(self.content)
        with TemporaryDirectory() as root:
            player = PlayerController(self.content, self.project, "main", root)
            self.assertFalse(hud_for_player(player, 800)["available"])
            for bad in ("menu.quit", "combat.open_inventory", "unknown", ""):
                with self.subTest(intent=bad), self.assertRaises(UiLayoutError):
                    perform_ui_intent(player, bad)
            self.assertFalse(player._path(1).exists())
            with self.assertRaises(UiLayoutError):
                hud_for_player(player, True)

    def test_shared_qml_assets_exist_without_author_scripting(self):
        qml = Path(__file__).parents[1] / "drawtemp" / "player"
        node = (qml / "R51Node.qml").read_text(encoding="utf-8")
        layout = (qml / "R51Layout.qml").read_text(encoding="utf-8")
        self.assertIn("textFormat: Text.PlainText", node)
        self.assertIn("permittedActions.indexOf", node)
        self.assertIn("R51Node", layout)


if __name__ == "__main__":
    unittest.main()
