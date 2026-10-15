"""R5 map Studio integration checks: canonical transactions, gestures and disk."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio


class MapStudioR5Tests(unittest.TestCase):
    def setUp(self):
        self.maps = MapStudio.reference()

    def test_create_rename_duplicate_is_one_undo_each(self):
        original = self.maps.map_ids()
        self.maps.create("village_r5", "Village de Jeanne", 12, 12)
        self.assertEqual(self.maps.mission()["board"]["width"], 12)
        self.maps.rename("Village restauré")
        self.assertEqual(self.maps.mission()["name"], "Village restauré")
        self.maps.duplicate("village_copy", "Copie du village")
        self.assertEqual(len(self.maps.map_ids()), len(original) + 2)
        self.maps.undo()
        self.assertNotIn("village_copy", self.maps.map_ids())
        self.maps.select_map("village_r5")
        self.maps.undo()
        self.assertEqual(self.maps.mission()["name"], "Village de Jeanne")
        self.maps.redo()
        self.assertEqual(self.maps.mission()["name"], "Village restauré")

    def test_paint_one_gesture_and_undo_redo(self):
        self.maps.create("village", "Village", 12, 12)
        baseline = self.maps.snapshot()
        self.maps.paint([(2, 2), (2, 3), (2, 3)], "surface:water")
        mission = self.maps.mission()
        self.assertEqual(len(mission["board"]["tiles"]), 2)
        self.assertTrue(all(t["blocked"] for t in mission["board"]["tiles"]))
        self.maps.undo()
        self.assertEqual(self.maps.mission()["board"]["tiles"], [])
        self.maps.redo()
        self.assertEqual(len(self.maps.mission()["board"]["tiles"]), 2)
        self.assertEqual(self.maps.snapshot()["revision"], baseline["revision"] + 3)

    def test_preview_lease_expires_on_edit_undo_aba(self):
        self.maps.create("village", "Village", 12, 12)
        preview = self.maps.preview([(3, 3)], "surface:stone")
        self.maps.paint([(5, 5)], "surface:water")
        self.maps.undo()
        before = self.maps.snapshot()
        with self.assertRaises(AuthoringError) as context:
            self.maps.commit(preview)
        self.assertEqual(context.exception.code, "stale_revision")
        self.assertEqual(self.maps.snapshot(), before)

    def test_rectangle_line_flood_and_pick(self):
        self.maps.create("village", "Village", 12, 12)
        self.maps.rectangle((2, 2), (4, 3), "surface:sand")
        self.assertEqual(self.maps.sample((3, 3)), "sand")
        self.maps.line((6, 2), (6, 5), "surface:stone")
        self.assertEqual(self.maps.sample((6, 4)), "stone")
        self.maps.flood((0, 0), "surface:cobble")
        self.assertEqual(self.maps.sample((0, 0)), "cobble")
        self.assertEqual(self.maps.sample((3, 3)), "sand")
        self.assertEqual(self.maps.sample((6, 4)), "stone")

    def test_structures_clipboard_and_goal_survive_save(self):
        self.maps.create("village", "Village", 12, 12)
        self.maps.structure("Maison", (5, 5))
        self.maps.paint([(3, 4), (3, 5)], "surface:water")
        self.maps.structure("Pont", (2, 4))
        self.maps.paint([(10, 9)], "goal")
        self.assertEqual(len(self.maps.mission().get("structures", [])), 2)
        self.maps.copy([(3, 4)])
        self.maps.paste((3, 7))
        self.assertEqual(self.maps.sample((3, 7)), "bridge")
        with TemporaryDirectory() as directory:
            filename = Path(directory) / "village.json"
            self.maps.save_as(filename)
            opened = MapStudio.open(filename)
            opened.select_map("village")
            self.assertEqual(opened.mission(), self.maps.mission())
            self.assertFalse(opened.snapshot()["dirty"])

    def test_bad_placement_is_atomic(self):
        self.maps.create("village", "Village", 12, 12)
        original = self.maps.snapshot()
        with self.assertRaises(Exception):
            self.maps.structure("Maison", (11, 11))
        self.assertEqual(self.maps.snapshot(), original)
        with self.assertRaises(Exception):
            self.maps.paint([(20, 20)], "surface:water")
        self.assertEqual(self.maps.snapshot(), original)

    def test_diagnostics_detect_unreachable_goal(self):
        self.maps.create("village", "Village", 12, 12)
        self.maps.paint([(8, 8)], "goal")
        self.maps.paint([(8, 7), (7, 8), (9, 8), (8, 9)], "wall")
        self.assertTrue(any("Unreachable goal" in row
                            for row in self.maps.diagnostics()))

    def test_playtest_is_detached_from_editor(self):
        self.maps.create("village", "Village", 12, 12)
        before = self.maps.snapshot()
        result = self.maps.playtest(max_steps=30)
        self.assertEqual(result["mission"], "village")
        self.assertEqual(result["seed"], 17)
        self.assertEqual(self.maps.snapshot(), before)

    def test_studio_core_imports_without_qt_or_tk(self):
        import subprocess
        import sys
        code = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', '_tkinter', 'PySide6', 'PyQt6'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from drawtemp.studio.map_authoring import MapStudio
studio = MapStudio.reference()
studio.paint([(2, 2)], 'surface:stone')
"""
        subprocess.run([sys.executable, "-c", code], check=True,
                       cwd=Path(__file__).resolve().parents[1], capture_output=True,
                       text=True)


if __name__ == "__main__":
    unittest.main()
