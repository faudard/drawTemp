"""3.7.23 — headless architecture gates; no Tk, no new Content schema."""
from copy import deepcopy
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_architecture import (
    EditingContext, EditorChange, ChangeNotifications, StructureCommand,
    EntityCommand, TacticalEventCommand, SelectionController, ToolController,
    RENDERER, MINIMAP, INSPECTOR, WORKSPACE)
from sporebound.event_composer import save_event, condition, action
from sporebound.iso_structures import place_structure
from sporebound.model import Content, RuleError


class EditorArchitectureTests(TestCase):
    mid = 'architecture_3723'

    def setUp(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 self.mid, 'Architecture', 20, 20)
        self.doc = Document(Content.from_dict(data))
        self.ctx = EditingContext(self.doc, lambda: self.mid)

    def mission(self):
        return next(m for m in self.doc.data['missions']
                    if m['id'] == self.mid)

    def test_bridge_preview_validate_apply_history_notify_only_relevant_views(self):
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Pont', (7, 7)))
        selected = next(s for s in self.mission()['structures']
                        if s['name'] == 'Pont')
        source = tuple(selected['anchor'])
        before = deepcopy(self.doc.data)
        count = len(self.doc.undo_stack)
        events = {view: [] for view in (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)}
        for view in events:
            self.ctx.notifications.subscribe(view, events[view].append)
        command = StructureCommand(source, anchor=(10, 10))
        preview = self.ctx.preview(command)
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), count)
        self.assertEqual(sum(map(len, events.values())), 0)
        notice = self.ctx.apply(preview)
        self.assertEqual(notice.kind, 'structure')
        self.assertEqual(len(self.doc.undo_stack), count + 1)
        self.assertEqual(tuple(self.mission()['structures'][-1]['anchor']), (10, 10))
        for view in (RENDERER, MINIMAP, INSPECTOR, WORKSPACE):
            self.assertEqual(events[view], [notice])
        self.doc.undo()
        self.assertEqual(self.doc.data, before)
        self.doc.redo()
        self.assertEqual(tuple(self.mission()['structures'][-1]['anchor']), (10, 10))

    def test_actor_edit_and_rejected_mutations_never_touch_history(self):
        original = deepcopy(self.doc.data)
        actor = self.mission()['units'][0]
        count = len(self.doc.undo_stack)
        command = EntityCommand('edit', 'actor', actor['id'],
                                fields=(('name', 'Nouvelle Jeanne'),))
        preview = self.ctx.preview(command)
        self.assertEqual(self.doc.data, original)
        self.assertEqual(len(self.doc.undo_stack), count)
        self.ctx.apply(preview)
        self.assertEqual(self.mission()['units'][0]['name'], 'Nouvelle Jeanne')
        before = deepcopy(self.doc.data)
        undo_count = len(self.doc.undo_stack)
        with self.assertRaises(RuleError):
            self.ctx.execute(EntityCommand(
                'edit', 'actor', actor['id'], fields=(('weapon', 'invalid'),)))
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), undo_count)

    def test_stale_preview_cannot_overwrite_unrelated_work(self):
        actor = self.mission()['units'][0]
        preview = self.ctx.preview(EntityCommand(
            'edit', 'actor', actor['id'], fields=(('name', 'Prévu'),)))
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Pont', (7, 7)))
        before = deepcopy(self.doc.data)
        undo_size = len(self.doc.undo_stack)
        with self.assertRaises(RuleError):
            self.ctx.apply(preview)
        self.assertEqual(self.doc.data, before)
        self.assertEqual(len(self.doc.undo_stack), undo_size)

    def test_tactical_event_uses_same_protocol_without_runtime_schema_change(self):
        self.doc.replace(save_event(
            self.doc.data, self.mid, 'bridge_signal',
            condition('tick', tick=8),
            [action('message', text='Pont surveillé')]))
        original = deepcopy(self.doc.data)
        notifications = {v: [] for v in (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)}
        for v in notifications:
            self.ctx.notifications.subscribe(v, notifications[v].append)
        cmd = TacticalEventCommand('bridge_signal', condition('tick', tick=12))
        self.ctx.execute(cmd)
        current = next(e for e in self.mission()['triggers']
                       if e['id'] == 'bridge_signal')
        self.assertEqual(current['value'], 12)
        self.assertEqual(current['actions'][0]['text'], 'Pont surveillé')
        self.assertFalse(notifications[RENDERER])
        self.assertFalse(notifications[MINIMAP])
        self.assertEqual(len(notifications[INSPECTOR]), 1)
        self.assertEqual(len(notifications[WORKSPACE]), 1)
        self.doc.undo()
        self.assertEqual(self.doc.data, original)

    def test_controller_selection_tool_deduplicate_and_unsubscribe(self):
        bus = ChangeNotifications()
        renderer, inspector, minimap = [], [], []
        bus.subscribe(RENDERER, renderer.append)
        stop = bus.subscribe(INSPECTOR, inspector.append)
        bus.subscribe(MINIMAP, minimap.append)
        selection = SelectionController(bus)
        tools = ToolController(bus)
        selection.set(self.mid, (2, 3), cells=((2, 3), (2, 3)))
        selection.set(self.mid, (2, 3), cells=((2, 3),))
        tools.set('Structure', self.mid)
        tools.set('Structure', self.mid)
        self.assertEqual(len(renderer), 1)
        self.assertEqual(len(inspector), 2)
        self.assertEqual(len(minimap), 0)
        stop()
        tools.set('Inspecter entité', self.mid)
        self.assertEqual(len(inspector), 2)
        self.assertEqual(selection.state.cells, ((2, 3),))

    def test_rejected_invalid_command_does_not_publish(self):
        notices = []
        self.ctx.notifications.subscribe(RENDERER, notices.append)
        before = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            self.ctx.execute(StructureCommand((5, 5), anchor=(300, 300)))
        self.assertEqual(self.doc.data, before)
        self.assertFalse(notices)
        self.assertFalse(self.doc.undo_stack)


if __name__ == '__main__':
    import unittest
    unittest.main()
