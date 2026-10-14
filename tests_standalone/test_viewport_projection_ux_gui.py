"""GUI regression: map projection stays visible, mission-scoped and lossless."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.map_layer_workspace import load_views, view_for
from sporebound.model import Content


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires Tk with a real screen or Xvfb')
class ViewportProjectionGuiTests(unittest.TestCase):
    def test_projection_switch_mission_restore_and_zoom_without_content_mutation(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'map.json'
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     'viewport_second', 'Other projection', 16, 16)
            first = data['missions'][0]['id']
            path.write_text(json.dumps(data), encoding='utf-8')
            errors = []

            def widgets(root):
                return list(descendants(root))

            def selector(root):
                radios = {w.cget('text'): w for w in widgets(root)
                          if isinstance(w, ttk.Radiobutton)}
                self.assertIn('2D', radios)
                self.assertIn('Iso 2.5D', radios)
                return radios

            def inspect_heading(root):
                return next(w.get('1.0', 'end').splitlines()[0]
                            for w in widgets(root) if isinstance(w, tk.Text)
                            and 'Objectif :' in w.get('1.0', 'end'))

            def drive(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    radios = selector(root)
                    self.assertTrue(radios['2D'].instate(['selected']))
                    all_widgets = widgets(root)
                    canvas = next(w for w in all_widgets if isinstance(w, tk.Canvas))
                    tool = next(w for w in all_widgets if isinstance(w, ttk.Combobox)
                                and 'Sélection' in w.cget('values'))
                    mission_box = next(w for w in all_widgets if isinstance(w, ttk.Combobox)
                                       and 'viewport_second' in w.cget('values'))
                    zoom = next(w for w in all_widgets if isinstance(w, ttk.Button)
                                and w.cget('text') == '+')
                    tool.set('Sélection')
                    canvas.event_generate('<Button-1>', x=100, y=100)
                    canvas.event_generate('<ButtonRelease-1>', x=100, y=100)
                    root.update()
                    heading = inspect_heading(root)
                    zoom.invoke()
                    root.update()
                    flat_region = canvas.cget('scrollregion')
                    self.assertEqual(float(flat_region.split()[2]), 
                                     data['missions'][0]['board']['width'] * 60)
                    radios['Iso 2.5D'].invoke()
                    root.update()
                    self.assertTrue(radios['Iso 2.5D'].instate(['selected']))
                    self.assertTrue(canvas.find_all())
                    self.assertEqual(inspect_heading(root), heading)
                    self.assertEqual(view_for(load_views(path), first)['projection'],
                                     'iso')
                    mission_box.set('viewport_second')
                    mission_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    self.assertTrue(radios['2D'].instate(['selected']))
                    self.assertEqual(view_for(load_views(path),
                                              'viewport_second')['projection'], '2d')
                    mission_box.set(first)
                    mission_box.event_generate('<<ComboboxSelected>>')
                    root.update()
                    self.assertTrue(radios['Iso 2.5D'].instate(['selected']))
                    radios['2D'].invoke()
                    root.update()
                    self.assertEqual(canvas.cget('scrollregion'), flat_region)
                    self.assertEqual(view_for(load_views(path), first)['projection'],
                                     '2d')
                    radios['Iso 2.5D'].invoke()
                    root.update()
                    self.assertEqual(view_for(load_views(path), first)['projection'],
                                     'iso')
                    self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', drive), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(path)
                show_error.assert_not_called()

            def reopened(root):
                try:
                    root.report_callback_exception = lambda *exc: errors.append(exc)
                    root.update()
                    self.assertTrue(selector(root)['Iso 2.5D'].instate(['selected']))
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, 'mainloop', reopened), \
                 patch('tkinter.messagebox.showerror') as show_error:
                launch(path)
                show_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
