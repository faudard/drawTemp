"""3.6.2 real Tk navigation: search, orphan root, collapsed path, far event."""
import os
from copy import deepcopy
from types import SimpleNamespace
import unittest

from sporebound.studio_story_graph import StoryGraphEditor
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Run under Tk/Xvfb')
class StoryGraphNavigationGUITests(unittest.TestCase):
    def test_search_focus_orphan_conditional_and_event_pinning(self):
        import tkinter as tk
        from tkinter import ttk

        fixture = VisualBranchGraphTests()
        fixture.setUp()
        data, project = fixture.build()
        root = tk.Tk()
        root.geometry('1450x850')
        errors = []
        try:
            notebook = ttk.Notebook(root)
            notebook.pack(fill='both', expand=True)
            doc = SimpleNamespace(data=deepcopy(data))
            owner = SimpleNamespace(
                tk=tk, ttk=ttk, project=project,
                mission=lambda: 'garden',
                doc=lambda: doc,
            )
            def field(parent, row, label, default='', **kwargs):
                ttk.Label(parent, text=label).grid(row=row, column=0,
                                                   sticky='w')
                variable = tk.StringVar(value=default)
                ttk.Entry(parent, textvariable=variable).grid(
                    row=row, column=1)
                return variable, None
            owner._field = field
            def run(fn):
                try:
                    fn()
                except Exception as exc:
                    errors.append(exc)
            owner._run = run
            editor = SimpleNamespace(owner=owner, notebook=notebook)
            graph = StoryGraphEditor(editor, notebook)
            graph.refresh()
            graph.root_var.set('Scène · v36_dialogue')
            graph._new_root()
            notebook.select(graph.page)
            root.update()
            self.assertIsNotNone(graph.nav_search_entry)
            self.assertTrue(graph.nav_bar.winfo_exists())

            # Search scenes with accents and focus an initially collapsed path.
            graph.collapsed = {('v36_dialogue',)}
            graph.draw()
            graph.nav_filter.set('Scènes')
            graph.nav_query.set('Trêve')
            found = graph._navigation_find()
            self.assertEqual(found['matches'], 1)
            graph._navigation_go()
            self.assertEqual(graph.selected_path,
                             ('v36_dialogue', 'parley'))
            self.assertNotIn(('v36_dialogue',), graph.collapsed)
            self.assertEqual(graph.current_root, 'v36_dialogue')
            self.assertFalse(errors, errors)

            # Orphan scene is not reachable from game roots; navigation
            # re-roots ONLY the editor view, never the project manifest.
            original_story = deepcopy(owner.project.story)
            graph.nav_filter.set('Problèmes')
            graph.nav_query.set('isolée')
            result = graph._navigation_find()
            self.assertTrue(any(
                row['id'] == 'v36_orphan' for row in result['results']))
            graph._navigation_go()
            self.assertEqual(graph.current_root, 'v36_orphan')
            self.assertEqual(graph.selected_path, ('v36_orphan',))
            self.assertEqual(owner.project.story, original_story)

            # Event index does not use the first 60 events as a hard search
            # limit; a far match gets pinned into a bounded visual palette.
            garden = next(m for m in doc.data['missions']
                          if m['id'] == 'garden')
            for i in range(70):
                garden['triggers'].append({
                    'id': 'z_far_%03d' % i, 'condition': 'tick',
                    'value': 0, 'actions': [{
                        'kind': 'message', 'text': 'Marker '+str(i)}],
                })
            graph.nav_filter.set('Événements')
            graph.nav_query.set('z_far_069')
            matches = graph._navigation_find()
            self.assertEqual(matches['matches'], 1)
            graph._navigation_go()
            self.assertEqual(graph.selected_event, 'z_far_069')
            self.assertTrue(any(
                item['id'] == 'z_far_069'
                for item in graph._visual_targets))
            self.assertLessEqual(
                len([x for x in graph._visual_targets
                     if x['kind'] == 'event']), 60)
            self.assertFalse(errors, errors)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
