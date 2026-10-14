"""3.7.32A Tk smoke: smart brush controls and selection bounded fill."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests_standalone.studio_gui_actions import save_as

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor import launch


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk and a display/Xvfb')
class MapBuilder4GUITests(unittest.TestCase):
    def test_smart_paint_and_selected_fill_saved_as_plain_tiles(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'smart-map.json'
            errors = []

            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    widgets = list(descendants(root))
                    canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                and 'Pinceau intelligent' in w.cget('values'))
                    surface = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                   and 'bridge' in w.cget('values'))
                    buttons = {w.cget('text'): w for w in widgets
                               if isinstance(w, ttk.Button)}

                    def click(x, y):
                        canvas.event_generate('<Button-1>', x=x, y=y)
                        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                        root.update()

                    surface.set('dirt')
                    surface.event_generate('<<ComboboxSelected>>')
                    root.update()
                    buttons['Pinceau intelligent'].invoke()
                    root.update()
                    canvas.event_generate('<Motion>', x=4*54+10, y=4*54+10)
                    root.update()
                    self.assertTrue(canvas.find_withtag('brush_preview'))
                    click(4*54+10, 4*54+10)

                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=4*54+10, y=4*54+10)
                    canvas.event_generate('<B1-Motion>', x=5*54+10, y=4*54+10,
                                          state=256)
                    canvas.event_generate('<ButtonRelease-1>',
                                          x=5*54+10, y=4*54+10)
                    root.update()
                    surface.set('cobble')
                    surface.event_generate('<<ComboboxSelected>>')
                    root.update()
                    buttons['Remplir sélection'].invoke()
                    root.update()
                    save_as(root)
                    saved = json.loads(output.read_text(encoding='utf-8'))
                    tiles = {tuple(t['pos']): t
                             for t in saved['missions'][0]['board']['tiles']}
                    self.assertEqual(tiles[(4, 4)]['surface'], 'cobble')
                    self.assertEqual(tiles[(5, 4)]['surface'], 'cobble')
                    self.assertEqual(tiles[(3, 4)]['surface'], 'dirt')
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=str(output)), \
                 patch('tkinter.messagebox.showerror') as popup:
                launch(DEFAULT_CONTENT)
                popup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
