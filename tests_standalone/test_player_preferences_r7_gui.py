"""R7.7 real Tk settings Apply -> relaunch -> restore acceptance gate."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication
from sporebound.player_preferences import preferences_path


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class PlayerPreferencesR7GUI(unittest.TestCase):
    def test_apply_and_relaunch_without_game_session_migration(self):
        from tkinter import ttk
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            app = PlayerApplication(DEFAULT_CONTENT, profile_path=profile)
            try:
                app.options_screen()
                app.high_contrast.set(True)
                app.text_scale.set(150)
                app.compact_hud.set(True)
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                mappings = [w for w in descendants(app.root)
                            if isinstance(w, ttk.Combobox)
                            and w.get() == "Entrée"]
                self.assertEqual(len(mappings), 1)
                self.assertFalse(any(
                    isinstance(w, ttk.Checkbutton) and
                    "playtests" in w.cget("text").lower()
                    for w in descendants(app.root)))
                mappings[0].set("F1")
                apply = next(w for w in descendants(app.root)
                             if isinstance(w, ttk.Button)
                             and w.cget("text") == "Appliquer")
                with patch.object(app.messagebox, "showerror") as show_error:
                    apply.invoke()
                    app.root.update()
                    show_error.assert_not_called()
                self.assertTrue(preferences_path(profile).exists())
            finally:
                app.close()
            reopened = PlayerApplication(DEFAULT_CONTENT, profile_path=profile)
            try:
                self.assertTrue(reopened.high_contrast.get())
                self.assertEqual(reopened.text_scale.get(), 150)
                self.assertTrue(reopened.compact_hud.get())
                self.assertEqual(reopened.keymap.get("execute"), "<F1>")
                self.assertFalse(reopened.player.session)
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
