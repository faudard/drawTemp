"""Player R7 Tk smoke; run with SPOREBOUND_GUI_SMOKE=1 and a display."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class PlayerUXR7GuiTests(unittest.TestCase):
    def test_keyboard_focus_zoom_hud_and_accessibility(self):
        with TemporaryDirectory() as tmp:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(tmp) / "player.profile")
            try:
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "battle")
                self.assertIsNotNone(app.canvas)
                self.assertIn("Case", app.feedback_var.get())
                for size in (24, 54, 96):
                    app._zoom_preset(size)
                    self.assertEqual(app.camera.cell_size, size)
                app._key_action("east")
                self.assertTrue(app.selection[0] >= 0)
                app._key_action("cancel")
                app.high_contrast.set(True)
                app.text_scale.set(125)
                app._style()
                app.battle_screen()
                app.root.update()
                self.assertIn("PV", app.info.get("1.0", "end"))
                self.assertTrue(app.canvas.cget("takefocus"))
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
