"""R22.2A procedural biome terrain: deterministic, safe, transactional."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_generation import BIOMES, MAX_SELECTION


def tiles(studio):
    return {tuple(row["pos"]): row for row in studio.mission()["board"]["tiles"]}


class TerrainGenerationTests(unittest.TestCase):
    def setUp(self):
        self.studio = MapStudio.reference()
        self.studio.create("r22_map", "Terrain R22", 16, 16)

    def test_preview_commit_one_undo_redo_and_roundtrip(self):
        before = self.studio.snapshot()
        preview = self.studio.preview_generation(
            seed=123, biome="Roche", coverage=100,
            cells=[(8, 8), (9, 8), (8, 9), (9, 9)],
        )
        self.assertEqual(self.studio.snapshot(), before)
        self.assertEqual(len(preview.cells), 4)
        self.studio.commit_generation(preview)
        self.assertEqual(self.studio.authoring.revision, before["revision"] + 1)
        expected = {(x, y): surface for x, y, surface in preview.cells}
        for cell, surface in expected.items():
            self.assertEqual(tiles(self.studio)[cell]["surface"], surface)
        after = self.studio.mission()
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], before["content"])
        self.studio.redo()
        self.assertEqual(self.studio.mission(), after)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            self.studio.save_as(path)
            reopened = MapStudio.open(path)
            reopened.select_map("r22_map")
            self.assertEqual(reopened.mission(), after)

    def test_seed_is_order_independent_and_repeatable(self):
        region = [(x, y) for y in range(5, 12) for x in range(5, 12)]
        p1 = self.studio.preview_generation(
            seed=77, biome="Marais", coverage=80, cells=region
        )
        p2 = self.studio.preview_generation(
            seed=77, biome="Marais", coverage=80, cells=list(reversed(region))
        )
        self.assertEqual(p1.cells, p2.cells)
        other = MapStudio.reference()
        other.create("r22_map", "Terrain R22", 16, 16)
        p3 = other.preview_generation(
            seed=77, biome="Marais", coverage=80, cells=region
        )
        self.assertEqual(p1.cells, p3.cells)
        self.assertTrue(all(surface in ("grass", "water", "dirt")
                            for _, _, surface in p1.cells))

    def test_existing_tiles_objective_actor_and_objects_preserved(self):
        self.studio.paint([(8, 8)], "surface:stone")
        self.studio.paint([(9, 9)], "goal")
        mission = self.studio.mission()
        actor_cell = tuple(mission["units"][0]["pos"])
        previous = self.studio.snapshot()
        self.studio.generate(seed=3, biome="Prairie", coverage=100)
        after = self.studio.mission()
        self.assertEqual(tiles(self.studio)[(8, 8)]["surface"], "stone")
        self.assertIn([9, 9], after["goal"])
        self.assertFalse(actor_cell in tiles(self.studio))
        self.assertEqual(after["units"], mission["units"])
        self.assertEqual(after["objects"], mission["objects"])
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], previous["content"])
        # The canonical reference mission contains lever/gate objects. They
        # are protected even if the user selects exactly their occupied cells.
        self.studio.select_map(self.studio.map_ids()[0])
        reference = self.studio.mission()
        obj_cell = tuple(reference["objects"][0]["pos"])
        ref_actor = tuple(reference["units"][0]["pos"])
        with self.assertRaises(RuleError):
            self.studio.preview_generation(
                seed=3, biome="Prairie", coverage=100,
                cells=[obj_cell, ref_actor]
            )

    def test_stale_preview_rejected_after_edit_undo_or_map_switch(self):
        preview = self.studio.preview_generation(
            seed=2, biome="Forêt", coverage=100, cells=[(8, 8)]
        )
        self.studio.paint([(10, 10)], "surface:stone")
        self.studio.undo()
        unchanged = self.studio.snapshot()
        with self.assertRaises(AuthoringError) as raised:
            self.studio.commit_generation(preview)
        self.assertEqual(raised.exception.code, "stale_revision")
        self.assertEqual(self.studio.snapshot(), unchanged)
        new = self.studio.preview_generation(
            seed=2, biome="Forêt", coverage=100, cells=[(8, 8)]
        )
        self.studio.select_map(self.studio.map_ids()[0])
        with self.assertRaises(AuthoringError):
            self.studio.commit_generation(new)

    def test_layer_lock_works_even_if_activated_after_preview(self):
        preview = self.studio.preview_generation(
            seed=4, biome="Prairie", coverage=100, cells=[(8, 8)]
        )
        self.studio.layers.set_locked(self.studio.mission_id, "Terrain", True)
        baseline = self.studio.snapshot()
        with self.assertRaises((RuleError, AuthoringError)):
            self.studio.commit_generation(preview)
        self.assertEqual(self.studio.snapshot(), baseline)
        with self.assertRaises((RuleError, AuthoringError)):
            self.studio.preview_generation(
                seed=4, biome="Prairie", coverage=100, cells=[(8, 8)]
            )

    def test_validation_and_guard_against_overwrite(self):
        for bad in (True, -1, 2147483648, "99"):
            with self.subTest(seed=bad), self.assertRaises(RuleError):
                self.studio.preview_generation(seed=bad, biome="Forêt")
        for bad in (0, 101, True, 1.2):
            with self.subTest(coverage=bad), self.assertRaises(RuleError):
                self.studio.preview_generation(seed=1, biome="Forêt", coverage=bad)
        with self.assertRaises(RuleError):
            self.studio.preview_generation(seed=1, biome="unknown")
        with self.assertRaises((RuleError, ValueError)):
            self.studio.preview_generation(
                seed=1, biome="Forêt", cells=[(999, 999)]
            )
        self.studio.paint([(8, 8)], "surface:grass")
        before = self.studio.snapshot()
        with self.assertRaises(RuleError):
            self.studio.preview_generation(
                seed=1, biome="Forêt", coverage=100, cells=[(8, 8)]
            )
        self.assertEqual(self.studio.snapshot(), before)
        self.assertEqual(MAX_SELECTION, 4096)
        self.assertEqual(set(BIOMES), {"Prairie", "Forêt", "Roche", "Marais"})

    def test_no_gui_dependencies_loaded(self):
        import subprocess
        import sys
        script = """
import sys
class UIBlock:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter', 'PyQt6'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, UIBlock())
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_generation import BIOMES
editor = MapStudio.reference()
editor.create("headless_r22", "Headless R22", 12, 12)
assert editor.preview_generation(seed=5, biome="Roche", coverage=100)
"""
        subprocess.run([sys.executable, "-c", script], check=True,
                       capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
