"""3.7.32E: reproducible, diffable assisted quarter generation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext, GroupPrefabPlaceCommand
from sporebound.group_prefabs import (
    load_group_prefab, place_group_prefab, save_group_prefab)
from sporebound.model import Content, RuleError
from sporebound.quarter_generator import (
    STYLES, SIZES, generate_quarter, suggest_quarters, preview_quarter)


class AssistedQuartersTests(unittest.TestCase):
    MID = 'generated_quarter'

    def setUp(self):
        original = Content.load(DEFAULT_CONTENT).to_dict()
        self.data = add_blank_mission(original, self.MID,
                                      'Quarter generation', 40, 40)

    def mission(self, raw):
        return next(m for m in raw['missions'] if m['id'] == self.MID)

    def test_all_styles_sizes_and_seeds_generate_valid_editable_prefabs(self):
        for style in STYLES:
            for size in SIZES:
                with self.subTest(style=style, size=size):
                    p = generate_quarter(style=style, size=size, seed=17)
                    self.assertEqual(p['kind'], 'drawtemp_editor_group_prefab')
                    self.assertEqual(p['size'], list(size))
                    self.assertGreaterEqual(len(p['structures']), 4)
                    self.assertTrue(p['tiles'])
                    self.assertEqual(len(p['objects']), 1)
                    self.assertEqual(len(p['groups']), 5)
                    placed = place_group_prefab(self.data, self.MID,
                                                p, (5, 5))
                    valid = Content.from_dict(placed).missions[self.MID]
                    self.assertEqual(len(valid.structures), len(p['structures']))
                    self.assertEqual(len(valid.editor_groups), 5)
                    self.assertEqual(valid.objects[0]['kind'], 'chest')
                    self.assertEqual(valid.board.tile(
                        (5+size[0]//2, 5+size[1]//2)).surface,
                        'cobble' if style != 'Village' else 'dirt')

    def test_three_variants_are_distinct_stable_and_do_not_mutate_content(self):
        before = deepcopy(self.data)
        variants = suggest_quarters(style='Fortifié', seed=37)
        again = suggest_quarters(style='Fortifié', seed=37)
        self.assertEqual(variants, again)
        self.assertEqual(len(variants), 3)
        self.assertEqual(len(set(tuple((s['name'], tuple(s['anchor']))
                                       for s in p['structures'])
                                 for p in variants)), 3)
        self.assertEqual(self.data, before)

    def test_preview_returns_real_diff_without_mutation(self):
        p = generate_quarter(seed=10)
        before = deepcopy(self.data)
        future, report = preview_quarter(self.data, self.MID, p, (10, 10))
        self.assertEqual(report['structures'], 4)
        self.assertEqual(report['objects'], 1)
        self.assertEqual(report['groups'], 5)
        self.assertGreater(report['cells'], 40)
        self.assertTrue(report['changed_cells'])
        self.assertEqual(self.data, before)
        self.assertEqual(
            future, place_group_prefab(self.data, self.MID, p, (10, 10)))
        old_mission = self.mission(self.data)
        new_mission = self.mission(future)
        self.assertEqual(old_mission.get('triggers'),
                         new_mission.get('triggers'))
        self.assertEqual(old_mission.get('goal'), new_mission.get('goal'))

    def test_confirm_one_undo_second_copy_and_player_content(self):
        p = generate_quarter(style='Marché', seed=19)
        doc = Document(Content.from_dict(self.data))
        ctx = EditingContext(doc, lambda: self.MID)
        original = deepcopy(doc.data)
        first = ctx.preview(GroupPrefabPlaceCommand(p, (2, 2)))
        self.assertEqual(doc.data, original)
        ctx.apply(first)
        once = deepcopy(doc.data)
        ctx.execute(GroupPrefabPlaceCommand(p, (21, 20)))
        groups = self.mission(doc.data)['editor_groups']
        self.assertEqual(len(groups), 10)
        self.assertEqual(len({g['id'] for g in groups}), 10)
        self.assertEqual(len(self.mission(doc.data)['objects']), 2)
        Content.from_dict(doc.data)
        doc.undo()
        self.assertEqual(doc.data, once)
        doc.undo()
        self.assertEqual(doc.data, original)
        doc.redo()
        self.assertEqual(doc.data, once)

    def test_save_as_existing_portable_prefab_and_reload(self):
        p = generate_quarter(style='Village', seed=21)
        with TemporaryDirectory() as folder:
            target = Path(folder) / 'village.json'
            save_group_prefab(p, target)
            loaded = load_group_prefab(target)
            self.assertEqual(loaded, p)
            placed = place_group_prefab(self.data, self.MID, loaded,
                                        (10, 10))
            self.assertTrue(Content.from_dict(placed))

    def test_invalid_and_colliding_suggestions_leave_history_clean(self):
        doc = Document(Content.from_dict(self.data))
        valid = generate_quarter(seed=2)
        initial = deepcopy(doc.data)
        for at in ((-1, 0), (35, 35), (True, 2)):
            with self.subTest(at=at), self.assertRaises(RuleError):
                preview_quarter(doc.data, self.MID, valid, at)
            self.assertEqual(doc.data, initial)
            self.assertFalse(doc.undo_stack)
        doc.replace(place_group_prefab(doc.data, self.MID, valid, (2, 2)))
        committed = deepcopy(doc.data)
        undo_count = len(doc.undo_stack)
        with self.assertRaises(RuleError):
            preview_quarter(doc.data, self.MID, valid, (2, 2))
        self.assertEqual(doc.data, committed)
        self.assertEqual(len(doc.undo_stack), undo_count)

    def test_reject_unbounded_or_nondeterministic_inputs(self):
        for kwargs in (dict(style='Inconnu'), dict(size=(128, 128)),
                       dict(seed=True), dict(seed=-1), dict(seed=1000001)):
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                generate_quarter(**kwargs)
        with self.assertRaises(RuleError):
            suggest_quarters(seed=999999)


if __name__ == '__main__':
    unittest.main()
