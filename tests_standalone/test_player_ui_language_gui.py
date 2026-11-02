"""Tk Options language selection acceptance test, intended for Xvfb CI."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication
from sporebound.player_ui_language import load_ui_language


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires display / Xvfb")
class GameLanguageGuiTests(unittest.TestCase):
    def test_options_apply_cancel_and_persistence(self):
        from tkinter import ttk
        def descendants(root):
            for child in root.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as folder:
            profile = Path(folder) / "test.profile"
            app = PlayerApplication(DEFAULT_CONTENT, profile_path=profile)
            try:
                self.assertEqual(app.ui_language, "en")
                app.options_screen()
                lang = next(w for w in descendants(app.root)
                            if isinstance(w, ttk.Combobox)
                            and "Français" in w.cget("values"))
                self.assertEqual(lang.get(), "English")
                lang.set("Français")
                cancel = next(w for w in descendants(app.root)
                              if isinstance(w, ttk.Button)
                              and w.cget("text") == "Back without saving")
                cancel.invoke()
                app.root.update()
                self.assertEqual(load_ui_language(profile), ("en", None))
                app.options_screen()
                lang = next(w for w in descendants(app.root)
                            if isinstance(w, ttk.Combobox)
                            and "Français" in w.cget("values"))
                lang.set("Français")
                apply = next(w for w in descendants(app.root)
                             if isinstance(w, ttk.Button)
                             and w.cget("text") == "Apply")
                apply.invoke()
                app.root.update()
                self.assertEqual(app.ui_language, "fr")
                self.assertEqual(load_ui_language(profile), ("fr", None))
                app.options_screen()
                labels = [w.cget("text") for w in descendants(app.root)
                          if isinstance(w, ttk.Label)]
                self.assertIn("Langue du jeu", labels)
            finally:
                app.close()
            reopened = PlayerApplication(DEFAULT_CONTENT, profile_path=profile)
            try:
                self.assertEqual(reopened.ui_language, "fr")
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
