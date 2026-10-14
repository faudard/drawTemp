"""Tk Project Workspace: one entry point over the existing Studio documents.

Only this module creates widgets; the index and game engine remain headless.
"""
from .model import RuleError
from .workspace_editing import editable_form
from .workspace_navigation import (NavigationHistory, map_selection_key,
                                   navigation_target)
from .workspace_shell import (inspect_resource, inspect_map,
                              inspect_persistent_group, map_resource_target,
                              problem_delta)
from .studio_index4 import WorkspaceModelCache
from .performance_trace import begin_ui, finish_ui
from .game_export4 import export_game
from .studio_release_gate import verify_game_bundle
from .workspace import (GROUPS, ProjectWorkspaceIndex, create_blank_mission,
                        create_campaign, duplicate_mission)


class ProjectWorkspaceTab:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.notebook = notebook
        self.query = owner.tk.StringVar()
        self.sidebar_tree = None
        self.sidebar_search = None
        self._sidebar_mission = None
        self._model_cache = WorkspaceModelCache()
        self.problem_tree = None
        self.problem_targets = {}
        self.problem_snapshot = ()
        self.problem_count = None
        self._explicit_tile = ''
        self._form_signature = None
        self._form_fields = ()
        self._form_vars = {}
        self._form_key = ''
        self._form_baseline = ''
        self.navigation = NavigationHistory()
        self._map_tile_key = ''
        self.breadcrumb = owner.tk.StringVar(value='Projet')
        self._navigation_busy = False
        ttk = owner.ttk
        root = ttk.Frame(notebook)
        notebook.add(root, text='Espace projet')
        self.tab = root
        ttk.Label(root, text='Mon RPG — navigateur global (mêmes données que les éditeurs)',
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        ttk.Label(root, text='Créer et organiser les contenus sans maintenir un second manifeste. '
                  'Les éditeurs spécialisés restent la source des modifications.',
                  wraplength=950).pack(anchor='w', padx=12, pady=(0, 8))

        searchbar = ttk.Frame(root)
        searchbar.pack(fill='x', padx=12, pady=5)
        ttk.Label(searchbar, text='Rechercher :').pack(side='left')
        ttk.Entry(searchbar, textvariable=self.query).pack(
            side='left', fill='x', expand=True, padx=7)
        self.query.trace_add('write', lambda *_: self.refresh())
        navigation_bar = ttk.Frame(root)
        navigation_bar.pack(fill='x', padx=12, pady=(0, 3))
        ttk.Button(navigation_bar, text='← Précédent',
                   command=lambda: self.owner._run(
                       lambda: self.navigate_history(-1))).pack(side='left', padx=(0, 3))
        ttk.Button(navigation_bar, text='Suivant →',
                   command=lambda: self.owner._run(
                       lambda: self.navigate_history(1))).pack(side='left', padx=(0, 9))
        ttk.Label(navigation_bar, textvariable=self.breadcrumb,
                  wraplength=620).pack(side='left', fill='x', expand=True)
        body = ttk.Panedwindow(root, orient='horizontal')
        body.pack(fill='both', expand=True, padx=10, pady=6)
        tree_frame = ttk.Frame(body)
        detail_frame = ttk.Frame(body)
        body.add(tree_frame, weight=2)
        body.add(detail_frame, weight=3)
        self.tree = ttk.Treeview(tree_frame, show='tree', selectmode='browse')
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._select)
        self.tree.bind('<Double-1>', lambda _e: self.owner._run(self.open_selected))
        self.tree.bind('<Return>', lambda _e: self.owner._run(self.open_selected))

        ttk.Label(detail_frame, text='Inspecteur', font=('TkDefaultFont', 11, 'bold')).pack(
            anchor='w', padx=10, pady=8)
        self.heading = ttk.Label(detail_frame, text='Sélectionner un élément')
        self.heading.pack(anchor='w', padx=10)
        self.summary = ttk.Label(detail_frame, text='', justify='left',
                                 wraplength=470)
        self.summary.pack(anchor='w', padx=10, pady=8)
        self.edit_frame = ttk.LabelFrame(detail_frame, text='Propriétés éditables')
        self.edit_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(detail_frame, text='Inspecter la case sélectionnée',
                   command=lambda: self.owner._run(self.inspect_selected_tile)).pack(
                       anchor='w', padx=10, pady=(2, 6))
        ttk.Label(detail_frame, text='Références entrantes / sortantes').pack(
            anchor='w', padx=10)
        self.refs = owner.tk.Listbox(detail_frame, height=7, exportselection=False)
        self.refs.pack(fill='x', padx=10, pady=5)
        self.ref_keys = []
        self.refs.bind('<Double-1>', lambda _e: self.owner._run(self.open_reference))
        ttk.Button(detail_frame, text='Ouvrir dans le Studio',
                   command=lambda: self.owner._run(self.open_selected)).pack(
                       anchor='w', padx=10, pady=6)

        controls = ttk.LabelFrame(detail_frame, text='Création guidée')
        controls.pack(fill='x', padx=10, pady=10)
        ttk.Button(controls, text='Nouvelle carte / mission',
                   command=lambda: self.owner._run(self.new_mission)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Dupliquer la mission choisie',
                   command=lambda: self.owner._run(self.copy_mission)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Nouvelle campagne',
                   command=lambda: self.owner._run(self.new_campaign)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Assistant siège (3 missions)',
                   command=lambda: self.owner._run(self.open_siege_wizard)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Carte du monde',
                   command=lambda: self.owner.world_studio.show()).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Battle Lab · équilibrage',
                   command=lambda: self.notebook.select(self.owner.battle_lab.tab)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Balance Matrix · comparer des rencontres',
                   command=lambda: self.notebook.select(self.owner.balance_matrix.tab)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Visual Battle Lab · graphiques et replay',
                   command=lambda: self.notebook.select(self.owner.visual_battle_lab.tab)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Human Playtest Lab · durée et décisions réelles',
                   command=lambda: self.notebook.select(self.owner.playtest_studio.tab)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Vérifier projet et assets',
                   command=lambda: self.owner._run(self.validate_all)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Button(controls, text='Exporter le jeu en ZIP',
                   command=lambda: self.owner._run(self.export)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Label(detail_frame, text='Les cartes sont enregistrées avec le contenu; '
                  'le titre, les campagnes, dialogues et assets avec le fichier .game.json. '
                  'Utiliser « Enregistrer tout » pour publier les deux documents avec récupération.',
                  wraplength=470, justify='left').pack(anchor='w', padx=10, pady=6)
        self.status = ttk.Label(root, text='')
        self.status.pack(anchor='w', padx=12, pady=(2, 9))

    def attach_navigator(self, parent):
        """Embed the same resource index beside the live map, not a second model."""
        ttk = self.owner.ttk
        ttk.Label(parent, text='PROJET', font=('TkDefaultFont', 11, 'bold')).pack(
            anchor='w', padx=7, pady=(8, 3))
        ttk.Label(parent, text='Rechercher les ressources').pack(
            anchor='w', padx=7)
        search = ttk.Entry(parent, textvariable=self.query)
        self.sidebar_search = search
        search.pack(fill='x', padx=7, pady=(2, 6))
        search.bind('<Return>', lambda _event: self.owner._run(
            self.open_sidebar_selected))
        search.bind('<Escape>', lambda _event: self.query.set(''))
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=6, pady=4)
        self.sidebar_tree = ttk.Treeview(
            frame, show='tree', selectmode='browse', height=12)
        scroll = ttk.Scrollbar(
            frame, orient='vertical', command=self.sidebar_tree.yview)
        self.sidebar_tree.configure(yscrollcommand=scroll.set)
        self.sidebar_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.sidebar_tree.bind(
            '<Double-1>', lambda _event: self.owner._run(self.open_sidebar_selected))
        self.sidebar_tree.bind(
            '<Return>', lambda _event: self.owner._run(self.open_sidebar_selected))
        self.sidebar_count = ttk.Label(parent, text='')
        self.sidebar_count.pack(anchor='w', padx=7, pady=(0, 4))
        self.refresh()
        return self.sidebar_tree

    def open_sidebar_selected(self):
        """Use the existing Studio navigation/guards for sidebar entries."""
        if self.sidebar_tree is None:
            return
        selected = self.sidebar_tree.selection()
        if selected and not selected[0].startswith('group:'):
            self.open_key(selected[0])
            return
        # Enter from search should open the first visible hit when no tree
        # selection survives filtering, rather than silently doing nothing.
        for group in self.sidebar_tree.get_children(''):
            matches = self.sidebar_tree.get_children(group)
            if matches:
                self.open_key(matches[0])
                return

    def open_key(self, key, *, record=True):
        """Navigate by stable key and keep one shared map/Workspace selection."""
        self._explicit_tile = ''
        if self.query.get():
            self.query.set('')
        if not self.tree.exists(key):
            raise RuleError('Ressource introuvable : ' + key)
        self._map_tile_key = ''
        self._explicit_tile = ''
        self.tree.selection_set(key)
        self.tree.see(key)
        if record:
            self.navigation.record(key)
        self._select()
        self.open_selected()


    def index(self):
        return self.model().workspace

    def model(self):
        return self._model_cache.get(self.owner.doc().data, self.owner.project)

    def refresh(self):
        if self.owner.project is None:
            return
        ui_started = begin_ui()
        model = self.model()
        sections = model.sections
        shown = {node.key for node in model.search(self.query.get())}
        self._populate_tree(self.tree, sections, shown)
        if self.sidebar_tree is not None:
            self._populate_tree(self.sidebar_tree, sections, shown)
            self.sidebar_count.config(
                text=f'{len(shown)} résultat(s) • Entrée pour ouvrir')
            mission = 'mission:' + self.owner.mission()
            if mission != self._sidebar_mission:
                self._sidebar_mission = mission
                if self.sidebar_tree.exists(mission):
                    self.sidebar_tree.selection_set(mission)
                    self.sidebar_tree.see(mission)
        self._select()
        if self.problem_tree is not None:
            self._refresh_problems(model)
        self.status.config(text=f'{sum(len(items) for items in sections.values())} '
                                'ressources indexées — modifications non sauvegardées : '
                                f'{"oui" if self.owner.doc().dirty or self.owner.dirty() else "non"}')
        finish_ui("workspace.refresh", ui_started, self.tree, counts={
            "resource_nodes": len(model.nodes), "visible_nodes": len(shown),
            "reference_edges": len(model.references),
        })

    @staticmethod
    def _populate_tree(tree, sections, shown):
        # Painting a tile refreshes Studio. Rebuilding two complete Tk trees
        # on every brush stroke causes visible flicker and wasted Tcl calls.
        signature = tuple(
            (kind, tuple((node.key, node.label) for node in sections[kind]
                         if node.key in shown))
            for kind, _title in GROUPS)
        if getattr(tree, '_workspace_signature', None) == signature:
            return
        current = tree.selection()
        selected = current[0] if current else ''
        existing_groups = tree.get_children('')
        expanded = {key for key in existing_groups if tree.item(key, 'open')}
        initial = not existing_groups
        for key in existing_groups:
            tree.delete(key)
        for (kind, title), (_, entries) in zip(GROUPS, signature):
            parent = 'group:' + kind
            tree.insert('', 'end', iid=parent, text=f'{title} ({len(entries)})',
                        open=parent in expanded or initial)
            for key, label in entries:
                tree.insert(parent, 'end', iid=key, text=label)
        tree._workspace_signature = signature
        if selected and tree.exists(selected):
            tree.selection_set(selected)

    def _selected_node(self):
        selected = self.tree.selection()
        if not selected or selected[0].startswith('group:'):
            return None
        node = self.model().nodes.get(selected[0])
        if node is None:
            raise RuleError('Workspace item no longer exists: ' + selected[0])
        return node

    def _select(self, _event=None):
        # Clearing the Treeview selection for a tile also emits a Tk event.
        # Preserve the explicit tile until the user actually picks a resource.
        if _event is not None and self.tree.selection():
            self._explicit_tile = ''
        node = self._selected_node()
        if _event is not None and node is not None and not self._navigation_busy:
            self._map_tile_key = ''
            changed = self.navigation.record(node.key)
            if changed:
                self._preview_map_reference(node.key)
        snapshot = inspect_resource(node) if node else None
        if node is None and self._map_tile_key:
            mid, cell = navigation_target(self.owner.doc().data, self._map_tile_key)
            snapshot = inspect_map(self.owner.doc().data, mid, cell)
        if node is not None:
            target = map_resource_target(node.key, self.owner.doc().data)
            if target is not None:
                mid, cell, _kind, _eid = target
                snapshot = inspect_map(
                    self.owner.doc().data, mid, cell,
                    preferred_kind='actor' if node.kind == 'map_actor' else 'object',
                    preferred_id=node.id.split('/', 1)[1])
            elif node.kind == 'editor_group':
                mid, gid = node.id.split('/', 1)
                snapshot = inspect_persistent_group(
                    self.owner.doc().data, mid, gid)
        edit_key = node.key if node is not None else self._explicit_tile
        if self._explicit_tile and node is None:
            _, identifier = self._explicit_tile.split(':', 1)
            mid, xy = identifier.split('/', 1)
            if snapshot is None:
                title = 'CASE — ' + xy
                detail = 'Mission : ' + mid + ' | Édition des propriétés du terrain'
            else:
                title, detail = snapshot.title, snapshot.detail
        else:
            title = ((snapshot.title + ' [' + node.kind + ']') if snapshot
                     else 'Sélectionner une ressource')
            detail = (snapshot.detail if snapshot else
                      'Explorer campagnes, missions, scénarios et bibliothèques.')
        self.heading.config(text=title)
        self.summary.config(text=detail)
        self._render_editable(edit_key)
        if snapshot is not None:
            self.breadcrumb.set(
                'Projet / ' + (snapshot.mission_id or self.owner.mission()) +
                (' / ' + str(snapshot.cell) if snapshot.cell else '') +
                ' / ' + (node.label if node else snapshot.title))
        self.refs.delete(0, 'end')
        self.ref_keys = []
        if node is not None:
            model = self.model()
            for relation in model.outgoing(node.key):
                self.ref_keys.append(relation.target)
                self.refs.insert('end', '→ ' + relation.label + ' : ' + relation.target)
            for relation in model.incoming(node.key):
                self.ref_keys.append(relation.source)
                self.refs.insert('end', '← ' + relation.label + ' : ' + relation.source)

    def inspect_selected_tile(self):
        """Project the current map tile without introducing a saved node."""
        mid = self.owner.mission()
        cell = self.owner.selection()
        self._explicit_tile = f'map_tile:{mid}/{cell[0]},{cell[1]}'
        selected = self.tree.selection()
        if selected:
            self.tree.selection_remove(*selected)
        self._select()

    def _render_editable(self, key):
        if not key or not key.startswith(
                ('map_actor:', 'map_object:', 'editor_group:', 'map_tile:')):
            form = None
        else:
            form = editable_form(self.owner.doc().data, key)
        signature = ((form.key, form.baseline) if form else (None, None))
        if signature == self._form_signature:
            return
        self._form_signature = signature
        for widget in self.edit_frame.winfo_children():
            widget.destroy()
        self._form_fields = form.fields if form else ()
        self._form_key = form.key if form else ''
        self._form_baseline = form.baseline if form else ''
        self._form_vars = {}
        if form is None:
            self.owner.ttk.Label(
                self.edit_frame,
                text='Choisir un acteur, un objet, un groupe ou une case.',
                wraplength=420).pack(anchor='w', padx=7, pady=4)
            return
        tk, ttk = self.owner.tk, self.owner.ttk
        for field in form.fields:
            row = ttk.Frame(self.edit_frame)
            row.pack(fill='x', padx=7, pady=2)
            ttk.Label(row, text=field.label, width=21).pack(side='left')
            variable = (tk.BooleanVar(value=field.value) if
                        field.kind == 'boolean' else
                        tk.StringVar(value=str(field.value)))
            self._form_vars[field.name] = variable
            if field.kind == 'boolean':
                editor = ttk.Checkbutton(row, variable=variable)
            elif field.kind == 'choice':
                editor = ttk.Combobox(row, textvariable=variable,
                                      values=field.choices, state='readonly')
            else:
                editor = ttk.Entry(row, textvariable=variable)
            editor.pack(side='left', fill='x', expand=True)
        ttk.Button(self.edit_frame, text='Appliquer les propriétés',
                   command=lambda: self.owner._run(self.apply_properties)).pack(
                       anchor='e', padx=7, pady=5)

    def apply_properties(self):
        if not self._form_key or self.owner.workspace_edit is None:
            raise RuleError('Aucune ressource éditable sélectionnée.')
        changed = {}
        for field in self._form_fields:
            value = self._form_vars[field.name].get()
            before = field.value
            if (value if field.kind == 'boolean' else str(value)) != (
                    before if field.kind == 'boolean' else str(before)):
                changed[field.name] = value
        if not changed:
            self.status.config(text='Aucune propriété modifiée.')
            return
        # The form's baseline must still match the current resource.
        self.owner.workspace_edit(self._form_key, self._form_baseline, changed)
        self.status.config(text='Propriétés appliquées. Undo/Redo disponibles.')

    def _preview_map_reference(self, key):
        """Reveal selection in the live map without stealing the Workspace tab."""
        mid, cell = navigation_target(self.owner.doc().data, key)
        if mid is not None and key.startswith('editor_group:'):
            gid = key.split('/', 1)[1]
            self.owner.focus_map_cell(
                mid, cell or (0, 0), show_map=False, group_id=gid)
        elif mid is not None and cell is not None:
            self.owner.focus_map_cell(mid, cell, show_map=False)

    def sync_map_selection(self, mission_id, cell, *, cells=(), group_id=None,
                           record=True, key_override=None):
        """Map/group editor -> canonical Workspace tree and inspector."""
        key = key_override or map_selection_key(
            self.owner.doc().data, mission_id, cell,
            group_id=group_id, cells=cells)
        if key_override and navigation_target(self.owner.doc().data, key) != (
                mission_id, tuple(cell)):
            raise RuleError('Sélection historique différente de la carte')
        self._map_tile_key = key if key.startswith('map_tile:') else ''
        self._explicit_tile = self._map_tile_key
        if record:
            self.navigation.record(key)
        self._navigation_busy = True
        try:
            if self.tree.exists(key):
                self.tree.selection_set(key)
                self.tree.see(key)
            else:
                previous = self.tree.selection()
                if previous:
                    self.tree.selection_remove(*previous)
            if self.sidebar_tree is not None and self.sidebar_tree.exists(key):
                self.sidebar_tree.selection_set(key)
                self.sidebar_tree.see(key)
            self._select()
        finally:
            self._navigation_busy = False

    def navigate_history(self, direction):
        """Visit previous/next valid key; skip deleted resources automatically."""
        model = self.model()
        data = self.owner.doc().data
        def valid(key):
            try:
                if key not in model.nodes and not key.startswith('map_tile:'):
                    return False
                navigation_target(data, key)
                return True
            except (RuleError, ValueError, KeyError):
                return False
        key = self.navigation.traverse(direction, valid)
        if not key:
            self.status.config(text='Aucun autre emplacement dans l’historique.')
            return False
        if key.startswith('map_tile:'):
            mid, cell = navigation_target(data, key)
            self.owner.focus_map_cell(mid, cell)
            self.sync_map_selection(mid, cell, record=False,
                                    key_override=key)
        else:
            self.open_key(key, record=False)
        return True

    def clear_navigation(self):
        """Open a different project without retaining cross-project identity."""
        self.navigation.reset()
        self._map_tile_key = ''
        self._explicit_tile = ''
        self.breadcrumb.set('Projet')

    def open_reference(self):
        selected = self.refs.curselection()
        if not selected:
            return
        target = self.ref_keys[selected[0]]
        self.open_key(target)

    def _show_tab(self, title):
        for tab in self.notebook.tabs():
            if self.notebook.tab(tab, 'text') == title:
                self.notebook.select(tab)
                return True
        return False

    def open_selected(self):
        node = self._selected_node()
        if node is None:
            raise RuleError('Sélectionnez une ressource, pas une catégorie.')
        if node.kind in ('map_actor', 'map_object'):
            mid, cell, kind, identifier = map_resource_target(
                node.key, self.owner.doc().data)
            self.owner.focus_map_cell(mid, cell)
            self._show_tab('Carte et combat')
        elif node.kind == 'editor_group':
            mid, gid = node.id.split('/', 1)
            snapshot = inspect_persistent_group(self.owner.doc().data, mid, gid)
            self.owner.focus_map_cell(mid, snapshot.cell or (0, 0),
                                      group_id=gid)
            self._show_tab('Carte et combat')
        elif node.kind == 'mission':
            self.owner.select_mission(node.id)
            self._show_tab('Carte et combat')
        elif node.kind == 'campaign':
            if (node.id != self.owner.campaign_id.get() and
                    self.owner._pending_fields()):
                raise RuleError('Appliquer la configuration en cours avant de changer de campagne.')
            self.owner.campaign_id.set(node.id)
            self.owner._show_campaign()
            self._show_tab('Jeu, campagnes et sauvegardes')
        elif node.kind == 'siege':
            self.owner.siege_studio.siege_id.set(node.id)
            self.owner.siege_studio.refresh()
            self._show_tab('Campagne & siège')
        elif node.kind == 'scene':
            self.owner.story_editor.scene_id = node.id
            self.owner.story_editor.refresh()
            self._show_tab('Scénario & dialogues')
        elif node.kind == 'strategic_event':
            siege_id, event_id = node.id.split('/', 1)
            studio = self.owner.siege_studio
            studio.siege_id.set(siege_id)
            studio.refresh()
            studio.pages.select(studio.strategic_page)
            studio.strategic_editor.nodes.selection_set(event_id)
            studio.strategic_editor._select_node()
            self._show_tab('Campagne & siège')
        elif node.kind == 'cinematic':
            self.owner.cinematic_studio.clip_id = node.id
            self.owner.cinematic_studio.refresh()
            self._show_tab('Cinématiques')
        elif node.kind == 'actor':
            self._show_tab('Bibliothèque d’acteurs')
        elif node.kind == 'game':
            self._show_tab('Jeu, campagnes et sauvegardes')
        else:
            self.status.config(text='Ressource inspectable ici. Édition guidée prévue '
                               'dans les chantiers 2.5.2 et 2.5.3.')

    def attach_problems(self, notebook):
        """Diagnostics on the live model; no duplicated document or refresh button."""
        ttk = self.owner.ttk
        area = ttk.Frame(notebook)
        notebook.add(area, text='Problèmes')
        top = ttk.Frame(area)
        top.pack(fill='x', padx=6, pady=3)
        self.problem_count = ttk.Label(top, text='Diagnostics')
        self.problem_count.pack(side='left')
        ttk.Button(top, text='Aller à la ressource',
                   command=lambda: self.owner._run(self.open_problem)).pack(
                       side='right', padx=5)
        self.problem_tree = ttk.Treeview(
            area, columns=('severity', 'resource', 'message'),
            show='headings', selectmode='browse', height=6)
        for column, label, width in (
                ('severity', 'Niveau', 80),
                ('resource', 'Ressource', 190),
                ('message', 'Problème et correction', 490)):
            self.problem_tree.heading(column, text=label)
            self.problem_tree.column(column, width=width, stretch=column == 'message')
        scroll = ttk.Scrollbar(area, orient='vertical',
                               command=self.problem_tree.yview)
        self.problem_tree.configure(yscrollcommand=scroll.set)
        self.problem_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.problem_tree.bind(
            '<Double-1>', lambda _e: self.owner._run(self.open_problem))
        self.problem_tree.bind(
            '<Return>', lambda _e: self.owner._run(self.open_problem))
        self.problem_tab = area
        self.problem_notebook = notebook
        self.refresh()
        return area

    def _refresh_problems(self, model):
        root = self.owner.project_path.parent
        current = model.diagnostics(root, map_warnings=True)
        added, resolved = problem_delta(self.problem_snapshot, current)
        if not added and not resolved and self.problem_targets:
            return
        self.problem_snapshot = current
        selected = self.problem_tree.selection()
        selected_key = self.problem_targets.get(selected[0]) if selected else None
        for item in self.problem_tree.get_children(''):
            self.problem_tree.delete(item)
        self.problem_targets.clear()
        for number, (level, key, message) in enumerate(current):
            iid = 'diagnostic:' + str(number)
            self.problem_targets[iid] = key
            self.problem_tree.insert('', 'end', iid=iid,
                                     values=('Erreur' if level == 'error'
                                             else 'Avertissement', key, message))
            if key == selected_key:
                self.problem_tree.selection_set(iid)
        errors = sum(level == 'error' for level, _, _ in current)
        self.problem_count.config(
            text=f'{errors} erreur(s) · {len(current)-errors} avertissement(s)'
                 + (f' · {len(resolved)} corrigé(s)' if resolved else ''))

    def focus_problems(self):
        if self.problem_tree is not None:
            self.problem_notebook.select(self.problem_tab)
            self.problem_tree.focus_set()

    def open_problem(self):
        selected = self.problem_tree.selection() if self.problem_tree else ()
        if not selected:
            raise RuleError('Choisir un diagnostic dans la liste.')
        key = self.problem_targets[selected[0]]
        target = map_resource_target(key, self.owner.doc().data)
        if target is not None:
            mid, cell, _kind, _identifier = target
            self.owner.focus_map_cell(mid, cell)
            self._show_tab('Carte et combat')
        else:
            self.open_key(key)

    def new_mission(self):
        dialogs = self.owner.dialogs
        mid = dialogs.askstring('Nouvelle mission', 'Identifiant unique :')
        if mid is None:
            return
        name = dialogs.askstring('Nouvelle mission', 'Titre :', initialvalue=mid)
        if name is None:
            return
        # Explicit numbers with a safe fallback: the UI does not accept invalid input.
        width = self._dimension('Largeur')
        if width is None:
            return
        height = self._dimension('Hauteur')
        if height is None:
            return
        project = self.owner.project
        self.owner.design_change(lambda: self.owner.doc().replace(
            create_blank_mission(self.owner.doc().data, project,
                                 mid, name, width, height)))
        self.owner.select_mission(mid)
        self.refresh()
        self.tree.selection_set('mission:' + mid)
        self.tree.see('mission:' + mid)

    def _dimension(self, title):
        # StudioPanels' dialogs object is intentionally minimal.
        value = self.owner.dialogs.askstring('Dimensions de la carte', title + ' (4 à 128) :',
                                             initialvalue='8')
        if value is None:
            return None
        try:
            number = int(value)
        except ValueError as exc:
            raise RuleError('Les dimensions doivent être des entiers.') from exc
        if not 4 <= number <= 128:
            raise RuleError('Les dimensions doivent être entre 4 et 128.')
        return number

    def copy_mission(self):
        node = self._selected_node()
        if node is None or node.kind != 'mission':
            raise RuleError('Sélectionnez une mission à dupliquer.')
        mid = self.owner.dialogs.askstring('Dupliquer', 'Nouvel identifiant :')
        if mid is None:
            return
        name = self.owner.dialogs.askstring('Dupliquer', 'Nouveau titre :',
                                            initialvalue=mid)
        if name is None:
            return
        project = self.owner.project
        self.owner.design_change(lambda: self.owner.doc().replace(
            duplicate_mission(self.owner.doc().data, project,
                              node.id, mid, name)))
        self.owner.select_mission(mid)
        self.refresh()
        self.tree.selection_set('mission:' + mid)
        self.tree.see('mission:' + mid)

    def new_campaign(self):
        if self.owner._pending_fields():
            raise RuleError('Appliquer la configuration en cours avant de créer une campagne.')
        cid = self.owner.dialogs.askstring('Nouvelle campagne', 'Identifiant unique :')
        if cid is None:
            return
        name = self.owner.dialogs.askstring('Nouvelle campagne', 'Nom :',
                                            initialvalue=cid)
        if name is None:
            return
        self.owner.project = create_campaign(
            self.owner.project, self.owner._content(), cid, name, self.owner.mission())
        self.owner.campaign_id.set(cid)
        self.owner._show_campaign()
        self.owner.refresh()
        self.tree.selection_set('campaign:' + cid)
        self.tree.see('campaign:' + cid)

    def open_siege_wizard(self):
        siege = self.owner.siege_studio
        self.notebook.select(siege.tab)
        siege.pages.select(siege.flow_page)

    def validate_all(self):
        issues = self.model().diagnostics(
            self.owner.project_path.parent, map_warnings=True)
        errors = [i for i in issues if i[0] == 'error']
        warnings = [i for i in issues if i[0] != 'error']
        self.focus_problems()
        self.status.config(text=f'Diagnostics : {len(errors)} erreur(s), '
                                f'{len(warnings)} avertissement(s).')

    def export(self):
        if self.owner._pending_fields():
            raise RuleError('Appliquer les champs de configuration avant export.')
        filename = self.owner.dialogs.asksaveasfilename(
            defaultextension='.zip', initialfile='jeu-export.zip',
            filetypes=[('Archive de jeu ZIP', '*.zip')])
        if filename:
            output = export_game(self.owner._content(), self.owner.project,
                                 self.owner.project_path.parent, filename)
            report = verify_game_bundle(output)
            self.status.config(
                text=f'Export prêt : {output} — {report["campaigns"]} campagne(s), '
                     f'{report["missions"]} mission(s), sauvegarde/reprise vérifiée')
