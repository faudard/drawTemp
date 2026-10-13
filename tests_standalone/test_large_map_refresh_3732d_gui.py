"""Xvfb end-to-end: 128² editor keeps minimap background while panning.

The real Editor, StudioPanels, Workspace and Canvas are exercised together.
A brush edit must invalidate the background; merely panning must not.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import launch
from sporebound.model import Content


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tcl/Tk and Xvfb")
class LargeMapRefreshGuiTests(unittest.TestCase):
    def test_real_128_map_pan_does_not_rebuild_minimap_but_edit_does(self):
        import tkinter as tk

        source = Content.load(DEFAULT_CONTENT).to_dict()
        data = add_blank_mission(source, "performance_large",
                                 "Performance 128", 128, 128)
        large = next(m for m in data["missions"] if m["id"] == "performance_large")
        data["missions"] = [large] + [
            m for m in data["missions"] if m["id"] != "performance_large"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "large-map.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            failures = []

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            def drive(root):
                try:
                    root.report_callback_exception = (
                        lambda *error: failures.append(
                            "".join(traceback.format_exception(*error))))
                    root.update()
                    canvases = [
                        w for w in descendants(root) if isinstance(w, tk.Canvas)]
                    mini = next(w for w in canvases
                                if int(w.cget("width")) == 184 and
                                int(w.cget("height")) == 184)
                    main = next(w for w in canvases
                                if w is not mini and
                                len(w.find_all()) >= 128 * 128)
                    before = mini.find_all()
                    self.assertGreater(len(before), 1)
                    mini.event_generate("<Button-1>", x=90, y=120)
                    root.update()
                    after_pan = mini.find_all()
                    self.assertEqual(before[:-1], after_pan[:-1],
                                     "Navigation unexpectedly rebuilt terrain")
                    self.assertNotEqual(before[-1], after_pan[-1])

                    # A wall painted on an otherwise empty map adds a
                    # distinctive minimap square: the static scene must update.
                    main.event_generate("<Button-1>", x=110, y=108)
                    main.event_generate("<ButtonRelease-1>", x=110, y=108)
                    root.update()
                    after_edit = mini.find_all()
                    self.assertNotEqual(after_pan[:-1], after_edit[:-1],
                                        "Brush edit unexpectedly reused terrain")
                    # An invisible Studio remains deferred until its tab is
                    # opened. At that point all editors must catch up safely.
                    from tkinter import ttk
                    notebooks = [w for w in descendants(root)
                                 if isinstance(w, ttk.Notebook)]
                    project_tabs = next(w for w in notebooks
                                        if 'Espace projet' in [
                                            w.tab(t, 'text') for t in w.tabs()])
                    workspace_tab = next(
                        t for t in project_tabs.tabs()
                        if project_tabs.tab(t, 'text') == 'Espace projet')
                    project_tabs.select(workspace_tab)
                    root.update()
                    workspace = root.nametowidget(workspace_tab)
                    resource_tree = next(w for w in descendants(workspace)
                                         if isinstance(w, ttk.Treeview)
                                         and w.exists('mission:performance_large'))
                    self.assertTrue(resource_tree.exists(
                        'mission:performance_large'))
                    self.assertFalse(failures, failures)
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as errors:
                launch(path)
                self.assertFalse(errors.called, errors.call_args_list)


    def test_128_iso_revision_invalidates_scene_and_matches_clean_draw(self):
        import tkinter as tk
        from sporebound.editor_refresh_scale import EditorContentProjection
        from sporebound.editor_render_cache import EditorRenderCache

        root = tk.Tk()
        try:
            root.geometry("700x500")
            canvas = tk.Canvas(root, width=650, height=450)
            canvas.pack()
            root.update()
            raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                    "iso_large", "Grande carte ISO", 128, 128)
            model = EditorContentProjection()
            renderer = EditorRenderCache(canvas)

            def draw(selected):
                content = model.get(raw)
                mission = content.missions["iso_large"]
                renderer.draw(
                    mission.board, mission, mission.units, cell_size=54,
                    layers={}, selected_cell=selected, selected_tiles=(),
                    scene_revision=(model.generation, mission.id))
                root.update_idletasks()

            draw((0, 0))
            self.assertEqual(renderer.stats["fast_path"], "full")
            draw((1, 0))
            self.assertEqual(renderer.stats["fast_path"], "selection")
            # A nested terrain mutation must reject the old scene,
            # including its cached isometric geometry.
            row = next(m for m in raw["missions"] if m["id"] == "iso_large")
            row["board"]["tiles"].append(
                {"pos": [2, 2], "height": 1, "surface": "water",
                 "blocked": True})
            draw((1, 0))
            self.assertEqual(renderer.stats["fast_path"], "full")
            self.assertTrue(renderer.stats["geometry_rebuilt"])

            # Same renderer after explicit cache reset is the parity oracle.
            def canvas_snapshot():
                return tuple((
                    canvas.type(i), tuple(canvas.coords(i)),
                    canvas.itemcget(i, "fill"),
                    canvas.itemcget(i, "outline")
                    if canvas.type(i) in ("polygon", "rectangle", "oval") else "",
                    canvas.itemcget(i, "text")
                    if canvas.type(i) == "text" else "",
                ) for i in canvas.find_all())

            fast = canvas_snapshot()
            renderer.invalidate()
            draw((1, 0))
            self.assertEqual(canvas_snapshot(), fast)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
