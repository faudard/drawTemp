"""3.7.31 — headless regression gates for the consolidated Workspace shell."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_object
from sporebound.editor import Document
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.studio_index4 import StudioIndex
from sporebound.workspace_shell import (
    LayoutStore, inspect_map, inspect_resource, map_reference_problems,
    map_resource_target, palette_source_for_tree, problem_delta,
)


class WorkspaceShellTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.data = self.content.to_dict()
        self.project = GameProject.default(self.content)
        self.mid = next(iter(self.content.missions))

    def free_cells(self, count):
        mission = self.content.missions[self.mid]
        occupied = {tuple(o['pos']) for o in mission.objects}
        occupied.update(cell for actor in mission.units for cell in actor.occupied_cells())
        result = [cell for cell in mission.board.cells()
                  if cell not in occupied and not mission.board.tile(cell).blocked]
        self.assertGreaterEqual(len(result), count)
        return result[:count]

    def test_map_nodes_are_real_and_inspectable_with_existing_content(self):
        index = StudioIndex(self.content, self.project)
        for actor in self.content.missions[self.mid].units:
            key = 'map_actor:' + self.mid + '/' + actor.id
            self.assertIn(key, index.nodes)
            target = map_resource_target(key, self.data)
            self.assertEqual(target[1], tuple(actor.pos))
            snapshot = inspect_map(self.data, self.mid, actor.pos)
            self.assertIn(snapshot.kind, ('actor', 'object'))
            self.assertTrue(snapshot.detail)
            self.assertTrue(inspect_resource(index.nodes[key]).title)
        with self.assertRaises(RuleError):
            map_resource_target('map_actor:missing/bad', self.data)
        self.assertIsNone(map_resource_target('mission:' + self.mid, self.data))

    def test_workspace_refs_and_exact_object_inspector(self):
        index = StudioIndex(self.content, self.project)
        mission = 'mission:' + self.mid
        actor = self.content.missions[self.mid].units[0]
        actor_key = 'map_actor:' + self.mid + '/' + actor.id
        self.assertIn(actor_key, {r.target for r in index.outgoing(mission)})
        obj = self.content.missions[self.mid].objects[0]
        object_key = 'map_object:' + self.mid + '/' + obj['id']
        self.assertIn(object_key, {r.target for r in index.outgoing(mission)})
        snapshot = inspect_map(self.data, self.mid, obj['pos'],
                               preferred_kind='object', preferred_id=obj['id'])
        self.assertEqual(snapshot.kind, 'object')
        self.assertEqual(snapshot.entity_id, obj['id'])
        with self.assertRaises(RuleError):
            inspect_map(self.data, self.mid, obj['pos'],
                        preferred_kind='actor', preferred_id='missing')

    def test_tile_and_multi_cell_group_share_the_same_inspector_contract(self):
        free = self.free_cells(3)
        single = inspect_map(self.data, self.mid, free[0])
        self.assertEqual(single.kind, 'cell')
        self.assertIn('Sol', single.detail)
        multiple = inspect_map(self.data, self.mid, free[0], free)
        self.assertEqual(multiple.kind, 'group')
        self.assertEqual(multiple.cell, free[0])
        with self.assertRaises(RuleError):
            inspect_map(self.data, self.mid, (-1, 0))

    def test_problem_to_door_to_fix_updates_without_rebuilding_content(self):
        cell, switch_cell = self.free_cells(2)
        doc = Document(self.content)
        before = doc.data
        doc.replace(add_object(doc.data, self.mid, 'gate_unlinked_3731',
                               'door', cell))
        orphan = 'map_object:' + self.mid + '/gate_unlinked_3731'
        index = StudioIndex(Content.from_dict(doc.data), self.project)
        warnings = index.diagnostics('.', map_warnings=True)
        self.assertTrue(any(key == orphan for _, key, _ in warnings))
        self.assertEqual(map_resource_target(orphan, doc.data)[1], cell)

        doc.replace(add_object(doc.data, self.mid, 'lever_3731',
                               'switch', switch_cell, link='gate_unlinked_3731'))
        refreshed = StudioIndex(Content.from_dict(doc.data), self.project)
        current = refreshed.diagnostics('.', map_warnings=True)
        self.assertFalse(any(key == orphan for _, key, _ in current))
        added, resolved = problem_delta(warnings, current)
        self.assertEqual(added, ())
        self.assertTrue(any(key == orphan for _, key, _ in resolved))
        doc.undo()
        self.assertTrue(any(key == orphan for _, key, _ in
                            map_reference_problems(Content.from_dict(doc.data))))
        doc.redo()
        self.assertFalse(any(key == orphan for _, key, _ in
                             map_reference_problems(Content.from_dict(doc.data))))
        self.assertIsNot(before, doc.data)

    def test_drag_uses_existing_entity_catalog_and_rejects_stale_sources(self):
        actor = self.content.missions[self.mid].units[0]
        key = 'map_actor:' + self.mid + '/' + actor.id
        entry = palette_source_for_tree(key, self.data, self.mid)
        self.assertEqual(entry.id, 'actor:' + actor.id)
        obj = self.content.missions[self.mid].objects[0]
        entry = palette_source_for_tree(
            'map_object:' + self.mid + '/' + obj['id'], self.data, self.mid)
        self.assertEqual(entry.id, 'object:' + obj['kind'])
        with self.assertRaises(RuleError):
            palette_source_for_tree('asset:missing', self.data, self.mid)
        with self.assertRaises(RuleError):
            palette_source_for_tree('map_actor:other/' + actor.id,
                                    self.data, self.mid)

    def test_layout_store_is_project_local_atomic_and_ignores_broken_json(self):
        with TemporaryDirectory() as root:
            path = Path(root) / 'user.workspace.layout.json'
            store = LayoutStore(path)
            self.assertEqual(store.load(), {})
            store.save({'outer_left': 245, 'outer_right': 810,
                        'vertical': 650, 'tab': 'Carte et combat',
                        'unknown': 'never serialized'})
            self.assertEqual(store.load(), {
                'outer_left': 245, 'outer_right': 810,
                'vertical': 650, 'tab': 'Carte et combat'})
            self.assertNotIn('unknown', path.read_text(encoding='utf-8'))
            path.write_text('broken', encoding='utf-8')
            self.assertEqual(store.load(), {})


if __name__ == '__main__':
    unittest.main()
