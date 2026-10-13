"""3.5 real Tk map→visual choice creation, preview, Save All and atomic Undo."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class VisualBranchWizardGUITests(unittest.TestCase):
    def test_map_wizard_previews_saves_and_undoes_both_artifacts(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(root):
            for child in root.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            content_path = Path(folder) / 'fork_content.json'
            content_path.write_bytes(Path(DEFAULT_CONTENT).read_bytes())
            project_path = content_path.with_suffix('.game.json')
            callback_errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: callback_errors.append(err)
                    root.update()
                    buttons = {w.cget('text'): w for w in descendants(root)
                               if isinstance(w, ttk.Button)}
                    self.assertIn('Créer un embranchement narratif sur la case',
                                  buttons)
                    buttons['Créer un embranchement narratif sur la case'].invoke()
                    root.update()
                    windows = [w for w in descendants(root)
                               if isinstance(w, tk.Toplevel) and
                               w.title().startswith('Embranchements')]
                    self.assertEqual(len(windows), 1)
                    wizard = windows[0]
                    buttons = {w.cget('text'): w for w in descendants(wizard)
                               if isinstance(w, ttk.Button)}
                    self.assertIn('Prévisualiser les deux chemins', buttons)
                    self.assertIn('Créer sur la carte', buttons)
                    # Each branch is editable in one panel, without switching
                    # tabs to Narrative Studio or Event Studio.
                    actions = [w for w in descendants(wizard)
                               if isinstance(w, ttk.Combobox)
                               and 'hazard' in tuple(w['values'])]
                    self.assertEqual(len(actions), 2)
                    texts = [w for w in descendants(wizard)
                             if isinstance(w, ttk.Entry)]
                    source = next(w for w in texts if w.get().startswith('choice_at_'))
                    self.assertTrue(source.get())
                    reunion = next(w for w in texts
                                   if w.get() == '')
                    reunion.insert(0, 'fork_join_gui')
                    buttons['Prévisualiser les deux chemins'].invoke()
                    root.update()
                    report = next(w for w in descendants(wizard)
                                  if isinstance(w, tk.Text))
                    self.assertIn('EMBRANCHEMENTS TACTIQUES',
                                  report.get('1.0', 'end'))
                    self.assertIn('CHOIX attack', report.get('1.0', 'end'))
                    self.assertIn('CHOIX parley', report.get('1.0', 'end'))
                    buttons['Créer sur la carte'].invoke()
                    root.update()
                    self.assertFalse(wizard.winfo_exists())
                    all_buttons = {w.cget('text'): w for w in descendants(root)
                                   if isinstance(w, ttk.Button)}
                    all_buttons['Enregistrer tout'].invoke()
                    root.update()
                    document = json.loads(content_path.read_text(encoding='utf-8'))
                    project = json.loads(project_path.read_text(encoding='utf-8'))
                    ids = {r['id'] for m in document['missions'] for r in
                           m.get('triggers', [])}
                    self.assertIn('fork_join_gui', ids)
                    self.assertEqual(len(project['story']['during_tactical_event']), 1)
                    self.assertEqual(len(project['story']['scenes']), 4)
                    self.assertEqual(Content.from_dict(document).to_dict(), document)
                    all_buttons['Annuler'].invoke()
                    root.update()
                    all_buttons['Enregistrer tout'].invoke()
                    root.update()
                    reset_content = json.loads(content_path.read_text(encoding='utf-8'))
                    reset_project = json.loads(project_path.read_text(encoding='utf-8'))
                    self.assertFalse(any(
                        row['id'] == 'fork_join_gui'
                        for m in reset_content['missions']
                        for row in m.get('triggers', [])))
                    self.assertFalse(reset_project.get('story'))
                    all_buttons['Rétablir'].invoke()
                    root.update()
                    all_buttons['Enregistrer tout'].invoke()
                    root.update()
                    restored = json.loads(content_path.read_text(encoding='utf-8'))
                    self.assertIn('fork_join_gui',
                                  [row['id'] for m in restored['missions']
                                   for row in m.get('triggers', [])])
                    self.assertFalse(callback_errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.messagebox.showerror') as errors:
                launch(content_path)
                errors.assert_not_called()


if __name__ == '__main__':
    unittest.main()
