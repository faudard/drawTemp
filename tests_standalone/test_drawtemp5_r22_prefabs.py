"""R22.2B: reusable terrain patterns, serialization and smart brush contracts."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_prefabs import (
    TerrainPrefabLibrary, FILE_KIND, VERSION,
    MAX_CUSTOM, ORIENTATIONS,
)


class TerrainPrefabTests(unittest.TestCase):
    def setUp(self):
        self.studio = MapStudio.reference()
        self.studio.create("r22b_map", "R22B test", 16, 16)

    def tile(self, pos):
        return next((tile for tile in self.studio.mission()["board"]["tiles"]
                     if tuple(tile["pos"]) == pos), None)

    def test_builtin_shelf_is_stable_and_filterable(self):
        shelf = self.studio.prefabs
        self.assertEqual(len(shelf.entries()), 4)
        self.assertEqual([e.title for e in shelf.entries(query="ÉTANG")],
                         ["Petit étang"])
        self.assertEqual([e.title for e in shelf.entries(category="Chemins")],
                         ["Carrefour pavé"])
        self.assertTrue(all(e.builtin for e in shelf.entries()))
        self.assertEqual(shelf.entries(category="Mes modèles"), ())
        with self.assertRaises(RuleError):
            shelf.entries(category="Inconnu")
        with self.assertRaises(RuleError):
            shelf.get("builtin:unknown")
        with self.assertRaises(RuleError):
            shelf.get("builtin:pond", "recolor")

    def test_preview_paste_undo_redo_and_water_collision(self):
        before = self.studio.snapshot()
        preview = self.studio.preview_prefab("builtin:pond", (7, 7))
        self.assertEqual(self.studio.snapshot(), before)
        self.assertEqual(len(preview.target_cells), 25)
        self.studio.commit_prefab(preview)
        self.assertEqual(self.studio.authoring.revision, before["revision"] + 1)
        self.assertEqual(self.tile((9, 9))["surface"], "water")
        self.assertIs(self.tile((9, 9))["blocked"], True)
        self.assertEqual(self.tile((7, 7))["surface"], "sand")
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], before["content"])
        self.studio.redo()
        self.assertEqual(self.tile((9, 9))["surface"], "water")

    def test_collision_footprint_bounds_and_locked_layer(self):
        self.studio.paint([(8, 8)], "surface:stone")
        baseline = self.studio.snapshot()
        for anchor in ((7, 7), (14, 14), (0, 11)):
            with self.subTest(anchor=anchor), self.assertRaises(
                    (RuleError, AuthoringError)):
                self.studio.preview_prefab("builtin:pond", anchor)
        self.assertEqual(self.studio.snapshot(), baseline)
        preview = self.studio.preview_prefab("builtin:grove", (8, 3))
        self.studio.layers.set_locked(self.studio.mission_id, "Terrain", True)
        with self.assertRaises((RuleError, AuthoringError)):
            self.studio.commit_prefab(preview)
        self.assertEqual(self.studio.snapshot(), baseline)

    def test_preview_lease_expires_after_edit_and_undo(self):
        plan = self.studio.preview_prefab("builtin:camp", (8, 5))
        self.studio.paint([(12, 12)], "surface:sand")
        self.studio.undo()
        baseline = self.studio.snapshot()
        with self.assertRaises(AuthoringError) as raised:
            self.studio.commit_prefab(plan)
        self.assertEqual(raised.exception.code, "stale_revision")
        self.assertEqual(self.studio.snapshot(), baseline)
        plan = self.studio.preview_prefab("builtin:camp", (8, 5))
        self.studio.select_map(self.studio.map_ids()[0])
        with self.assertRaises(AuthoringError):
            self.studio.commit_prefab(plan)

    def test_capture_saved_prefab_roundtrips_goals_and_rotation(self):
        self.studio.paint([(4, 4)], "surface:stone")
        self.studio.paint([(5, 4)], "surface:cobble")
        self.studio.paint([(5, 4)], "goal")
        revision = self.studio.authoring.revision
        key = self.studio.capture_prefab("Chemin Test", [(4, 4), (5, 4)])
        self.assertEqual(key, "custom:chemin-test")
        self.assertEqual(self.studio.authoring.revision, revision)
        self.assertEqual(len(self.studio.prefabs.entries(category="Mes modèles")), 1)
        with self.assertRaises(RuleError):
            self.studio.capture_prefab("chemin test", [(4, 4)])
        for orientation in ORIENTATIONS:
            stamp = self.studio.prefabs.get(key, orientation)
            self.assertEqual(len(stamp.clip.offsets), 2)
            self.assertEqual(len(stamp.clip.goals), 1)

        with TemporaryDirectory() as folder:
            path = Path(folder) / "my-prefabs.json"
            self.studio.prefabs.export_file(path)
            original = path.read_bytes()
            with self.assertRaises(RuleError):
                self.studio.prefabs.export_file(path)
            self.assertEqual(path.read_bytes(), original)
            loaded = TerrainPrefabLibrary.import_file(path)
            self.assertEqual(
                loaded.get(key).clip, self.studio.prefabs.get(key).clip
            )
            self.assertEqual(len(loaded.entries()), 5)
            # Reuse in another map: no stable entity IDs are introduced.
            self.studio.prefabs = loaded
            preview = self.studio.preview_prefab(key, (9, 9))
            self.studio.commit_prefab(preview)
            self.assertEqual(self.tile((9, 9))["surface"], "stone")
            self.assertIn([10, 9], self.studio.mission()["goal"])

    def test_import_rejects_broken_or_oversized_without_mutation(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "broken.json"
            previous = tuple(self.studio.prefabs.entries())
            for doc in (
                {},
                {"kind": FILE_KIND, "version": 999, "entries": []},
                {"kind": FILE_KIND, "version": VERSION,
                 "entries": [{"name": "Broken"}]},
                {"kind": FILE_KIND, "version": VERSION,
                 "entries": [{"name": "Bad", "width": 1, "height": 1,
                              "offsets": [[0, 0]], "terrain": [
                                  {"surface": "fire"}], "goals": []}]},
                {"kind": FILE_KIND, "version": VERSION, "entries": [] * MAX_CUSTOM,
                 "extra": 1},
            ):
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.subTest(doc=doc), self.assertRaises(
                        (RuleError, ValueError, TypeError, KeyError)):
                    TerrainPrefabLibrary.import_file(path)
            path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
            with self.assertRaises(RuleError):
                TerrainPrefabLibrary.import_file(path)
            self.assertEqual(self.studio.prefabs.entries(), previous)
            self.assertEqual(self.studio.authoring.revision, 1)

    def test_smart_brush_interpolates_connected_strokes_and_selection_mask(self):
        selection = [(5, 5), (6, 5), (7, 5)]
        before = self.studio.snapshot()
        self.studio.smart(
            [(5, 5), (7, 5)], "surface:stone",
            radius=1, shape="square", selection_mask=selection
        )
        self.assertEqual(self.studio.authoring.revision, before["revision"] + 1)
        for point in selection:
            self.assertEqual(self.tile(point)["surface"], "stone")
        self.assertIsNone(self.tile((6, 4)))
        self.studio.undo()
        self.assertEqual(self.studio.snapshot()["content"], before["content"])
        self.studio.smart(
            [(10, 10), (12, 10)], "surface:sand", radius=0, shape="diamond")
        self.assertEqual(self.tile((11, 10))["surface"], "sand")
        bad = self.studio.snapshot()
        with self.assertRaises(RuleError):
            self.studio.smart(
                [(10, 10)], "surface:grass",
                radius=0, selection_mask=[(0, 0)]
            )
        self.assertEqual(self.studio.snapshot(), bad)

    def test_imports_headless_without_qt_or_tk(self):
        import subprocess
        import sys
        script = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter', 'PyQt6'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.studio.map_authoring import MapStudio
studio = MapStudio.reference()
studio.create("test_b", "Map", 16, 16)
plan = studio.preview_prefab("builtin:pond", (6, 6))
studio.commit_prefab(plan)
assert studio.authoring.revision == 2
"""
        subprocess.run([sys.executable, "-c", script],
                       check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
