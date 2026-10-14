"""R7.18 real Tk/PNG alpha and Studio/Player Canvas parity gate (Xvfb)."""
import os
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import zlib

from sporebound.assets import AssetRegistry
from sporebound.cinematic_player import draw_frame
from sporebound.cinematic_visual_goldens import golden_at
from sporebound.tk_renderer import CanvasRenderer
from tests_standalone.test_r7_cinematic_goldens import castle_golden_clip


def _png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def synthetic_rgba_png():
    """2x2 PNG with transparent and opaque texels, no Pillow dependency."""
    header = struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0)
    # RGBA row: transparent red, opaque green / opaque blue, transparent white.
    raw = (b"\0" + bytes([255, 0, 0, 0, 0, 255, 0, 255]) +
           b"\0" + bytes([0, 0, 255, 255, 255, 255, 255, 0]))
    return (b"\x89PNG\r\n\x1a\n" +
            _png_chunk(b"IHDR", header) +
            _png_chunk(b"IDAT", zlib.compress(raw)) +
            _png_chunk(b"IEND", b""))


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Real Tk/Xvfb display required")
class R718TkFidelityTests(unittest.TestCase):
    def test_real_png_alpha_expressive_portrait_and_canvas_parity(self):
        import tkinter as tk
        root = tk.Tk()
        root.geometry("820x540")
        root.update_idletasks()
        renderer = None
        try:
            with TemporaryDirectory() as folder:
                image = Path(folder) / "face.png"
                image.write_bytes(synthetic_rgba_png())
                registry = AssetRegistry({
                    "version": 1,
                    "entries": [{"id": "face", "kind": "portrait",
                                 "path": "face.png"}],
                    "bindings": {"portrait": {"jeanne_determined": "face",
                                              "jeanne": "face"}},
                })
                clip = castle_golden_clip()
                canvas = tk.Canvas(root, width=800, height=500,
                                   highlightthickness=0)
                canvas.pack()
                root.update()
                renderer = CanvasRenderer(canvas, registry=registry,
                                          asset_root=folder)
                photo = renderer.image("portrait", "jeanne_determined")
                self.assertIsNotNone(photo)
                self.assertTrue(photo.transparency_get(0, 0))
                self.assertFalse(photo.transparency_get(1, 0))
                self.assertFalse(photo.transparency_get(0, 1))
                self.assertTrue(photo.transparency_get(1, 1))
                original = draw_frame(canvas, clip, 1000, renderer)
                self.assertEqual(original.dialogue_presentation.expression,
                                 "determined")
                self.assertTrue(any(canvas.type(i) == "image"
                                    for i in canvas.find_all()))
                self.assertEqual(golden_at(clip, 1000, portrait=True)
                                 ["dialogue"]["visible"], "Une ")
                # Studio preview and Player both use draw_frame; same input
                # and Canvas yield identical ordered draw commands.
                def capture():
                    return [(canvas.type(item), canvas.coords(item),
                             canvas.itemcget(item, "text")
                             if canvas.type(item) == "text" else "")
                            for item in canvas.find_all()]
                first = capture()
                self.assertEqual(draw_frame(canvas, clip, 1000, renderer),
                                 original)
                self.assertEqual(capture(), first)
                for viewport in ((640, 400), (1280, 800)):
                    canvas.configure(width=viewport[0], height=viewport[1])
                    root.update()
                    draw_frame(canvas, clip, 1000, renderer)
                    self.assertTrue(any(canvas.type(i) == "image"
                                        for i in canvas.find_all()))
                    self.assertEqual(
                        golden_at(clip, 1000, viewport=viewport,
                                  portrait=True)["portrait_images"],
                        ["portrait:jeanne_determined"])
        finally:
            if renderer is not None:
                renderer.dispose()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
