"""3.7.25D Tk/Xvfb smoke: prefab library export, cross-mission placement."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document, launch
from sporebound.editor_groups import create_editor_group
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Tk GUI/Xvfb required')
class GroupPrefabGUITests(unittest.TestCase):

    def test_export_library_preview_place_save_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            src, dst = 'prefab_gui_source', 'prefab_gui_target'
            data = Content.load(DEFAULT_CONTENT).to_dict()
            data = add_blank_mission(data, src, 'Source', 20, 20)
            data = add_blank_mission(data, dst, 'Destination', 20, 20)
            doc = Document(Content.from_dict(data))
            doc.paint_many(src, ((5, 5),), 'feature:tree')
            raw = create_editor_group(doc.data, src, 'Bosquet',
                                      cells=((5, 5),))
            path = Path(folder) / 'project.json'
            target = Path(folder) / 'out.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            errors = []

            def saved_group_count():
                data = json.loads(target.read_text(encoding='utf-8'))
                return next(m for m in data['missions'] if m['id'] == dst
                            ).get('editor_groups', [])

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    tree = next(w for w in widgets
                                if isinstance(w, ttk.Treeview)
                                and w.exists('root:groups'))
                    missions = next(w for w in widgets
                                    if isinstance(w, ttk.Combobox)
                                    and src in w.cget('values')
                                    and dst in w.cget('values'))
                    missions.set(src)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    tree.selection_set('g:group_1')
                    tree.event_generate('<<TreeviewSelect>>')
                    root.update()
                    buttons['Enregistrer préfab'].invoke()
                    self.assertTrue((Path(folder) / 'prefabs' /
                                     'Bosquet_prefab.json').is_file())
                    missions.set(dst)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    buttons['Aperçu préfab'].invoke()
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    self.assertTrue(canvas.find_withtag('editor_group_preview'))
                    buttons['Placer préfab'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(saved_group_count()), 1)
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(saved_group_count()), 0)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(target)), \
                 patch('tkinter.simpledialog.askstring',
                       return_value='Bosquet prefab'), \
                 patch('tkinter.messagebox.showerror') as showerror:
                launch(path)
                showerror.assert_not_called()


if __name__ == '__main__':
    unittest.main()
