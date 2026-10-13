"""3.7.19C — actual editor passage workflow with mouse picking and no JSON edits."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.iso_map import IsoGeometry
from sporebound.model import Content
from sporebound.studio_entity_palette import EntityPalette


def descendants(parent):
    for child in parent.winfo_children():
        yield child
        yield from descendants(child)


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
            'Requires actual Tk/Xvfb display')
class GraphicalPassageEditorTests(TestCase):
    def test_select_entrance_exit_cancel_undo_and_save(self):
        import tkinter as tk
        from tkinter import ttk
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / 'original.json'
            saved = Path(tmp) / 'authored.json'
            mid = 'graphical_passage'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     mid, 'Passage', 16, 16)
            data['missions'].sort(key=lambda m: m['id'] != mid)
            source.write_text(json.dumps(data), encoding='utf-8')
            errors, palettes = [], []
            original_init = EntityPalette.__init__

            def capture(instance, *args, **kwargs):
                original_init(instance, *args, **kwargs)
                palettes.append(instance)

            def drive(root):
                try:
                    root.report_callback_exception = lambda *args: errors.append(args)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}
                    buttons['Acteurs et objets'].invoke()
                    root.update()
                    palette = palettes[0]
                    palette.tree.selection_set('object:passage')
                    palette.on_selection()
                    palette.use()
                    root.update()
                    board = Content.from_dict(data).missions[mid].board
                    geo = IsoGeometry(board, 54)

                    def click(cell):
                        px, py = geo.center(cell)
                        canvas.xview_moveto(max(0.0, (px-canvas.winfo_width()/2) / geo.width))
                        canvas.yview_moveto(max(0.0, (py-canvas.winfo_height()/2) / geo.height))
                        root.update()
                        x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                        self.assertTrue(0 <= x < canvas.winfo_width())
                        self.assertTrue(0 <= y < canvas.winfo_height())
                        canvas.event_generate('<Motion>', x=x, y=y)
                        root.update()
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        root.update()

                    click((6, 7))
                    buttons['Enregistrer sous'].invoke()
                    first = Content.load(saved).missions[mid]
                    self.assertEqual(first.objects, [], 'First click must not persist')
                    click((10, 7))
                    buttons['Enregistrer sous'].invoke()
                    mission = Content.load(saved).missions[mid]
                    passages = [o for o in mission.objects if o['kind'] == 'passage']
                    self.assertEqual(len(passages), 1)
                    self.assertEqual(tuple(passages[0]['pos']), (6, 7))
                    self.assertEqual(tuple(passages[0]['destination']), (10, 7))
                    self.assertEqual(len(canvas.find_withtag('iso_object_sprite')), 1)
                    buttons['Annuler'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(Content.load(saved).missions[mid].objects, [])
                    buttons['Rétablir'].invoke()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(Content.load(saved).missions[mid].objects), 1)
                    palette.show()
                    palette.tree.selection_set('object:passage')
                    palette.on_selection()
                    palette.use()
                    root.update()
                    click((4, 7))
                    canvas.event_generate('<Escape>')
                    root.update()
                    buttons['Enregistrer sous'].invoke()
                    self.assertEqual(len(Content.load(saved).missions[mid].objects), 1)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch.object(EntityPalette, '__init__', capture), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(saved)), \
                 patch('tkinter.messagebox.showerror') as error:
                launch(source)
                error.assert_not_called()
