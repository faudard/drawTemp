"""Valcroix reference-level regression for reversible structure terrain.

These tests use the real reference village authoring pipeline, not a crafted
JSON substitute. They are independent of Tk and exercise Content round-trip.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.fortified_village_3717a import (
    MISSION_ID, WIDTH, HEIGHT, build_village_document,
)
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_structures import move_structure, remove_structure, structure_at
from sporebound.model import Content
from sporebound.structure_groups import transform_structure_group


def village(data):
    return Content.from_dict(data).missions[MISSION_ID]


def ids_and_anchors(data):
    return {row['id']: (row['name'], tuple(row['anchor']))
            for row in village(data).structures}


def terrain(data):
    return {tuple(tile['pos']): {k: v for k, v in tile.items() if k != 'pos'}
            for tile in next(m for m in data['missions']
                             if m['id'] == MISSION_ID)['board']['tiles']}


class ValcroixStructureUnderlayTests(unittest.TestCase):
    def setUp(self):
        self.doc = build_village_document(Content.load(DEFAULT_CONTENT))
        self.source = deepcopy(self.doc.data)
        self.assertEqual((village(self.source).board.width,
                          village(self.source).board.height), (WIDTH, HEIGHT))

    def test_bridge_move_reveals_water_and_remove_restores_river(self):
        original = structure_at(self.source, MISSION_ID, (13, 9))
        self.assertEqual((original.name, original.anchor), ('Pont', (12, 9)))
        old_record = next(row for row in village(self.source).structures
                          if row['id'] == original.id)
        self.assertEqual(len(old_record['underlay']), 6)
        self.assertTrue(all(row['tile']['surface'] == 'water'
                            for row in old_record['underlay']))
        identity_before = ids_and_anchors(self.source)
        # The destination is another river segment; old and new bridges do
        # not overlap and no actors, events or objects are displaced.
        self.doc.replace(move_structure(self.doc.data, MISSION_ID,
                                        (13, 9), (12, 7)))
        bridge = structure_at(self.doc.data, MISSION_ID, (13, 7))
        self.assertEqual((bridge.id, bridge.anchor), (original.id, (12, 7)))
        self.assertEqual(len(village(self.doc.data).structures), 10)
        for record in old_record['underlay']:
            cell = tuple(record['pos'])
            self.assertEqual(asdict(village(self.doc.data).board.tile(cell)),
                             record['tile'])
        for sid, identity in ids_and_anchors(self.doc.data).items():
            if sid != original.id:
                self.assertEqual(identity, identity_before[sid])

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'valcroix.json'
            self.doc.save(path)
            reopened = Content.load(path).to_dict()
            self.assertEqual(terrain(reopened), terrain(self.doc.data))
            self.assertEqual(ids_and_anchors(reopened),
                             ids_and_anchors(self.doc.data))
            # Removing the moved bridge leaves precisely the same terrain
            # as removing it at its original position, including all props.
            without_original = remove_structure(self.source, MISSION_ID, (13, 9))
            without_moved = remove_structure(reopened, MISSION_ID, (13, 7))
            self.assertEqual(terrain(without_moved), terrain(without_original))
            self.assertEqual(ids_and_anchors(without_moved),
                             ids_and_anchors(without_original))
        self.doc.undo()
        self.assertEqual(self.doc.data, self.source)
        self.doc.redo()
        self.assertEqual(bridge.id,
                         structure_at(self.doc.data, MISSION_ID, (13, 7)).id)

    def test_group_move_keeps_other_valcroix_structures_and_underlays(self):
        # Two separated houses, selected by their *entire* footprint.
        houses = [structure_at(self.source, MISSION_ID, cell)
                  for cell in ((4, 4), (7, 14))]
        self.assertEqual([item.name for item in houses], ['Maison', 'Maison'])
        chosen = set().union(*(item.cells for item in houses))
        before = ids_and_anchors(self.source)
        self.doc.replace(transform_structure_group(
            self.doc.data, MISSION_ID, chosen, 1, 0))
        after = ids_and_anchors(self.doc.data)
        self.assertEqual(len(after), 10)
        selected_ids = {item.id for item in houses}
        for sid, (name, anchor) in before.items():
            expected = (anchor[0] + 1, anchor[1]) if sid in selected_ids else anchor
            self.assertEqual(after[sid], (name, expected))
        # Removing the translated houses must restore the same background
        # as removing their originals, without affecting other structures.
        restored = deepcopy(self.doc.data)
        for house in houses:
            anchor = after[house.id][1]
            restored = remove_structure(restored, MISSION_ID, anchor)
        expected = deepcopy(self.source)
        for house in houses:
            expected = remove_structure(expected, MISSION_ID, house.anchor)
        self.assertEqual(terrain(restored), terrain(expected))
        self.assertEqual(ids_and_anchors(restored), ids_and_anchors(expected))
        self.doc.undo()
        self.assertEqual(self.doc.data, self.source)


    def test_editor_player_and_replay_agree_on_moved_bridge(self):
        """A moved bridge changes the actual tactical board, not just its PNG."""
        from sporebound.storage import save_battle, load_battle

        self.doc.replace(move_structure(self.doc.data, MISSION_ID,
                                        (13, 9), (12, 7)))
        scene = village(self.doc.data)
        battle = self.doc.playtest(MISSION_ID, seed=7)
        self.assertEqual(scene.board.tile((13, 9)).surface, 'water')
        self.assertEqual(scene.board.tile((13, 7)).surface, 'bridge')
        self.assertTrue(battle.board.tile((13, 9)).blocked)
        self.assertEqual(battle.board.tile((13, 9)).surface, 'water')
        self.assertFalse(battle.board.tile((13, 7)).blocked)
        self.assertEqual(battle.board.tile((13, 7)).surface, 'bridge')
        self.assertEqual(battle.mission.structures, scene.structures)
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'replay.json'
            save_battle(target, battle)
            self.assertEqual(load_battle(target).digest(), battle.digest())


if __name__ == '__main__':
    unittest.main()
