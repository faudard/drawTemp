"""3.7.17B: stable authoring identities, legacy maps, save/replay invariants."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_structures import (
    place_structure, remove_structure, structure_template)
from sporebound.map_authoring import paste_terrain
from sporebound.model import Content, RuleError
from sporebound.storage import load_battle, save_battle


class PersistentArchitectureTests(unittest.TestCase):
    MID = "persistent_architecture"

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT)
        source = add_blank_mission(base.to_dict(), self.MID, "Atelier", 16, 16)
        self.doc = Document(Content.from_dict(source))

    def mission(self):
        return Content.from_dict(self.doc.data).missions[self.MID]

    def test_paint_keeps_identity_and_roundtrip_preserves_replay(self):
        self.doc.replace(place_structure(
            self.doc.data, self.MID, "Maison", (3, 3), 1, door_slot=1))
        original_scene = self.mission()
        self.assertEqual(original_scene.structures[0]["id"], "structure_1")
        original = architecture_instances(original_scene.board,
                                          original_scene.structures)
        self.assertEqual((original[0].turns, original[0].door_slot), (1, 1))
        self.doc.paint_many(self.MID, [(3, 3)], "feature-erase")
        changed = self.mission()
        self.assertFalse(architecture_instances(changed.board))
        self.assertEqual(architecture_instances(changed.board, changed.structures),
                         original)
        self.doc.undo()
        self.assertEqual(architecture_instances(self.mission().board,
                                               self.mission().structures), original)
        self.doc.redo()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "content.json"
            replay = Path(tmp) / "battle.json"
            self.doc.save(path)
            reopened = Content.load(path)
            restored = reopened.missions[self.MID]
            self.assertEqual(restored.structures, changed.structures)
            self.assertEqual(architecture_instances(restored.board,
                                                    restored.structures), original)
            battle = self.doc.playtest(self.MID, seed=11)
            save_battle(replay, battle)
            self.assertEqual(load_battle(replay).digest(), battle.digest())
            self.assertEqual(battle.mission.structures, restored.structures)

    def test_explicit_remove_is_atomic_undoable_and_clears_footprint(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Maison", (3, 3)))
        before = deepcopy(self.doc.data)
        self.doc.replace(remove_structure(self.doc.data, self.MID, (4, 4)))
        self.assertEqual(self.mission().structures, [])
        self.assertEqual(architecture_instances(self.mission().board), ())
        self.assertEqual(self.mission().board.tile((3, 3)).feature, "")
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertFalse(self.mission().structures)
        with self.assertRaisesRegex(RuleError, "No structure"):
            remove_structure(self.doc.data, self.MID, (4, 4))

    def test_legacy_map_keeps_old_content_payload_and_inference(self):
        old = paste_terrain(self.doc.data, self.MID,
                            structure_template("Maison"), (3, 3))
        self.assertNotIn("structures", next(m for m in old["missions"]
                                            if m["id"] == self.MID))
        legacy = Content.from_dict(old)
        self.assertEqual(legacy.to_dict(), old)
        scene = legacy.missions[self.MID]
        self.assertEqual(len(architecture_instances(scene.board,
                                                    scene.structures)), 1)
        self.doc.replace(old)
        self.doc.paint_many(self.MID, [(3, 3)], "feature-erase")
        self.assertEqual(architecture_instances(self.mission().board,
                                                self.mission().structures), ())

    def test_mixed_authored_and_legacy_shapes_do_not_overlap(self):
        old = paste_terrain(self.doc.data, self.MID,
                            structure_template("Maison"), (3, 3))
        self.doc.replace(old)
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Tour", (10, 4)))
        scene = self.mission()
        found = architecture_instances(scene.board, scene.structures)
        self.assertEqual(sorted(x.name for x in found), ["Maison", "Tour"])
        self.assertEqual(len([x for x in found if x.id]), 1)
        with self.assertRaisesRegex(RuleError, "overlaps"):
            place_structure(self.doc.data, self.MID, "Maison", (10, 4))

    def test_invalid_records_are_rejected_without_mutation(self):
        self.doc.replace(place_structure(self.doc.data, self.MID,
                                         "Maison", (3, 3)))
        clean = deepcopy(self.doc.data)
        changes = (
            {"id": ""},
            {"name": "Unknown"},
            {"turns": 4},
            {"anchor": [15, 15]},
            {"door_slot": 99},
        )
        for update in changes:
            with self.subTest(update=update):
                broken = deepcopy(clean)
                mission = next(m for m in broken["missions"]
                               if m["id"] == self.MID)
                mission["structures"][0].update(update)
                with self.assertRaises(RuleError):
                    Content.from_dict(broken)
        self.assertEqual(self.doc.data, clean)


if __name__ == "__main__":
    unittest.main()
