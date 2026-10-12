"""3.7.18A real Tk/Xvfb smoke: ISO scene in both Editor and Player."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.model import Content
from sporebound.iso_map import IsoGeometry
from sporebound.iso_battle_view import viewport_shift
from sporebound.presentation import Camera


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Tk/Xvfb display')
class SharedIsometricBattleGuiTests(unittest.TestCase):
    def test_editor_keeps_iso_when_playtest_starts_and_ends(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.editor import launch

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        errors = []
        def drive(root):
            try:
                root.report_callback_exception = lambda *err: errors.append(err)
                root.update()
                widgets = list(descendants(root))
                canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
                toggle = next(w for w in widgets if isinstance(w, ttk.Checkbutton)
                              and w.cget('text') == 'Vue isométrique 2.5D')
                buttons = {w.cget('text'): w for w in widgets
                           if isinstance(w, ttk.Button)}
                toggle.invoke()
                root.update()
                self.assertTrue(canvas.find_withtag('iso_actor'))
                buttons['Playtest'].invoke()
                root.update()
                self.assertTrue(canvas.find_withtag('iso_actor'))
                # Isometric selection remains usable while Battle is active.
                board = next(iter(Content.load(DEFAULT_CONTENT).missions.values())).board
                geo = IsoGeometry(board, 54)
                px, py = geo.center((2, 2))
                canvas.xview_moveto(max(0, (px-canvas.winfo_width()/2)/geo.width))
                canvas.yview_moveto(max(0, (py-canvas.winfo_height()/2)/geo.height))
                root.update()
                x, y = int(px-canvas.canvasx(0)), int(py-canvas.canvasy(0))
                self.assertTrue(0 <= x < canvas.winfo_width())
                self.assertTrue(0 <= y < canvas.winfo_height())
                canvas.event_generate('<Button-1>', x=x, y=y)
                canvas.event_generate('<ButtonRelease-1>', x=x, y=y)
                root.update()
                self.assertTrue(canvas.find_withtag('selection'))
                buttons['Éditer'].invoke()
                root.update()
                self.assertTrue(canvas.find_withtag('iso_actor'))
                self.assertEqual(errors, [])
            finally:
                root.destroy()

        with (patch.object(tk.Tk, 'mainloop', drive),
              patch('tkinter.messagebox.showerror') as error_dialog):
            launch(DEFAULT_CONTENT)
            error_dialog.assert_not_called()

    def test_player_switches_iso_picks_cells_zooms_and_returns_to_2d(self):
        import tkinter as tk
        from tkinter import ttk
        from sporebound.player_app import launch

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            errors = []
            def drive(root):
                try:
                    root.report_callback_exception = lambda *err: errors.append(err)
                    root.update()
                    def button(text):
                        return next(w for w in descendants(root)
                                    if isinstance(w, ttk.Button)
                                    and w.cget('text') == text)
                    button('Nouvelle partie').invoke()
                    root.update()
                    next(w for w in descendants(root)
                         if isinstance(w, ttk.Button)
                         and 'Escarmouche du jardin' in w.cget('text')).invoke()
                    root.update()
                    canvas = next(w for w in descendants(root)
                                  if isinstance(w, tk.Canvas))
                    self.assertTrue(canvas.find_withtag('actor'))
                    toggle = next(w for w in descendants(root)
                                  if isinstance(w, ttk.Checkbutton)
                                  and w.cget('text') == 'Vue isométrique 2.5D')
                    toggle.invoke()
                    root.update()
                    self.assertTrue(canvas.find_withtag('iso_actor'))
                    board = Content.load(DEFAULT_CONTENT).missions['garden'].board
                    geo = IsoGeometry(board, 52)
                    sx, sy = viewport_shift(geo, Camera(52, 8, 8),
                                            (canvas.winfo_width(), canvas.winfo_height()))
                    x, y = geo.center((2, 2))
                    px, py = int(x+sx), int(y+sy)
                    self.assertTrue(0 <= px < canvas.winfo_width())
                    self.assertTrue(0 <= py < canvas.winfo_height())
                    canvas.event_generate('<Button-1>', x=px, y=py)
                    root.update()
                    self.assertTrue(canvas.find_withtag('selection'))
                    canvas.event_generate('<MouseWheel>', x=px, y=py, delta=120)
                    root.update()
                    self.assertTrue(canvas.find_withtag('iso_actor'))
                    toggle.invoke()
                    root.update()
                    self.assertTrue(canvas.find_withtag('actor'))
                    self.assertFalse(canvas.find_withtag('iso_actor'))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with (patch.object(tk.Tk, 'mainloop', drive),
                  patch('tkinter.messagebox.showerror') as error_dialog):
                launch(DEFAULT_CONTENT,
                       profile_path=Path(folder)/'profile.game.json')
                error_dialog.assert_not_called()


if __name__ == '__main__':
    unittest.main()
