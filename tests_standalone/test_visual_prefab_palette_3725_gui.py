"""Tk/Xvfb: visual prefab thumbnail filtering and cross-widget drop."""
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
from sporebound.group_prefabs import capture_group_prefab, save_group_prefab
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk/Xvfb')
class VisualPrefabPaletteTests(unittest.TestCase):
    def test_search_filter_preview_drag_commit_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def widgets(widget):
            for child in widget.winfo_children():
                yield child
                yield from widgets(child)

        with TemporaryDirectory() as folder:
            source_id = 'palette_source'
            dest_id = 'palette_target'
            data = Content.load(DEFAULT_CONTENT).to_dict()
            data = add_blank_mission(data, source_id, 'Source', 20, 20)
            data = add_blank_mission(data, dest_id, 'Destination', 20, 20)
            doc = Document(Content.from_dict(data))
            doc.paint_many(source_id, ((3, 3),), 'feature:tree')
            data = create_editor_group(doc.data, source_id, 'Bosquet',
                                       cells=((3, 3),))
            prefab = capture_group_prefab(data, source_id,
                                          ('group_1',), 'Bosquet')
            path = Path(folder) / 'project.json'
            out = Path(folder) / 'saved.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            save_group_prefab(prefab, Path(folder) / 'prefabs' / 'Bosquet.json')
            errors = []

            def saved():
                document = json.loads(out.read_text(encoding='utf-8'))
                return next(m for m in document['missions']
                            if m['id'] == dest_id)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    all_widgets = list(widgets(root))
                    canvas = next(w for w in all_widgets
                                  if isinstance(w, tk.Canvas))
                    picture = next(w for w in all_widgets
                                   if isinstance(w, tk.Canvas) and
                                   int(w.cget('width')) == 132)
                    categories = next(
                        w for w in all_widgets if isinstance(w, ttk.Combobox)
                        and 'Fortifications' in w.cget('values'))
                    missions = next(
                        w for w in all_widgets if isinstance(w, ttk.Combobox)
                        and source_id in w.cget('values')
                        and dest_id in w.cget('values'))
                    buttons = {w.cget('text'): w for w in all_widgets
                               if isinstance(w, ttk.Button)}
                    missions.set(dest_id)
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    categories.set('Décors')
                    categories.event_generate('<<ComboboxSelected>>')
                    root.update()
                    # A filter rerenders cards; select the newly rendered one.
                    all_widgets = list(widgets(root))
                    picture = next(w for w in all_widgets
                                   if isinstance(w, tk.Canvas) and
                                   int(w.cget('width')) == 132)
                    self.assertTrue(picture.winfo_exists())
                    self.assertGreater(len(picture.find_all()), 0)

                    # Simulate pointer ownership moving from source thumbnail to
                    # the map. The drag handles both map render modes.
                    source_x = picture.winfo_rootx() + 20
                    source_y = picture.winfo_rooty() + 20
                    tx = canvas.winfo_rootx() + 5 * 54 + 16
                    ty = canvas.winfo_rooty() + 6 * 54 + 16
                    self.assertLess(tx, canvas.winfo_rootx()+canvas.winfo_width())
                    self.assertLess(ty, canvas.winfo_rooty()+canvas.winfo_height())
                    picture.event_generate('<ButtonPress-1>', x=20, y=20,
                                           rootx=source_x, rooty=source_y)
                    picture.event_generate('<B1-Motion>', x=20, y=20,
                                           rootx=tx, rooty=ty)
                    self.assertTrue(canvas.find_withtag('prefab_drag_preview'))
                    picture.event_generate('<ButtonRelease-1>', x=20, y=20,
                                           rootx=tx, rooty=ty)
                    root.update()
                    buttons['Enregistrer sous'].invoke()
                    groups = saved().get('editor_groups', [])
                    self.assertEqual(len(groups), 1)
                    self.assertEqual(groups[0]['cells'], [[5, 6]])
                    self.assertEqual(
                        Content.from_dict(json.loads(out.read_text()))
                        .missions[dest_id].board.tile((5, 6)).feature, 'tree')
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(saved().get('editor_groups', []), [])
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(out)), \
                 patch('tkinter.messagebox.showerror') as error:
                launch(path)
                error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
