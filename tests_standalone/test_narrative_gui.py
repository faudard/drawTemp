"""Xvfb UI tests for storyboard editing and conditional player dialogue."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch as editor_launch
from sporebound.player_shell import launch as player_launch
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_session import PlayerSession


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE')=='1',
                     'Run with Tk and Xvfb')
class StoryGUITests(unittest.TestCase):
    def test_studio_creates_dialogue_with_an_additional_choice(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            destination=Path(folder)/'authoring.game.json'
            errors=[]
            def drive(root):
                try:
                    root.report_callback_exception=lambda *err:errors.append(err)
                    root.update()
                    widgets=list(descendants(root))
                    tabs=[w.tab(i,'text') for w in widgets if isinstance(w,ttk.Notebook)
                          for i in range(len(w.tabs()))]
                    self.assertIn('Scénario & dialogues',tabs)
                    buttons={w.cget('text'):w for w in widgets if isinstance(w,ttk.Button)}
                    buttons['Créer scène'].invoke()
                    buttons['Ajouter choix'].invoke()
                    buttons['Enregistrer projet de jeu…'].invoke()
                    result=GameProject.load(destination,Content.load(DEFAULT_CONTENT))
                    created=next(scene for scene in result.story['scenes']
                                 if scene['id']=='new_scene')
                    self.assertEqual([c['id'] for c in created['choices']],
                                     ['continue','choice'])
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.filedialog.asksaveasfilename',return_value=str(destination)), \
                 patch('tkinter.messagebox.showerror') as show_error:
                editor_launch(DEFAULT_CONTENT)
                show_error.assert_not_called()

    def test_player_intro_changes_flags_and_awards_gold(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            path=Path(folder)/'player.game.json'
            errors=[]
            def buttons(root):
                return [w for w in descendants(root) if isinstance(w,ttk.Button)]
            def drive(root):
                try:
                    root.report_callback_exception=lambda *err:errors.append(err)
                    root.update()
                    combobox=next(w for w in descendants(root)
                                 if isinstance(w,ttk.Combobox) and
                                 'relique' in tuple(w['values']))
                    combobox.set('relique')
                    next(w for w in buttons(root) if w.cget('text')=='Nouvelle partie').invoke()
                    root.update()
                    next(w for w in buttons(root)
                         if w.cget('text')=='Je protégerai la garde.').invoke()
                    root.update()
                    next(w for w in buttons(root)
                         if 'Accepter l’aide de la garde' in w.cget('text')).invoke()
                    root.update()
                    self.assertTrue(any('Couronne Beatbox' in w.cget('text')
                                        for w in buttons(root)))
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.messagebox.showerror') as show_error:
                player_launch(DEFAULT_CONTENT,profile_path=path)
                show_error.assert_not_called()
            content=Content.load(DEFAULT_CONTENT)
            project=GameProject.load(Path(DEFAULT_CONTENT).with_suffix('.game.json'),content)
            restored=PlayerSession(content,project,path)
            restored.load_game('relique',1)
            self.assertEqual(restored.progress.story_flags['guard_oath'],True)
            self.assertEqual(restored.progress.gold,25)
            self.assertEqual(restored.progress.story_pending,'')


if __name__=='__main__':
    unittest.main()
