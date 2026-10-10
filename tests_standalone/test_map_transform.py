"""Map Editor 3.0 transformations and portable stamps: headless regression gate."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.map_authoring import copy_terrain, paste_terrain
from sporebound.map_transform import (group_entities, load_stamp, move_group,
                                     parse_stamp, save_stamp, stamp_document,
                                     transform_terrain)
from sporebound.model import Content, RuleError


class MapTransformTests(unittest.TestCase):
    def setUp(self):
        self.mid = 'workshop'
        self.base = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                      self.mid, 'Atelier', 12, 12)

    def mission(self, data):
        return Content.from_dict(data).missions[self.mid]

    def source_clipboard(self):
        doc = Document(Content.from_dict(self.base))
        doc.paint_many(self.mid, [(3, 3)], 'hazard')
        doc.paint_many(self.mid, [(4, 4)], 'height+')
        doc.paint_many(self.mid, [(4, 4)], 'goal')
        return copy_terrain(doc.data, self.mid, [(3, 3), (4, 4)])

    def test_four_rotations_and_double_mirrors_are_exact(self):
        original = self.source_clipboard()
        turned = original
        for _ in range(4):
            turned = transform_terrain(turned, 'rotate_cw')
        self.assertEqual(turned, original)
        for name in ('mirror_x', 'mirror_y'):
            self.assertEqual(transform_terrain(transform_terrain(original, name),
                                               name), original)
        self.assertEqual(transform_terrain(
            transform_terrain(original, 'rotate_cw'), 'rotate_ccw'), original)

    def test_rotation_moves_goal_and_sparse_terrain_correctly(self):
        original = self.source_clipboard()
        cw = transform_terrain(original, 'rotate_cw')
        self.assertEqual(cw.width, 2)
        self.assertEqual(cw.height, 2)
        pasted = paste_terrain(self.base, self.mid, cw, (6, 6))
        board = self.mission(pasted).board
        self.assertEqual(board.tile((7, 6)).hazard, 4)
        self.assertEqual(board.tile((6, 7)).height, 1)
        self.assertIn((6, 7), self.mission(pasted).goal)
        self.assertEqual(board.tile((6, 6)).hazard, 0)

    def test_non_square_rotation_changes_dimensions(self):
        doc = Document(Content.from_dict(self.base))
        clip = copy_terrain(doc.data, self.mid, [(1, 1), (2, 1), (3, 1)])
        rotated = transform_terrain(clip, 'rotate_cw')
        self.assertEqual((rotated.width, rotated.height), (1, 3))
        self.assertEqual(rotated.offsets, ((0, 0), (0, 1), (0, 2)))

    def test_group_selection_and_move_keeps_ids_and_undo(self):
        new = add_object(self.base, self.mid, 'chest1', 'chest', (3, 8))
        selected = group_entities(new, self.mid, [(1, 10), (3, 8)])
        self.assertEqual(len(selected[0]), 1)
        self.assertEqual(selected[1], ('chest1',))
        doc = Document(Content.from_dict(new))
        saved = deepcopy(doc.data)
        doc.replace(move_group(doc.data, self.mid, *selected, dx=1, dy=-1))
        actor = self.mission(doc.data).units
        self.assertEqual(next(u for u in actor if u.id == selected[0][0]).pos,
                         (2, 9))
        self.assertEqual(self.mission(doc.data).objects[0]['pos'], [4, 7])
        doc.undo()
        self.assertEqual(doc.data, saved)
        doc.redo()
        self.assertEqual(self.mission(doc.data).objects[0]['pos'], [4, 7])

    def test_multicell_actor_and_defense_group_moves_every_footprint(self):
        content = deepcopy(self.base)
        mission = next(m for m in content['missions'] if m['id'] == self.mid)
        player = next(u for u in mission['units'] if u['team'] == 'player')
        player['footprint'] = [2, 2]
        content = Content.from_dict(content).to_dict()
        content = add_object(content, self.mid, 'oil', 'defense', (4, 4))
        unit_ids, object_ids = group_entities(content, self.mid,
                                               [(2, 11), (4, 4)])
        self.assertEqual(unit_ids, (player['id'],))
        self.assertEqual(object_ids, ('oil',))
        original = deepcopy(content)
        result = move_group(content, self.mid, unit_ids, object_ids,
                            dx=1, dy=-1)
        moved = self.mission(result)
        actor = next(u for u in moved.units if u.id == player['id'])
        self.assertEqual(actor.pos, (2, 9))
        self.assertEqual(actor.occupied_cells(),
                         {(2, 9), (3, 9), (2, 10), (3, 10)})
        trap = next(o for o in moved.objects if o['id'] == 'oil')
        self.assertEqual(trap['pos'], [5, 3])
        self.assertEqual(trap['cells'], [[5, 3]])
        self.assertEqual(content, original)

    def test_group_rejects_invalid_move_without_modifying_source(self):
        original = deepcopy(self.base)
        mid = self.mid
        uid = group_entities(self.base, mid, [(1, 10)])[0][0]
        for dx, dy in ((9, -9), (-2, 0), (0, 2), (True, 1), (0, 0)):
            with self.subTest(offset=(dx, dy)), self.assertRaises(RuleError):
                move_group(self.base, mid, (uid,), (), dx=dx, dy=dy)
            self.assertEqual(original, self.base)
        with self.assertRaises(RuleError):
            move_group(self.base, mid, ('does-not-exist',), (), dx=1)

    def test_portable_stamp_roundtrip_preserves_sparse_goals(self):
        original = self.source_clipboard()
        with TemporaryDirectory() as folder:
            output = Path(folder) / 'my_stamp.json'
            save_stamp(output, original, 'Escalier et danger')
            payload = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(payload['version'], 1)
            self.assertEqual(load_stamp(output), original)
            self.assertEqual(parse_stamp(stamp_document(original, 'test')), original)
            modified = deepcopy(payload)
            modified['cells'][0]['terrain']['height'] = 12
            self.assertNotEqual(parse_stamp(modified), original)
            self.assertEqual(load_stamp(output), original)

    def test_untrusted_stamp_is_strictly_rejected(self):
        payload = stamp_document(self.source_clipboard(), 'Valid')
        invalids = []
        bad = deepcopy(payload)
        bad['version'] = True
        invalids.append(bad)
        bad = deepcopy(payload)
        bad['size'] = [128, 0]
        invalids.append(bad)
        bad = deepcopy(payload)
        bad['cells'].append(deepcopy(bad['cells'][0]))
        invalids.append(bad)
        bad = deepcopy(payload)
        bad['cells'][0]['terrain']['blocked'] = 1
        invalids.append(bad)
        bad = deepcopy(payload)
        bad['cells'][0]['terrain']['unknown_property'] = 'x'
        invalids.append(bad)
        bad = deepcopy(payload)
        bad['goals'].append([99, 99])
        invalids.append(bad)
        for i, data in enumerate(invalids):
            with self.subTest(case=i), self.assertRaises(RuleError):
                parse_stamp(data)

    def test_oversize_stamp_load_is_rejected_before_json_decode(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'bad_stamp.json'
            path.write_bytes(b'[' * (2*1024*1024 + 1))
            with self.assertRaisesRegex(RuleError, 'size limit'):
                load_stamp(path)


if __name__ == '__main__':
    unittest.main()
