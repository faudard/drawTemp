"""3.7.19C: project-backed actor/object palette and atomic placement."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.actor_catalog import create_archetype
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.entity_placement import (palette_entities, place_palette_entity,
                                         preview_entity_cells, suggested_id)
from sporebound.model import Content, RuleError


class EntityPlacementTests(unittest.TestCase):
    def setUp(self):
        data = Content.load(DEFAULT_CONTENT).to_dict()
        self.data = add_blank_mission(data, 'palette_entities', 'Village', 12, 12)
        self.mid = 'palette_entities'

    def entry(self, identifier, data=None):
        entries = palette_entities(data or self.data, self.mid)
        return next(entry for entry in entries if entry.id == identifier)

    def mission(self, data):
        return Content.from_dict(data).missions[self.mid]

    def test_catalog_uses_real_templates_and_object_types(self):
        entries = palette_entities(self.data, self.mid)
        self.assertEqual(len({entry.id for entry in entries}), len(entries))
        self.assertEqual({entry.value for entry in entries if entry.kind == 'object'},
                         {'door', 'switch', 'chest', 'ram', 'catapult', 'passage', 'defense'})
        for unit in self.mission(self.data).units:
            self.assertIn('actor:unit:' + unit.id, {entry.id for entry in entries})
        self.assertEqual({entry.category for entry in entries}, {'Acteurs', 'Interactions'})

    def test_actor_facing_snapshot_undo_redo_and_round_trip(self):
        unit = self.mission(self.data).units[0]
        entry = self.entry('actor:unit:' + unit.id)
        self.assertEqual(preview_entity_cells(self.data, self.mid, entry, (4, 4)),
                         (((4, 4),), True))
        doc = Document(Content.from_dict(self.data))
        original = deepcopy(doc.data)
        doc.replace(place_palette_entity(doc.data, self.mid, entry, (4, 4),
                                         name='Sentinelle', team='enemy', facing='north'))
        spawn = next(u for u in self.mission(doc.data).units if u.name == 'Sentinelle')
        self.assertEqual(spawn.facing, (0, -1))
        self.assertEqual(spawn.pos, (4, 4))
        self.assertEqual(spawn.ct, 0)
        self.assertEqual(spawn.hp, spawn.max_hp)
        self.assertNotEqual(spawn.id, unit.id)
        self.assertFalse(preview_entity_cells(doc.data, self.mid, entry, (4, 4))[1])
        placed = deepcopy(doc.data)
        doc.undo()
        self.assertEqual(doc.data, original)
        doc.redo()
        self.assertEqual(doc.data, placed)
        with TemporaryDirectory() as temp:
            target = Path(temp)/'scene.json'
            doc.save(target)
            self.assertEqual(Content.load(target).to_dict(), doc.data)
        self.assertIsNotNone(doc.playtest(self.mid))

    def test_archetype_template_and_repeated_placement_have_unique_ids(self):
        data = create_archetype(self.data, 'scout_3719c', kind='monster', speed=12)
        entry = self.entry('actor:archetype:scout_3719c', data)
        self.assertEqual(suggested_id(data, self.mid, entry), 'actor_scout_3719c')
        first = place_palette_entity(data, self.mid, entry, (3, 3), team='enemy')
        second = place_palette_entity(first, self.mid, entry, (5, 5),
                                      team='enemy', facing='west')
        actors = {u.id: u for u in self.mission(second).units}
        self.assertIn('actor_scout_3719c', actors)
        self.assertIn('actor_scout_3719c_2', actors)
        self.assertEqual(actors['actor_scout_3719c_2'].facing, (-1, 0))
        self.assertEqual(actors['actor_scout_3719c'].archetype, 'scout_3719c')

    def test_object_link_passage_and_invalid_rollback(self):
        door = self.entry('object:door')
        switch = self.entry('object:switch')
        passage = self.entry('object:passage')
        first = place_palette_entity(self.data, self.mid, door, (7, 7))
        did = suggested_id(self.data, self.mid, door)
        self.assertIn(did, {o['id'] for o in self.mission(first).objects})
        self.assertFalse(preview_entity_cells(first, self.mid, switch, (7, 6))[1])
        self.assertTrue(preview_entity_cells(first, self.mid, switch, (7, 6), link=did)[1])
        before = deepcopy(first)
        with self.assertRaises(RuleError):
            place_palette_entity(first, self.mid, switch, (7, 6))
        self.assertEqual(first, before)
        linked = place_palette_entity(first, self.mid, switch, (7, 6), link=did)
        obj = next(o for o in self.mission(linked).objects if o['kind'] == 'switch')
        self.assertEqual(obj['link'], did)
        self.assertFalse(preview_entity_cells(linked, self.mid, passage,
                                              (6, 6), destination='99,1')[1])
        with self.assertRaises(RuleError):
            place_palette_entity(linked, self.mid, passage, (6, 6),
                                 destination='99,1')
        result = place_palette_entity(linked, self.mid, passage, (6, 6),
                                      destination='2,3')
        self.assertEqual(next(o['destination'] for o in self.mission(result).objects
                              if o['kind'] == 'passage'), [2, 3])

    def test_rejects_overlap_blocked_tiles_bad_orientation_and_invalid_id(self):
        entry = self.entry('actor:unit:' + self.mission(self.data).units[0].id)
        before = deepcopy(self.data)
        for kwargs, cell in [({}, (1, 10)), ({}, (12, 2)),
                             ({'facing': 'diagonal'}, (3, 3)),
                             ({'entity_id': 'bad space'}, (3, 3))]:
            with self.subTest(kwargs=kwargs, cell=cell), self.assertRaises(RuleError):
                place_palette_entity(self.data, self.mid, entry, cell, **kwargs)
        self.assertEqual(self.data, before)
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.mid, [(4, 4)], 'wall')
        self.assertFalse(preview_entity_cells(doc.data, self.mid, entry, (4, 4))[1])
        with self.assertRaises(RuleError):
            place_palette_entity(doc.data, self.mid, entry, (4, 4))
        self.assertEqual(len(doc.undo_stack), 1)


if __name__ == '__main__':
    unittest.main()
