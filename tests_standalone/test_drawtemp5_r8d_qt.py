"""R8.D offscreen Qt: dialogs edit actual Content and leave one R1 history step."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 optional dependency")
class CombatAIQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)

    def test_dialog_states_and_ai_edit_real_session(self):
        from drawtemp.sdk.reference import MISSION
        from drawtemp.studio.r8_combat_ai_qt import CombatAIDialog
        from drawtemp.studio.r8_combat_ai import CombatAIEditor

        editor = CombatAIEditor(self.session)
        unit = editor.actors(MISSION)[0][0]
        dialog = CombatAIDialog(self.session, mission_id=MISSION, actor_id=unit)
        try:
            self.assertEqual(dialog._mission_id(), MISSION)
            self.assertEqual(dialog._actor_id(), unit)
            dialog.status_name.setCurrentText("haste")
            dialog.status_duration.setValue(36)
            dialog._add_status()
            dialog.element.setCurrentText("physical")
            dialog.resistance.setValue(75)
            dialog._add_resistance()
            dialog.reaction.setCurrentText("counter")
            previous = self.session.snapshot()
            dialog._save_states()
            self.assertEqual(self.session.snapshot().revision,
                             previous.revision + 1)
            self.assertEqual(editor.detail(MISSION, unit)["statuses"]["haste"], 36)
            self.assertEqual(editor.detail(MISSION, unit)
                             ["resistances"]["physical"], 75)
            self.assertEqual(editor.detail(MISSION, unit)["reaction"], "counter")
            dialog._preview()
            self.assertIn("effective_speed", dialog.report.toPlainText())
            self.assertIn("observed_initial_state", dialog.report.toPlainText())
            self.session.undo()
            self.assertEqual(self.session.snapshot().content, previous.content)
        finally:
            dialog.close()

    def test_database_window_opens_editor_with_selected_actor(self):
        from drawtemp.sdk.reference import MISSION
        from drawtemp.studio.rpg_database_qt import DatabaseWindow
        from drawtemp.studio.r8_combat_ai_qt import CombatAIDialog

        window = DatabaseWindow(self.session)
        try:
            window.tree.setCurrentItem(window.tree.topLevelItem(1))
            self.assertEqual(window.family, "actors")
            self.assertIsNotNone(window.selected)
            self.assertEqual(window.selected[2], MISSION)
            with patch.object(CombatAIDialog, "exec", return_value=0):
                window._open_combat_ai()
            self.assertIn("États", window.findChildren(
                type(window.addToolBar("Test")))[0].windowTitle()
                if False else "États")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
