"""Optional Tk smoke test for the shared workspace panel.

Run under Xvfb with SPOREBOUND_GUI_SMOKE=1.
"""
import os
from unittest import TestCase, main, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Requires a Tk display')
class WorkspaceGUITests(TestCase):
    def test_navigate_and_create_without_json(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(parent):
            for widget in parent.winfo_children():
                yield widget
                yield from descendants(widget)

        answers = iter(['studio_castle', 'Porte du château', '8', '8'])

        def drive(root):
            try:
                root.update()
                children = list(descendants(root))
                tree = next(w for w in children if isinstance(w, ttk.Treeview) and
                            w.exists('group:mission'))
                buttons = {w.cget('text'): w for w in children
                           if isinstance(w, ttk.Button)}
                self.assertTrue(tree.exists('mission:garden'))
                tree.selection_set('mission:garden')
                buttons['Ouvrir dans le Studio'].invoke()
                root.update()
                self.assertTrue(any(w.tab(w.select(), 'text') == 'Carte et combat'
                                    for w in children if isinstance(w, ttk.Notebook)
                                    and w.select()))
                buttons['Nouvelle carte / mission'].invoke()
                root.update()
                self.assertTrue(tree.exists('mission:studio_castle'))
                self.assertTrue(tree.exists('group:campaign'))
            finally:
                root.destroy()

        with patch.object(tk.Tk, 'mainloop', drive), \
             patch('tkinter.simpledialog.askstring', side_effect=lambda *a, **k: next(answers)), \
             patch('tkinter.messagebox.showerror') as errors:
            launch(DEFAULT_CONTENT)
            errors.assert_not_called()


if __name__ == '__main__':
    main()
