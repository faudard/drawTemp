"""Real-Tk regression: narrative choices must stay reachable at minimum size.

Opt-in smoke, since CI workers without a display cannot create a Tk window.
Run with SPOREBOUND_GUI_SMOKE=1 (Xvfb on Linux).
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.exploration import _key
from sporebound.player_app import PlayerApplication

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound" / "content" / "jeanne.json"
PROJECT = ROOT / "sporebound" / "content" / "jeanne.game.json"


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk display")
class NarrativeViewportTests(unittest.TestCase):
    def test_prologue_choices_and_navigation_are_visible_at_minimum_size(self):
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as directory:
            app = PlayerApplication(CONTENT, PROJECT,
                                    Path(directory) / "jeanne.game.json")
            root = app.root
            try:
                app.player.new_game("jeanne", 1)
                # Rendering fixture only: the gameplay gate verifies that a
                # player completes the exploratory hotspots before this flag.
                app.player.session.progress.story_flags[
                    _key("sc_p0_champs", "done")] = True
                for width, height in ((800, 580), (1160, 820)):
                    with self.subTest(size=(width, height)):
                        root.geometry(f"{width}x{height}")
                        app.show()
                        root.update()
                        buttons = [w for w in descendants(root)
                                   if isinstance(w, ttk.Button)]
                        for label in ("Écouter les voix.",
                                      "Faire taire la peur et continuer.",
                                      "Sauvegarder", "Menu principal"):
                            matches = [w for w in buttons if w.cget("text") == label]
                            self.assertEqual(len(matches), 1, label)
                            widget = matches[0]
                            self.assertTrue(widget.winfo_ismapped(), label)
                            self.assertLessEqual(
                                widget.winfo_rooty() + widget.winfo_height(),
                                root.winfo_rooty() + root.winfo_height(),
                                label + " fell below the game window")
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
