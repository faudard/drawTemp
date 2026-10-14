"""Scale controls for the existing StoryGraphEditor, never a second editor."""
from .story_graph_scale import (
    trace_occurrence, compare_occurrences, grouped_branches,
    grouped_collapse_paths, format_path_comparison)


class StoryGraphScaleControls:
    def _scale_setup(self):
        tk, ttk = self.tk, self.ttk
        self.scale_density = tk.StringVar(value='Normal')
        self.scale_is_grouped = False
        self.scale_previous_collapsed = set()
        self.scale_path_a = None
        self.scale_path_b = None
        parent = self.visual_details
        # Use the existing inspector, not an additional heavyweight tab.
        self.info.configure(height=8)
        ttk.Separator(parent, orient='horizontal').pack(
            fill='x', padx=8, pady=(5, 4))
        ttk.Label(parent, text='Parcours complexes · disposition et comparaison',
                  wraplength=290).pack(anchor='w', padx=8)
        density = ttk.Frame(parent)
        density.pack(fill='x', padx=8, pady=3)
        ttk.Label(density, text='Disposition').pack(side='left')
        box = ttk.Combobox(
            density, textvariable=self.scale_density,
            values=['Normal', 'Compact'], state='readonly', width=12)
        box.pack(side='left', padx=6)
        box.bind('<<ComboboxSelected>>', lambda event: self.draw())
        row = ttk.Frame(parent)
        row.pack(fill='x', padx=5, pady=2)
        self._button(row, 'Regrouper', self._scale_toggle_groups)
        self._button(row, 'Déployer tout', self._scale_expand_all)
        row = ttk.Frame(parent)
        row.pack(fill='x', padx=5, pady=2)
        self._button(row, 'Marquer A', lambda: self._scale_mark('a'))
        self._button(row, 'Marquer B', lambda: self._scale_mark('b'))
        row = ttk.Frame(parent)
        row.pack(fill='x', padx=5, pady=2)
        self._button(row, 'Comparer A / B', self._scale_compare)
        self._button(row, 'Effacer A / B', self._scale_clear)
        self.scale_text = tk.Text(
            parent, height=9, width=34, wrap='word',
            state='disabled', relief='flat', background='#f8fafc')
        self.scale_text.pack(fill='both', expand=True, padx=8, pady=(2, 5))
        self._scale_report([])

    def _scale_report(self, lines):
        self.scale_text.configure(state='normal')
        self.scale_text.delete('1.0', 'end')
        self.scale_text.insert('1.0', '\n'.join(lines))
        self.scale_text.configure(state='disabled')

    def _scale_reset(self):
        self.scale_is_grouped = False
        self.scale_previous_collapsed = set()
        self.scale_path_a = None
        self.scale_path_b = None

    def _scale_mark(self, which):
        from .model import require
        require(self.selected_path and self.current_root,
                'Sélectionner un nœud narratif pour ce parcours')
        trace_occurrence(self.owner.project.story,
                         self.current_root, self.selected_path)
        if which == 'a':
            self.scale_path_a = tuple(self.selected_path)
        else:
            self.scale_path_b = tuple(self.selected_path)
        self.draw()
        self.status.set('Parcours ' + which.upper() +
                        ' sélectionné : choisir une autre occurrence puis comparer.')

    def _scale_compare(self):
        from .model import require
        require(self.scale_path_a is not None and
                self.scale_path_b is not None,
                'Marquer deux occurrences A et B avant comparaison')
        report = compare_occurrences(
            self.owner.project.story, self.owner.doc().data,
            self._visual_mission_id(), self.current_root,
            self.scale_path_a, self.scale_path_b)
        self._scale_report(format_path_comparison(report))
        self.status.set(
            'Parcours comparés · bleu = A, orange = B, violet = commun.')

    def _scale_clear(self):
        self.scale_path_a = None
        self.scale_path_b = None
        self.draw()

    def _scale_toggle_groups(self):
        if not self.current_root:
            return
        if self.scale_is_grouped:
            self.collapsed = self.scale_previous_collapsed
            self.scale_previous_collapsed = set()
            self.scale_is_grouped = False
        else:
            self.scale_previous_collapsed = set(self.collapsed)
            self.collapsed = grouped_collapse_paths(
                self.owner.project.story, self.current_root,
                at_depth=1)
            self.scale_is_grouped = True
        self.draw()

    def _scale_expand_all(self):
        self.collapsed.clear()
        self.scale_is_grouped = False
        self.scale_previous_collapsed = set()
        self.draw()

    def _scale_style(self, path):
        """Temporary overlay for routes, leaving canonical node styles intact."""
        a = self.scale_path_a
        b = self.scale_path_b
        a_hit = a is not None and path == a[:len(path)]
        b_hit = b is not None and path == b[:len(path)]
        if a_hit and b_hit:
            return '#ddd6fe'
        if a_hit:
            return '#bfdbfe'
        if b_hit:
            return '#fed7aa'
        return None

    def _scale_summary(self):
        if not self.current_root or self.scale_path_a or self.scale_path_b:
            return
        groups = grouped_branches(
            self.owner.project.story, self.current_root,
            self.owner.doc().data, self._visual_mission_id(),
            max_depth=32, max_visits=1500)
        lines = ['SOUS-BRANCHES — ' + self.current_root]
        for group in groups:
            lines.append(
                group['label'] + ' : ' +
                str(group['scene_count']) + ' scènes · ' +
                str(group['ending_count']) + ' fins · ' +
                str(len(group['event_ids'])) + ' événements' +
                (' · LIMITÉ' if group['truncated'] else ''))
        if not groups:
            lines.append('Aucun choix à cette racine.')
        self._scale_report(lines)

    def _scale_after_draw(self):
        if self.scale_path_a and self.scale_path_a[0] != self.current_root:
            self.scale_path_a = None
        if self.scale_path_b and self.scale_path_b[0] != self.current_root:
            self.scale_path_b = None
        if self.scale_path_a and self.scale_path_b:
            self._scale_compare_report_only()
        elif self.scale_path_a or self.scale_path_b:
            marks = ('A : '+str(self.scale_path_a) if self.scale_path_a
                     else 'A : non sélectionné')
            marks_b = ('B : '+str(self.scale_path_b) if self.scale_path_b
                       else 'B : non sélectionné')
            self._scale_report(['COMPARAISON DE PARCOURS', marks, marks_b])
        else:
            self._scale_summary()

    def _scale_compare_report_only(self):
        try:
            result = compare_occurrences(
                self.owner.project.story, self.owner.doc().data,
                self._visual_mission_id(), self.current_root,
                self.scale_path_a, self.scale_path_b)
        except (ValueError, KeyError, TypeError):
            self.scale_path_a = None
            self.scale_path_b = None
            self._scale_summary()
        else:
            self._scale_report(format_path_comparison(result))
