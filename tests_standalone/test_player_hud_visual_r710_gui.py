"""Real Tk/Xvfb visual acceptance matrix for Player Combat HUD R7.10.

Stores lossless window screenshots + measured layout rectangles; this is a
pixel-backed UI test, NOT a mock or an illustration. Non-zero on clipping,
invisible action controls or unusable map viewport.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.player_app import PlayerApplication


def rectangle(widget):
    return {
        "x": widget.winfo_rootx(),
        "y": widget.winfo_rooty(),
        "width": widget.winfo_width(),
        "height": widget.winfo_height(),
    }


def contains(outer, inner, tolerance=3):
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and inner["x"] + inner["width"] <=
        outer["x"] + outer["width"] + tolerance
        and inner["y"] + inner["height"] <=
        outer["y"] + outer["height"] + tolerance
    )


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk display")
class PlayerHudVisualR710Tests(unittest.TestCase):
    def test_real_player_viewport_and_screenshots(self):
        from tkinter import ttk
        from PIL import ImageGrab

        directory = os.environ.get("SPOREBOUND_HUD_VISUAL_DIR")
        self.assertTrue(directory, "SPOREBOUND_HUD_VISUAL_DIR is required")
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory() as temporary:
            app = PlayerApplication(
                DEFAULT_CONTENT, profile_path=Path(temporary) / "profile")
            snapshots = []
            try:
                app.root.attributes("-fullscreen", False)
                app.player.new_game("main", 1)
                app.player.start_mission("garden")
                self.assertIsNotNone(app.player.session.active_battle)
                # Each screenshot contains the REAL runtime BattleFrame and
                # Tk widgets, not a recreated mock scene.
                scenarios = (
                    (800, 580, False, False, False, 100),
                    (800, 580, True, False, False, 100),
                    (1160, 820, False, False, False, 100),
                    (1160, 820, True, False, False, 100),
                    (1920, 1080, False, False, False, 100),
                    (1920, 1080, True, False, False, 100),
                    (800, 580, False, True, True, 125),
                    (1160, 820, True, True, True, 150),
                )
                for width, height, iso, compact, contrast, text_scale in scenarios:
                    case = (f"{width}x{height}-"
                            f"{'iso' if iso else '2d'}-"
                            f"{'compact' if compact else 'normal'}-"
                            f"{'hc' if contrast else 'default'}-{text_scale}")
                    with self.subTest(case=case):
                        app.compact_hud.set(compact)
                        app.high_contrast.set(contrast)
                        app.text_scale.set(text_scale)
                        app._style()
                        app.iso_view_var.set(iso)
                        app.battle_screen()
                        app.root.geometry(f"{width}x{height}+0+0")
                        app.root.update()
                        app._switch_projection()
                        app.root.update()

                        win = rectangle(app.root)
                        canvas = rectangle(app.canvas)
                        footer = rectangle(app.hud_footer)
                        strip = rectangle(app.hud_workspace)
                        side = rectangle(app.hud_sidebar)
                        # A passing layout must leave a sizeable practical
                        # map and keep action submission controls visible.
                        buttons = {
                            w.cget("text"): rectangle(w)
                            for w in descendants(app.hud_footer)
                            if isinstance(w, ttk.Button)
                        }
                        self.assertIn("Exécuter", buttons)
                        self.assertTrue(contains(win, buttons["Exécuter"]),
                                        (case, "execute clipped", buttons))
                        self.assertTrue(contains(win, footer),
                                        (case, "footer clipped", footer))
                        self.assertTrue(contains(win, canvas),
                                        (case, "canvas clipped", canvas))
                        self.assertGreaterEqual(canvas["width"], 160,
                                                (case, "narrow map", canvas))
                        self.assertGreaterEqual(canvas["height"], 140,
                                                (case, "short map", canvas))
                        self.assertGreaterEqual(side["width"], 180,
                                                (case, "sidebar collapsed", side))
                        self.assertEqual(
                            app.presentation.screen, "battle")
                        self.assertTrue(app.hud_objective_var.get())
                        self.assertEqual(app.info.cget("bg"),
                                         "#000000" if contrast else "#182a40")
                        if iso:
                            self.assertIsNotNone(app.iso_renderer.geometry)
                        # Inspect actual compositor output, NOT Canvas.postscript
                        # (which omits native controls and Tk image widgets).
                        shot = ImageGrab.grab(
                            bbox=(win["x"], win["y"],
                                  win["x"] + win["width"],
                                  win["y"] + win["height"]),
                            xdisplay=os.environ.get("DISPLAY"))
                        shot.save(output / (case + ".png"))
                        snapshots.append({
                            "case": case, "window": win, "canvas": canvas,
                            "footer": footer, "sidebar": side,
                            "workspace": strip,
                            "canvas_area_ratio": round(
                                canvas["width"] * canvas["height"] /
                                (win["width"] * win["height"]), 4),
                            "buttons": buttons,
                            "screenshot": case + ".png",
                        })
                # A collapsed sidebar must return the map space to the user.
                app.root.geometry("800x580+0+0")
                app.root.update()
                width_before = app.canvas.winfo_width()
                app._toggle_hud_sidebar()
                app.root.update()
                self.assertGreater(app.canvas.winfo_width(), width_before)
                app._toggle_hud_sidebar()
                app.root.update()
                self.assertEqual(len(app.hud_panes.panes()), 2)
            finally:
                (output / "layout-metrics.json").write_text(
                    json.dumps({"format": "drawtemp-r710-visual-v1",
                                "snapshots": snapshots},
                               ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                app.close()
        self.assertEqual(len(snapshots), 8)


if __name__ == "__main__":
    unittest.main()
