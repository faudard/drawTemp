"""R6 construction authoring gates: real Content, revisioned undo and persistence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.construction import (
    ConstructionPick, ConstructionWorkspace, catalog,
)
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.iso_structures import structure_template, validate_structure_placement
from sporebound.building_visuals import exterior_wall_cells
from drawtemp.core import Content, GameProject, RuleError


def available_anchor(content, name="Maison"):
    data = content.to_dict()
    mission = next(m for m in data["missions"] if m["id"] == MISSION)
    clip = structure_template(name)
    for y in range(mission["board"]["height"] - clip.height + 1):
        for x in range(mission["board"]["width"] - clip.width + 1):
            try:
                validate_structure_placement(data, MISSION, clip, (x, y))
                return x, y
            except (ValueError, RuleError):
                continue
    raise AssertionError("Jeanne reference scene needs a free building footprint")


class ConstructionR6Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.anchor = available_anchor(content)
        self.editor = AuthoringSession.new(content, project)
        self.workspace = ConstructionWorkspace(self.editor, MISSION)

    def place_house(self):
        before = self.editor.snapshot()
        plan = self.workspace.preview_place("Maison", self.anchor)
        self.assertEqual(self.editor.snapshot(), before)
        change = self.workspace.apply(plan)
        self.assertEqual(change.kind, "construction:place")
        info = self.workspace.inspect()
        self.assertEqual(info.name, "Maison")
        self.assertEqual(info.anchor, self.anchor)
        self.assertEqual(len(info.footprint), 12)
        self.assertTrue(info.structure_id)
        return info

    def test_existing_presets_and_transactional_place_undo_redo(self):
        names = {row["name"] for row in catalog()}
        self.assertTrue({"Maison", "Tour", "Rempart", "Pont"}.issubset(names))
        before = self.editor.snapshot()
        info = self.place_house()
        self.assertTrue(self.editor.snapshot().dirty)
        self.assertTrue(self.editor.snapshot().can_undo)
        self.workspace.undo()
        self.assertEqual(self.editor.snapshot().content, before.content)
        self.assertIsNone(self.workspace.pick)
        self.workspace.redo()
        self.assertEqual(self.workspace.inspect().structure_id, info.structure_id)

    def test_material_window_and_interiors_preserve_tactical_board(self):
        house = self.place_house()
        initial_board = deepcopy(self.editor.snapshot().to_dict()["content"]
                                 ["missions"][0]["board"])
        self.workspace.apply(self.workspace.preview_material(
            facade="torchis", roof="ardoise"))
        wall = exterior_wall_cells({
            "name": "Maison", "turns": 0, "door_slot": 0})[0]
        world_wall = (self.anchor[0]+wall[0], self.anchor[1]+wall[1])
        self.workspace.apply(self.workspace.preview_window(world_wall))
        windows = self.workspace.inspect().windows
        self.assertIn(world_wall, windows)
        self.workspace.select(ConstructionPick(
            house.structure_id, self.anchor, world_wall, "window"))
        self.workspace.apply(self.workspace.preview_floor_add(1))
        self.workspace.apply(self.workspace.preview_floor_add(2))
        self.assertEqual(self.workspace.inspect().levels, (1, 2))
        self.workspace.set_level(1)
        # Every authored deck includes at least one walkable preset tile.
        info = self.workspace.inspect()
        content = self.editor.snapshot().to_dict()["content"]
        mission = content["missions"][0]
        floor = next(f for f in mission["interior_floors"]
                     if f["structure_id"] == info.structure_id and f["level"] == 1)
        local = floor["tiles"][0]["pos"]
        cell = (self.anchor[0]+local[0], self.anchor[1]+local[1])
        self.workspace.apply(self.workspace.preview_floor_tile(
            1, cell, surface="cobble", feature="lantern"))
        self.assertEqual(self.editor.snapshot().to_dict()["content"]
                         ["missions"][0]["board"], initial_board)
        self.assertEqual(self.workspace.inspect().roof, "ardoise")
        self.assertEqual(self.workspace.inspect().facade, "torchis")
        self.assertEqual(self.workspace.inspect().levels, (1, 2))
        self.assertEqual(self.workspace.active_level, 1)

    def test_rejected_overlap_invalid_pick_and_stale_preview_are_non_mutating(self):
        info = self.place_house()
        baseline = self.editor.snapshot()
        with self.assertRaises(AuthoringError):
            self.workspace.preview_place("Maison", self.anchor)
        self.assertEqual(self.editor.snapshot(), baseline)
        with self.assertRaises(AuthoringError) as error:
            self.workspace.select(ConstructionPick(
                info.structure_id, self.anchor, (999, 999), "roof"))
        self.assertEqual(error.exception.code, "invalid_pick")
        self.workspace.select(ConstructionPick(
            info.structure_id, self.anchor, self.anchor, "roof"))
        stale = self.workspace.preview_material(roof="plat")
        self.workspace.apply(self.workspace.preview_material(roof="ardoise"))
        with self.assertRaises(AuthoringError) as error:
            self.workspace.apply(stale)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(self.workspace.inspect().roof, "ardoise")

    def test_invalid_opening_is_rejected_without_tactical_breach(self):
        info = self.place_house()
        entry = info.entry
        self.assertIsNotNone(entry)
        with self.assertRaises(AuthoringError) as error:
            self.workspace.select(ConstructionPick(
                info.structure_id, self.anchor, entry, "window"))
        self.assertEqual(error.exception.code, "invalid_pick")
        before = self.editor.snapshot()
        with self.assertRaises(AuthoringError):
            self.workspace.preview_window(entry)
        self.assertEqual(self.editor.snapshot(), before)
        self.workspace.select(ConstructionPick(
            info.structure_id, self.anchor, entry, "door"))
        self.workspace.apply(self.workspace.preview_door(1))
        self.assertEqual(self.workspace.inspect().door_slot, 1)

    def test_persistence_parity_and_undo_full_house(self):
        self.place_house()
        self.workspace.apply(self.workspace.preview_material(roof="plat"))
        self.workspace.apply(self.workspace.preview_floor_add(1))
        content = self.editor.snapshot().to_dict()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "r6_house.json"
            self.editor.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(reopened.snapshot().content, self.editor.snapshot().content)
            self.assertEqual(reopened.snapshot().project, self.editor.snapshot().project)
            obj = reopened.snapshot().to_dict()
            canonical_content = Content.from_dict(obj["content"])
            GameProject.from_dict(obj["project"], canonical_content)
            new_workspace = ConstructionWorkspace(reopened, MISSION)
            building = self.workspace.inspect()
            new_workspace.select(ConstructionPick(building.structure_id, building.anchor,
                                                  building.anchor, "roof"))
            self.assertEqual(new_workspace.inspect().roof, "plat")
            self.assertEqual(new_workspace.inspect().levels, (1,))
            self.assertEqual(new_workspace.inspect().footprint, building.footprint)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))
                             ["missions"][0]["structures"],
                             obj["content"]["missions"][0]["structures"])

    def test_active_floor_and_cutaway_validated(self):
        info = self.place_house()
        with self.assertRaises(ValueError):
            self.workspace.set_level(1)
        with self.assertRaises(ValueError):
            self.workspace.set_level(True)
        with self.assertRaises(ValueError):
            self.workspace.set_cutaway("yes")
        self.workspace.set_cutaway(True)
        self.assertTrue(self.workspace.cutaway)
        self.workspace.apply(self.workspace.preview_floor_add(1))
        self.workspace.set_level(1)
        self.assertEqual(self.workspace.active_level, 1)
        self.workspace.apply(self.workspace.preview_floor_remove(1))
        self.assertEqual(self.workspace.active_level, 0)

    def test_headless_does_not_import_tk_or_qt(self):
        source = """import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'PyQt6', 'tkinter', '_tkinter'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.sdk.construction import ConstructionWorkspace, catalog
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
content, project = reference_project()
workspace = ConstructionWorkspace(AuthoringSession.new(content, project), MISSION)
assert 'Maison' in {item['name'] for item in catalog()}
"""
        result = subprocess.run([sys.executable, "-c", source], capture_output=True,
                                text=True, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
