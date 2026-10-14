"""Visual theme regression gates; no gameplay or graphics dependencies."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.studio_theme import (
    PALETTES, AppearancePreferences, StudioAppearance,
    contrast_ratio, palette_for,
)


class StudioThemeTests(unittest.TestCase):
    def test_text_contrast_and_semantic_selection(self):
        for name, palette in PALETTES.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(
                    contrast_ratio(palette.text, palette.surface), 7.0)
                self.assertGreaterEqual(
                    contrast_ratio(palette.muted, palette.surface), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(palette.accent_text, palette.accent), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(palette.selected_text, palette.selected), 4.5)
                self.assertGreaterEqual(
                    contrast_ratio(palette.text, palette.elevated), 4.5)
                for item in vars(palette).values():
                    self.assertRegex(item, r"^#[0-9A-Fa-f]{6}$")
        with self.assertRaises(ValueError):
            palette_for("theme-not-in-catalog")

    def test_preferences_roundtrip_and_invalid_inputs(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.workspace.appearance.json"
            store = AppearancePreferences(path)
            self.assertEqual(store.load(), "light")
            store.save("dark")
            self.assertEqual(store.load(), "dark")
            self.assertEqual(json.loads(path.read_text()), {"theme": "dark"})
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                store.save("not-a-theme")
            self.assertEqual(path.read_bytes(), before)
            for content in ('{bad', '[]', '{"theme": []}',
                            '{"theme": {}}', '{"theme": null}',
                            '{"theme": "legacy"}'):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(store.load(), "light")


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Real Tk display / Xvfb required")
class StudioThemeTkTests(unittest.TestCase):
    def test_light_dark_switch_preserves_widget_identity(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        try:
            appearance = StudioAppearance(root, ttk)
            self.assertEqual(appearance.mode, "light")
            root.geometry("1250x840")
            controls = ttk.Frame(root)
            controls.pack()
            btn = ttk.Button(controls, text="Playtest",
                             style="Studio.Primary.TButton")
            btn.pack()
            text = tk.Text(root, height=3)
            text.pack()
            text.insert("1.0", "Éditeur")
            canvas = tk.Canvas(root, width=150, height=100)
            canvas.pack()
            canvas.create_rectangle(3, 4, 32, 42, fill="#AABBCC")
            appearance.register_text(text)
            appearance.register_canvas(canvas)
            root.update()
            canvas_items = canvas.find_all()
            before = (str(btn), str(text), str(canvas))
            appearance.apply("dark")
            root.update()
            self.assertEqual(text.get("1.0", "end-1c"), "Éditeur")
            self.assertEqual(canvas_items, canvas.find_all())
            self.assertEqual((str(btn), str(text), str(canvas)), before)
            self.assertEqual(str(text.cget("background")), PALETTES["dark"].surface)
            self.assertEqual(str(canvas.cget("background")), PALETTES["dark"].canvas)
            self.assertEqual(
                appearance.style.lookup("Studio.Primary.TButton", "background"),
                PALETTES["dark"].accent)
            appearance.apply("light")
            root.update()
            self.assertEqual(text.cget("background"), PALETTES["light"].surface)
            self.assertEqual(canvas.find_all(), canvas_items)
        finally:
            root.destroy()


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Real Tk display / Xvfb required")
class StudioEditorAppearanceSmoke(unittest.TestCase):
    def test_live_studio_switches_theme_without_recreating_map(self):
        from unittest.mock import patch
        import tkinter as tk
        from tkinter import ttk
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.editor import launch

        caught = []

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def drive(root):
            try:
                root.report_callback_exception = lambda *args: caught.append(args)
                root.update()
                menu_button = next(
                    w for w in descendants(root)
                    if isinstance(w, ttk.Menubutton)
                    and w.cget("text") == "Affichage ▾")
                menu = root.nametowidget(menu_button.cget("menu"))
                dark_index = next(
                    i for i in range(menu.index("end") + 1)
                    if menu.type(i) == "radiobutton"
                    and menu.entrycget(i, "label") == "Thème sombre")
                light_index = next(
                    i for i in range(menu.index("end") + 1)
                    if menu.type(i) == "radiobutton"
                    and menu.entrycget(i, "label") == "Thème clair")
                canvas = next(
                    w for w in descendants(root)
                    if isinstance(w, tk.Canvas) and
                    ("<Button-1>" in w.bind() or
                     "<B1-Motion>" in w.bind()))
                original = str(canvas)
                menu.invoke(dark_index)
                root.update()
                self.assertEqual(root._studio_palette, PALETTES["dark"])
                self.assertEqual(root.cget("background"),
                                 PALETTES["dark"].background)
                menu.invoke(light_index)
                root.update()
                self.assertEqual(root._studio_palette, PALETTES["light"])
                self.assertEqual(str(canvas), original)
                self.assertFalse(caught)
            finally:
                root.destroy()

        with patch.object(tk.Tk, "mainloop", drive), \\
             patch("tkinter.messagebox.showerror") as dialogs:
            launch(DEFAULT_CONTENT)
            dialogs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
