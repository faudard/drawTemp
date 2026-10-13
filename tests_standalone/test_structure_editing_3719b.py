"""3.7.19B: whole-structure editing, legacy migration and undo safety."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_structures import (
    duplicate_structure, edit_structure, move_structure, place_structure,
    structure_at, structure_template, validate_structure_edit,
)
from sporebound.map_authoring import paste_terrain
from sporebound.model import Content, RuleError


class StructureEditing3719BTests(unittest.TestCase):
    MID = "structure_editing"

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT)
        data = add_blank_mission(base.to_dict(), self.MID, "Atelier", 20, 20)
        self.doc = Document(Content.from_dict(data))
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Maison", (3, 3)))
        self.original_id = structure_at(
            self.doc.data, self.MID, (4, 4)).id

    def mission(self):
        return Content.from_dict(self.doc.data).missions[self.MID]

    def test_move_overlapping_own_footprint_preserves_id_and_undo(self):
        before = deepcopy(self.doc.data)
        moved = move_structure(self.doc.data, self.MID, (4, 4), (4, 3))
        self.assertEqual(self.doc.data, before, "Input must stay immutable")
        self.doc.replace(moved)
        selected = structure_at(self.doc.data, self.MID, (5, 4))
        self.assertEqual((selected.id, selected.anchor),
                         (self.original_id, (4, 3)))
        self.assertEqual(self.mission().board.tile((3, 3)).feature, "")
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(structure_at(
            self.doc.data, self.MID, (5, 4)).id, self.original_id)

    def test_duplicate_has_independent_id_and_survives_save(self):
        result = duplicate_structure(self.doc.data, self.MID, (4, 4), (11, 5))
        self.doc.replace(result)
        original = structure_at(self.doc.data, self.MID, (4, 4))
        duplicate = structure_at(self.doc.data, self.MID, (12, 6))
        self.assertEqual(original.id, self.original_id)
        self.assertNotEqual(duplicate.id, original.id)
        self.assertEqual(len(self.mission().structures), 2)
        with TemporaryDirectory() as folder:
            target = Path(folder) / "content.json"
            self.doc.save(target)
            reopened = Content.load(target).missions[self.MID]
            found = architecture_instances(reopened.board, reopened.structures)
            self.assertEqual({item.id for item in found},
                             {original.id, duplicate.id})
        self.doc.undo()
        self.assertEqual(len(self.mission().structures), 1)

    def test_change_type_rotation_door_and_repaint(self):
        self.doc.paint_many(self.MID, [(3, 3)], "feature:tree")
        modified = edit_structure(
            self.doc.data, self.MID, (4, 4), anchor=(5, 4),
            name="Ruines", quarter_turns=1, door_slot=1)
        self.doc.replace(modified)
        current = structure_at(self.doc.data, self.MID, (6, 5))
        self.assertEqual(current.id, self.original_id)
        self.assertEqual((current.name, current.anchor, current.turns,
                          current.door_slot), ("Ruines", (5, 4), 1, 1))
        self.assertEqual(self.mission().board.tile((3, 3)).feature, "")
        self.doc.undo()
        self.assertEqual(self.mission().board.tile((3, 3)).feature, "tree")

    def test_invalid_moves_do_not_mutate_data_or_history(self):
        before = deepcopy(self.doc.data)
        undo_len, redo_len = len(self.doc.undo_stack), len(self.doc.redo_stack)
        unit_pos = tuple(next(m for m in self.doc.data["missions"]
                              if m["id"] == self.MID)["units"][0]["pos"])
        cases = [
            lambda: move_structure(self.doc.data, self.MID, (3, 3), (19, 19)),
            lambda: duplicate_structure(self.doc.data, self.MID, (4, 4), (4, 4)),
            lambda: move_structure(self.doc.data, self.MID, (3, 3), unit_pos),
            lambda: edit_structure(self.doc.data, self.MID, (3, 3),
                                   name="Tour", door_slot=1),
            lambda: validate_structure_edit(self.doc.data, self.MID,
                                            (3, 3), anchor=(-1, 0)),
        ]
        for action in cases:
            with self.subTest(action=action), self.assertRaises(RuleError):
                self.doc.replace(action())
            self.assertEqual(self.doc.data, before)
            self.assertEqual(len(self.doc.undo_stack), undo_len)
            self.assertEqual(len(self.doc.redo_stack), redo_len)

    def test_other_structure_overlap_and_legacy_promotion(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Tour", (11, 5)))
        with self.assertRaisesRegex(RuleError, "overlaps"):
            move_structure(self.doc.data, self.MID, (4, 4), (10, 5))
        fresh = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                  "legacy_edit", "Ancien", 20, 20)
        old = paste_terrain(fresh, "legacy_edit",
                            structure_template("Maison"), (3, 3))
        initial = next(m for m in old["missions"] if m["id"] == "legacy_edit")
        self.assertNotIn("structures", initial)
        promoted = move_structure(old, "legacy_edit", (4, 4), (5, 4))
        old_mission = next(m for m in old["missions"] if m["id"] == "legacy_edit")
        self.assertNotIn("structures", old_mission)
        new = Content.from_dict(promoted).missions["legacy_edit"]
        self.assertEqual(len(new.structures), 1)
        self.assertEqual(new.structures[0]["anchor"], [5, 4])
        self.assertTrue(new.structures[0]["id"])

    def test_edit_noop_keeps_payload(self):
        before = deepcopy(self.doc.data)
        result = edit_structure(self.doc.data, self.MID, (4, 4))
        self.assertEqual(result, before)


if __name__ == "__main__":
    unittest.main()
