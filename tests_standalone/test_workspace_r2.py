"""R2 — Workspace UX gates: atomic inspector, canonical explorer, diagnostics."""
import unittest
from copy import deepcopy

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_object, add_unit
from sporebound.editor import Document
from sporebound.editor_architecture import EditingContext
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.studio_index4 import StudioIndex
from sporebound.workspace_editing import editable_form, WorkspacePropertyCommand
from sporebound.workspace_navigation import navigation_target
from sporebound.workspace_r2 import (
    BatchPropertyCommand, ExplorerState, batch_form, dependency_impact,
    validate_drop,
)
from sporebound.workspace_shell import map_reference_problems, problem_delta
from sporebound.workspace_refactoring import (RenameMapResourceCommand,
                                              DeleteMapResourceCommand,
                                              plan_coordinated_rename)
from sporebound.cinematics import cinematic_template, event_template
from sporebound.studio_transaction import StudioHistory
from sporebound.workspace_story_refactoring import (
    story_baseline, plan_story_rename,
)
from tempfile import TemporaryDirectory
from pathlib import Path


class WorkspaceR2Tests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.doc = Document(self.content)
        self.project = GameProject.default(self.content)
        self.mid = 'garden'
        self.context = EditingContext(self.doc, lambda: self.mid)

    def free_tiles(self, count):
        mission = self.content.missions[self.mid]
        occupied = {tuple(obj['pos']) for obj in mission.objects}
        occupied.update(cell for actor in mission.units
                        for cell in actor.occupied_cells())
        cells = [cell for cell in mission.board.cells()
                 if cell not in occupied and not mission.board.tile(cell).blocked]
        self.assertGreaterEqual(len(cells), count)
        return cells[:count]

    def tile_keys(self):
        return tuple('map_tile:%s/%s,%s' % (self.mid, x, y)
                     for x, y in self.free_tiles(2))

    def test_batch_edits_two_tiles_as_one_undo_redo(self):
        keys = self.tile_keys()
        form = batch_form(self.doc.data, keys)
        before = self.doc.data
        self.assertEqual(set(field.name for field in form.fields),
                         {'surface', 'feature', 'height'})
        self.context.execute(BatchPropertyCommand(
            form.keys, form.baselines, (('height', '3'),)))
        self.assertEqual(len(self.doc.undo_stack), 1)
        for key in keys:
            height = next(f.value for f in editable_form(self.doc.data, key).fields
                          if f.name == 'height')
            self.assertEqual(height, 3)
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(next(f.value for f in editable_form(self.doc.data, keys[0]).fields
                              if f.name == 'height'), 3)

    def test_mixed_values_and_stale_batch_are_explicit_and_atomic(self):
        keys = self.tile_keys()
        form = editable_form(self.doc.data, keys[0])
        self.context.execute(WorkspacePropertyCommand(
            keys[0], form.baseline, (('height', '2'),)))
        batch = batch_form(self.doc.data, keys)
        self.assertIn('height', batch.mixed)
        unchanged = self.doc.data
        for payload in ((('forbidden', 'x'),), (('height', 'invalid'),)):
            with self.assertRaises(RuleError):
                self.context.execute(BatchPropertyCommand(
                    batch.keys, batch.baselines, payload))
            self.assertEqual(self.doc.data, unchanged)
        self.context.execute(WorkspacePropertyCommand(
            keys[1], editable_form(self.doc.data, keys[1]).baseline,
            (('height', '4'),)))
        changed = self.doc.data
        with self.assertRaises(RuleError):
            self.context.execute(BatchPropertyCommand(
                batch.keys, batch.baselines, (('height', '5'),)))
        self.assertEqual(self.doc.data, changed)

    def test_mixed_families_cannot_trigger_partial_edit(self):
        actor = self.content.missions[self.mid].units[0]
        keys = (self.tile_keys()[0], f'map_actor:{self.mid}/{actor.id}')
        with self.assertRaises(RuleError):
            batch_form(self.doc.data, keys)

    def test_explorer_filters_favorites_recents_and_deleted_keys(self):
        index = StudioIndex(self.content, self.project)
        state = ExplorerState(limit=2)
        key = f'map_actor:{self.mid}/{self.content.missions[self.mid].units[0].id}'
        self.assertIn(key, state.shown(index, kind='map_actor'))
        self.assertTrue(state.toggle_favorite(key))
        self.assertEqual(state.shown(index, scope='favorites'), {key})
        state.visit(key)
        state.visit('mission:' + self.mid)
        state.visit(key)
        self.assertEqual(state.recents, [key, 'mission:' + self.mid])
        self.assertIn(key, state.shown(index, scope='recents'))
        self.assertEqual(state.shown(index, query='nom introuvable'), set())
        self.assertEqual(state.shown(index, scope='favorites', kind='mission'), set())
        state.toggle_favorite(key)
        self.assertFalse(state.shown(index, scope='favorites'))
        state.favorites.add('mission:deleted')
        state.reconcile(index)
        self.assertNotIn('mission:deleted', state.favorites)

    def test_impact_uses_index_incoming_outgoing_and_validated_drop(self):
        index = StudioIndex(self.content, self.project)
        actor = self.content.missions[self.mid].units[0]
        key = f'map_actor:{self.mid}/{actor.id}'
        report = dependency_impact(index, key)
        self.assertTrue(any(r.source == 'mission:' + self.mid for r in report.incoming))
        self.assertEqual(report.outgoing, index.outgoing(key))
        self.assertEqual(validate_drop(self.doc.data, self.mid, key).id,
                         'actor:' + actor.id)
        with self.assertRaises(RuleError):
            dependency_impact(index, 'map_actor:garden:deleted')
        with self.assertRaises(RuleError):
            validate_drop(self.doc.data, self.mid, 'asset:missing')

    @staticmethod
    def _linked_story_project(content):
        raw = GameProject.default(content).to_dict()
        raw['story'] = {
            'scenes': [
                {'id': 'r2_old_scene', 'title': 'Scène R2',
                 'speaker': 'Jeanne', 'text': 'Prologue',
                 'choices': [{'id': 'continue', 'label': 'Continuer'}]},
                {'id': 'r2_parent_scene', 'title': 'Choix R2',
                 'speaker': '', 'text': 'Que faire ?',
                 'choices': [{'id': 'begin', 'label': 'Entrer',
                              'next_scene': 'r2_old_scene'}]},
            ],
            'entry_scenes': {'main': 'r2_parent_scene'},
            'after_mission': {'garden': 'r2_old_scene'},
        }
        raw['cinematics'] = [cinematic_template(
            'r2_scene_clip', 'Scène cinématique', 'scene', 'r2_old_scene')]
        return GameProject.from_dict(raw, content)

    def test_scene_rename_rewrites_narrative_branches_and_cinematics(self):
        project = self._linked_story_project(self.content)
        key = 'scene:r2_old_scene'
        form = story_baseline(project, key)
        candidate, updated = plan_story_rename(
            self.doc.data, project, key, form, 'r2_renamed_scene')
        self.assertEqual(candidate, self.doc.data)
        self.assertEqual(updated.story['after_mission']['garden'],
                         'r2_renamed_scene')
        self.assertEqual(updated.story['scenes'][1]['choices'][0]['next_scene'],
                         'r2_renamed_scene')
        self.assertEqual(updated.cinematics[0]['trigger']['target'],
                         'r2_renamed_scene')
        self.assertEqual(story_baseline(updated, 'scene:r2_renamed_scene'),
                         story_baseline(updated.to_dict(), 'scene:r2_renamed_scene'))
        history = StudioHistory(self.doc.data, project)
        self.assertTrue(history.record(candidate, updated))
        undo_content, undo_project = history.undo()
        self.assertEqual(undo_project.story['after_mission']['garden'],
                         'r2_old_scene')
        redo_content, redo_project = history.redo()
        self.assertEqual(redo_project.story['after_mission']['garden'],
                         'r2_renamed_scene')
        self.assertEqual(undo_content, redo_content)

    def test_scene_rename_updates_content_choice_guards_and_story_links(self):
        doc = deepcopy(self.doc.data)
        first = next(m for m in doc['missions'] if m['id'] == 'garden')
        trigger = first['triggers'][0]
        trigger['after_choice'] = {
            'scene': 'r2_old_scene', 'choice': 'continue'}
        content = Content.from_dict(doc)
        project_data = self._linked_story_project(content).to_dict()
        project_data['story']['during_tactical_event'] = {
            'garden/' + trigger['id']: 'r2_old_scene'}
        project = GameProject.from_dict(project_data, content)
        result, updated = plan_story_rename(
            doc, project, 'scene:r2_old_scene',
            story_baseline(project, 'scene:r2_old_scene'), 'r2_new_scene')
        changed = next(m for m in result['missions'] if m['id'] == 'garden')
        self.assertEqual(changed['triggers'][0]['after_choice']['scene'],
                         'r2_new_scene')
        self.assertEqual(
            updated.story['during_tactical_event']['garden/' + trigger['id']],
            'r2_new_scene')
        index = StudioIndex(Content.from_dict(result), updated)
        sources = {link.source for link in index.incoming('scene:r2_new_scene')}
        self.assertIn('tactical_event:garden/' + trigger['id'], sources)
        self.assertIn('mission:garden', sources)

    def test_scene_rename_rejects_stale_and_unknown_project_refs(self):
        project = self._linked_story_project(self.content)
        before = project.to_dict()
        baseline = story_baseline(project, 'scene:r2_old_scene')
        with self.assertRaises(RuleError):
            plan_story_rename(self.doc.data, project,
                              'scene:r2_old_scene', '{}', 'another_scene')
        modified = deepcopy(before)
        modified['subtitle'] = 'r2_old_scene'
        with self.assertRaises(RuleError):
            plan_story_rename(self.doc.data, modified,
                              'scene:r2_old_scene', baseline, 'another_scene')
        self.assertEqual(project.to_dict(), before)
        self.assertEqual(self.doc.data, self.content.to_dict())

    def test_campaign_rename_updates_links_and_checks_save_namespace(self):
        project = self._linked_story_project(self.content)
        project_data = project.to_dict()
        project_data['cinematics'].append(cinematic_template(
            'r2_campaign_clip', 'Ouverture', 'campaign_start', 'main'))
        project = GameProject.from_dict(project_data, self.content)
        key = 'campaign:main'
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'scenario.game.json'
            candidate, updated = plan_story_rename(
                self.doc.data, project, key, story_baseline(project, key),
                'r2_new_campaign', project_path=path)
            self.assertEqual(candidate, self.doc.data)
            self.assertEqual(updated.campaigns[0]['id'], 'r2_new_campaign')
            self.assertEqual(updated.story['entry_scenes'],
                             {'r2_new_campaign': 'r2_parent_scene'})
            self.assertEqual(updated.cinematics[-1]['trigger']['target'],
                             'r2_new_campaign')
            legacy = path.with_name(path.stem + '_saves') / 'main'
            legacy.mkdir(parents=True)
            with self.assertRaises(RuleError):
                plan_story_rename(self.doc.data, project, key,
                                  story_baseline(project, key),
                                  'r2_new_campaign', project_path=path)
        with self.assertRaises(RuleError):
            plan_story_rename(self.doc.data, project, key,
                              story_baseline(project, key),
                              'r2_new_campaign')

    def test_known_cinematic_actor_reference_migrates_both_documents(self):
        clip = cinematic_template(
            'r2_cast', 'Acteur R2', 'before_mission', self.mid)
        cue = event_template('actor', 'r2_cue')
        cue['actor'] = 'ziggy'
        clip['events'].append(cue)
        project_data = self.project.to_dict()
        project_data['cinematics'] = [clip]
        project = GameProject.from_dict(project_data, self.content)
        indexed = StudioIndex(self.content, project)
        impact = dependency_impact(indexed, 'map_actor:garden/ziggy')
        self.assertTrue(any(ref.source == 'cinematic:r2_cast'
                            for ref in impact.incoming))
        key = 'map_actor:garden/ziggy'
        baseline = editable_form(self.doc.data, key).baseline
        candidate, updated = plan_coordinated_rename(
            self.doc.data, project, key, baseline, 'ziggy_r2')
        Content.from_dict(candidate)
        self.assertEqual(updated.cinematics[0]['events'][0]['actor'], 'ziggy_r2')
        self.assertTrue(any(actor['id'] == 'ziggy_r2'
                            for actor in Content.from_dict(
                                candidate).missions[self.mid].units))
        history = StudioHistory(self.doc.data, project)
        self.doc.replace(candidate)
        self.assertTrue(history.record(self.doc.data, updated))
        old_content, old_project = history.undo()
        self.assertTrue(any(actor['id'] == 'ziggy'
                            for actor in Content.from_dict(
                                old_content).missions[self.mid].units))
        self.assertEqual(old_project.cinematics[0]['events'][0]['actor'], 'ziggy')
        new_content, new_project = history.redo()
        self.assertEqual(new_project.cinematics[0]['events'][0]['actor'], 'ziggy_r2')
        self.assertTrue(any(actor['id'] == 'ziggy_r2'
                            for actor in Content.from_dict(
                                new_content).missions[self.mid].units))

    def test_ambiguous_foreign_mission_cinematic_blocks_migration(self):
        clip = cinematic_template(
            'r2_foreign', 'Autre mission', 'before_mission', 'escape')
        cue = event_template('actor', 'r2_other_cue')
        cue['actor'] = 'ziggy'
        clip['events'].append(cue)
        project_data = self.project.to_dict()
        project_data['cinematics'] = [clip]
        project = GameProject.from_dict(project_data, self.content)
        original = self.doc.data
        with self.assertRaises(RuleError):
            plan_coordinated_rename(
                original, project, 'map_actor:garden/ziggy',
                editable_form(original, 'map_actor:garden/ziggy').baseline,
                'ziggy_r2')
        self.assertEqual(self.doc.data, original)
        self.assertFalse(self.doc.undo_stack)

    def test_delete_independent_object_is_atomic_and_undoable(self):
        mid = self.mid
        free = self.free_tiles(1)[0]
        data = add_object(self.doc.data, mid, 'r2_unused_chest', 'chest', free)
        self.doc.replace(data)
        key = 'map_object:garden/r2_unused_chest'
        count = len(self.doc.undo_stack)
        baseline = editable_form(self.doc.data, key).baseline
        self.context.execute(DeleteMapResourceCommand(
            key, baseline, self.project.to_dict()))
        self.assertEqual(len(self.doc.undo_stack), count + 1)
        self.assertFalse(any(obj['id'] == 'r2_unused_chest'
                             for obj in next(m for m in self.doc.data['missions']
                                             if m['id'] == mid)['objects']))
        self.doc.undo()
        self.assertTrue(any(obj['id'] == 'r2_unused_chest'
                            for obj in next(m for m in self.doc.data['missions']
                                            if m['id'] == mid)['objects']))
        self.doc.redo()
        with self.assertRaises(RuleError):
            editable_form(self.doc.data, key)

    def test_delete_refused_when_object_still_referenced(self):
        mid = self.mid
        first, second = self.free_tiles(2)
        data = add_object(self.doc.data, mid, 'r2_referenced_door',
                          'door', first)
        data = add_object(data, mid, 'r2_referencing_switch',
                          'switch', second, link='r2_referenced_door')
        self.doc.replace(data)
        key = 'map_object:garden/r2_referenced_door'
        before = self.doc.data
        count = len(self.doc.undo_stack)
        with self.assertRaises(RuleError):
            self.context.execute(DeleteMapResourceCommand(
                key, editable_form(self.doc.data, key).baseline,
                self.project.to_dict()))
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), count)

    def test_delete_refused_on_stale_or_project_reference(self):
        key = 'map_actor:garden/ziggy'
        form = editable_form(self.doc.data, key)
        before = self.doc.data
        with self.assertRaises(RuleError):
            self.context.execute(DeleteMapResourceCommand(
                key, form.baseline, {'caption': 'ziggy'}))
        with self.assertRaises(RuleError):
            self.context.execute(DeleteMapResourceCommand(
                key, '{}', self.project.to_dict()))
        self.assertEqual(self.doc.data, before)
        self.assertFalse(self.doc.undo_stack)

    def test_resource_id_rename_propagates_known_actor_dependencies(self):
        mid = self.mid
        initial = add_unit(self.doc.data, mid, 'r2_actor_old',
                           'Unit R2', 'player', self.free_tiles(1)[0])
        mission = next(m for m in initial['missions'] if m['id'] == mid)
        mission['protected_id'] = 'r2_actor_old'
        mission['triggers'][0]['actions'].append({
            'kind': 'despawn', 'unit': 'r2_actor_old'})
        self.doc.replace(initial)
        key = 'map_actor:garden/r2_actor_old'
        form = editable_form(self.doc.data, key)
        count = len(self.doc.undo_stack)
        self.context.execute(RenameMapResourceCommand(
            key, form.baseline, 'r2_actor_new', self.project.to_dict()))
        self.assertEqual(len(self.doc.undo_stack), count + 1)
        after = next(m for m in self.doc.data['missions'] if m['id'] == mid)
        self.assertEqual(after['protected_id'], 'r2_actor_new')
        self.assertTrue(any(u['id'] == 'r2_actor_new' for u in after['units']))
        self.assertEqual(after['triggers'][0]['actions'][-1]['unit'], 'r2_actor_new')
        self.doc.undo()
        self.assertTrue(any(u['id'] == 'r2_actor_old'
                            for u in next(m for m in self.doc.data['missions']
                                          if m['id'] == mid)['units']))

    def test_rename_linked_door_updates_switch_and_blocks_unknown_refs(self):
        mid = self.mid
        first, second = self.free_tiles(2)
        data = add_object(self.doc.data, mid, 'r2_door_old', 'door', first)
        data = add_object(data, mid, 'r2_switch_new', 'switch', second,
                          link='r2_door_old')
        self.doc.replace(data)
        key = 'map_object:garden/r2_door_old'
        baseline = editable_form(self.doc.data, key).baseline
        self.context.execute(RenameMapResourceCommand(
            key, baseline, 'r2_door_new', self.project.to_dict()))
        mission = next(m for m in self.doc.data['missions'] if m['id'] == mid)
        self.assertIn('r2_door_new', {o['id'] for o in mission['objects']})
        self.assertEqual(next(o['link'] for o in mission['objects']
                              if o['id'] == 'r2_switch_new'), 'r2_door_new')
        with self.assertRaises(RuleError):
            self.context.execute(RenameMapResourceCommand(
                'map_object:garden/r2_door_new',
                editable_form(self.doc.data,
                              'map_object:garden/r2_door_new').baseline,
                'r2_door_new', self.project.to_dict()))

        # Unknown references are blocked, never silently left behind.
        data = self.doc.data
        mission = next(m for m in data['missions'] if m['id'] == mid)
        mission['triggers'][0]['actions'].append({
            'kind': 'message', 'text': 'r2_door_new'})
        self.doc.replace(data)
        frozen = self.doc.data
        with self.assertRaises(RuleError):
            self.context.execute(RenameMapResourceCommand(
                'map_object:garden/r2_door_new',
                editable_form(self.doc.data,
                              'map_object:garden/r2_door_new').baseline,
                'r2_door_later', self.project.to_dict()))
        self.assertEqual(self.doc.data, frozen)

    def test_actor_reference_warning_is_repairable_by_existing_inspector(self):
        """An authored despawn action can reference an unknown actor ID."""
        source = self.doc.data
        source['missions'][0]['triggers'][0]['actions'].append({
            'kind': 'despawn', 'unit': 'unknown_actor_r2'})
        # Input is still valid authored Content; the reference is an editor
        # warning, not a new alternative validation rule.
        self.doc.replace(source)
        before = StudioIndex(Content.from_dict(self.doc.data), self.project)
        trigger = self.doc.data['missions'][0]['triggers'][0]
        key = f'tactical_event:{self.mid}/{trigger["id"]}'
        problems = before.diagnostics('.', map_warnings=True)
        self.assertTrue(any(ref == key for _, ref, _ in problems))
        self.assertIn(key, before.nodes)
        form = editable_form(self.doc.data, key)
        self.assertEqual(tuple(f.name for f in form.fields), ('despawn_unit',))
        target = self.content.missions[self.mid].units[0].id
        original_undo_count = len(self.doc.undo_stack)
        self.context.execute(WorkspacePropertyCommand(
            key, form.baseline, (('despawn_unit', target),)))
        self.assertEqual(len(self.doc.undo_stack), original_undo_count + 1)
        after = StudioIndex(Content.from_dict(self.doc.data), self.project)
        self.assertFalse(any(ref == key for _, ref, _ in
                             after.diagnostics('.', map_warnings=True)))
        self.assertIn(key, {ref.source for ref in after.incoming(
            f'map_actor:{self.mid}/{target}')})
        self.doc.undo()
        self.assertTrue(any(ref == key for _, ref, _ in
                            StudioIndex(Content.from_dict(self.doc.data),
                                        self.project).diagnostics(
                                            '.', map_warnings=True)))

    def test_problem_to_inspector_fix_to_map_without_manual_refresh(self):
        door_id = 'r2_unlinked_door'
        self.doc.replace(add_object(self.doc.data, self.mid,
                                    door_id, 'door', self.free_tiles(1)[0]))
        orphan = f'map_object:{self.mid}/{door_id}'
        before = StudioIndex(Content.from_dict(self.doc.data), self.project)
        problems = before.diagnostics('.', map_warnings=True)
        self.assertTrue(any(key == orphan for _, key, _ in problems))
        mid, cell = navigation_target(self.doc.data, orphan)
        self.assertEqual(mid, self.mid)
        self.assertEqual(len(cell), 2)
        switch = next(obj for obj in self.content.missions[self.mid].objects
                      if obj['kind'] == 'switch')
        key = f'map_object:{self.mid}/{switch["id"]}'
        edit = editable_form(self.doc.data, key)
        self.context.execute(WorkspacePropertyCommand(
            key, edit.baseline, (('link', door_id),)))
        after = StudioIndex(Content.from_dict(self.doc.data), self.project)
        current = after.diagnostics('.', map_warnings=True)
        self.assertFalse(any(key == orphan for _, key, _ in current))
        _, resolved = problem_delta(problems, current)
        self.assertTrue(any(key == orphan for _, key, _ in resolved))
        self.doc.undo()
        self.assertTrue(any(key == orphan for _, key, _ in
                            map_reference_problems(Content.from_dict(self.doc.data))))


if __name__ == '__main__':
    unittest.main()
