"""R55.B Qt offscreen smoke: visual graph, forecast and single Studio commit."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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
