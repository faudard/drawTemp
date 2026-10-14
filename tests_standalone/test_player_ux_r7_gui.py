"""Real Tk acceptance smoke for R7; CI must set SPOREBOUND_GUI_SMOKE=1."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class PlayerUXR7GuiTests(unittest.TestCase):
    def test_keyboard_zoom_hud_accessibility_and_results(self):
        from tkinter import ttk
        with TemporaryDirectory() as tmp:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(tmp) / "player.profile")
            battle = None
            try:
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                battle = app.player.session.active_battle
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "battle")
                self.assertIsNotNone(app.canvas)
                self.assertIn("Case", app.feedback_var.get())
                self.assertTrue(app.canvas.bind(app.keymap.get("execute")))
                for iso in (False, True):
                    app.iso_view_var.set(iso)
                    app._switch_projection()
                    app.root.update_idletasks()
                    for size in (24, 54, 96):
                        app._zoom_preset(size)
                        self.assertEqual(app.camera.cell_size, size)
                app._key_action("east")
                self.assertGreaterEqual(app.selection[0], 0)
                app._key_action("cancel")
                app._key_action("pan_north")
                app.keymap.replace({"execute": "<F1>", "end": "<F2>"})
                app.high_contrast.set(True)
                app.text_scale.set(125)
                app.compact_hud.set(True)
                app._style()
                app.battle_screen()
                app.root.update()
                self.assertTrue(app.canvas.bind("<F1>"))
                self.assertIn("PV", app.info.get("1.0", "end"))
                self.assertEqual(app.info.cget("bg"), "#000000")
                self.assertTrue(app.canvas.cget("takefocus"))

                # Exercise results rendering only: do not serialize a forged
                # terminal Battle. GameSession replay/persistence is independently
                # exercised by headless campaign tests.
                battle.result = "victory"
                app.player.session.finalized = True
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "results")

                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                labels = [w.cget("text") for w in descendants(app.root)
                          if isinstance(w, ttk.Label)]
                buttons = [w.cget("text") for w in descendants(app.root)
                           if isinstance(w, ttk.Button)]
                self.assertTrue(any("Résultats" in text for text in labels))
                self.assertIn("Continuer vers la campagne", buttons)
                self.assertIn("Voir le champ de bataille", buttons)
                old_revision = app.presentation.revision
                app.title_screen()
                self.assertFalse(app.presentation.current(old_revision))
                self.assertEqual(app.presentation.screen, "title")
            finally:
                if battle is not None:
                    # The mock result is visual-only, not a valid saved replay.
                    battle.result = None
                    app.player.session.finalized = False
                app.close()


if __name__ == "__main__":
    unittest.main()
