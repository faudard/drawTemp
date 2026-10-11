"""3.3.2 Xvfb: author strategic -> narrative link without JSON editing."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from tests_standalone.test_strategic_narrative_bridge import fixtures


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk and Xvfb')
class StrategicNarrativeGUITests(unittest.TestCase):
    def test_create_link_from_story_studio_and_save(self):
        import tkinter as tk
        from tkinter import ttk

        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)

        def control(root, caption):
            label = next(widget for widget in widgets(root)
                         if isinstance(widget, ttk.Label)
                         and widget.cget('text') == caption)
            row = label.grid_info()['row']
            return next(widget for widget in label.master.winfo_children()
                        if isinstance(widget, ttk.Combobox)
                        and widget.grid_info().get('row') == row)

        def button(root, caption):
            return next(w for w in widgets(root)
                        if isinstance(w, ttk.Button)
                        and w.cget('text') == caption)

        content, bp, project = fixtures()
        project.story.pop('after_strategic_event')
        with TemporaryDirectory() as folder:
            content_path = Path(folder) / 'castle.json'
            project_path = content_path.with_suffix('.game.json')
            content_path.write_text(
                json.dumps(content.to_dict()), encoding='utf-8')
            project.save(project_path, content)
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    control(root, 'Siège / événement').set(
                        'castle_causal/open_portcullis')
                    control(root, 'Scène après activation').set('breach')
                    button(root, 'Lier événement stratégique').invoke()
                    root.update()
                    button(root, 'Enregistrer projet de jeu…').invoke()
                    root.update()
                    self.assertFalse(errors)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(project_path)), \
                 patch('tkinter.messagebox.showerror') as popup:
                launch(content_path)
                popup.assert_not_called()
            reloaded = GameProject.load(project_path, Content.load(content_path))
            self.assertEqual(
                reloaded.story['after_strategic_event'],
                {'castle_causal/open_portcullis': 'breach'})


if __name__ == '__main__':
    unittest.main()
