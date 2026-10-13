"""Long-chain structure editing acceptance: no terrain/ID drift over time.

Use the real Document + headless authoring functions. Tests are deterministic,
small enough for every OS/Python CI job, and independent of Tk/PIL.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_structures import (
    duplicate_structure, edit_structure, place_structure, remove_structure,
    structure_at,
)
from sporebound.model import Content, RuleError
from sporebound.structure_groups import transform_structure_group


MID = 'structure_chain_3719b'


def board_tiles(data):
    mission = next(m for m in data['missions'] if m['id'] == MID)
    return {tuple(t['pos']): {key: value for key, value in t.items()
                              if key != 'pos'}
            for t in mission['board']['tiles']}


def structures(data):
    mission = next(m for m in data['missions'] if m['id'] == MID)
    return {row['id']: row for row in mission.get('structures', ())}


def new_document():
    data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                             MID, 'Reversible editing stress', 28, 20)
    row = next(m for m in data['missions'] if m['id'] == MID)
    # Explicit sparse terrain under the whole path: rivers, paths and props,
    # including non-default heights/costs/cover and many absent cells.
    for y in range(3, 15):
        for x in range(2, 23):
            if (x * 7 + y * 11) % 4 == 0:
                row['board']['tiles'].append({
                    'pos': [x, y],
                    'surface': ('water' if x % 7 == 0 else
                                'cobble' if y % 3 == 0 else 'dirt'),
                    'feature': 'tree' if (x + y) % 6 == 0 else '',
                    'blocked': x % 7 == 0,
                    'height': (x + y) % 3,
                    'cost': 2 if y % 3 == 0 else 1,
                    'cover': 10 if (x + y) % 6 == 0 else 0,
                })
    return Document(Content.from_dict(data))


class StructureUnderlayStressTests(unittest.TestCase):
    def test_32_individual_moves_rotations_doors_and_reopen(self):
        doc = new_document()
        baseline = deepcopy(doc.data)
        ground = board_tiles(baseline)
        doc.replace(place_structure(doc.data, MID, 'Maison', (4, 5)))
        stable_id = next(iter(structures(doc.data)))
        layouts = ((4, 5, 0, 0), (5, 5, 1, 0),
                   (6, 5, 2, 1), (5, 6, 3, 1),
                   (4, 6, 0, 0), (4, 5, 2, 1))
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'cycle.json'
            for index in range(32):
                anchor_x, anchor_y, turns, door = layouts[index % len(layouts)]
                current_anchor = tuple(structures(doc.data)[stable_id]['anchor'])
                before = deepcopy(doc.data)
                doc.replace(edit_structure(
                    doc.data, MID, current_anchor,
                    anchor=(anchor_x, anchor_y),
                    quarter_turns=turns, door_slot=door))
                self.assertEqual(set(structures(doc.data)), {stable_id})
                self.assertEqual(tuple(structures(doc.data)[stable_id]['anchor']),
                                 (anchor_x, anchor_y))
                if index % 5 == 0:
                    finished = deepcopy(doc.data)
                    doc.undo()
                    self.assertEqual(doc.data, before)
                    doc.redo()
                    self.assertEqual(doc.data, finished)
                    doc.save(destination)
                    restored = Content.load(destination)
                    self.assertEqual(restored.to_dict(), doc.data)
        current_anchor = tuple(structures(doc.data)[stable_id]['anchor'])
        doc.replace(remove_structure(doc.data, MID, current_anchor))
        self.assertEqual(board_tiles(doc.data), ground)
        self.assertEqual(structures(doc.data), {})
        doc.undo()
        self.assertEqual(set(structures(doc.data)), {stable_id})
        doc.redo()
        self.assertEqual(doc.data, baseline)

    def test_12_group_moves_then_duplicates_and_full_ground_recovery(self):
        doc = new_document()
        baseline = deepcopy(doc.data)
        # Buildings touch at their edges, so group translations repeatedly
        # overlap other members' previous footprints.
        for x in (3, 7, 11):
            doc.replace(place_structure(doc.data, MID, 'Maison', (x, 5)))
        original_ids = set(structures(doc.data))
        for index in range(12):
            scene = Content.from_dict(doc.data).missions[MID]
            cells = set().union(*(i.cells for i in architecture_instances(
                scene.board, scene.structures)))
            dx = 1 if index % 2 == 0 else -1
            before = deepcopy(doc.data)
            doc.replace(transform_structure_group(
                doc.data, MID, cells, dx, 0))
            self.assertEqual(set(structures(doc.data)), original_ids)
            doc.undo()
            self.assertEqual(doc.data, before)
            doc.redo()
        self.assertEqual({tuple(r['anchor']) for r in structures(doc.data).values()},
                         {(3, 5), (7, 5), (11, 5)})

        scene = Content.from_dict(doc.data).missions[MID]
        cells = set().union(*(i.cells for i in architecture_instances(
            scene.board, scene.structures)))
        doc.replace(transform_structure_group(
            doc.data, MID, cells, 0, 7, duplicate=True))
        self.assertEqual(len(structures(doc.data)), 6)
        self.assertEqual(len(set(structures(doc.data))), 6)
        duplicate_ids = set(structures(doc.data)) - original_ids
        self.assertEqual(len(duplicate_ids), 3)
        # Remove copies first, then originals: no saved background should
        # accidentally contain another structure's stamp.
        for sid in (*sorted(duplicate_ids), *sorted(original_ids)):
            anchor = tuple(structures(doc.data)[sid]['anchor'])
            doc.replace(remove_structure(doc.data, MID, anchor))
        self.assertEqual(structures(doc.data), {})
        self.assertEqual(board_tiles(doc.data), board_tiles(baseline))
        self.assertEqual(doc.data, baseline)

    def test_failed_operation_in_middle_of_chain_leaves_no_history(self):
        doc = new_document()
        baseline = deepcopy(doc.data)
        doc.replace(place_structure(doc.data, MID, 'Maison', (4, 5)))
        for anchor in ((5, 5), (6, 5), (5, 6)):
            before = deepcopy(doc.data)
            count = len(doc.undo_stack)
            source = next(iter(structures(doc.data).values()))
            old_anchor = tuple(source['anchor'])
            with self.assertRaises(RuleError):
                doc.replace(edit_structure(
                    doc.data, MID, old_anchor, anchor=(27, 19)))
            self.assertEqual(doc.data, before)
            self.assertEqual(len(doc.undo_stack), count)
            doc.replace(edit_structure(
                doc.data, MID, old_anchor, anchor=anchor))
        doc.replace(remove_structure(doc.data, MID,
                                     tuple(next(iter(structures(doc.data).values()))['anchor'])))
        self.assertEqual(doc.data, baseline)

    def test_legacy_without_snapshot_starts_recording_after_first_edit(self):
        doc = new_document()
        doc.replace(place_structure(doc.data, MID, 'Maison', (4, 5)))
        sid = next(iter(structures(doc.data)))
        old_data = deepcopy(doc.data)
        row = next(m for m in old_data['missions'] if m['id'] == MID)
        del next(s for s in row['structures'] if s['id'] == sid)['underlay']
        assert 'underlay' not in structures(old_data)[sid]
        # We cannot recover the overwritten ground beneath a legacy house.
        # But every subsequent location captures the new underlying terrain.
        changed = edit_structure(old_data, MID, (4, 5), anchor=(9, 5))
        self.assertIn('underlay', structures(changed)[sid])
        changed = edit_structure(changed, MID, (9, 5), anchor=(10, 5))
        changed = remove_structure(changed, MID, (10, 5))
        expected = deepcopy(old_data)
        old = next(m for m in expected['missions'] if m['id'] == MID)
        old['board']['tiles'] = [tile for tile in old['board']['tiles']
                               if not (4 <= tile['pos'][0] <= 7
                                       and 5 <= tile['pos'][1] <= 7)]
        old.pop('structures', None)
        self.assertEqual(board_tiles(changed), board_tiles(expected))
        self.assertEqual(structures(changed), {})


if __name__ == '__main__':
    unittest.main()
