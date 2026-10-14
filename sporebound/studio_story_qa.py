"""3.6.3 Branch QA window attached to the existing StoryGraphEditor.

The inspector is read-only: no Content or GameProject mutation. Double click
a finding to focus the same Story Graph navigation used by 3.6.2.
"""
import json

from .branch_qa_363 import (
    audit_branch_coverage, probe_story_choices, probe_tactical_branches,
    format_branch_qa)
from .model import require


class StoryGraphQAControls:
    def _qa_setup(self):
        self.qa_window = None
        self.qa_last_report = None
        self.qa_issue_refs = {}
        self._button(self.qa_header, 'QA & couverture', self._qa_open)

    def _qa_open(self):
        require(self.owner.project is not None, 'Ouvrir un projet de jeu')
        if self.qa_window is not None:
            try:
                if self.qa_window.winfo_exists():
                    self.qa_window.lift()
                    return
            except self.tk.TclError:
                pass
        ttk, tk = self.ttk, self.tk
        window = tk.Toplevel(self.page)
        self.qa_window = window
        window.title('Branch QA & Coverage — Story Graph')
        window.geometry('1000x680')
        window.transient(self.page.winfo_toplevel())
        window.protocol('WM_DELETE_WINDOW', self._qa_close)
        bar = ttk.Frame(window)
        bar.pack(fill='x', padx=10, pady=7)
        self._button(bar, 'Auditer la structure', self._qa_audit)
        self._button(bar, 'Simuler les dialogues', self._qa_simulate)
        self._button(bar, 'Prévisualiser événements', self._qa_events)
        self._button(bar, 'Exporter JSON', self._qa_export)
        ttk.Label(
            window, text=(
                'Les sondes StoryBook sont synthétiques. Les aperçus Battle '
                'ne certifient PAS un replay GameSession. '
                'Double-cliquer un diagnostic pour ouvrir la scène.'),
            wraplength=950).pack(fill='x', padx=10, pady=(0, 5))
        splitter = ttk.PanedWindow(window, orient='vertical')
        splitter.pack(fill='both', expand=True, padx=10, pady=8)
        upper = ttk.Frame(splitter)
        lower = ttk.Frame(splitter)
        splitter.add(upper, weight=2)
        splitter.add(lower, weight=3)
        self.qa_tree = ttk.Treeview(
            upper, columns=('priority', 'scene', 'choice', 'reason'),
            show='headings', height=8, selectmode='browse')
        for key, label, width in (
                ('priority', 'Niveau', 100),
                ('scene', 'Scène', 190),
                ('choice', 'Choix', 155),
                ('reason', 'Diagnostic', 480)):
            self.qa_tree.heading(key, text=label)
            self.qa_tree.column(key, width=width, stretch=key == 'reason')
        self.qa_tree.pack(fill='both', expand=True)
        self.qa_tree.bind('<Double-Button-1>',
                          lambda _event: self.owner._run(self._qa_focus_issue))
        self.qa_text = tk.Text(
            lower, wrap='word', state='disabled', relief='flat')
        scroll = ttk.Scrollbar(lower, command=self.qa_text.yview)
        self.qa_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.qa_text.pack(fill='both', expand=True)
        self._qa_audit()

    def _qa_close(self):
        if self.qa_window is not None:
            self.qa_window.destroy()
        self.qa_window = None

    def _qa_update(self, report):
        self.qa_last_report = report
        self.qa_text.configure(state='normal')
        self.qa_text.delete('1.0', 'end')
        self.qa_text.insert('1.0', '\n'.join(format_branch_qa(report)))
        self.qa_text.configure(state='disabled')
        for row in self.qa_tree.get_children():
            self.qa_tree.delete(row)
        self.qa_issue_refs = {}
        if report['kind'] == 'structural':
            for i, issue in enumerate(report['issues'][:300]):
                ref = self.qa_tree.insert(
                    '', 'end', values=(
                        issue['severity'], issue['scene_id'],
                        issue['choice_id'], issue['detail']))
                self.qa_issue_refs[ref] = (
                    issue['scene_id'], issue['choice_id'])
        self.status.set('Branch QA : '+report['kind']+
                        ' · lecture seule · '+str(len(self.qa_issue_refs))+
                        ' diagnostics visibles')

    def _qa_audit(self):
        report = audit_branch_coverage(
            self.owner.project.story, self.owner.doc().data,
            self._visual_mission_id())
        self._qa_update(report)
        return report

    def _qa_simulate(self):
        report = probe_story_choices(
            self.owner.doc().data, self.owner.project,
            max_states=220, max_depth=24)
        self._qa_update(report)
        return report

    def _qa_events(self):
        report = probe_tactical_branches(
            self.owner.doc().data, self.owner.project,
            self._visual_mission_id(), max_events=8)
        self._qa_update(report)
        return report

    def _qa_focus_issue(self):
        selected = self.qa_tree.selection()
        require(bool(selected), 'Sélectionner un diagnostic')
        item = self.qa_issue_refs.get(selected[0])
        require(item is not None, 'Ce diagnostic ne contient pas de scène')
        sid, cid = item
        self._navigation_focus_scene(sid, cid)
        self.qa_window.lift()

    def _qa_export(self):
        require(self.qa_last_report is not None,
                'Exécuter un contrôle de couverture avant export')
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self.qa_window, defaultextension='.json',
            filetypes=[('Branch QA report', '*.json')])
        if not path:
            return
        from pathlib import Path
        Path(path).write_text(
            json.dumps(self.qa_last_report, indent=2,
                       ensure_ascii=False, sort_keys=True)+'\n',
            encoding='utf-8')
