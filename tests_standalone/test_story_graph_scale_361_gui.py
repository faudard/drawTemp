"""3.6.1 Tk/Xvfb: large Story Graph layout, grouping, A/B overlays."""
import os
from types import SimpleNamespace
import unittest

from sporebound.studio_story_graph import StoryGraphEditor
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Run under Tk/Xvfb')
class StoryGraphScaleGuiTests(unittest.TestCase):
    def test_compact_group_compare_refresh_and_root_change(self):
        import tkinter as tk
        from tkinter import ttk
        fixture = VisualBranchGraphTests()
        fixture.setUp()
        data, project = fixture.build()
        root = tk.Tk()
        root.geometry('1300x900')
        errors = []
        try:
            book = ttk.Notebook(root)
            book.pack(fill='both', expand=True)
            owner = SimpleNamespace(
                tk=tk, ttk=ttk, project=project,
                mission=lambda: 'garden',
                doc=lambda: SimpleNamespace(data=data),
            )
            def field(parent, row, label, default='', **kwargs):
                ttk.Label(parent, text=label).grid(
                    row=row, column=0, sticky='w')
                v = tk.StringVar(value=default)
                ttk.Entry(parent, textvariable=v).grid(
                    row=row, column=1)
                return v, None
            owner._field = field
            def run(fn):
                try:
                    fn()
                except Exception as exc:
                    errors.append(exc)
            owner._run = run
            editor = SimpleNamespace(owner=owner, notebook=book)
            graph = StoryGraphEditor(editor, book)
            graph.refresh()
            graph.root_var.set('Scène · v36_dialogue')
            graph._new_root()
            book.select(graph.page)
            root.update()
            normal = graph.layout
            self.assertEqual(normal['density'], 'normal')
            node_paths = {node['path'] for node in normal['nodes']}
            a = ('v36_dialogue', 'assault')
            b = ('v36_dialogue', 'parley')
            self.assertIn(a, node_paths)
            self.assertIn(b, node_paths)

            graph.scale_density.set('Compact')
            graph.draw()
            self.assertEqual(graph.layout['density'], 'compact')
            self.assertLess(graph.layout['width'], normal['width'])
            graph.selected_path = a
            graph.draw()
            graph._scale_mark('a')
            graph.selected_path = b
            graph.draw()
            graph._scale_mark('b')
            self.assertEqual(graph._scale_style((graph.current_root,)),
                             '#ddd6fe')
            self.assertEqual(graph._scale_style(a), '#bfdbfe')
            self.assertEqual(graph._scale_style(b), '#fed7aa')
            graph._scale_compare()
            info = graph.scale_text.get('1.0', 'end')
            self.assertIn('COMPARAISON DES PARCOURS', info)
            self.assertIn('v36_assault', info)
            self.assertIn('v36_parley', info)

            graph._scale_clear()
            self.assertIsNone(graph.scale_path_a)
            self.assertIsNone(graph.scale_path_b)
            self.assertIn('SOUS-BRANCHES', graph.scale_text.get('1.0', 'end'))
            graph._scale_toggle_groups()
            self.assertTrue(graph.scale_is_grouped)
            graph._scale_expand_all()
            self.assertFalse(graph.scale_is_grouped)
            self.assertFalse(graph.collapsed)
            graph.root_var.set('Scène · v36_assault_scene')
            graph._new_root()
            self.assertIsNone(graph.scale_path_a)
            self.assertEqual(graph.current_root, 'v36_assault_scene')
            self.assertFalse(errors, errors)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
