"""Graphical AND/OR/NOT authoring for GameProject narrative choices.

A condition tree belongs to a canonical scene/choice. The Tk tree displays
ephemeral paths: repeated narrative occurrences still share one definition.
"""
from . import story_authoring
from .model import RuleError
from .story_conditions import (change_choice, evaluate, predicate, rows,
                               typed_value, update_expression)
from .story_graph import condition_label


class StoryConditionEditor:
    def __init__(self, editor, notebook):
        self.editor = editor
        self.owner = editor.owner
        self.tk, self.ttk = self.owner.tk, self.owner.ttk
        self.notebook = notebook
        self._refreshing = False
        self._paths = {}
        self._build(notebook)

    def _button(self, parent, label, callback):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.owner._run(callback)).pack(
                            side='left', padx=3, pady=3)

    def _build(self, notebook):
        ttk, tk = self.ttk, self.tk
        root = ttk.Frame(notebook)
        notebook.add(root, text='Conditions & variables')
        self.tab = root
        header = ttk.Frame(root)
        header.pack(fill='x', padx=8, pady=5)
        ttk.Label(header, text='Scène').pack(side='left')
        self.scene_var = tk.StringVar()
        self.scene_box = ttk.Combobox(header, textvariable=self.scene_var,
                                     state='readonly', width=23)
        self.scene_box.pack(side='left', padx=4)
        self.scene_box.bind('<<ComboboxSelected>>', lambda e: self._pick_scene())
        ttk.Label(header, text='Choix').pack(side='left')
        self.choice_var = tk.StringVar()
        self.choice_box = ttk.Combobox(header, textvariable=self.choice_var,
                                      state='readonly', width=23)
        self.choice_box.pack(side='left', padx=4)
        self.choice_box.bind('<<ComboboxSelected>>', lambda e: self._pick_choice())
        self._button(header, 'Voir dans le graphe', self.open_graph)

        center = ttk.Frame(root)
        center.pack(fill='both', expand=True, padx=9, pady=5)
        left = ttk.LabelFrame(center, text='Arbre de conditions (ET / OU / NON)')
        left.pack(side='left', fill='both', expand=True)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse', height=14)
        self.tree.pack(fill='both', expand=True, padx=7, pady=7)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._selected_changed())

        controls = ttk.LabelFrame(center, text='Composer la condition')
        controls.pack(side='right', fill='y', padx=(10, 0))
        ttk.Label(controls, text='Prédicat').pack(anchor='w', padx=8, pady=(6, 0))
        self.preset = tk.StringVar(value='flag =')
        self.preset_box = ttk.Combobox(
            controls, textvariable=self.preset, state='readonly', width=25,
            values=['flag =', 'flag ≥', 'flag ≤', 'mission terminée', 'or ≥'])
        self.preset_box.pack(fill='x', padx=8, pady=4)
        ttk.Label(controls, text='Variable / mission').pack(anchor='w', padx=8)
        self.key = tk.StringVar(value='trust')
        ttk.Entry(controls, textvariable=self.key, width=27).pack(fill='x', padx=8, pady=4)
        ttk.Label(controls, text='Valeur (true / false / entier / texte)').pack(
            anchor='w', padx=8)
        self.value = tk.StringVar(value='1')
        ttk.Entry(controls, textvariable=self.value, width=27).pack(fill='x', padx=8, pady=4)
        tools = ttk.Frame(controls)
        tools.pack(fill='x', padx=4, pady=6)
        self._button(tools, 'Remplacer / init.', self.replace)
        tools = ttk.Frame(controls)
        tools.pack(fill='x', padx=4)
        self._button(tools, '+ enfant', self.append)
        self._button(tools, 'Supprimer', self.delete)
        ttk.Label(controls, text='Encadrer la sélection :').pack(
            anchor='w', padx=8, pady=(8, 0))
        tools = ttk.Frame(controls)
        tools.pack(fill='x', padx=4)
        self._button(tools, 'ET', lambda: self.wrap('all'))
        self._button(tools, 'OU', lambda: self.wrap('any'))
        self._button(tools, 'NON', lambda: self.wrap('not'))
        ttk.Separator(controls, orient='horizontal').pack(fill='x', padx=8, pady=8)
        ttk.Label(controls, text='Créer directement un choix conditionnel').pack(
            anchor='w', padx=8)
        self.new_id = tk.StringVar(value='new_route')
        self.new_label = tk.StringVar(value='Nouvelle branche')
        ttk.Label(controls, text='Identifiant').pack(anchor='w', padx=8)
        ttk.Entry(controls, textvariable=self.new_id, width=27).pack(fill='x', padx=8)
        ttk.Label(controls, text='Libellé').pack(anchor='w', padx=8)
        ttk.Entry(controls, textvariable=self.new_label, width=27).pack(fill='x', padx=8)
        self._button(controls, 'Créer un choix + condition', self.create_choice)
        ttk.Separator(controls, orient='horizontal').pack(fill='x', padx=8, pady=8)

        ttk.Label(controls, text='Prévisualiser la visibilité (non sauvegardé)').pack(
            anchor='w', padx=8)
        self.preview_flags = tk.StringVar(value='trust=2')
        self.preview_gold = tk.StringVar(value='0')
        self.preview_completed = tk.StringVar()
        ttk.Label(controls, text='Variables : clef=valeur, séparées par ;').pack(
            anchor='w', padx=8)
        ttk.Entry(controls, textvariable=self.preview_flags, width=27).pack(
            fill='x', padx=8, pady=3)
        ttk.Label(controls, text='Or').pack(anchor='w', padx=8)
        ttk.Entry(controls, textvariable=self.preview_gold, width=27).pack(
            fill='x', padx=8, pady=3)
        ttk.Label(controls, text='Missions terminées (IDs, ; séparées)').pack(
            anchor='w', padx=8)
        ttk.Entry(controls, textvariable=self.preview_completed, width=27).pack(
            fill='x', padx=8, pady=3)
        self._button(controls, 'Tester la condition', self.preview)
        self.status = tk.StringVar(value='Sélectionner une scène et un choix.')
        ttk.Label(root, textvariable=self.status, wraplength=1000).pack(
            fill='x', padx=10, pady=6)

    def _scene(self):
        sid = self.scene_var.get()
        return next((s for s in self.owner.project.story.get('scenes', [])
                     if s['id'] == sid), None)

    def _choice(self):
        scene = self._scene()
        if scene is None:
            raise RuleError('Sélectionner une scène')
        choice = next((c for c in scene['choices']
                       if c['id'] == self.choice_var.get()), None)
        if choice is None:
            raise RuleError('Sélectionner un choix')
        return choice

    def _expression(self):
        return self._choice().get('when')

    def _selected_path(self):
        selection = self.tree.selection()
        return self._paths.get(selection[0], ()) if selection else ()

    def _selected_changed(self):
        if self._refreshing:
            return
        selected = self.tree.selection()
        if not selected:
            return
        path = self._selected_path()
        row = next((r for r in rows(self._expression())
                    if r['path'] == path), None)
        if row is None:
            return
        node = row['expression']
        if 'flag' in node:
            k = next(k for k in ('eq', 'gte', 'lte') if k in node)
            self.preset.set({'eq': 'flag =', 'gte': 'flag ≥',
                             'lte': 'flag ≤'}[k])
            self.key.set(node['flag'])
            self.value.set(str(node[k]).lower() if type(node[k]) is bool
                           else str(node[k]))
        elif 'completed_mission' in node:
            self.preset.set('mission terminée')
            self.key.set(node['completed_mission'])
        elif 'gold_gte' in node:
            self.preset.set('or ≥')
            self.value.set(str(node['gold_gte']))

    def _draw(self):
        self._refreshing = True
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        tree_rows = rows(self._expression()) if self._scene() and self.choice_var.get() else []
        index = {}
        for n, node in enumerate(tree_rows):
            path = node['path']
            parent = index.get(path[:-1], '') if path else ''
            iid = 'p'+str(n)
            title = node['label'] if node['kind'] not in ('all', 'any', 'not') else {
                'all': 'ET (toutes les conditions)',
                'any': 'OU (au moins une condition)',
                'not': 'NON (inverser la condition)',
            }[node['kind']]
            self.tree.insert(parent, 'end', iid=iid, text=title, open=True)
            self._paths[iid] = path
            index[path] = iid
        if tree_rows:
            self.tree.selection_set('p0')
        self._refreshing = False
        self.status.set('Condition : '+condition_label(self._expression())
                        if tree_rows else 'Sélectionner un choix ou créer une scène.')

    def _pick_scene(self):
        if self._refreshing:
            return
        self.refresh(choice='')
        self._pick_choice()

    def _pick_choice(self):
        if self._refreshing:
            return
        self.editor.scene_id = self.scene_var.get()
        self.editor.choice_id = self.choice_var.get()
        self._draw()

    def refresh(self, *, scene=None, choice=None):
        if self.owner.project is None:
            return
        scenes = self.owner.project.story.get('scenes', [])
        scene_ids = [s['id'] for s in scenes]
        previous_scene = self.scene_var.get()
        previous_choice = self.choice_var.get()
        self._refreshing = True
        self.scene_box['values'] = scene_ids
        target_scene = scene if scene is not None else (
            previous_scene if previous_scene in scene_ids else
            self.editor.scene_id if self.editor.scene_id in scene_ids else
            scene_ids[0] if scene_ids else '')
        self.scene_var.set(target_scene)
        selected_scene = next((s for s in scenes if s['id'] == target_scene), None)
        choice_ids = [c['id'] for c in selected_scene['choices']] if selected_scene else []
        self.choice_box['values'] = choice_ids
        preferred = choice if choice is not None else (
            previous_choice if target_scene == previous_scene else self.editor.choice_id)
        self.choice_var.set(preferred if preferred in choice_ids else
                            choice_ids[0] if choice_ids else '')
        self._refreshing = False
        self._draw()

    def open_choice(self, scene_id, choice_id):
        """Navigate from the repeated-scene graph to canonical condition data."""
        self.refresh(scene=scene_id, choice=choice_id)
        self.notebook.select(self.tab)

    def open_graph(self):
        self.editor.graph.root_var.set('Scène · '+self.scene_var.get())
        self.editor.graph._new_root()
        self.notebook.select(self.editor.graph.page)

    def _leaf(self):
        kinds = {'flag =': 'flag_eq', 'flag ≥': 'flag_gte',
                 'flag ≤': 'flag_lte', 'mission terminée': 'completed_mission',
                 'or ≥': 'gold_gte'}
        return predicate(kinds[self.preset.get()], self.key.get(),
                         self.value.get(), content=self.owner._content())

    def _commit(self, expression):
        scene, choice = self.scene_var.get(), self.choice_var.get()
        self.editor._apply(lambda project, content: change_choice(
            project, content, scene, choice, expression))
        self.refresh(scene=scene, choice=choice)

    def replace(self):
        self._commit(update_expression(self._expression(), 'replace',
                                       path=self._selected_path(),
                                       leaf=self._leaf()))

    def append(self):
        self._commit(update_expression(self._expression(), 'append',
                                       path=self._selected_path(),
                                       leaf=self._leaf()))

    def wrap(self, operator):
        self._commit(update_expression(self._expression(), 'wrap',
                                       path=self._selected_path(),
                                       operator=operator))

    def delete(self):
        self._commit(update_expression(self._expression(), 'delete',
                                       path=self._selected_path()))

    def create_choice(self):
        sid = self.scene_var.get()
        cid = self.new_id.get()
        spec = self._leaf()
        self.editor._apply(lambda project, content: story_authoring.add_choice(
            project, content, sid, cid, self.new_label.get(), when=spec))
        self.editor.scene_id = sid
        self.editor.choice_id = cid
        self.editor.refresh()
        self.refresh(scene=sid, choice=cid)

    def preview(self):
        flags = {}
        for fragment in self.preview_flags.get().split(';'):
            if not fragment.strip():
                continue
            if '=' not in fragment:
                raise RuleError('Variable attendue : clef=valeur')
            key, value = fragment.split('=', 1)
            key = key.strip()
            if not key or key in flags:
                raise RuleError('Variable de simulation invalide ou dupliquée')
            flags[key] = typed_value(value.strip())
        gold = int(self.preview_gold.get())
        missions = [s.strip() for s in self.preview_completed.get().split(';')
                    if s.strip()]
        result = evaluate(self._expression(), flags=flags,
                          gold=gold, completed=missions)
        self.status.set(('VISIBLE' if result else 'MASQUÉ')
                        + ' dans cette simulation ; sauvegarde non modifiée.')
        return result
