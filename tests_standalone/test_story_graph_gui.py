"""Xvfb smoke test of the narrative decision tree embedded in Tk Studio."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch
from sporebound.game_project import GameProject
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE')=='1',
                     'Run under an Xvfb display')
class StoryGraphGUITests(unittest.TestCase):
    def test_unfolded_tree_create_link_and_edit_scene(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            path=Path(folder)/'with_tree.game.json'
            errors=[]

            def drive(root):
                try:
                    root.report_callback_exception=lambda *err:errors.append(err)
                    root.update()
                    widgets=list(descendants(root))
                    notebooks=[w for w in widgets if isinstance(w,ttk.Notebook)]
                    book=next(w for w in notebooks if
                              'Arbre narratif' in [w.tab(tab,'text') for tab in w.tabs()])
                    index=next(i for i in range(len(book.tabs()))
                               if book.tab(i,'text')=='Arbre narratif')
                    book.select(index)
                    root.update()
                    tree_page=root.nametowidget(book.select())
                    tree=next(w for w in descendants(tree_page)
                              if isinstance(w,tk.Canvas) and
                              any(tag.startswith('node_') for item in w.find_all()
                                  for tag in w.gettags(item)))
                    self.assertGreater(len(tree.find_all()),3)
                    roots=next(w for w in descendants(root)
                               if isinstance(w,ttk.Combobox) and
                               'Scène · oath_reward' in tuple(w['values']))
                    roots.set('Scène · oath_reward')
                    roots.event_generate('<<ComboboxSelected>>')
                    root.update()
                    self.assertTrue(any('node_' in tag for item in tree.find_all()
                                        for tag in tree.gettags(item)))
                    buttons={w.cget('text'):w for w in descendants(root)
                             if isinstance(w,ttk.Button)}
                    buttons['Créer et relier en une fois'].invoke()
                    root.update()
                    buttons['Enregistrer projet de jeu…'].invoke()
                    saved=GameProject.load(path,Content.load(DEFAULT_CONTENT))
                    branch=next(x for x in saved.story['scenes']
                                if x['id']=='new_branch')
                    self.assertEqual(branch['title'],'Nouvelle scène')
                    original=next(x for x in saved.story['scenes']
                                  if x['id']=='oath_reward')
                    self.assertEqual(original['choices'][0]['next_scene'],'new_branch')
                    buttons['Éditer scène / choix'].invoke()
                    root.update()
                    self.assertEqual(book.tab(book.select(),'text'),'Scénario & dialogues')
                    self.assertEqual(errors,[])
                finally:
                    root.destroy()

            with patch.object(tk.Tk,'mainloop',drive), \
                 patch('tkinter.filedialog.asksaveasfilename',return_value=str(path)), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(DEFAULT_CONTENT)
                show_error.assert_not_called()


if __name__=='__main__':
    unittest.main()
