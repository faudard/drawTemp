"""Tk/Xvfb gate for Game Studio 4.0 guided three-front siege authoring."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.siege_scenarios import siege_content
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a Tk display')
class SiegeFlowWizardGUITests(unittest.TestCase):
    def test_three_fronts_from_workspace_through_project_save_and_replay(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def button(parent, label):
            return next(widget for widget in descendants(parent)
                        if isinstance(widget, ttk.Button)
                        and widget.cget('text') == label)

        def field(parent, caption):
            label = next(widget for widget in descendants(parent)
                         if isinstance(widget, ttk.Label)
                         and widget.cget('text') == caption)
            siblings = label.master.grid_slaves(
                row=int(label.grid_info()['row']), column=1)
            return siblings[0]

        with TemporaryDirectory() as folder:
            content_path = Path(folder) / 'castle.json'
            project_path = content_path.with_suffix('.game.json')
            content_path.write_text(
                json.dumps(siege_content().to_dict(), ensure_ascii=False),
                encoding='utf-8')
            callbacks = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: callbacks.append(exc)
                    root.update()
                    button(root, 'Assistant siège (3 missions)').invoke()
                    root.update()
                    inner = next(
                        w for w in descendants(root)
                        if isinstance(w, ttk.Notebook) and
                        'Assistant 3 missions' in [w.tab(t, 'text') for t in w.tabs()])
                    self.assertEqual(inner.tab(inner.select(), 'text'),
                                     'Assistant 3 missions')
                    page = root.nametowidget(inner.select())
                    field(page, 'Identifiant du siège').delete(0, 'end')
                    field(page, 'Identifiant du siège').insert(0, 'jeanne_guided')
                    for caption, mission in (
                            ('1 · Remparts', 'castle_ramparts'),
                            ('2 · Porte', 'castle_ram'),
                            ('3 · Salle du trône', 'castle_throne')):
                        field(page, caption).set(mission)
                    button(page, 'Vérifier préparation').invoke()
                    button(page, 'Préparer déploiements').invoke()
                    button(page, 'Créer siège guidé').invoke()
                    root.update()
                    button(root, 'Enregistrer projet de jeu…').invoke()
                    root.update()
                    button(root, 'Démarrer / rejouer').invoke()
                    button(root, 'Sauver partie').invoke()
                    root.update()
                    button(root, 'Charger siège').invoke()
                    self.assertEqual(callbacks, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(project_path)), \
                 patch('tkinter.messagebox.showerror') as errors:
                launch(content_path)
                errors.assert_not_called()
            content = Content.load(content_path)
            project = GameProject.load(project_path, content)
            self.assertEqual(project.sieges[0]['id'], 'jeanne_guided')
            self.assertEqual(len(project.sieges[0]['fronts']), 3)
            saved = Path(folder) / 'castle.game_saves' / 'siege_jeanne_guided' / 'slot_1.json'
            self.assertTrue(saved.is_file())


if __name__ == '__main__':
    unittest.main()
