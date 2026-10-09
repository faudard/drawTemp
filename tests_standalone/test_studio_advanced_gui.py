"""Real Tk smoke scenarios for the advanced authoring and player shell.

Enable SPOREBOUND_GUI_SMOKE=1 and execute under Xvfb on Linux.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch as editor_launch
from sporebound.player_shell import launch as player_launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE')=='1','Tk display required')
class AdvancedStudioGUITests(unittest.TestCase):
    def test_guided_graph_actor_library_and_event_blocks(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        problems=[]
        def drive(root):
            try:
                root.report_callback_exception=lambda *err: problems.append(err)
                root.update()
                widgets=list(descendants(root))
                tabs=[w.tab(i,'text') for w in widgets if isinstance(w,ttk.Notebook)
                      for i in range(len(w.tabs()))]
                self.assertIn('Graphe des missions',tabs)
                self.assertIn('Bibliothèque d’acteurs',tabs)
                self.assertIn('Événements par blocs',tabs)
                buttons={w.cget('text'):w for w in widgets if isinstance(w,ttk.Button)}
                buttons['Créer archétype'].invoke()
                buttons['Ajouter bloc'].invoke()
                buttons['Valider événement'].invoke()
                buttons['Relier →'].invoke()
                root.update()
                self.assertEqual(problems,[])
            finally:
                root.destroy()

        with patch.object(tk.Tk,'mainloop',drive), \
             patch('tkinter.messagebox.showerror') as show_error:
            editor_launch(DEFAULT_CONTENT)
            show_error.assert_not_called()

    def test_standalone_player_menu_campaign_and_battle(self):
        import tkinter as tk
        from tkinter import ttk

        with TemporaryDirectory() as folder:
            errors=[]
            def buttons(root):
                def descendants(parent):
                    for child in parent.winfo_children():
                        yield child
                        yield from descendants(child)
                return [child for child in descendants(root) if isinstance(child,ttk.Button)]

            def drive(root):
                try:
                    root.report_callback_exception=lambda *err:errors.append(err)
                    root.update()
                    next(b for b in buttons(root) if b.cget('text')=='Nouvelle partie').invoke()
                    root.update()
                    mission=next(b for b in buttons(root) if 'Escarmouche du jardin' in b.cget('text'))
                    mission.invoke()
                    root.update()
                    self.assertTrue(any('Abandonner' in b.cget('text') for b in buttons(root)))
                    next(b for b in buttons(root) if 'Abandonner' in b.cget('text')).invoke()
                    root.update()
                    self.assertTrue(any(b.cget('text')=='Menu principal' for b in buttons(root)))
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.messagebox.askyesno',return_value=True), \
                 patch('tkinter.messagebox.showerror') as errors_dialog:
                player_launch(DEFAULT_CONTENT,profile_path=Path(folder)/'demo.game.json')
                errors_dialog.assert_not_called()


if __name__=='__main__':
    unittest.main()
