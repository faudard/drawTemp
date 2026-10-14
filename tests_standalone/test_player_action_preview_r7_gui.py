"""R7.9 Player Tk smoke: optional hover preview, projections, cleanup."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a display")
class ActionPreviewR7GuiTests(unittest.TestCase):
    def test_preview_is_opt_in_tracks_hover_and_disposes_on_navigation(self):
        with TemporaryDirectory() as directory:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(directory) / "profile")
            try:
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "battle")
                self.assertFalse(app.preview_enabled.get())
                self.assertFalse(app.preview_panel.winfo_manager())

                app.preview_enabled.set(True)
                app._toggle_action_preview()
                self.assertTrue(app.preview_panel.winfo_manager())
                self.assertIn("Déploiement", app.preview_var.get())
                original = app.selection
                # Hover must not commit the selection or execute a command.
                app._preview_motion(SimpleNamespace(x=25, y=25))
                app._update_action_preview()
                self.assertEqual(app.selection, original)
                self.assertTrue(app.preview_var.get())
                self.assertTrue(app.canvas.find_withtag("player_action_preview"))
                app._preview_leave()
                self.assertEqual(app.selection, original)

                for iso in (False, True):
                    app.iso_view_var.set(iso)
                    app._switch_projection()
                    for size in (24, 54, 96):
                        app._zoom_preset(size)
                        app.root.update_idletasks()
                        self.assertEqual(app.camera.cell_size, size)
                        self.assertTrue(app.preview_var.get())

                app.preview_enabled.set(False)
                app._toggle_action_preview()
                self.assertFalse(app.preview_panel.winfo_manager())
                self.assertFalse(app.canvas.find_withtag("player_action_preview"))
                self.assertIsNone(app._preview_result)
                app.title_screen()
                self.assertIsNone(app._preview_job)
                self.assertIsNone(app.canvas)
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
