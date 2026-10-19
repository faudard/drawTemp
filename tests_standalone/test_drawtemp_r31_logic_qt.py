"""R31.B: typed visual editing, no hidden saves, Qt canvas and shared Studio session."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft


def new_session():
    return AuthoringSession.new(*reference_project())


class LogicDraftTests(unittest.TestCase):
    def setUp(self):
        self.session = new_session()
        self.draft = LogicGraphDraft.new(
            MISSION, "le_portail", source_revision=self.session.revision)

    def test_new_flow_compiles_to_original_r9_without_editing_project(self):
        before = self.session.snapshot().to_dict()
        plan, native = self.draft.prepare(self.session)
        self.assertEqual(native["id"], "r31_le_portail")
        self.assertEqual(native["condition"], "tick")
        self.assertEqual(self.session.snapshot().to_dict(), before)
        self.session.apply(plan)
        self.assertIn("r31_le_portail", [
            trigger["id"] for trigger in
            self.session.snapshot().to_dict()["content"]["missions"][0]["triggers"]])
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"], before["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"], before["project"])

    def test_partial_add_copy_edit_link_and_remove(self):
        added = self.draft.add_action("message")
        self.assertEqual(added, "message1")
        self.assertEqual(self.draft.node(added)["params"]["text"], "Nouveau message")
        snapshot = self.draft.document()
        with self.assertRaises(LogicGraphError) as caught:
            self.draft.prepare(self.session)
        self.assertEqual(caught.exception.code, "invalid_edges")
        self.assertEqual(self.session.revision, 0)
        self.assertEqual(self.draft.document(), snapshot)

        self.draft.connect("message", added)
        self.assertEqual(len(self.draft.prepare(self.session)[1]["actions"]), 2)
        self.draft.edit_node(added, {"kind": "message", "text": "Deuxième"})
        copied = self.draft.copy_action(added)
        self.assertNotEqual(copied, added)
        self.assertEqual(self.draft.node(copied)["params"]["text"], "Deuxième")
        self.draft.connect(added, copied)
        self.assertEqual(self.draft.prepare(self.session)[1]["actions"][-1]["text"],
                         "Deuxième")
        self.draft.disconnect(added, copied)
        with self.assertRaises(LogicGraphError):
            self.draft.prepare(self.session)
        self.draft.remove_action(copied)
        self.draft.connect(added, self.draft.add_action("message"))
        self.assertEqual(len(self.draft.prepare(self.session)[1]["actions"]), 3)

    def test_rejects_bad_links_before_mutation_and_stale_drafts(self):
        original = self.draft.document()
        for source, target, code in (
            ("start", "start", "port_type"),
            ("ghost", "message", "unknown_node"),
            ("start", "message", "multiple_connections"),
            ("message", "start", "port_type"),
        ):
            with self.subTest(source=source, target=target):
                with self.assertRaises(LogicGraphError) as error:
                    self.draft.connect(source, target)
                self.assertEqual(error.exception.code, code)
                self.assertEqual(self.draft.document(), original)
        self.draft.edit_node("message", {"kind": "message", "text": "Le jeu"})
        with self.assertRaises(LogicGraphError):
            self.draft.edit_node("message", {"kind": "python", "code": "x"})
        with self.assertRaises(LogicGraphError):
            self.draft.copy_action("start")
        with self.assertRaises(LogicGraphError):
            self.draft.remove_action("start")
        self.assertEqual(self.draft.node("message")["params"]["text"], "Le jeu")

        # A foreign R1 edit invalidates a detached draft, including an undo ABA.
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "External editor"}))
        before = self.session.snapshot().to_dict()
        with self.assertRaises(LogicGraphError) as error:
            self.draft.apply(self.session)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_cycle_protection_of_active_draft(self):
        added = self.draft.add_action("hazard")
        self.draft.connect("message", added)
        before = self.draft.document()
        with self.assertRaises(LogicGraphError) as caught:
            self.draft.connect(added, "message")
        self.assertEqual(caught.exception.code, "multiple_connections")
        self.assertEqual(self.draft.document(), before)

    def test_graph_storage_roundtrip_uses_single_canonical_undo(self):
        self.draft.apply(self.session)
        self.assertEqual(self.draft.source_revision, 1)
        loaded = LogicGraphDraft.load(self.session, "le_portail")
        self.assertEqual(loaded.document(), self.draft.document())
        loaded.edit_node("message", {"kind": "message", "text": "Nouveau"})
        loaded.apply(self.session)
        self.assertEqual(self.session.revision, 2)
        self.assertEqual(
            graphs_from_project(self.session.snapshot().to_dict()["project"])[0]
            ["nodes"][1]["params"]["text"], "Nouveau")
        self.session.undo()
        self.assertEqual(
            graphs_from_project(self.session.snapshot().to_dict()["project"])[0]
            ["nodes"][1]["params"]["text"], "Nouveau message")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "content.json"
            self.session.save_as(path)
            reloaded = AuthoringSession.open(path)
            self.assertEqual(len(graphs_from_project(reloaded.snapshot().to_dict()
                                                     ["project"])), 1)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Optional PySide6 missing")
class VisualLogicQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_node_selection_connect_duplicate_preview_and_undo(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QInputDialog
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        session = new_session()
        before = session.snapshot().to_dict()
        view = LogicGraphDialog(session)
        try:
            view.show()
            with patch.object(QInputDialog, "getText",
                              return_value=("le_portail", True)):
                view.new_graph()
            self.assertIsNotNone(view.draft)
            self.assertEqual(view.draft.graph["id"], "le_portail")
            self.assertFalse(view.mission.isEnabled())
            # The UI switches event types with typed dialogs, never editing JSON.
            with patch.object(QInputDialog, "getItem",
                              return_value=("interact", True)), \
                 patch.object(QInputDialog, "getText",
                              return_value=("lever", True)):
                view.choose_node("start")
                view.edit_node()
            self.assertEqual(view.draft.node("start")["params"],
                             {"kind": "interact", "object_id": "lever"})
            self.assertTrue(view.preview())
            self.assertEqual(session.snapshot().to_dict(), before)
            with patch.object(QInputDialog, "getItem",
                              return_value=("message", True)):
                view.add_action()
            self.assertFalse(view.preview())
            self.assertIn("invalid_edges", view.diagnostics.toPlainText())
            target = view.selected_node
            view.choose_node("message")
            view.start_connect()
            view.choose_node(target)
            self.assertTrue(view.preview())
            self.assertTrue(view.apply_changes())
            self.assertEqual(session.revision, 1)
            with patch.object(QInputDialog, "getText",
                              return_value=("le_portail", True)):
                view.new_graph()
            self.assertIn("duplicate_graph", view.diagnostics.toPlainText())
            self.assertEqual(view.draft.graph["id"], "le_portail")
            self.assertEqual(len(graphs_from_project(
                session.snapshot().to_dict()["project"])), 1)
            view.choose_node("message")
            box = view.canvas._cards["message"]
            position = view.canvas.mapFromScene(box.sceneBoundingRect().center())
            QTest.mouseClick(view.canvas.viewport(), Qt.LeftButton, pos=position)
            self.assertEqual(view.selected_node, "message")
            view.undo()
            self.assertEqual(session.snapshot().to_dict()["content"], before["content"])
            self.assertEqual(session.snapshot().to_dict()["project"], before["project"])
            view.redo()
            self.assertEqual(session.revision, 3)
        finally:
            view.close()

    def test_branch_ui_builds_typed_if_else_without_json(self):
        from PySide6.QtWidgets import QInputDialog
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        session = new_session()
        view = LogicGraphDialog(session)
        try:
            with patch.object(QInputDialog, "getText",
                              return_value=("branch_qt", True)):
                view.new_graph()
            view.add_branch()
            self.assertEqual(view.draft.graph["schema_version"], 2)
            self.assertIn("if1", view.canvas._cards)
            self.assertTrue(view.preview())
            self.assertIn("cancel_after", view.diagnostics.toPlainText())
            view.choose_node("if1")
            with patch.object(QInputDialog, "getItem",
                              side_effect=[("Remplacer", True), ("tick", True)]), \
                 patch.object(QInputDialog, "getInt", return_value=(100, True)):
                view.edit_node()
            self.assertEqual(view.draft.node("if1")["params"]["predicate"],
                             {"condition": "tick", "value": 100})
            self.assertTrue(view.preview())
            self.assertTrue(view.apply_changes())
            self.assertEqual(session.revision, 1)
            native = session.snapshot().to_dict()["content"]["missions"][0]["triggers"]
            self.assertTrue(all(any(event["id"] == suffix for event in native)
                                for suffix in ("r31_branch_qt_yes", "r31_branch_qt_no")))
            view.undo()
            self.assertEqual(session.revision, 2)
        finally:
            view.close()

    def test_debugger_ui_breakpoint_step_inspect_and_stale_revision(self):
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        session = new_session()
        draft = LogicGraphDraft.new(
            MISSION, "qt_debug", source_revision=session.revision)
        draft.add_branch({"condition": "tick", "value": 0})
        draft.apply(session)
        before = session.snapshot().to_dict()
        view = LogicGraphDialog(session)
        try:
            index = view.graphs.findData("qt_debug")
            self.assertGreaterEqual(index, 0)
            view.graphs.setCurrentIndex(index)
            self.assertIsNotNone(view.draft)
            self.assertTrue(view.buttons["debug_start"].isEnabled())
            view.choose_node("if1")
            self.assertTrue(view.start_debug())
            self.assertTrue(view.toggle_breakpoint())
            self.assertTrue(view.debug_resume())
            self.assertIn("POINT D’ARRÊT", view.diagnostics.toPlainText())
            self.assertEqual(view.debug_session.report()["report"]["paused_node"], "if1")
            self.assertTrue(view.debug_inspect())
            self.assertIn("condition", view.diagnostics.toPlainText())
            self.assertTrue(view.debug_step())
            self.assertIn("r31_qt_debug_yes", view.diagnostics.toPlainText())
            self.assertEqual(session.snapshot().to_dict(), before)
            view.choose_node("message")
            self.assertFalse(view.toggle_breakpoint())
            self.assertIn("breakpoint_granularity", view.diagnostics.toPlainText())
            session.undo()
            self.assertFalse(view.debug_step())
            self.assertIn("stale_revision", view.diagnostics.toPlainText())
            self.assertIsNone(view.debug_session)
        finally:
            view.close()

    def test_debug_rejects_unapplied_graph_and_preserves_session(self):
        from PySide6.QtWidgets import QInputDialog
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        session = new_session()
        initial = session.snapshot().to_dict()
        view = LogicGraphDialog(session)
        try:
            with patch.object(QInputDialog, "getText",
                              return_value=("unsaved_qt", True)):
                view.new_graph()
            self.assertFalse(view.start_debug())
            self.assertIn("unsaved_graph", view.diagnostics.toPlainText())
            self.assertIsNone(view.debug_session)
            self.assertEqual(session.snapshot().to_dict(), initial)
        finally:
            view.close()

    def test_studio_shell_menu_shares_owner_and_rejects_stale_preview(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        with TemporaryDirectory() as directory:
            session = new_session()
            settings = QSettings(str(Path(directory) / "studio.ini"),
                                 QSettings.IniFormat)
            window = StudioWindow(session, settings=settings)
            try:
                self.assertIn("r31_logic", window.commands)
                dialog = LogicGraphDialog(window.session, parent=window)
                self.assertIs(dialog.session, window.session)
                dialog.draft = LogicGraphDraft.new(
                    MISSION, "le_portail", source_revision=session.revision)
                dialog._render()
                self.assertTrue(dialog.preview())
                session.apply(session.preview_project(
                    lambda data: {**data, "title": "Concurrent change"}))
                self.assertFalse(dialog.apply_changes())
                self.assertIn("stale_revision", dialog.diagnostics.toPlainText())
                dialog.close()
                with patch.object(LogicGraphDialog, "exec", return_value=0):
                    window.open_logic_graph()
                self.assertIs(window.session, session)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
