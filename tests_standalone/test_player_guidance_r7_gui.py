"""R7.8 Player guidance is actually wired into Tk and handles RuleError inline."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.model import RuleError
from sporebound.player_app import PlayerApplication


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Xvfb or a Tk display")
class PlayerGuidanceR7GuiTests(unittest.TestCase):
    def test_opt_in_help_and_rejected_command_are_non_blocking(self):
        import tkinter.ttk as ttk

        with TemporaryDirectory() as directory:
            app = PlayerApplication(
                DEFAULT_CONTENT, profile_path=Path(directory) / "profile")
            try:
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                app.show()
                app.root.update()
                self.assertEqual(app.presentation.screen, "battle")
                self.assertFalse(app.guidance_enabled.get())
                self.assertFalse(app.guide_panel.winfo_manager())

                app.guidance_enabled.set(True)
                app._toggle_guidance()
                self.assertEqual(app.guide_panel.winfo_manager(), "pack")
                self.assertIn("déploiement", app.guidance_var.get().lower())

                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                action_boxes = [
                    child for child in descendants(app.root)
                    if isinstance(child, ttk.Combobox)
                    and "deploy" in child.cget("values")
                ]
                self.assertEqual(len(action_boxes), 1)
                action_boxes[0].set("start_battle")
                action_boxes[0].event_generate("<<ComboboxSelected>>")
                app.root.update()
                self.assertTrue(app.guidance_var.get())

                app.action_var.set("deploy")
                with patch.object(app.player, "execute",
                                  side_effect=RuleError("case interdite")):
                    with patch.object(app.messagebox, "showerror") as popup:
                        app._execute()
                        popup.assert_not_called()
                self.assertIn("case interdite", app.feedback_var.get())

                app.guidance_enabled.set(False)
                app._toggle_guidance()
                self.assertFalse(app.guide_panel.winfo_manager())
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
