"""3.6 real Tk canvas port drag between StoryBook scenes and Mission triggers."""
import os
from types import SimpleNamespace
import unittest

from sporebound.studio_story_graph import StoryGraphEditor
from sporebound.studio_transaction import StudioHistory
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Use xvfb-run on Linux')
class VisualBranchGraphGUITests(unittest.TestCase):
    def test_drag_link_scene_event_and_shift_create_nodes_in_one_history(self):
        import tkinter as tk
        from tkinter import ttk

        fixture = VisualBranchGraphTests()
        fixture.setUp()
        root = tk.Tk()
        errors = []
        root.geometry('1350x850')
        try:
            notebook = ttk.Notebook(root)
            notebook.pack(fill='both', expand=True)
            document = SimpleNamespace(data=fixture.data)
            def replace(value):
                document.data = value
            document.replace = replace
            history = StudioHistory(fixture.data, fixture.project)
            owner = SimpleNamespace(
                tk=tk, ttk=ttk, project=fixture.project,
                mission=lambda: 'garden',
                doc=lambda: document,
                design_change=lambda fn: fn(),
                set_active_mission=lambda mid: None,
            )
            def field(parent, row, label, default='', **kwargs):
                ttk.Label(parent, text=label).grid(
                    row=row, column=0, sticky='w')
                variable = tk.StringVar(value=default)
                ttk.Entry(parent, textvariable=variable).grid(
                    row=row, column=1)
                return variable, None
            owner._field = field
            editor = SimpleNamespace(owner=owner, notebook=notebook)
            graph = StoryGraphEditor(editor, notebook)
            editor.reset_project = lambda: graph.refresh()
            owner.refresh = lambda: graph.refresh()
            def run(operation):
                try:
                    operation()
                except Exception as exc:
                    errors.append(exc)
                else:
                    history.record(document.data, owner.project)
            owner._run = run
            graph.refresh()
            graph.root_var.set('Scène · v36_dialogue')
            graph._new_root()
            notebook.select(graph.page)
            root.update()
            self.assertGreater(len(graph._visual_ports), 2)
            self.assertGreater(len(graph._visual_targets), 3)
            self.assertTrue(any(
                'visual_link_port' in graph.canvas.gettags(item)
                for item in graph.canvas.find_all()))

            def drag(source_kind, source_id, target_kind=None,
                     target_id=None, *, shift=False, choice=None):
                if choice is not None:
                    graph.choice_var.set(choice)
                    graph._choice_selected()
                source_n = next(i for i, port in enumerate(graph._visual_ports)
                                if port['kind'] == source_kind and
                                port['id'] == source_id and
                                (choice is None or port['choice'] == choice))
                source = graph._visual_ports[source_n]
                origin = SimpleNamespace(x=source['x'], y=source['y'],
                                         state=0)
                graph._visual_begin(origin, source_n)
                if target_kind is None:
                    destination = SimpleNamespace(
                        x=10000, y=10000, state=1 if shift else 0)
                else:
                    target = next(t for t in graph._visual_targets
                                  if t['kind'] == target_kind and
                                  t['id'] == target_id)
                    x1, y1, x2, y2 = target['rect']
                    destination = SimpleNamespace(
                        x=(x1+x2)//2, y=(y1+y2)//2, state=0)
                graph._visual_motion(destination)
                graph._visual_release(destination)
                root.update()

            drag('scene', 'v36_dialogue', 'event', 'v36_assault',
                 choice='assault')
            self.assertEqual(
                fixture.trigger(document.data, 'v36_assault')['after_choice'],
                {'scene': 'v36_dialogue', 'choice': 'assault'})
            self.assertTrue(history.can_undo)
            self.assertEqual(len(errors), 0, errors)

            drag('scene', 'v36_dialogue', 'scene', 'v36_assault_scene',
                 choice='assault')
            definition = next(s for s in owner.project.story['scenes']
                              if s['id'] == 'v36_dialogue')
            self.assertEqual(definition['choices'][0]['next_scene'],
                             'v36_assault_scene')

            graph.event_join_var.set('OU')
            drag('event', 'v36_assault', 'event', 'v36_join')
            self.assertEqual(
                fixture.trigger(document.data, 'v36_join')['after_any'],
                ['v36_assault'])

            graph.choice_var.set('parley')
            graph._choice_selected()
            drag('scene', 'v36_dialogue', shift=True, choice='parley')
            self.assertTrue(any(s['id'] == 'visual_scene_1'
                                for s in owner.project.story['scenes']))
            drag('event', 'v36_assault', shift=True)
            self.assertTrue(any(e['id'] == 'visual_event_1'
                                for m in document.data['missions']
                                for e in m['triggers']))
            self.assertEqual(len(errors), 0, errors)
            # The drag-to-create produced ONE history state for BOTH docs.
            before_undo = document.data, owner.project.to_dict()
            restored_data, restored_project = history.undo()
            self.assertFalse(any(e['id'] == 'visual_event_1'
                                 for m in restored_data['missions']
                                 for e in m['triggers']))
            new_data, new_project = history.redo()
            self.assertEqual((new_data, new_project.to_dict()), before_undo)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
