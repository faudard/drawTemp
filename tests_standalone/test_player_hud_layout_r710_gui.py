"""R7.10 acceptance gate for the compact, responsive Tk Combat HUD."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a live Tk display")
class PlayerHudLayoutR710GuiTests(unittest.TestCase):
    def test_battle_viewport_ct_toolbar_and_collapsible_notebook(self):
        from tkinter import ttk
        with TemporaryDirectory() as tmp:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(tmp) / "profile")
            try:
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "battle")
                self.assertIsNotNone(app.canvas)
                self.assertEqual(len(app.hud_panes.panes()), 2)
                self.assertIs(app.info.master, app.hud_tactics_tab)
                self.assertIs(app.canvas.master.master, app.hud_map)
                self.assertIsNotNone(app.hud_footer)
                self.assertIn("Objectif :", app.hud_objective_var.get())
                self.assertTrue(app.hud_focus_var.get())
                self.assertTrue(app.hud_party_var.get())
                self.assertIn("PV", app.info.get("1.0", "end"))
                self.assertEqual(app.hud_notebook.tab(
                    app.hud_journal_tab, "state"), "hidden")

                app.hud_log_visible.set(True)
                app._toggle_combat_log()
                self.assertEqual(app.hud_notebook.tab(
                    app.hud_journal_tab, "state"), "normal")
                self.assertEqual(app.hud_notebook.select(),
                                 str(app.hud_journal_tab))
                app.hud_log_visible.set(False)
                app._toggle_combat_log()
                self.assertEqual(app.hud_notebook.tab(
                    app.hud_journal_tab, "state"), "hidden")

                app.guidance_enabled.set(True)
                app._toggle_guidance()
                self.assertEqual(app.guide_panel.winfo_manager(), "pack")
                self.assertEqual(app.hud_notebook.select(),
                                 str(app.hud_assistance_tab))
                app.preview_enabled.set(True)
                app._toggle_action_preview()
                self.assertEqual(app.preview_panel.winfo_manager(), "pack")
                app.guidance_enabled.set(False)
                app._toggle_guidance()
                app.preview_enabled.set(False)
                app._toggle_action_preview()

                app._toggle_hud_sidebar()
                self.assertEqual(len(app.hud_panes.panes()), 1)
                self.assertFalse(app.hud_sidebar_visible.get())
                app._toggle_hud_sidebar()
                self.assertEqual(len(app.hud_panes.panes()), 2)
                self.assertTrue(app.hud_sidebar_visible.get())

                for size in (24, 54, 96):
                    app._zoom_preset(size)
                    self.assertEqual(app.camera.cell_size, size)
                app.root.geometry("800x580")
                app.root.update()
                self.assertGreater(app.canvas.winfo_width(), 100)
                self.assertGreater(app.canvas.winfo_height(), 100)
                self.assertTrue(app.canvas.cget("takefocus"))
                self.assertTrue(any(
                    child.winfo_manager() == "pack"
                    for child in app.hud_footer.winfo_children()))
            finally:
                app.close()

    def test_compact_high_contrast_has_same_controls(self):
        with TemporaryDirectory() as tmp:
            app = PlayerApplication(DEFAULT_CONTENT,
                                    profile_path=Path(tmp) / "profile")
            try:
                app.high_contrast.set(True)
                app.compact_hud.set(True)
                app.text_scale.set(125)
                app._style()
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                app.show()
                app.root.update()
                self.assertEqual(app.info.cget("bg"), "#000000")
                self.assertEqual(app.hud_journal.cget("bg"), "#000000")
                self.assertEqual(app.hud_party.cget("bg"), "#000000")
                self.assertIn("PV", app.hud_focus_var.get())
                self.assertTrue(app.canvas.bind(app.keymap.get("execute")))
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
