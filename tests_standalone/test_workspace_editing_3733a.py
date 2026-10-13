"""3.7.33A — headless workspace inspector, one validated edit per command."""
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_object
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext
from sporebound.editor_groups import create_editor_group
from sporebound.model import Content, RuleError
from sporebound.workspace_editing import editable_form, WorkspacePropertyCommand
from sporebound.workspace_shell import map_reference_problems


class WorkspaceEditableTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.mid = 'garden'
        self.doc = Document(self.content)
        self.context = EditingContext(self.doc, lambda: self.mid)

    def apply(self, key, **fields):
        form = editable_form(self.doc.data, key)
        self.context.execute(WorkspacePropertyCommand(
            key, form.baseline, tuple(fields.items())))
        return editable_form(self.doc.data, key)

    def free_cell(self):
        m = self.content.missions[self.mid]
        occupied = {tuple(o['pos']) for o in m.objects}
        occupied.update(c for u in m.units for c in u.occupied_cells())
        return next(c for c in m.board.cells() if c not in occupied
                    and not m.board.tile(c).blocked)

    def test_actor_name_is_atomic_undoable_and_restored_after_redo(self):
        actor = self.content.missions[self.mid].units[0]
        key = f'map_actor:{self.mid}/{actor.id}'
        before = self.doc.data
        form = self.apply(key, name='Personnage Workspace')
        self.assertEqual({f.name: f.value for f in form.fields}['name'],
                         'Personnage Workspace')
        self.assertEqual(len(self.doc.undo_stack), 1)
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(self.apply_name(key), 'Personnage Workspace')

    def apply_name(self, key):
        return next(f.value for f in editable_form(self.doc.data, key).fields
                    if f.name == 'name')

    def test_group_rename_does_not_lose_members_or_create_a_new_schema(self):
        base = create_editor_group(self.doc.data, self.mid, 'Campement')
        self.doc.replace(base)
        self.doc.undo_stack.clear()
        updated = self.apply(f'editor_group:{self.mid}/group_1',
                             name='Campement fortifié')
        self.assertEqual(updated.fields[0].value, 'Campement fortifié')
        self.assertEqual(len(self.doc.undo_stack), 1)
        self.doc.undo()
        self.assertEqual(editable_form(
            self.doc.data, f'editor_group:{self.mid}/group_1').fields[0].value,
            'Campement')

    def test_door_reference_update_resolves_actionable_problem(self):
        door = 'workspace_gate_3733a'
        self.doc.replace(add_object(self.doc.data, self.mid, door, 'door',
                                    self.free_cell()))
        switch = next(o for o in self.content.missions[self.mid].objects
                      if o['kind'] == 'switch')
        key = f'map_object:{self.mid}/{switch["id"]}'
        orphan = f'map_object:{self.mid}/{door}'
        self.assertTrue(any(k == orphan for _, k, _ in
                            map_reference_problems(Content.from_dict(self.doc.data))))
        self.apply(key, link=door)
        self.assertFalse(any(k == orphan for _, k, _ in
                             map_reference_problems(Content.from_dict(self.doc.data))))
        self.doc.undo()
        self.assertTrue(any(k == orphan for _, k, _ in
                            map_reference_problems(Content.from_dict(self.doc.data))))

    def test_tile_brush_uses_canonical_authoring_with_single_undo(self):
        cell = self.free_cell()
        key = f'map_tile:{self.mid}/{cell[0]},{cell[1]}'
        original = self.doc.data
        updated = self.apply(key, surface='stone', feature='bush', height='2')
        self.assertEqual({field.name: field.value for field in updated.fields},
                         {'surface': 'stone', 'feature': 'bush', 'height': 2})
        self.assertEqual(len(self.doc.undo_stack), 1)
        self.doc.undo()
        self.assertEqual(self.doc.data, original)

    def test_stale_input_invalid_choice_and_unsupported_edit_are_atomic(self):
        actor = self.content.missions[self.mid].units[0]
        key = f'map_actor:{self.mid}/{actor.id}'
        before = self.doc.data
        form = editable_form(self.doc.data, key)
        bad = (
            WorkspacePropertyCommand(key, form.baseline, (('team', 'unknown'),)),
            WorkspacePropertyCommand(key, form.baseline, (('hp', 200),)),
            WorkspacePropertyCommand(key, form.baseline, (('team', True),)),
            WorkspacePropertyCommand(key, form.baseline, ()),
        )
        for command in bad:
            with self.subTest(command=command.values), self.assertRaises(RuleError):
                self.context.execute(command)
            self.assertEqual(self.doc.data, before)
        self.apply(key, name='Changed')
        previous = self.doc.data
        with self.assertRaisesRegex(RuleError, 'modifiée depuis'):
            self.context.execute(WorkspacePropertyCommand(
                key, form.baseline, (('name', 'stale'),)))
        self.assertEqual(self.doc.data, previous)
        with self.assertRaises(RuleError):
            editable_form(self.doc.data, 'map_object:garden/nonexistent')
        with self.assertRaises(RuleError):
            editable_form(self.doc.data, 'map_tile:garden/500,500')


if __name__ == '__main__':
    unittest.main()
