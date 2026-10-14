"""Real Tk VF-B gallery: lazy art previews do not mutate map-authoring tools."""
import json
import os
from pathlib import Path
from hashlib import sha256
from tempfile import TemporaryDirectory
import unittest

from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_map import IsoTerrainAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.studio_asset_palette import AssetPalette
from sporebound.watercolor_catalog import (
    DEFAULT_WATERCOLOR_ROOT, WatercolorCatalog,
)


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Requires a real Tk display")
class WatercolorCatalogGuiTests(unittest.TestCase):
    def test_88_sprites_15_animations_and_certified_preview(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            chosen = []
            palette = AssetPalette(
                root, terrain=IsoTerrainAtlas(canvas), props=IsoPropAtlas(canvas),
                buildings=IsoBuildingAtlas(canvas),
                fortifications=IsoFortificationAtlas(canvas),
                choose=lambda e, n: chosen.append(e.id) or True,
                cell_size=lambda: 54)
            root.update()
            palette.category.set("Aquarelle")
            root.update()
            self.assertEqual(len(palette.tree.get_children()), 9)
            self.assertTrue(palette.tree.exists("watercolor-group:jeanne"))
            self.assertFalse(palette.tree.item("watercolor-group:jeanne", "open"))
            self.assertFalse(palette.tree.exists("watercolor:jeanne_walk_b"))
            self.assertIn("watercolor:anim_jeanne_walk",
                          palette.tree.get_children("watercolor-group:jeanne"))

            # One character row; swap its pose/animation without expanding
            # 12 individual frames into the library.
            palette.tree.selection_set("watercolor-group:jeanne")
            palette.select()
            self.assertEqual(palette.selected().id, "watercolor:jeanne_idle")
            self.assertTrue(palette.variant_controls.winfo_manager())
            walk = next(label for label, eid in palette._group_option_lookup.items()
                        if eid == "watercolor:anim_jeanne_walk")
            palette.watercolor_variant.set(walk)
            palette.choose_group_variant()
            self.assertEqual(palette.selected().id, "watercolor:anim_jeanne_walk")
            self.assertTrue(palette.watercolor_animation_controls.winfo_manager())
            self.assertFalse(palette.tree.item("watercolor-group:jeanne", "open"))

            # Exact-ID search can still reveal a frame hidden by default.
            palette.query.set("jeanne_walk_b")
            root.update()
            self.assertTrue(palette.tree.exists("watercolor:jeanne_walk_b"))
            self.assertTrue(palette.tree.item("watercolor-group:jeanne", "open"))
            palette.query.set("")
            root.update()

            palette.tree.selection_set("watercolor:jeanne_idle")
            palette.select()
            self.assertIn("PNG absent", palette.detail.get())
            self.assertTrue(palette.use_button.instate(["disabled"]))
            palette.use()
            self.assertEqual(chosen, [])

            palette.tree.selection_set("watercolor:anim_jeanne_walk")
            palette.select()
            self.assertTrue(palette.watercolor_animation_controls.winfo_manager())
            self.assertEqual(tuple(palette.watercolor_frame_selector["values"]),
                             ("0", "1"))
            palette.watercolor_frame.set("1")
            palette.preview()
            self.assertIn("jeanne_walk_b", palette.detail.get())
            palette.play_watercolor()
            self.assertIsNotNone(palette._watercolor_timer)
            palette.stop_watercolor()
            self.assertIsNone(palette._watercolor_timer)
            palette.watercolor_frame.set("1")
            palette.preview()

            # Publish one matching preview sprite in an isolated temp gallery.
            # The normal 88 files remain optional and untouched on disk.
            with TemporaryDirectory() as tmp:
                temp = Path(tmp)
                for name in ("index.json", "registry.json", "provenance.json"):
                    (temp / name).write_bytes(
                        (DEFAULT_WATERCOLOR_ROOT / name).read_bytes())
                art = temp / "sprites/jeanne/walk_b.png"
                art.parent.mkdir(parents=True, exist_ok=True)
                source = tk.PhotoImage(width=384, height=341, master=root)
                source.put("#d17c31", to=(130, 50, 265, 310))
                source.write(str(art), format="png")
                provenance_file = temp / "provenance.json"
                provenance = json.loads(provenance_file.read_text())
                provenance["sprite_hashes"]["sprites/jeanne/walk_b.png"] = (
                    sha256(art.read_bytes()).hexdigest())
                provenance_file.write_text(json.dumps(provenance))
                palette.watercolor = WatercolorCatalog(temp)
                palette.preview()
                self.assertIsNotNone(palette.preview_image)
                self.assertIn("Sprite V3 vérifié", palette.detail.get())
                self.assertTrue(palette.use_button.instate(["disabled"]))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
