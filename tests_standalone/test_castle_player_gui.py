"""Real Tk smoke for the 2.8.1 castle player; gated by the Xvfb workflow."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.castle_vertical_slice import castle_blueprint, castle_content
from sporebound.castle_player_app import launch
from sporebound.castle_player_controller import CastlePlayerController
from sporebound.tactical_rpg3 import tactical_rpg_rules


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires Tk and a graphical display")
class CastlePlayerGuiTests(unittest.TestCase):
    def test_player_preparation_battle_strategy_and_checkpoint(self):
        import tkinter as tk
        from tkinter import ttk

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        with TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "castle_gui.json"
            errors = []

            def drive(root):
                root.report_callback_exception = lambda *args: errors.append(args)
                try:
                    root.update()

                    def button(label):
                        return next(w for w in descendants(root)
                                    if isinstance(w, ttk.Button) and
                                    w.cget("text") == label)

                    button("Nouvelle campagne").invoke()
                    root.update()
                    self.assertTrue(any(
                        isinstance(w, ttk.LabelFrame) and w.cget("text") == "Escouade"
                        for w in descendants(root)))
                    button("Déployer et commencer").invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, tk.Canvas)
                                        for w in descendants(root)))
                    button("Carte des fronts / Diplomatie").invoke()
                    root.update()
                    self.assertTrue(any(isinstance(w, ttk.Treeview)
                                        for w in descendants(root)))
                    button("Carte tactique").invoke()
                    root.update()
                    button("Début du combat").invoke()
                    root.update()
                    button("Sauvegarder").invoke()
                    root.update()
                    self.assertEqual(errors, [])
                finally:
                    root.destroy()

            with patch.object(tk.Tk, "mainloop", drive), \
                 patch("tkinter.messagebox.showerror") as error_box:
                launch(castle_content(), castle_blueprint(), save_path,
                       rules=tactical_rpg_rules())
                error_box.assert_not_called()
            loaded = CastlePlayerController(
                castle_content(), castle_blueprint(), save_path,
                rules=tactical_rpg_rules()).continue_game()
            self.assertEqual(loaded.approach, "ram")
            self.assertFalse(loaded.fronts.active.deploying)


if __name__ == "__main__":
    unittest.main()
