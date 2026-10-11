"""Tk guided multi-front siege composition on top of the canonical editors."""
from .model import require
from .studio_siege_flow import (FRONTS, build_guided_siege,
                                prepare_deployment, readiness)


class SiegeFlowWizard:
    def __init__(self, siege, root):
        self.siege = siege
        self.owner = siege.owner
        self.tk, self.ttk = siege.tk, siege.ttk
        self.vars = {
            name: self.tk.StringVar(value=default)
            for name, default in {
                'id': 'castle_campaign', 'campaign': '',
                'walls': '', 'gate': '', 'throne': '',
                'reserves': '3', 'supplies': '6',
                'escorts': '1', 'capacity': '4',
                'lever': '', 'door': '',
            }.items()
        }
        self.change_start = self.tk.BooleanVar(value=False)
        self.inputs = {}
        self._build(root)

    def _field(self, parent, row, caption, name, *, values=None):
        self.ttk.Label(parent, text=caption).grid(
            row=row, column=0, sticky='w', padx=6, pady=4)
        if values is None:
            widget = self.ttk.Entry(parent, textvariable=self.vars[name], width=29)
        else:
            widget = self.ttk.Combobox(parent, textvariable=self.vars[name],
                                        values=values, state='readonly', width=27)
        widget.grid(row=row, column=1, sticky='ew', padx=6, pady=4)
        parent.columnconfigure(1, weight=1)
        self.inputs[name] = widget
        return widget

    def _button(self, parent, caption, callback):
        self.ttk.Button(parent, text=caption,
                        command=lambda: self.owner._run(callback)).pack(
                            side='left', padx=4, pady=5)

    def _build(self, root):
        ttk = self.ttk
        ttk.Label(root, text='Assistant de siège — 3 missions réelles, deux fronts '
                  'd’approche et une finale verrouillée',
                  font=('TkDefaultFont', 12, 'bold'), wraplength=900).pack(
                      anchor='w', padx=10, pady=8)
        ttk.Label(root, text='Composer un siège sans modifier les JSON. '
                  'Aucune victoire n’est inventée : les deux fronts doivent '
                  'être remportés en jeu avant la salle du trône.',
                  wraplength=900).pack(anchor='w', padx=10, pady=4)

        area = ttk.Frame(root)
        area.pack(fill='x', padx=8)
        left, right = ttk.LabelFrame(area, text='Campagne et cartes', padding=8), \
                      ttk.LabelFrame(area, text='Réserves et liaison tactique', padding=8)
        left.pack(side='left', fill='both', expand=True, padx=4)
        right.pack(side='left', fill='both', expand=True, padx=4)
        self._field(left, 0, 'Identifiant du siège', 'id')
        self._field(left, 1, 'Campagne parente', 'campaign', values=[])
        for row, (front, label) in enumerate((
                ('walls', '1 · Remparts'), ('gate', '2 · Porte'),
                ('throne', '3 · Salle du trône')), 2):
            selector = self._field(left, row, label, front, values=[])
            selector.bind('<<ComboboxSelected>>',
                          lambda _event, name=front: self._update_objects()
                          if name in ('walls', 'gate') else None)
        ttk.Checkbutton(left, text='Définir les remparts comme départ de campagne',
                        variable=self.change_start).grid(
                            row=5, column=0, columnspan=2, sticky='w', pady=6)

        for row, (key, label) in enumerate((
                ('reserves', 'Réservistes'),
                ('supplies', 'Provisions'),
                ('capacity', 'Capacité du convoi'),
                ('escorts', 'Escortes disponibles'))):
            self._field(right, row, label, key)
        self._field(right, 4, 'Levier des remparts (optionnel)',
                    'lever', values=[''])
        self._field(right, 5, 'Porte cible (optionnelle)',
                    'door', values=[''])
        ttk.Label(right, text='Pour ouvrir une porte à distance, choisir un '
                  'levier réel et une porte existante. La preuve est vérifiée '
                  'par le graphe stratégique #51.',
                  wraplength=360).grid(
                      row=6, column=0, columnspan=2, sticky='w', pady=4)

        bar = ttk.Frame(root)
        bar.pack(fill='x', padx=8, pady=6)
        self._button(bar, 'Vérifier préparation', self.preview)
        self._button(bar, 'Préparer déploiements', self.prepare)
        self._button(bar, 'Ouvrir carte', self.open_map)
        self._button(bar, 'Créer siège guidé', self.create)
        self._button(bar, 'Scénario et fins', lambda:
                     self.siege._open_tab('Scénario & dialogues'))
        self.report = self.tk.Text(root, height=11, wrap='word')
        self.report.pack(fill='both', expand=True, padx=12, pady=6)
        self.report.configure(state='disabled')

    def _selected(self):
        return tuple(self.vars[key].get() for key in FRONTS)

    def _numbers(self):
        return {name: int(self.vars[name].get())
                for name in ('reserves', 'supplies', 'capacity', 'escorts')}

    def _update_objects(self):
        content = self.owner._content()
        for front, key, kind in (
                ('walls', 'lever', 'switch'), ('gate', 'door', 'door')):
            mid = self.vars[front].get()
            values = ['']
            if mid in content.missions:
                values += sorted(obj['id'] for obj in content.missions[mid].objects
                                 if obj['kind'] == kind)
            self.inputs[key]['values'] = values
            if self.vars[key].get() not in values:
                self.vars[key].set('')

    def refresh(self):
        if self.owner.project is None:
            return
        campaigns = [c['id'] for c in self.owner.project.campaigns]
        missions = sorted(self.owner._content().missions)
        self.inputs['campaign']['values'] = campaigns
        if self.vars['campaign'].get() not in campaigns:
            self.vars['campaign'].set(campaigns[0] if campaigns else '')
        for front in FRONTS:
            self.inputs[front]['values'] = missions
        # Prefer the active mission for the approach, but never silently
        # change user-selected values on later editor refreshes.
        if self.vars['walls'].get() not in missions:
            active = self.owner.mission()
            self.vars['walls'].set(active if active in missions else
                                   (missions[0] if missions else ''))
        for index, front in enumerate(FRONTS[1:], 1):
            if self.vars[front].get() not in missions:
                available = [mid for mid in missions
                             if mid not in (self.vars[f].get() for f in FRONTS[:index])]
                self.vars[front].set(available[0] if available else '')
        self._update_objects()

    def _show(self, lines):
        self.report.configure(state='normal')
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', '\n'.join(lines))
        self.report.configure(state='disabled')

    def preview(self):
        content = self.owner._content()
        diagnostics = readiness(content, self._selected())
        # Test whole-project validation without touching either live document.
        project = build_guided_siege(
            self.owner.project, content, siege_id=self.vars['id'].get(),
            campaign_id=self.vars['campaign'].get(), missions=self._selected(),
            link_lever=self.vars['lever'].get(), link_door=self.vars['door'].get(),
            set_campaign_start=self.change_start.get(), **self._numbers())
        plan = next(s for s in project.sieges if s['id'] == self.vars['id'].get())
        lines = ['Validation de la configuration : OK',
                 'Campagne : ' + plan['campaign_id'],
                 'Fronts : ' + ', '.join(
                     front + ' → ' + mid for front, mid in plan['fronts'].items()),
                 'Finale : ' + plan['campaign']['final_front'],
                 'Pré-requis : remparts + porte remportés en combat',
                 'Routes : ' + str(len(plan['logistics']['routes'])),
                 'Événements stratégiques : ' +
                 str(len(plan.get('event_graph', [])))]
        lines += [level.upper() + ' [' + front + '] ' + message
                  for level, front, message in diagnostics]
        self._show(lines)

    def prepare(self):
        if self.owner._pending_fields():
            raise ValueError('Appliquer les champs de campagne avant le déploiement.')
        # Single undoable tactical Content change; project remains untouched.
        self.owner.design_change(lambda: self.owner.doc().replace(
            prepare_deployment(self.owner.doc().data, self.owner.project,
                               self._selected())))
        self.owner.refresh()
        self.preview()

    def open_map(self):
        mid = self.vars['walls'].get()
        require(mid in self.owner._content().missions, 'Choisir une mission de remparts.')
        self.owner.select_mission(mid)
        self.siege._open_tab('Carte et combat')

    def create(self):
        if self.owner._pending_fields():
            raise ValueError('Appliquer les champs de campagne avant de créer le siège.')
        candidate = build_guided_siege(
            self.owner.project, self.owner._content(),
            siege_id=self.vars['id'].get(), campaign_id=self.vars['campaign'].get(),
            missions=self._selected(), link_lever=self.vars['lever'].get(),
            link_door=self.vars['door'].get(),
            set_campaign_start=self.change_start.get(), **self._numbers())
        # Commit only after the entire candidate has been validated.
        self.owner.project = candidate
        self.siege.siege_id.set(self.vars['id'].get())
        if self.change_start.get() and self.owner.campaign_id.get() == self.vars['campaign'].get():
            self.owner._show_campaign()
        self.owner.refresh()
        self.siege.pages.select(self.siege.front_page)
        self.siege.status.set('Siège guidé prêt — sauvegarder le projet .game.json '
                              'et jouer dans Player.')
