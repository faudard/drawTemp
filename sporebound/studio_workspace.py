"""Tk Project Workspace: one entry point over the existing Studio documents.

Only this module creates widgets; the index and game engine remain headless.
"""
from .model import RuleError
from .workspace import (GROUPS, ProjectWorkspaceIndex, create_blank_mission,
                        create_campaign, duplicate_mission)


class ProjectWorkspaceTab:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.notebook = notebook
        ttk = owner.ttk
        root = ttk.Frame(notebook)
        notebook.add(root, text='Espace projet')
        self.tab = root
        ttk.Label(root, text='Mon RPG — navigateur global (mêmes données que les éditeurs)',
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        ttk.Label(root, text='Créer et organiser les contenus sans maintenir un second manifeste. '
                  'Les éditeurs spécialisés restent la source des modifications.',
                  wraplength=950).pack(anchor='w', padx=12, pady=(0, 8))

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

        ttk.Label(detail_frame, text='Inspecteur', font=('TkDefaultFont', 11, 'bold')).pack(
            anchor='w', padx=10, pady=8)
        self.heading = ttk.Label(detail_frame, text='Sélectionner un élément')
        self.heading.pack(anchor='w', padx=10)
        self.summary = ttk.Label(detail_frame, text='', justify='left',
                                 wraplength=470)
        self.summary.pack(anchor='w', padx=10, pady=8)
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
        ttk.Button(controls, text='Vérifier projet et assets',
                   command=lambda: self.owner._run(self.validate_all)).pack(
                       fill='x', padx=8, pady=4)
        ttk.Label(detail_frame, text='Les cartes sont enregistrées avec le contenu; '
                  'le titre, les campagnes, dialogues et assets avec le fichier .game.json. '
                  'Les deux enregistrements restent distincts.',
                  wraplength=470, justify='left').pack(anchor='w', padx=10, pady=6)
        self.status = ttk.Label(root, text='')
        self.status.pack(anchor='w', padx=12, pady=(2, 9))

    def index(self):
        return ProjectWorkspaceIndex(self.owner._content(), self.owner.project)

    def refresh(self):
        if self.owner.project is None:
            return
        current = self.tree.selection()
        selected = current[0] if current else ''
        expanded = {key for key in self.tree.get_children('')
                    if self.tree.item(key, 'open')}
        for key in self.tree.get_children(''):
            self.tree.delete(key)
        sections = self.index().sections()
        for kind, title in GROUPS:
            parent = 'group:' + kind
            items = sections[kind]
            self.tree.insert('', 'end', iid=parent, text=f'{title} ({len(items)})',
                             open=parent in expanded or not expanded)
            for node in items:
                self.tree.insert(parent, 'end', iid=node.key, text=node.label)
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
        self._select()
        self.status.config(text=f'{sum(len(items) for items in sections.values())} '
                                'ressources indexées — modifications non sauvegardées : '
                                f'{"oui" if self.owner.doc().dirty or self.owner.dirty() else "non"}')

    def _selected_node(self):
        selected = self.tree.selection()
        if not selected or selected[0].startswith('group:'):
            return None
        return self.index().node(selected[0])

    def _select(self, _event=None):
        node = self._selected_node()
        self.heading.config(text=f'{node.label}  [{node.kind} / {node.id}]'
                            if node else 'Sélectionner une ressource')
        self.summary.config(text=node.summary if node else
                            'Explorer campagnes, missions, scénarios et bibliothèques.')

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
        if node.kind == 'mission':
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
        elif node.kind == 'actor':
            self._show_tab('Bibliothèque d’acteurs')
        elif node.kind == 'game':
            self._show_tab('Jeu, campagnes et sauvegardes')
        else:
            self.status.config(text='Ressource inspectable ici. Édition guidée prévue '
                               'dans les chantiers 2.5.2 et 2.5.3.')

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

    def validate_all(self):
        index = self.index()
        issues = index.asset_issues(self.owner.project_path.parent)
        if issues:
            self.owner.dialogs.showerror('Assets non valides',
                                         '\n'.join(f'{i["asset_id"]}: {i["message"]}'
                                                   for i in issues[:15]))
            self.status.config(text=f'{len(issues)} erreur(s) de fichiers assets.')
        else:
            self.status.config(text='Contenu, projet, références et fichiers assets : valides.')
