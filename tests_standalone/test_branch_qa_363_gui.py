"""3.6.3 real Tk Branch QA diagnostics, probes, focus and JSON export."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sporebound.studio_story_graph import StoryGraphEditor
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Execute with Xvfb')
class BranchQAGUITests(unittest.TestCase):
    def test_story_graph_quality_panel_runs_and_links_diagnostics(self):
        import tkinter as tk
        from tkinter import ttk

        fixture = VisualBranchGraphTests()
        fixture.setUp()
        data, project = fixture.build()
        before = json.dumps((data, project.to_dict()), sort_keys=True)
        root = tk.Tk()
        root.geometry('1500x930')
        callback_errors = []
        try:
            book = ttk.Notebook(root)
            book.pack(fill='both', expand=True)
            owner = SimpleNamespace(
                tk=tk, ttk=ttk, project=project,
                mission=lambda: 'garden',
                doc=lambda: SimpleNamespace(data=data))
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
                    return fn()
                except Exception as exc:
                    callback_errors.append(exc)
                    return None
            owner._run = run
            editor = SimpleNamespace(owner=owner, notebook=book)
            graph = StoryGraphEditor(editor, book)
            graph.refresh()
            book.select(graph.page)
            root.update()

            graph._qa_open()
            root.update()
            self.assertTrue(graph.qa_window.winfo_exists())
            structural = graph.qa_last_report
            self.assertEqual(structural['kind'], 'structural')
            self.assertTrue(graph.qa_issue_refs)
            orphan = next(iid for iid, pair in graph.qa_issue_refs.items()
                          if pair[0] == 'v36_orphan')
            graph.qa_tree.selection_set(orphan)
            graph._qa_focus_issue()
            root.update()
            self.assertEqual(graph.current_root, 'v36_orphan')
            self.assertEqual(graph.selected_path, ('v36_orphan',))

            simulated = graph._qa_simulate()
            self.assertEqual(simulated['kind'], 'storybook_probe')
            self.assertTrue(simulated['executed_choices'])
            self.assertFalse(simulated['replay_verified'])
            self.assertIn('SYNTHÉTIQUES',
                          graph.qa_text.get('1.0','end'))

            tactical = graph._qa_events()
            self.assertEqual(tactical['kind'], 'isolated_battle_preview')
            self.assertFalse(tactical['replay_verified'])
            self.assertIn('BATTLE ISOLÉS',
                          graph.qa_text.get('1.0','end'))
            # 3.6.4: certify real GameSession commands from the same Studio
            # window, not the preview's disposable Battle state.
            contract = {
                'version': 1, 'min_passed_paths': 1,
                'required_choices': ['v36_dialogue/assault'],
                'required_events': [
                    'v36_origin', 'v36_assault', 'v36_join'],
                'cases': [{
                    'id': 'gui_real_assault', 'campaign': 'main', 'seed': 17,
                    'steps': [
                        {'kind': 'start_mission', 'mission': 'garden',
                         'expect': {
                             'pending_tactical': 'v36_dialogue',
                             'fired': ['v36_origin']}},
                        {'kind': 'tactical_choice', 'choice': 'assault',
                         'expect': {
                             'pending_tactical': 'v36_assault_scene',
                             'fired': ['v36_assault', 'v36_join'],
                             'not_fired': ['v36_parley']}},
                    ],
                }],
            }
            with TemporaryDirectory() as folder:
                script_path = Path(folder)/'certification.json'
                script_path.write_text(
                    json.dumps(contract), encoding='utf-8')
                with patch('tkinter.filedialog.askopenfilename',
                           return_value=str(script_path)):
                    certified = graph._qa_certify()
                self.assertTrue(certified['passed'], certified['gate_errors'])
                self.assertTrue(certified['replay_verified'])
                self.assertIn('Gate : PASS',
                              graph.qa_text.get('1.0','end'))
            with TemporaryDirectory() as folder:
                target = Path(folder)/'qa-report.json'
                with patch('tkinter.filedialog.asksaveasfilename',
                           return_value=str(target)):
                    graph._qa_export()
                written = json.loads(target.read_text(encoding='utf-8'))
                self.assertEqual(written, tactical)
            graph._qa_close()
            self.assertIsNone(graph.qa_window)
            self.assertEqual(json.dumps((data, project.to_dict()),
                                        sort_keys=True), before)
            self.assertFalse(callback_errors, callback_errors)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
