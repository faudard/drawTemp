"""Real Tk integration test. CI runs this under Xvfb on Linux."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Run with SPOREBOUND_GUI_SMOKE=1 under a display')
class EditorGUITests(unittest.TestCase):
    def test_author_save_playtest_and_return_to_edit(self):
        import tkinter as tk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'project.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *error: errors.append(error)
                    root.update()
                    widgets = list(descendants(root))
                    buttons = {w.cget('text'): w for w in widgets if w.winfo_class() == 'TButton'}
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    canvas.event_generate('<Button-1>', x=20, y=20)
                    root.update()
                    buttons['Annuler'].invoke()
                    buttons['Rétablir'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertTrue(output.exists())
                    data = json.loads(output.read_text(encoding='utf-8'))
                    self.assertTrue(next(t for t in data['missions'][0]['board']['tiles'] if t['pos']==[0,0])['blocked'])
                    buttons['Playtest'].invoke()
                    buttons['IA : 1 tour'].invoke()
                    root.update()
                    text = '\n'.join(w.get('1.0','end') for w in widgets if isinstance(w,tk.Text))
                    self.assertIn('activation',text)
                    self.assertIn('Actif :',text)
                    buttons['Éditer'].invoke()
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), patch('tkinter.filedialog.asksaveasfilename',return_value=str(output)), patch('tkinter.messagebox.showerror') as error:
                launch(DEFAULT_CONTENT)
                error.assert_not_called()
