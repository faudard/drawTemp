"""3.6.2 navigation bar within the existing StoryGraphEditor canvas tab.

All index results are read-only. A focus jumps to an actual occurrence or
re-roots to a canonical scene when the target is disconnected or too deep.
"""
from .story_graph_navigation import (
    navigation_diagnostics, search_narrative, shortest_occurrence)
from .model import require


class StoryGraphNavigationControls:
    FILTERS = {
        'Tout': 'all',
        'Scènes': 'scenes',
        'Choix': 'choices',
        'Conditions': 'conditions',
        'Événements': 'events',
        'Problèmes': 'issues',
    }

    def _navigation_setup(self):
        tk, ttk = self.tk, self.ttk
        self.nav_query = tk.StringVar(value='')
        self.nav_filter = tk.StringVar(value='Tout')
        self.nav_selection = tk.StringVar(value='')
        self.nav_rows = {}
        bar = self.nav_bar
        ttk.Label(bar, text='Rechercher :').pack(side='left')
        self.nav_search_entry = ttk.Entry(
            bar, textvariable=self.nav_query, width=24)
        self.nav_search_entry.pack(side='left', padx=(4, 6))
        self.nav_search_entry.bind(
            '<Return>', lambda _event: self.owner._run(self._navigation_find))
        self.nav_filter_box = ttk.Combobox(
            bar, textvariable=self.nav_filter, state='readonly',
            values=list(self.FILTERS), width=13)
        self.nav_filter_box.pack(side='left', padx=3)
        self.nav_filter_box.bind(
            '<<ComboboxSelected>>',
            lambda _event: self.owner._run(self._navigation_find))
        self._button(bar, 'Chercher', self._navigation_find)
        self._button(bar, 'Diagnostiquer', self._navigation_issues)
        self.nav_result_box = ttk.Combobox(
            bar, textvariable=self.nav_selection, state='readonly', width=31)
        self.nav_result_box.pack(side='left', padx=(8, 2),
                                 fill='x', expand=True)
        self.nav_result_box.bind(
            '<<ComboboxSelected>>',
            lambda _event: self.owner._run(self._navigation_go))
        self._button(bar, 'Centrer', self._navigation_go)
        self.nav_status = tk.StringVar(value='Recherche non exécutée.')
        self.ttk.Label(self.page, textvariable=self.nav_status,
                       wraplength=1000).pack(fill='x', padx=10, pady=2)

    def _navigation_find(self):
        kind = self.FILTERS[self.nav_filter.get()]
        report = search_narrative(
            self.owner.project.story, self.owner.doc().data,
            self._visual_mission_id(), self.nav_query.get(),
            kind=kind, max_results=180)
        diagnostics = navigation_diagnostics(self.owner.project.story)
        mapping = {}
        values = []
        for index, item in enumerate(report['results']):
            marker = {
                'scene': 'SCÈNE', 'choice': 'CHOIX',
                'event': 'ÉVÉNEMENT',
            }[item['kind']]
            status = ' · À vérifier' if item['status'] != 'reachable' and (
                item['kind'] != 'event') else ''
            label = ('%03d · %s · %s · %s%s' %
                     (index+1, marker, item['id'], item['label'][:34],
                      status))
            values.append(label)
            mapping[label] = item
        self.nav_rows = mapping
        self.nav_result_box['values'] = values
        self.nav_selection.set(values[0] if values else '')
        self.nav_status.set(
            '%d résultat(s)%s · %d scène(s) structurellement sans entrée · '
            '%d chemin(s) uniquement conditionnel(s)' %
            (report['matches'],
             ' (affichage limité)' if report['truncated'] else '',
             len(diagnostics['structurally_unreachable']),
             len(diagnostics['conditional_only'])))
        return report

    def _navigation_issues(self):
        self.nav_filter.set('Problèmes')
        self._navigation_find()

    def _navigation_center(self, cx, cy):
        canvas = self.canvas
        extents = canvas.cget('scrollregion').split()
        if len(extents) != 4:
            return
        x1, y1, x2, y2 = map(float, extents)
        canvas.update_idletasks()
        w = max(canvas.winfo_width(), 1)
        h = max(canvas.winfo_height(), 1)
        fx = ((cx-x1-w/2) / max(x2-x1-w, 1))
        fy = ((cy-y1-h/2) / max(y2-y1-h, 1))
        canvas.xview_moveto(max(0, min(1, fx)))
        canvas.yview_moveto(max(0, min(1, fy)))

    def _navigation_focus_scene(self, scene_id, choice_id=''):
        scene_ids = {s['id'] for s in self.owner.project.story['scenes']}
        require(scene_id in scene_ids, 'Selected scene no longer exists')
        if not self.current_root:
            self.refresh()
        path = shortest_occurrence(
            self.owner.project.story, self.current_root, scene_id)
        if path is None or len(path) > 25:
            # Unconnected authoring drafts and deep paths are still
            # navigable, without promoting them to gameplay entry scenes.
            key = 'Scène · ' + scene_id
            require(key in self.roots, 'Missing scene root')
            self.root_var.set(key)
            self._new_root()
            path = (scene_id,)
        if self.scale_is_grouped:
            self.scale_is_grouped = False
            self.scale_previous_collapsed = set()
        self.collapsed.difference_update(
            path[:size] for size in range(1, len(path)+1))
        self.selected_path = path
        self.selected_choice = choice_id
        self.selected_event = ''
        self.draw()
        if path not in self.layout['positions']:
            # Existing max_nodes bound can truncate a deep occurrence.
            key = 'Scène · ' + scene_id
            self.root_var.set(key)
            self._new_root()
            path = (scene_id,)
            self.selected_path = path
            self.draw()
        x, y = self._pos(path)
        self._navigation_center(x+105, y)

    def _navigation_focus_event(self, event_id):
        mission = self._visual_mission_id()
        require(any(e['id'] == event_id
                    for row in self.owner.doc().data['missions']
                    if row['id'] == mission
                    for e in row.get('triggers', ())),
                'Selected tactical event no longer exists')
        self.selected_event = event_id
        self.draw()
        card = next((row for row in self._visual_targets
                     if row['kind'] == 'event' and row['id'] == event_id), None)
        require(card is not None, 'Event missing from visual palette')
        x1, y1, x2, y2 = card['rect']
        self._navigation_center((x1+x2)/2, (y1+y2)/2)
        self._visual_details_event()

    def _navigation_go(self):
        row = self.nav_rows.get(self.nav_selection.get())
        require(row is not None, 'Choisir un résultat de recherche')
        if row['kind'] == 'event':
            self._navigation_focus_event(row['event_id'])
        else:
            self._navigation_focus_scene(row['scene_id'],
                                         row.get('choice_id', ''))
        self.nav_status.set('Centré sur ' + row['kind'] + ' : ' + row['id'])

    def _navigation_refresh_index(self):
        # Avoid redraws triggered by typing. Invalidate stale results after
        # project mutations/undo; the next explicit Find runs a fresh index.
        if self.nav_rows:
            self.nav_rows = {}
            self.nav_selection.set('')
            self.nav_result_box['values'] = []
            self.nav_status.set('Projet modifié : relancer la recherche.')
