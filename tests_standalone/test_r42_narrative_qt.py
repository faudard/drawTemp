"""Qt offscreen smoke for R42.B1, optional PySide6 on developer machines."""
import importlib.util
import os
import unittest

from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.authoring import AuthoringSession

HAS_QT = importlib.util.find_spec('PySide6') is not None


@unittest.skipUnless(HAS_QT, 'PySide6 not installed')
class NarrativeQtR42Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from drawtemp.studio.narrative_qt_r42 import NarrativeStudioDialog
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.dialog = NarrativeStudioDialog(self.session)

    def tearDown(self):
        self.dialog.close()

    def test_graph_selection_and_dialogue_migration_apply(self):
        self.assertEqual(self.dialog.graph.scene().items() != [], True)
        self.assertEqual(self.dialog._selected, 'arrival')
        self.assertFalse(self.dialog.buttons['preview'].isEnabled())
        self.dialog.preview_migration()
        self.assertTrue(self.dialog.buttons['apply'].isEnabled())
        self.assertEqual(self.session.snapshot().to_dict()['project']['story'].get(
            'schema_version'), None)
        self.dialog.apply_preview()
        self.assertTrue(self.dialog.buttons['preview'].isEnabled())
        self.assertEqual(self.dialog.lines.rowCount(), 1)
        self.dialog.add_line()
        self.assertEqual(self.dialog.lines.rowCount(), 2)
        self.dialog.lines.item(1, 1).setText('Capitaine')
        self.dialog.lines.item(1, 2).setText('Jeanne, partons.')
        self.assertFalse(self.dialog.buttons['apply'].isEnabled())
        self.dialog.preview_lines()
        self.assertTrue(self.dialog.buttons['apply'].isEnabled())
        self.dialog.apply_preview()
        self.assertEqual(len(self.session.snapshot().to_dict()[
            'project']['story']['scenes'][0]['lines']), 2)
        self.dialog.undo()
        self.assertEqual(self.dialog.lines.rowCount(), 1)

    def test_debugger_is_isolated_and_qt_displays_trace(self):
        from drawtemp.studio.narrative_debugger_r42 import NarrativeDebugger
        self.dialog.preview_migration()
        self.dialog.apply_preview()
        before = self.session.snapshot().to_dict()
        self.dialog.debugger = NarrativeDebugger(self.session, 'main')
        self.dialog.debug_render()
        self.assertIn('arrival', self.dialog.debug_output.toPlainText())
        self.assertIn('isolé', self.dialog.debug_output.toPlainText())
        self.dialog.debugger.choose('enter')
        self.dialog.debug_render()
        self.assertIn('décisions', self.dialog.debug_output.toPlainText())
        self.assertEqual(self.session.snapshot().to_dict(), before)
        self.dialog.debug_reset()
        self.assertIsNone(self.dialog.debugger)

    def test_vs42_template_audit_is_read_only_and_undoable(self):
        before = self.session.snapshot().to_dict()
        self.dialog.workbench.apply(
            self.dialog.workbench.preview_captain_slice())
        self.dialog.refresh()
        template = self.session.snapshot().to_dict()
        self.assertEqual(template['project']['title'],
                         'La loyauté du capitaine')
        report = self.dialog._audit_campaign('main')
        self.assertTrue(report['passed'])
        self.assertEqual(set(report['endings']), {'alliance', 'accord', 'exile'})
        self.assertIn('fins_et_chemins', self.dialog.debug_output.toPlainText())
        self.assertEqual(self.session.snapshot().to_dict(), template)
        self.dialog.undo()
        self.assertEqual(self.session.snapshot().to_dict()['content'],
                         before['content'])
        self.assertEqual(self.session.snapshot().to_dict()['project'],
                         before['project'])

    def test_source_usage_and_undo_refresh(self):
        self.dialog.preview_migration()
        self.dialog.apply_preview()
        self.dialog.workbench.apply(self.dialog.workbench.preview_create_scene(
            'captain', 'Capitaine', '', 'Bienvenue'))
        self.dialog.refresh(prefer='captain')
        self.assertEqual(self.dialog._selected, 'captain')
        self.assertIn('Bienvenue', self.dialog.lines.item(0, 2).text())
        self.assertEqual(self.dialog.variables.rowCount(), 0)


if __name__ == '__main__':
    unittest.main()
