"""Modeless visual palette using the editor's existing image loaders and tools."""
from .asset_palette import CATEGORIES, ENTRIES, PaletteEntry, search_entries
from .watercolor_catalog import WatercolorCatalog
from .asset_browser_state import (AssetBrowserState, FAMILIES, FAMILY_LABELS,
                                  BROWSER_SCOPES, collection_key, family_for)
from .tk_images import resize_photo
from .iso_building_atlas import BUILDING_FRAMES
from .iso_actor_atlas import actor_style
from types import SimpleNamespace


class AssetPalette:
    def __init__(self, parent, *, terrain, props, buildings, fortifications,
                 choose, cell_size, actors=None, entities=None, content=None,
                 mission=None, preferences_path=None):
        import tkinter as tk
        from tkinter import ttk
        self.window = tk.Toplevel(parent)
        self.window.title('Bibliothèque d’assets — Carte')
        self.window.geometry('1100x720')
        self.window.minsize(850, 580)
        self.window.transient(parent)
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.loaders = terrain, props, buildings, fortifications
        self.choose, self.cell_size = choose, cell_size
        self.actors, self.entities = actors, entities
        self.content, self.mission = content, mission
        self.watercolor = WatercolorCatalog()
        self.watercolor_entries = tuple(
            PaletteEntry('watercolor:' + item.id, item.title + ' · ' + item.group,
                         'Aquarelle', 'watercolor', item.id)
            for item in self.watercolor.entries)
        self.entries = {e.id: e for e in (*ENTRIES, *self.watercolor_entries)}
        self._preferences_path = preferences_path
        self.browser = AssetBrowserState.load(
            preferences_path() if callable(preferences_path) else preferences_path)
        self.browse_scope = tk.StringVar(self.window, value='all')
        self.images = {}
        self.group_variants = {}
        self._group_selected = None
        self._group_active_id = None
        self._group_option_lookup = {}
        self.turns = 0
        self.query = tk.StringVar(self.window)
        self.category = tk.StringVar(self.window, value='Tous')
        self.detail = tk.StringVar(self.window)
        self.count = tk.StringVar(self.window)
        self.scale = tk.IntVar(self.window, value=cell_size())
        self.entity_id = tk.StringVar(self.window)
        self.entity_name = tk.StringVar(self.window)
        self.entity_team = tk.StringVar(self.window, value='enemy')
        self.entity_facing = tk.StringVar(self.window, value='south')
        self.entity_pose = tk.StringVar(self.window, value='idle')
        self.watercolor_frame = tk.StringVar(self.window, value='0')
        self.watercolor_variant = tk.StringVar(self.window)
        self._watercolor_timer = None
        self.entity_link = tk.StringVar(self.window)
        self.entity_destination = tk.StringVar(self.window)
        controls = ttk.Frame(self.window, padding=8)
        controls.pack(fill='x')
        ttk.Label(controls, text='Rechercher').pack(side='left')
        entry = ttk.Entry(controls, textvariable=self.query, width=28)
        entry.pack(side='left', padx=8)
        ttk.Combobox(controls, state='readonly', textvariable=self.category,
                     values=CATEGORIES + ('Aquarelle',), width=16).pack(side='left')
        ttk.Label(controls, textvariable=self.count).pack(side='right')
        body = ttk.Panedwindow(self.window, orient='horizontal')
        body.pack(fill='both', expand=True, padx=8)
        navigation, listing, preview = ttk.Frame(body), ttk.Frame(body), ttk.Frame(body)
        body.add(navigation, weight=0)
        body.add(listing, weight=1)
        body.add(preview, weight=2)
        ttk.Label(navigation, text='COLLECTIONS').pack(anchor='w', padx=6, pady=(8, 4))
        self.nav = ttk.Treeview(navigation, show='tree', height=11,
                                selectmode='browse')
        self.nav.column('#0', width=150, minwidth=130, stretch=False)
        nav_rows = (
            ('all', 'Tous les assets'),
            ('favorites', '☆ Favoris'),
            ('recents', '◷ Récents'),
        ) + FAMILIES
        for scope, label in nav_rows:
            self.nav.insert('', 'end', iid='browse:' + scope, text=label)
        self.nav.pack(fill='both', expand=True, padx=3)
        self.nav.selection_set('browse:all')
        self.nav.bind('<<TreeviewSelect>>', self.choose_collection)
        style = ttk.Style(self.window)
        style.configure('AssetPalette.Treeview', rowheight=48)
        self.tree = ttk.Treeview(listing, show='tree', selectmode='browse',
                                 style='AssetPalette.Treeview')
        self.tree.column('#0', width=280, minwidth=210)
        scroll = ttk.Scrollbar(listing, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        image_frame = ttk.Frame(preview)
        image_frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(image_frame, width=390, height=280,
                                background='#e5e0d4', highlightthickness=0)
        self.preview_image = None
        self._preview_item_id = None
        self.canvas.bind('<Configure>', self._center_preview)
        ys = ttk.Scrollbar(image_frame, orient='vertical', command=self.canvas.yview)
        ys.pack(side='right', fill='y')
        self.canvas.configure(yscrollcommand=ys.set)
        self.canvas.pack(fill='both', expand=True)
        xs = ttk.Scrollbar(preview, orient='horizontal', command=self.canvas.xview)
        xs.pack(fill='x')
        self.canvas.configure(xscrollcommand=xs.set)
        self.variant_controls = ttk.Frame(preview)
        ttk.Label(self.variant_controls, text='Pose / animation').pack(side='left')
        self.variant_selector = ttk.Combobox(
            self.variant_controls, textvariable=self.watercolor_variant,
            state='readonly', width=28)
        self.variant_selector.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.variant_selector.bind('<<ComboboxSelected>>', self.choose_group_variant)
        self.detail_label = ttk.Label(preview, textvariable=self.detail,
                                      wraplength=345, justify='left')
        self.detail_label.pack(fill='x', padx=8, pady=6)
        opts = ttk.Frame(preview)
        opts.pack(fill='x', padx=8)
        self.rotate_button = ttk.Button(opts, text='Rotation 90°', command=self.rotate)
        self.rotate_button.pack(side='left')
        ttk.Label(opts, text='Échelle').pack(side='left', padx=8)
        scale_box = ttk.Combobox(opts, state='readonly', textvariable=self.scale,
                                values=tuple(range(24, 97, 6)), width=4)
        scale_box.pack(side='left')
        scale_box.bind('<<ComboboxSelected>>', self.preview)
        self.watercolor_animation_controls = ttk.Frame(opts)
        ttk.Label(self.watercolor_animation_controls, text='Frame').pack(side='left')
        self.watercolor_frame_selector = ttk.Combobox(
            self.watercolor_animation_controls, state='readonly', width=4,
            textvariable=self.watercolor_frame)
        self.watercolor_frame_selector.pack(side='left', padx=5)
        self.watercolor_frame_selector.bind('<<ComboboxSelected>>', self.preview)
        ttk.Button(self.watercolor_animation_controls, text='▶', width=3,
                   command=self.play_watercolor).pack(side='left')
        ttk.Button(self.watercolor_animation_controls, text='■', width=3,
                   command=self.stop_watercolor).pack(side='left')
        ttk.Button(preview, text='Échelle de la carte', command=self.map_scale).pack(
            anchor='w', padx=8, pady=4)
        self.entity_frame = ttk.LabelFrame(preview, text='Placement — acteurs / objets')
        fields = (('ID (vide = automatique)', self.entity_id, None),
                  ('Nom de l’acteur', self.entity_name, None),
                  ('Équipe', self.entity_team, ('player', 'enemy')),
                  ('Orientation', self.entity_facing, ('south', 'north', 'east', 'west')),
                  ('Pose (aperçu)', self.entity_pose, ('idle', 'move')),
                  ('Porte liée (ID)', self.entity_link, None),
                  ('Sortie passage (x,y)', self.entity_destination, None))
        self.entity_rows = {}
        for label, variable, values in fields:
            row = ttk.Frame(self.entity_frame)
            row.pack(fill='x', padx=5, pady=1)
            ttk.Label(row, text=label, width=24).pack(side='left')
            widget = (ttk.Combobox(row, textvariable=variable,
                                   values=values or (), state='readonly', width=18)
                      if values or label == 'Porte liée (ID)'
                      else ttk.Entry(row, textvariable=variable, width=20))
            widget.pack(side='left', fill='x', expand=True)
            self.entity_rows[label] = row
        for variable in (self.entity_facing, self.entity_pose, self.entity_team):
            variable.trace_add('write', lambda *_: self.preview())
        self.favorite_button = ttk.Button(preview, text='☆ Ajouter aux favoris',
                                          command=self.toggle_favorite)
        self.favorite_button.pack(fill='x', padx=8, pady=(4, 0))
        self.use_button = ttk.Button(preview, text='Utiliser sur la carte', command=self.use)
        self.use_button.pack(fill='x', padx=8, pady=8)
        ttk.Label(self.window, text='Choisir → Utiliser → cliquer sur la carte. '
                  'Annuler/Rétablir restent disponibles dans l’éditeur.').pack(pady=8)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind('<Double-1>', lambda _e: self.use())
        self.tree.bind('<Return>', lambda _e: self.use())
        self.query.trace_add('write', self.populate)
        self.category.trace_add('write', self.populate)
        self.browse_scope.trace_add('write', self.populate)
        self.window.bind('<Control-d>', self.toggle_favorite)
        self.window.bind('<Control-f>', lambda _e: entry.focus_set())
        self.populate()
        entry.focus_set()

    def hide(self):
        self.stop_watercolor()
        self.window.withdraw()

    def show(self):
        self.populate()
        self.window.deiconify()
        self.window.lift()

    def sprite(self, entry, size, turns=0):
        terrain, props, buildings, fortifications = self.loaders
        if entry.kind == 'watercolor':
            item = self.watercolor.lookup(entry.value)
            frame_index = (int(self.watercolor_frame.get())
                           if item.kind == 'animation' else 0)
            sprite_id, duration = self.watercolor.frame(entry.value, frame_index)
            status, path = self.watercolor.status(sprite_id, verify=True)
            if status != 'ready':
                label = ('Fichier PNG absent : pack V3 à publier' if status == 'missing'
                         else 'Provenance SHA-256 absente : image non certifiée'
                         if status == 'uncertified'
                         else 'PNG modifié : provenance SHA-256 incorrecte')
                return None, label, 'assets/watercolor/' + sprite_id
            import tkinter as tk
            try:
                source = tk.PhotoImage(file=str(path), master=self.canvas)
                target_w = min(320, max(72, int(size) * 3))
                target_h = max(1, round(source.height() * target_w / source.width()))
                photo = resize_photo(source, target_w, target_h, master=self.canvas)
            except (OSError, RuntimeError, ValueError, tk.TclError):
                return None, 'PNG non décodable par Tk', str(path)
            elapsed = f' · durée {duration} ms' if duration else ''
            return photo, 'Sprite V3 vérifié (SHA-256)' + elapsed, path.name
        if entry.kind == 'surface':
            loader, photo = terrain, terrain.tile(entry.value, size)
        elif entry.kind == 'feature':
            loader, photo = props, props.sprite(entry.value, size)
        elif entry.kind == 'object':
            return None, 'Marqueur tactique vectoriel (aucun PNG requis)', 'Player/Studio'
        elif entry.kind == 'actor':
            if self.actors is None:
                return None, 'Sprite indisponible — secours vectoriel', 'Acteurs'
            style = self.actor_visual_style(entry)
            photo = self.actors.sprite(style, self.entity_facing.get(),
                                       int(self.entity_pose.get() == 'move'), size)
            loader = self.actors
        else:
            loader = buildings if (entry.value, 0) in BUILDING_FRAMES else fortifications
            photo = loader.sprite(entry.value, turns, size)
        if photo is not None:
            return photo, 'PNG disponible', loader.path.name
        reason = ('PNG absent' if not loader.path.is_file()
                  else 'PNG invalide ou non lisible par Tk')
        return None, reason + ' — rendu de secours sur la carte', loader.path.name

    def actor_visual_style(self, entry):
        if self.content is not None and self.mission is not None:
            data, mid = self.content(), self.mission()
            if entry.value.startswith('unit:'):
                mission = next((m for m in data['missions'] if m['id'] == mid), None)
                actor = next((u for u in mission['units']
                              if u['id'] == entry.value[5:]), None) if mission else None
                if actor:
                    return actor_style(SimpleNamespace(**actor))
            elif entry.value.startswith('archetype:'):
                key = entry.value[10:]
                actor = data.get('archetypes', {}).get(key, {})
                return actor_style(SimpleNamespace(id=key, name=key,
                                   team=self.entity_team.get(), **actor))
        return ('jeanne' if 'jeanne' in entry.value.lower() else
                'hero' if self.entity_team.get() == 'player' else 'guard')

    def asset_family(self, entry):
        group = (self.watercolor.lookup(entry.value).group
                 if entry.kind == 'watercolor' else '')
        return family_for(entry, watercolor_group=group)

    def asset_bookmark(self, entry):
        group = (self.watercolor.lookup(entry.value).group
                 if entry.kind == 'watercolor' else '')
        return collection_key(entry, watercolor_group=group)

    def choose_collection(self, _event=None):
        selected = self.nav.selection()
        if not selected:
            return
        value = selected[0].removeprefix('browse:')
        if value not in BROWSER_SCOPES:
            return
        if self.category.get() != 'Tous':
            self.category.set('Tous')
        self.browse_scope.set(value)

    def _refresh_nav(self):
        keys = set()
        families = {key: set() for key, _label in FAMILIES}
        for entry in self.entries.values():
            key = self.asset_bookmark(entry)
            keys.add(key)
            families[self.asset_family(entry)].add(key)
        labels = {'all': f'Tous les assets ({len(keys)})',
                  'favorites': f'☆ Favoris ({len(keys & self.browser.favorites)})',
                  'recents': f'◷ Récents ({len(keys & set(self.browser.recents))})'}
        labels.update({key: f'{name} ({len(families[key])})'
                       for key, name in FAMILIES})
        for key, title in labels.items():
            self.nav.item('browse:' + key, text=title)

    def _favorite_key(self):
        entry = self.selected()
        return self.asset_bookmark(entry) if entry is not None else None

    def _update_favorite_button(self):
        key = self._favorite_key()
        if key is None:
            self.favorite_button.configure(text='☆ Ajouter aux favoris')
            self.favorite_button.state(['disabled'])
        else:
            label = ('★ Retirer des favoris' if key in self.browser.favorites
                     else '☆ Ajouter aux favoris')
            self.favorite_button.configure(text=label)
            self.favorite_button.state(['!disabled'])

    def toggle_favorite(self, _event=None):
        key = self._favorite_key()
        if key is None:
            return
        try:
            self.browser.toggle_favorite(key)
        except (OSError, ValueError) as exc:
            from tkinter import messagebox
            messagebox.showerror('Favoris non enregistrés', str(exc),
                                 parent=self.window)
            return
        if self.browse_scope.get() == 'favorites':
            self.populate()
        else:
            self._refresh_nav()
            self._update_favorite_button()

    def populate(self, *_args):
        old = self.tree.selection()
        open_ids = set()
        def save_expanded(parent=''):
            for iid in self.tree.get_children(parent):
                if self.tree.item(iid, 'open'):
                    open_ids.add(iid)
                save_expanded(iid)
        save_expanded()
        first_population = not self.tree.get_children()
        self.tree.delete(*self.tree.get_children())
        self.images.clear()
        extra = tuple(self.entities() if self.entities is not None else ())
        extra += self.watercolor_entries
        self.entries = {e.id: e for e in (*ENTRIES, *extra)}
        scope = self.browse_scope.get()
        rows = tuple(entry for entry in search_entries(
            self.query.get(), self.category.get(), extra)
            if self.browser.contains(scope, self.asset_bookmark(entry),
                                     self.asset_family(entry)))
        if scope == 'recents':
            index = {key: i for i, key in enumerate(self.browser.recents)}
            rows = tuple(sorted(rows, key=lambda entry: index.get(
                self.asset_bookmark(entry), self.browser.MAX_RECENTS)))
        animated_frames = self.watercolor.animation_frame_ids()
        searching = bool(self.query.get().strip())
        compact = tuple(entry for entry in rows
                        if not (entry.kind == 'watercolor' and not searching
                                and self.watercolor.lookup(entry.value).kind == 'sprite'
                                and entry.value in animated_frames))
        # In the unfiltered "Tous" view, root rows are six meaningful
        # collections. The existing entry IDs remain the selectable leaves.
        by_family = scope == 'all' and self.category.get() == 'Tous' and not searching
        counts = {key: 0 for key, _label in FAMILIES}
        for entry in compact:
            counts[self.asset_family(entry)] += 1
        if by_family:
            for key, label in FAMILIES:
                if counts[key]:
                    self.tree.insert('', 'end', iid='group:' + key,
                                     text=f'{label} ({counts[key]})',
                                     open=('group:' + key in open_ids or
                                           first_population and key == 'terrain'))

        def parent_of(entry):
            return 'group:' + self.asset_family(entry) if by_family else ''

        grouped = {}
        for entry in compact:
            if entry.kind == 'watercolor':
                grouped.setdefault(self.watercolor.lookup(entry.value).group, []).append(entry)
                continue
            photo, _state, _path = self.sprite(
                entry, 8 if entry.kind == 'structure' else 22)
            options = {}
            if photo is not None:
                self.images[entry.id] = photo
                options['image'] = photo
            self.tree.insert(parent_of(entry), 'end', iid=entry.id,
                             text=entry.name + (' ⚠' if photo is None and
                                  entry.kind != 'object' else ''), **options)

        names = {'jeanne': 'Jeanne', 'wolf': 'Loup', 'spearman': 'Lancier',
                 'vfx': 'Effets visuels', 'props': 'Objets et décors',
                 'townfolk': 'Villageois', 'soldiers': 'Soldats',
                 'bestiary': 'Bestiaire', 'heroes': 'Héros'}
        self.group_variants = {}
        for group, entries in grouped.items():
            group_id = 'watercolor-group:' + group
            entries = sorted(entries, key=lambda e: (
                0 if self.watercolor.lookup(e.value).kind == 'animation' else 1,
                e.name.casefold()))
            animations = sum(self.watercolor.lookup(e.value).kind == 'animation'
                             for e in entries)
            poses = len(entries) - animations
            self.group_variants[group_id] = tuple(e.id for e in entries)
            label = f"{names.get(group, group.capitalize())}  ·  {animations} animations / {poses} poses"
            parent = parent_of(entries[0])
            self.tree.insert(parent, 'end', iid=group_id, text=label,
                             open=searching or group_id in open_ids)
            for entry in entries:
                item = self.watercolor.lookup(entry.value)
                suffix = (f" ({item.frame_count} images)"
                          if item.kind == 'animation' else '')
                sprite_id, _duration = self.watercolor.frame(entry.value)
                available, _path = self.watercolor.status(sprite_id)
                title = entry.value.removeprefix('anim_' + group + '_')
                title = title.removeprefix(group + '_').replace('_', ' ').capitalize()
                prefix = '▶ ' if item.kind == 'animation' else '• '
                self.tree.insert(group_id, 'end', iid=entry.id,
                                 text=prefix + title + suffix +
                                 (' ⚠ PNG absent' if available != 'ready' else ''))

        self.count.set(f'{len(rows)} / {len(self.entries)} assets'
                       + (f' · {len(grouped)} familles' if grouped else ''))
        self._refresh_nav()
        if compact and self.tree.get_children():
            previous = old[0] if old else None
            if previous is not None and self.tree.exists(previous):
                selected = previous
            elif previous and previous.startswith('watercolor:'):
                item = self.watercolor.lookup(previous[len('watercolor:'):])
                selected = 'watercolor-group:' + item.group
                if not self.tree.exists(selected):
                    selected = self.tree.get_children()[0]
            else:
                selected = self.tree.get_children()[0]
            if selected.startswith('group:'):
                # Prefer an actual preview rather than an inert category row.
                children = self.tree.get_children(selected)
                if children:
                    selected = children[0]
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.select()
        else:
            self._group_selected = None
            self.variant_controls.pack_forget()
            self.entity_frame.pack_forget()
            self.canvas.delete('all')
            self.preview_image = None
            self._preview_item_id = None
            self.detail.set('Aucun asset ne correspond à cette collection/recherche.')
            self.use_button.state(['disabled'])
            self.rotate_button.state(['disabled'])
            self._update_favorite_button()

    def choose_group_variant(self, _event=None):
        if self._group_selected is None:
            return
        selected_id = self._group_option_lookup.get(self.watercolor_variant.get())
        if selected_id is None:
            return
        self._group_active_id = selected_id
        self.stop_watercolor()
        self.watercolor_frame.set('0')
        self._configure_watercolor_controls(self.selected())
        self.preview()

    def _configure_watercolor_controls(self, entry):
        self.watercolor_animation_controls.pack_forget()
        if entry is not None and entry.kind == 'watercolor':
            item = self.watercolor.lookup(entry.value)
            if item.kind == 'animation':
                self.watercolor_frame_selector['values'] = tuple(
                    str(i) for i in range(item.frame_count))
                self.watercolor_animation_controls.pack(side='left', padx=8)

    def _center_preview(self, _event=None):
        if self._preview_item_id is None or self.preview_image is None:
            return
        width = max(self.canvas.winfo_width(), self.preview_image.width() + 24)
        height = max(self.canvas.winfo_height(), self.preview_image.height() + 24)
        self.canvas.coords(self._preview_item_id, width / 2, height / 2)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def stop_watercolor(self):
        if self._watercolor_timer is not None:
            self.window.after_cancel(self._watercolor_timer)
            self._watercolor_timer = None

    def _queue_watercolor_frame(self):
        entry = self.selected()
        if entry is None or entry.kind != 'watercolor':
            return
        item = self.watercolor.lookup(entry.value)
        if item.kind != 'animation':
            return
        idx = int(self.watercolor_frame.get())
        _id, duration = self.watercolor.frame(entry.value, idx)
        animation = self.watercolor.registry.require_reference(
            entry.value, 'animation')
        if idx + 1 == item.frame_count and not animation['loop']:
            return  # Hold the actual final frame of this one-shot animation.
        self._watercolor_timer = self.window.after(
            duration, self._advance_watercolor_frame)

    def _advance_watercolor_frame(self):
        self._watercolor_timer = None
        entry = self.selected()
        if entry is None or entry.kind != 'watercolor':
            return
        item = self.watercolor.lookup(entry.value)
        if item.kind != 'animation':
            return
        self.watercolor_frame.set(str(
            (int(self.watercolor_frame.get()) + 1) % item.frame_count))
        self.preview()
        self._queue_watercolor_frame()

    def play_watercolor(self):
        self.stop_watercolor()
        entry = self.selected()
        if entry is None or entry.kind != 'watercolor' or \
                self.watercolor.lookup(entry.value).kind != 'animation':
            return
        self.watercolor_frame.set('0')
        self.preview()
        self._queue_watercolor_frame()

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            return None
        key = selection[0]
        if key == self._group_selected and key in self.group_variants:
            return self.entries.get(self._group_active_id)
        return self.entries.get(key)

    def select(self, _event=None):
        self.turns = 0
        self.stop_watercolor()
        selection = self.tree.selection()
        key = selection[0] if selection else None
        if key in self.group_variants:
            values = self.group_variants[key]
            if key != self._group_selected or self._group_active_id not in values:
                # Choose idle first for a stable character preview; use the
                # first authored animation if no standalone idle exists.
                self._group_active_id = next(
                    (eid for eid in values if eid.endswith('_idle')), values[0])
            self._group_selected = key
            group = key.split(':', 1)[1]
            options = {}
            for eid in values:
                item = self.watercolor.lookup(self.entries[eid].value)
                label = item.id.removeprefix('anim_' + group + '_')
                label = label.removeprefix(group + '_').replace('_', ' ').capitalize()
                label = ('Animation · ' if item.kind == 'animation' else 'Pose · ') + label
                if item.kind == 'animation':
                    label += f' ({item.frame_count} images)'
                options[label] = eid
            self._group_option_lookup = options
            self.variant_selector['values'] = tuple(options)
            selected_label = next(label for label, eid in options.items()
                                  if eid == self._group_active_id)
            self.watercolor_variant.set(selected_label)
            self.variant_controls.pack(fill='x', padx=8, pady=(6, 0),
                                       before=self.detail_label)
        else:
            self._group_selected = None
            self._group_active_id = None
            self.variant_controls.pack_forget()

        entry = self.selected()
        self.watercolor_frame.set('0')
        self._configure_watercolor_controls(entry)
        if entry is not None:
            self.entity_id.set('')
            self.entity_destination.set('')
            if self.content is not None and self.mission is not None:
                data, mid = self.content(), self.mission()
                mission = next((m for m in data['missions'] if m['id'] == mid), None)
                doors = [o['id'] for o in mission['objects'] if o['kind'] == 'door'] if mission else []
                self.entity_rows['Porte liée (ID)'].winfo_children()[1]['values'] = doors
                self.entity_link.set(doors[0] if len(doors) == 1 else '')

            self.entity_name.set(entry.name.split(' (', 1)[0] if entry.kind == 'actor' else '')
            self.entity_pose.set('idle')
            if entry.kind == 'actor' and self.content is not None and self.mission is not None:
                data = self.content()
                mission = next((m for m in data['missions'] if m['id'] == self.mission()), None)
                source = next((u for u in mission['units'] if entry.value == 'unit:' + u['id']), None) if mission else None
                self.entity_team.set(source['team'] if source else 'enemy')
            if entry.kind in ('actor', 'object'):
                self.entity_frame.pack(fill='x', padx=8, pady=4, before=self.use_button)
                for label, row in self.entity_rows.items():
                    visible = (label.startswith('ID') or
                               (entry.kind == 'actor' and label in ('Nom de l’acteur', 'Équipe', 'Orientation', 'Pose (aperçu)')) or
                               (entry.kind == 'object' and label == 'Porte liée (ID)' and entry.value in ('switch', 'ram', 'catapult')) or
                               (entry.kind == 'object' and label == 'Sortie passage (x,y)' and entry.value == 'passage'))
                    if visible:
                        row.pack(fill='x', padx=5, pady=1)
                    else:
                        row.pack_forget()
            else:
                self.entity_frame.pack_forget()
        self.preview()

    def map_scale(self):
        self.scale.set(self.cell_size())
        self.preview()

    def rotate(self):
        self.turns = (self.turns + 1) % 4
        self.preview()

    def preview(self, _event=None):
        entry = self.selected()
        if entry is None:
            return
        self.use_button.state(['disabled'] if entry.kind == 'watercolor'
                              else ['!disabled'])
        self.rotate_button.state(['!disabled'] if entry.kind == 'structure' else ['disabled'])
        self.canvas.delete('all')
        self._preview_item_id = None
        photo, state, path = self.sprite(entry, self.scale.get(), self.turns)
        self.preview_image = photo
        if photo is not None:
            self._preview_item_id = self.canvas.create_image(
                0, 0, anchor='center', image=photo)
            self._center_preview()
        elif entry.kind == 'object':
            self.canvas.create_rectangle(80, 50, 220, 140, fill='#9264ab',
                                         outline='#3d2554', width=3)
            self.canvas.create_text(150, 95, text=entry.name,
                                    fill='white', font=('TkDefaultFont', 14, 'bold'))
            self.canvas.configure(scrollregion=(0, 0, 320, 180))
        else:
            self.canvas.create_text(20, 30, anchor='nw', text=state, width=330)
            self.canvas.configure(scrollregion=(0, 0, 360, 100))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        w, h = entry.footprint(self.turns)
        rotation = (f'\nRotation du terrain : {self.turns*90}° ; 2 vues PNG partagées.'
                    if entry.kind == 'structure' else '')
        effect = ('Illustration seule : non liée aux acteurs/objets du Player.'
                  if entry.kind == 'watercolor' else entry.effect)
        self.detail.set(f'{entry.name} — {entry.category}\n{entry.id}\n'
                        f'Emprise : {w} × {h} case(s) · {path}\n{state}'
                        f'{rotation}\n{effect}')

    def placement_settings(self):
        return dict(entity_id=self.entity_id.get().strip(),
                    name=self.entity_name.get().strip(),
                    team=self.entity_team.get(), facing=self.entity_facing.get(),
                    link=self.entity_link.get().strip(),
                    destination=self.entity_destination.get().strip())

    def use(self):
        entry = self.selected()
        if entry is None or entry.kind == 'watercolor':
            return
        if entry.kind == 'object':
            if entry.value in ('switch', 'ram', 'catapult') and not self.entity_link.get():
                self.detail.set('Créer d’abord une porte, puis choisir sa référence.')
                return
            if entry.value == 'passage':
                from .entity_placement import parse_destination
                try:
                    parse_destination(self.entity_destination.get())
                except ValueError as exc:
                    self.detail.set(str(exc))
                    return
        if self.choose(entry, self.turns):
            self.hide()
