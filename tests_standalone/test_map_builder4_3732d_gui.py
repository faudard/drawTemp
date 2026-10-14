"""3.7.32D GUI smoke: rotate prefab and stamp by hovering/clicking the map."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import traceback
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document, launch
from sporebound.editor_groups import create_editor_group
from sporebound.group_prefabs import capture_group_prefab, save_group_prefab
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Tk and Xvfb required')
class ReusablePrefab4GuiTests(unittest.TestCase):
    def test_90_degree_hover_stamp_and_undo(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            data = Content.load(DEFAULT_CONTENT).to_dict()
            data = add_blank_mission(data, 'prefab_gui_src4', 'Source', 20, 20)
            data = add_blank_mission(data, 'prefab_gui_dst4', 'Dest', 20, 20)
            doc = Document(Content.from_dict(data))
            doc.paint_many('prefab_gui_src4', [(4, 4)], 'surface:cobble')
            data = create_editor_group(doc.data, 'prefab_gui_src4', 'Chemin',
                                       cells=[(4, 4), (5, 4)])
            prefab = capture_group_prefab(
                data, 'prefab_gui_src4', ('group_1',), 'Chemin réutilisable')
            content_path = folder / 'project.json'
            output_path = folder / 'result.json'
            content_path.write_text(json.dumps(data), encoding='utf-8')
            lib = folder / 'prefabs'
            save_group_prefab(prefab, lib / 'Chemin.json')
            errors, popups = [], []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    widgets = list(descendants(root))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Préfab' in w.cget('values'))
                    missions = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and 'prefab_gui_src4' in w.cget('values')
                                    and 'prefab_gui_dst4' in w.cget('values'))
                    rotation = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                    and '90°' in w.cget('values')
                                    and '270°' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    missions.set('prefab_gui_dst4')
                    missions.event_generate('<<ComboboxSelected>>')
                    root.update()
                    rotation.set('90°')
                    buttons['Poser à la souris'].invoke()
                    self.assertEqual(tool.get(), 'Préfab')
                    root.update()
                    # Isometric coordinates would need projection. New editor
                    # starts with rectangular view, where (8,8) is stable.
                    canvas.event_generate('<Motion>', x=8*54+8, y=8*54+8)
                    root.update()
                    preview = canvas.find_withtag('editor_group_preview')
                    self.assertTrue(preview)
                    self.assertEqual(
                        canvas.itemcget(preview[0], 'outline'), '#36a16c',
                        'Prefab hover is invalid (red) before the click-to-stamp')
                    canvas.event_generate('<Button-1>', x=8*54+8, y=8*54+8)
                    canvas.event_generate('<ButtonRelease-1>', x=8*54+8, y=8*54+8)
                    root.update()
                    self.assertEqual(popups, [],
                                     'Prefab stamping rejected: ' + repr(popups))
                    self.assertFalse(
                        errors, 'Tk callback exception: ' + '\n'.join(
                            ''.join(traceback.format_exception(*exc))
                            for exc in errors))
                    buttons['Enregistrer sous'].invoke()
                    saved = json.loads(output_path.read_text(encoding='utf-8'))
                    dst = next(m for m in saved['missions'] if m['id'] == 'prefab_gui_dst4')
                    group = dst['editor_groups'][0]
                    self.assertEqual({tuple(p) for p in group['cells']},
                                     {(8, 8), (8, 9)})
                    self.assertEqual(Content.from_dict(saved).missions['prefab_gui_dst4']
                                     .board.tile((8, 8)).surface, 'cobble')
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    undo = json.loads(output_path.read_text(encoding='utf-8'))
                    self.assertFalse(next(m for m in undo['missions']
                                          if m['id'] == 'prefab_gui_dst4'
                                          ).get('editor_groups'))
                    self.assertEqual(errors, [])
                    self.assertEqual(popups, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename',
                       return_value=str(output_path)), \
                 patch('tkinter.messagebox.showerror',
                       side_effect=lambda *args: popups.append(args)):
                launch(content_path)


if __name__ == '__main__':
    unittest.main()
