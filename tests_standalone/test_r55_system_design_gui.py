"""R55.B Qt offscreen smoke: visual graph, forecast and single Studio commit."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.system_design_qt import SystemDesignerDialog, _parse_amount_text
    QT = True
except ImportError:
    QT = False

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.system_design import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture
from tests_standalone.test_r55_system_design import system_spec


@unittest.skipUnless(QT, "PySide6 not available")
class SystemDesignerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_graph_projection_preview_and_undoable_apply(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        dlg = SystemDesignerDialog(session)
        dlg.document = system_spec()
        dlg.refresh()
        self.assertEqual(dlg.lists["resources"].count(), 3)
        self.assertEqual(dlg.lists["producers"].count(), 2)
        self.assertGreater(len(dlg.scene.items()), 0)
        dlg.ticks.setValue(4)
        dlg.preview()
        self.assertIn("ore: 8 → 4 (-4)", dlg.report.toPlainText())
        self.assertNotIn(EXTENSION,
                         session.snapshot().to_dict()["project"].get("extensions", {}))
        dlg.apply()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        session.undo()
        self.assertNotIn(EXTENSION,
                         session.snapshot().to_dict()["project"].get("extensions", {}))
        session.redo()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        dlg.close()

    def test_multiport_parser_and_graph_edit_with_immediate_validation(self):
        self.assertEqual(
            _parse_amount_text("ore:2, ingot:3", {"ore", "ingot"}),
            {"ore": 2, "ingot": 3})
        for malformed in ("ore:2,ore:3", "missing:1", "ore:-2", "ore:True",
                          "ore:1001", "ore:2:1", "", "ore:1,"):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                _parse_amount_text(malformed, {"ore", "ingot"})
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        dlg = SystemDesignerDialog(session)
        dlg.document = system_spec()
        dlg.refresh()
        self.assertEqual(dlg.lists["producers"].count(), 2)
        dlg._commit_row("producers", {
            "id": "smelter", "inputs": "ore:3",
            "outputs": "ingot:2", "interval": 2}, 0)
        self.assertEqual(dlg.document["producers"][0]["inputs"], {"ore": 3})
        self.assertEqual(dlg.document["producers"][0]["outputs"], {"ingot": 2})
        dlg.preview()
        self.assertIn("ore:", dlg.report.toPlainText())
        dlg.close()

    def _authored_graph(self):
        content, project = scene_fixture()
        project.extensions[EXTENSION] = {
            "schema_version": 1, "data": system_spec(), "references": []}
        project.validate(content)
        session = AuthoringSession(content, project)
        dlg = SystemDesignerDialog(session)
        return dlg, session

    def test_draft_undo_redo_move_graph_inspector_and_one_project_commit(self):
        dlg, session = self._authored_graph()
        original_revision = session.revision
        old = dlg.graph.nodes[("resources", "ore")].pos()
        dlg.move_node(("resources", "ore"), old.x() + 32, old.y() + 18)
        self.assertEqual(
            dlg.positions[("resources", "ore")], (old.x() + 32, old.y() + 18))
        self.assertEqual(session.revision, original_revision)
        self.assertTrue(dlg.undo_draft())
        self.assertNotIn(("resources", "ore"), dlg.positions)
        self.assertTrue(dlg.redo_draft())
        self.assertIn(("resources", "ore"), dlg.positions)

        # Selecting a QGraphicsItem fills inspector and syncs list selection.
        node = dlg.graph.nodes[("resources", "ore")]
        node.setSelected(True)
        self.assertIn("ore", dlg.inspector.toPlainText())
        self.assertEqual(dlg.tabs.currentIndex(), 0)
        self.assertTrue(dlg.edit_selected.isEnabled())
        self.assertFalse(dlg.unlink_selected.isEnabled())
        self.assertTrue(dlg.connect_button.isEnabled())
        self.assertEqual(dlg.inspector.objectName(), "r55GraphInspector")

        self.assertTrue(dlg.connect_nodes(
            ("resources", "ore"), ("producers", "jeweler"), 3))
        self.assertEqual(dlg.document["producers"][1]["inputs"]["ore"], 3)
        self.assertEqual(session.revision, original_revision)
        self.assertTrue(dlg.undo_draft())
        self.assertNotIn("ore", dlg.document["producers"][1]["inputs"])
        self.assertTrue(dlg.redo_draft())
        self.assertEqual(dlg.document["producers"][1]["inputs"]["ore"], 3)
        dlg.apply()
        self.assertEqual(session.revision, original_revision + 1)
        self.assertEqual(
            session.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["producers"][1]["inputs"]["ore"], 3)
        session.undo()
        self.assertNotIn(
            "ore", session.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["producers"][1]["inputs"])
        dlg.close()

    def test_click_graph_ports_to_rebind_merchant_and_select_link(self):
        dlg, session = self._authored_graph()
        dlg.show()
        self.app.processEvents()
        source = dlg.graph.nodes[("resources", "gem")].output
        target = dlg.graph.nodes[("merchants", "trader")].input

        def click(port):
            dlg.graph.centerOn(port.sceneBoundingRect().center())
            self.app.processEvents()
            pos = dlg.graph.mapFromScene(port.sceneBoundingRect().center())
            QTest.mouseClick(dlg.graph.viewport(), Qt.LeftButton, pos=pos)
            self.app.processEvents()

        click(source)
        self.assertEqual(dlg.graph.pending, ("resources", "gem"))
        click(target)
        self.assertIsNone(dlg.graph.pending)
        self.assertEqual(dlg.document["merchants"][0]["resource"], "gem")
        self.assertEqual(
            session.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["merchants"][0]["resource"], "ingot")
        edge = next(e for e in dlg.graph.connections
                    if e.source == ("resources", "gem")
                    and e.target == ("merchants", "trader"))
        dlg.scene.clearSelection()
        edge.setSelected(True)
        self.assertIn("Liaison", dlg.inspector.toPlainText())
        self.assertTrue(dlg.unlink_selected.isEnabled())
        self.assertTrue(dlg.undo_draft())
        self.assertEqual(dlg.document["merchants"][0]["resource"], "ingot")
        dlg.close()

    def test_keyboard_node_movement_and_incompatible_graph_edge(self):
        dlg, session = self._authored_graph()
        node = dlg.graph.nodes[("producers", "smelter")]
        node.setSelected(True)
        dlg.graph.setFocus()
        original = node.pos()
        QTest.keyClick(dlg.graph, Qt.Key_Right)
        self.assertEqual(dlg.graph.nodes[("producers", "smelter")].pos().x(),
                         original.x() + 12)
        self.assertTrue(dlg.undo_draft())
        self.assertEqual(dlg.graph.nodes[("producers", "smelter")].pos().x(),
                         original.x())
        before = session.snapshot().to_dict()
        with self.assertRaises(ValueError):
            dlg.connect_nodes(("resources", "gem"), ("producers", "smelter"))
        self.assertEqual(session.snapshot().to_dict(), before)
        dlg.close()

    def test_delete_selected_recipe_link_by_keyboard_is_undoable(self):
        dlg, session = self._authored_graph()
        previous = session.snapshot().to_dict()
        dlg.connect_nodes(
            ("resources", "ore"), ("producers", "jeweler"), 3)
        edge = next(e for e in dlg.graph.connections
                    if e.source == ("resources", "ore")
                    and e.target == ("producers", "jeweler"))
        dlg.scene.clearSelection()
        edge.setSelected(True)
        dlg.graph.setFocus()
        QTest.keyClick(dlg.graph, Qt.Key_Delete)
        self.app.processEvents()
        self.assertNotIn("ore", dlg.document["producers"][1]["inputs"])
        self.assertEqual(session.snapshot().to_dict(), previous)
        self.assertTrue(dlg.undo_draft())
        self.assertEqual(dlg.document["producers"][1]["inputs"]["ore"], 3)
        dlg.close()

    def test_stale_editor_cannot_override_new_revision(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        first = SystemDesignerDialog(session)
        second = SystemDesignerDialog(session)
        first.document = system_spec()
        first.apply()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        second.document = system_spec()
        # Do not show modal QMessageBox: exercise the underlying
        # preview contract while preserving second's captured revision.
        from drawtemp.studio.system_design_authoring import preview_system_design
        with self.assertRaises(ValueError):
            preview_system_design(
                session, second.document, expected_revision=second.source_revision)
        first.close()
        second.close()


if __name__ == "__main__":
    unittest.main()
