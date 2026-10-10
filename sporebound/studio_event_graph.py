"""Tk tactical event graph connected to the real trigger authoring contracts.

An event diagram is always a projection of Mission.triggers, not a second
event model. Clicking a node selects the canonical authored condition/action.
"""
from copy import deepcopy

from . import event_composer, event_graph
from .model import RuleError, require


class EventGraphStudio:
    def __init__(self, advanced, notebook):
        self.advanced = advanced
        self.owner = advanced.owner
        self.tk, self.ttk = self.owner.tk, self.owner.ttk
        self.notebook = notebook
        self.event_id = self.tk.StringVar()
        self.new_id = self.tk.StringVar(value='event_new')
        self.action_index = None
        self.cond_kind = self.tk.StringVar(value='tick')
        self.cond_value = self.tk.StringVar(value='10')
        self.cond_unit = self.tk.StringVar()
        self.cond_team = self.tk.StringVar(value='enemy')
        self.cond_pos = self.tk.StringVar(value='0,0')
        self.action_kind = self.tk.StringVar(value='message')
        self.action_text = self.tk.StringVar(value='Renforts !')
        self.action_amount = self.tk.StringVar(value='4')
        self.action_unit = self.tk.StringVar()
        self.action_status = self.tk.StringVar(value='haste')
        self.action_team = self.tk.StringVar(value='enemy')
        self.action_archetype = self.tk.StringVar()
        self.action_pos = self.tk.StringVar(value='0,0')
        self.action_lifetime = self.tk.StringVar()
        self.zoom = self.tk.StringVar(value='100%')
        self.status = self.tk.StringVar(value='Choisir ou créer un événement.')
        self._build(notebook)

    def _button(self, parent, label, callback):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.owner._run(callback)).pack(
                            side='left', padx=2, pady=2)

    def _field(self, root, row, label, variable, choices=None):
        ttk = self.ttk
        ttk.Label(root, text=label).grid(row=row, column=0, sticky='w',
                                        padx=5, pady=3)
        if choices is None:
            widget = ttk.Entry(root, textvariable=variable, width=23)
        else:
            widget = ttk.Combobox(root, textvariable=variable, width=21,
                                  values=choices, state='readonly')
        widget.grid(row=row, column=1, sticky='ew', padx=4, pady=3)
        root.columnconfigure(1, weight=1)
        return widget

    def _build(self, notebook):
        ttk, tk = self.ttk, self.tk
        tab = ttk.Frame(notebook)
        self.tab = tab
        notebook.add(tab, text='Graphe des événements')
        header = ttk.Frame(tab)
        header.pack(fill='x', padx=9, pady=5)
        ttk.Label(header, text='Mission active · événements').pack(side='left')
        self.event_box = ttk.Combobox(header, textvariable=self.event_id,
                                     state='readonly', width=25)
        self.event_box.pack(side='left', padx=5)
        self.event_box.bind('<<ComboboxSelected>>', lambda e: self.select_event())
        self._button(header, '↑ Priorité', lambda: self.reorder_event(-1))
        self._button(header, '↓ Priorité', lambda: self.reorder_event(1))
        self._button(header, 'Supprimer événement', self.delete_event)
        ttk.Label(header, text='Zoom').pack(side='left', padx=(12, 3))
        self.zoom_box = ttk.Combobox(header, textvariable=self.zoom,
                                    values=['70%', '100%', '130%'],
                                    width=6, state='readonly')
        self.zoom_box.pack(side='left')
        self.zoom_box.bind('<<ComboboxSelected>>', lambda e: self.draw())
        main = ttk.Frame(tab)
        main.pack(fill='both', expand=True, padx=8, pady=3)
        frame = ttk.Frame(main)
        frame.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(frame, bg='#f8fafc', highlightthickness=0)
        sx = ttk.Scrollbar(frame, orient='horizontal', command=self.canvas.xview)
        sy = ttk.Scrollbar(frame, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side='bottom', fill='x')
        sy.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        inspector = ttk.Frame(main, width=355)
        inspector.pack(side='right', fill='y', padx=(8, 0))
        inspector.pack_propagate(False)
        tabs = ttk.Notebook(inspector)
        tabs.pack(fill='both', expand=True)
        cond = ttk.Frame(tabs)
        tabs.add(cond, text='Condition')
        self._field(cond, 0, 'Type', self.cond_kind,
                    choices=['tick', 'enter', 'defeated', 'hp_below', 'wave_capacity'])
        self._field(cond, 1, 'Tick / % PV / limite', self.cond_value)
        self.cond_unit_box = self._field(cond, 2, 'Unité surveillée', self.cond_unit,
                                         choices=[])
        self._field(cond, 3, 'Camp (capacité)', self.cond_team,
                    choices=['enemy', 'player', 'neutral'])
        self._field(cond, 4, 'Position x,y', self.cond_pos)
        ttk.Button(cond, text='Position sélectionnée dans la carte',
                   command=lambda: self.cond_pos.set(
                       ','.join(map(str, self.owner.selection())))).grid(
                           row=5, column=0, columnspan=2, sticky='ew', padx=4, pady=5)
        ttk.Button(cond, text='Appliquer condition',
                   command=lambda: self.owner._run(self.save_condition)).grid(
                       row=6, column=0, columnspan=2, sticky='ew', padx=4, pady=5)
        ttk.Label(cond, text='Nouvel ID').grid(row=7, column=0, sticky='w', padx=5)
        ttk.Entry(cond, textvariable=self.new_id, width=24).grid(
            row=7, column=1, sticky='ew', padx=5)
        ttk.Button(cond, text='Créer événement',
                   command=lambda: self.owner._run(self.create_event)).grid(
                       row=8, column=0, columnspan=2, sticky='ew', padx=4, pady=4)
        ttk.Button(cond, text='Dupliquer événement simple',
                   command=lambda: self.owner._run(self.duplicate)).grid(
                       row=9, column=0, columnspan=2, sticky='ew', padx=4, pady=5)
        actions_tab = ttk.Frame(tabs)
        tabs.add(actions_tab, text='Actions')
        self.action_list = tk.Listbox(actions_tab, height=5, exportselection=False)
        self.action_list.pack(fill='x', padx=5, pady=4)
        self.action_list.bind('<<ListboxSelect>>', lambda e: self.select_action())
        form = ttk.Frame(actions_tab)
        form.pack(fill='both', expand=True)
        self._field(form, 0, 'Action', self.action_kind,
                    choices=['message', 'hazard', 'status', 'spawn',
                             'despawn', 'queue_wave', 'wave'])
        self._field(form, 1, 'Message / nom', self.action_text)
        self._field(form, 2, 'Puissance / durée / limite', self.action_amount)
        self.action_unit_box = self._field(form, 3, 'Unité / nouveau ID', self.action_unit)
        self._field(form, 4, 'Statut', self.action_status,
                    choices=['haste', 'poison', 'slow', 'protect', 'regen'])
        self.action_archetype_box = self._field(form, 5, 'Archétype', self.action_archetype,
                                                choices=[])
        self._field(form, 6, 'Camp renfort', self.action_team,
                    choices=['enemy', 'player'])
        self._field(form, 7, 'Position x,y', self.action_pos)
        self._field(form, 8, 'Durée de vie (optionnel)', self.action_lifetime)
        buttons = ttk.Frame(actions_tab)
        buttons.pack(fill='x', padx=4)
        self._button(buttons, 'Ajouter', self.add_action)
        self._button(buttons, 'Remplacer', self.replace_action)
        self._button(buttons, 'Supprimer', self.remove_action)
        buttons = ttk.Frame(actions_tab)
        buttons.pack(fill='x', padx=4)
        self._button(buttons, '↑', lambda: self.move_action(-1))
        self._button(buttons, '↓', lambda: self.move_action(1))
        self._button(buttons, 'Éditeur par blocs', self.open_blocks)
        wave_buttons = ttk.Frame(actions_tab)
        wave_buttons.pack(fill='x', padx=4, pady=2)
        self._button(wave_buttons, '+ acteur dans vague', self.add_wave_actor)
        self._button(wave_buttons, '− dernier acteur vague', self.remove_wave_actor)
        ttk.Label(tab, textvariable=self.status, wraplength=1030).pack(
            fill='x', padx=9, pady=5)

    def _mission(self):
        return next(m for m in self.owner.doc().data['missions']
                    if m['id'] == self.owner.mission())

    def _event(self):
        item = next((e for e in self._mission().get('triggers', [])
                     if e['id'] == self.event_id.get()), None)
        require(item is not None, 'Choisir un événement')
        return item

    def _edit(self, transform):
        self.advanced._edit(transform)
        self.refresh()

    def _pos(self, raw):
        parts = [part.strip() for part in raw.split(',')]
        require(len(parts) == 2, 'Position attendue : x,y')
        return [int(p) for p in parts]

    def _condition(self):
        kind = self.cond_kind.get()
        n = int(self.cond_value.get())
        return event_composer.condition(kind, tick=n, percent=n,
                                        max_alive=n, unit=self.cond_unit.get(),
                                        team=self.cond_team.get(),
                                        pos=self._pos(self.cond_pos.get()))

    def _action(self):
        kind = self.action_kind.get()
        lifetime = self.action_lifetime.get().strip()
        n = int(self.action_amount.get())
        return event_composer.action(
            kind, text=self.action_text.get(), name=self.action_text.get(),
            pos=self._pos(self.action_pos.get()), amount=n, duration=n,
            max_active=n, actor_id=self.action_unit.get(),
            unit=self.action_unit.get(), status=self.action_status.get(),
            archetype=self.action_archetype.get(),
            team=self.action_team.get(),
            lifetime=int(lifetime) if lifetime else None)

    def create_event(self):
        eid = self.new_id.get()
        spec = self._condition()
        self._edit(lambda doc: event_composer.save_event(
            doc, self.owner.mission(), eid, spec,
            [event_composer.action('message', text='Nouvel événement')]))
        self.event_id.set(eid)
        self.action_index = 0
        self.refresh()

    def save_condition(self):
        eid = self.event_id.get()
        spec = self._condition()
        self._event()  # Apply only to a selected existing event.
        self._edit(lambda doc: event_graph.update_condition(
            doc, self.owner.mission(), eid, spec))

    def delete_event(self):
        eid = self._event()['id']
        self._edit(lambda doc: event_graph.delete_event(
            doc, self.owner.mission(), eid))
        self.event_id.set('')
        self.refresh()

    def duplicate(self):
        event = self._event()
        dest = self.new_id.get()
        self._edit(lambda doc: event_graph.duplicate_event(
            doc, self.owner.mission(), event['id'], dest))
        self.event_id.set(dest)
        self.refresh()

    def reorder_event(self, direction):
        eid = self._event()['id']
        self._edit(lambda doc: event_graph.reorder_event(
            doc, self.owner.mission(), eid, direction))

    def _selected_index(self):
        require(self.action_index is not None and
                0 <= self.action_index < len(self._event()['actions']),
                'Sélectionner une action du graphe')
        return self.action_index

    def add_action(self):
        event = self._event()
        self._edit(lambda doc: event_graph.add_action(
            doc, self.owner.mission(), event['id'], self._action()))
        self.action_index = len(self._event()['actions']) - 1
        self.refresh()

    def replace_action(self):
        event = self._event()
        index = self._selected_index()
        self._edit(lambda doc: event_graph.update_action(
            doc, self.owner.mission(), event['id'], index, self._action()))

    def add_wave_actor(self):
        event = self._event()
        index = self._selected_index()
        current = event['actions'][index]
        require(current['kind'] in ('wave', 'queue_wave'),
                'Sélectionner une vague de renforts')
        require(self.action_kind.get() == current['kind'],
                'Conserver le type de la vague sélectionnée')
        actor = self._action()['actors'][0]
        self._edit(lambda doc: event_graph.append_wave_actor(
            doc, self.owner.mission(), event['id'], index, actor))

    def remove_wave_actor(self):
        event = self._event()
        index = self._selected_index()
        self._edit(lambda doc: event_graph.remove_wave_actor(
            doc, self.owner.mission(), event['id'], index))

    def remove_action(self):
        event = self._event()
        index = self._selected_index()
        self._edit(lambda doc: event_graph.remove_action(
            doc, self.owner.mission(), event['id'], index))
        self.action_index = None
        self.refresh()

    def move_action(self, direction):
        event = self._event()
        index = self._selected_index()
        self._edit(lambda doc: event_graph.reorder_action(
            doc, self.owner.mission(), event['id'], index, direction))
        self.action_index = index + direction
        self.refresh()

    def select_event(self):
        self.action_index = None
        self._load_event()
        self.draw()

    def _load_event(self):
        try:
            event = self._event()
        except RuleError:
            return
        self.cond_kind.set(event['condition'])
        self.cond_value.set(str(event.get('value', event.get('percent',
                               event.get('max_alive', 10)))))
        self.cond_unit.set(event.get('unit', ''))
        self.cond_team.set(event.get('team', 'enemy'))
        self.cond_pos.set(','.join(map(str, event.get('pos', self.owner.selection()))))
        self.action_list.delete(0, 'end')
        for i, action in enumerate(event['actions']):
            self.action_list.insert('end', f"{i+1}. {event_graph.action_title(action)}")
        if self.action_index is not None:
            if self.action_index < len(event['actions']):
                self.action_list.selection_set(self.action_index)
                self._load_action(event['actions'][self.action_index])
            else:
                self.action_index = None

    def _load_action(self, action):
        kind = action['kind']
        self.action_kind.set(kind)
        self.action_text.set(action.get('text',
                             action.get('actor', {}).get('name',
                             action.get('actors', [{}])[0].get('name', ''))))
        self.action_amount.set(str(action.get('amount', action.get('duration',
                                  action.get('max_active', 4)))))
        actor = (action.get('actor') or
                 next(iter(action.get('actors', [])), {}))
        self.action_unit.set(action.get('unit', actor.get('id', '')))
        self.action_status.set(action.get('status', 'haste'))
        self.action_archetype.set(actor.get('archetype', ''))
        self.action_team.set(actor.get('team', 'enemy'))
        self.action_pos.set(','.join(map(str, action.get('pos',
                               actor.get('pos', self.owner.selection())))))
        self.action_lifetime.set(str(action.get('lifetime', '')))

    def select_action(self):
        selected = self.action_list.curselection()
        if selected:
            self.action_index = selected[0]
            self._load_action(self._event()['actions'][self.action_index])
            self.draw()

    def open_blocks(self):
        # Keep one Content document: the pre-existing block composer reads it.
        event = self._event()
        self.advanced.event_id.set(event['id'])
        self.advanced._load_event()
        self.notebook.select(self.advanced.events_tab)

    def refresh(self):
        if self.owner.project is None:
            return
        events = self._mission().get('triggers', [])
        choices = [event['id'] for event in events]
        self.event_box['values'] = choices
        if self.event_id.get() not in choices:
            self.event_id.set(choices[0] if choices else '')
            self.action_index = None
        unit_ids = [u['id'] for u in self._mission()['units']]
        self.cond_unit_box['values'] = unit_ids
        self.action_archetype_box['values'] = sorted(
            self.owner.doc().data.get('archetypes', {}))
        self._load_event()
        self.draw()

    def draw(self):
        graph = event_graph.build_event_graph(
            self.owner.doc().data, self.owner.mission(),
            max_nodes=750, max_events=200)
        canvas = self.canvas
        canvas.delete('all')
        scale = int(self.zoom.get().rstrip('%'))/100
        width, height = int(200*scale), int(70*scale)
        nodes = {n['key']: n for n in graph['nodes']}
        for edge in graph['edges']:
            a, b = nodes[edge['source']], nodes[edge['target']]
            x1,y1 = int(a['x']*scale), int(a['y']*scale)
            x2,y2 = int(b['x']*scale), int(b['y']*scale)
            canvas.create_line(x1+width,y1,x2,y2,arrow='last',
                               fill='#64748b',width=2)
        for index, node in enumerate(graph['nodes']):
            x,y = int(node['x']*scale), int(node['y']*scale)
            selected = node['event_id'] == self.event_id.get()
            if node['kind'] == 'action':
                selected = selected and node['index'] == self.action_index
            fill = ('#bbf7d0' if node['kind'] == 'condition'
                    else '#dbeafe' if selected else '#f1f5f9')
            tag = 'event_node_'+str(index)
            canvas.create_rectangle(x,y-height//2,x+width,y+height//2,
                                    fill=fill,outline='#2563eb' if selected else '#94a3b8',
                                    width=3 if selected else 1,tags=(tag,))
            label = node['label']
            if node['kind'] == 'condition':
                label = f"{node['order']+1}. {node['event_id']}\nSI {label}"
            else:
                label = f"{node['index']+1}. {label}"
            canvas.create_text(x+width//2,y,text=label,
                               width=width-12,justify='center',
                               fill='#0f172a',tags=(tag,))
            canvas.tag_bind(tag, '<Button-1>',
                            lambda e,k=node['key']: self.select_node(k))
        canvas.configure(scrollregion=(
            0,0,max(600,int(graph['width']*scale)),
            max(250,int(graph['height']*scale))))
        self.status.set(
            f"Mission {self.owner.mission()} : {graph['drawn_events']}/"
            f"{graph['total_events']} événements, {len(graph['nodes'])} nœuds."
            + (' Graphe limité : réduire le nombre de déclencheurs visibles.'
               if graph['truncated'] else
               ' Clic sur une condition ou une action pour modifier le bloc.'))

    def select_node(self, key):
        self.event_id.set(key[0])
        self.action_index = key[2] if len(key) == 3 else None
        self._load_event()
        self.draw()
