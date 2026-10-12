"""Modeless visual palette using the editor's existing image loaders and tools."""
from .asset_palette import CATEGORIES, ENTRIES, search_entries
from .iso_building_atlas import BUILDING_FRAMES


class AssetPalette:
    def __init__(self, parent, *, terrain, props, buildings, fortifications,
                 choose, cell_size):
        import tkinter as tk
        from tkinter import ttk
        self.window = tk.Toplevel(parent)
        self.window.title('Bibliothèque d’assets — Carte')
        self.window.geometry('860x660')
        self.window.minsize(700, 540)
        self.window.transient(parent)
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.loaders = terrain, props, buildings, fortifications
        self.choose, self.cell_size = choose, cell_size
        self.entries = {e.id: e for e in ENTRIES}
        self.images = {}
        self.turns = 0
        self.query = tk.StringVar(self.window)
        self.category = tk.StringVar(self.window, value='Tous')
        self.detail = tk.StringVar(self.window)
        self.count = tk.StringVar(self.window)
        self.scale = tk.IntVar(self.window, value=cell_size())
        controls = ttk.Frame(self.window, padding=8)
        controls.pack(fill='x')
        ttk.Label(controls, text='Rechercher').pack(side='left')
        entry = ttk.Entry(controls, textvariable=self.query, width=28)
        entry.pack(side='left', padx=8)
        ttk.Combobox(controls, state='readonly', textvariable=self.category,
                     values=CATEGORIES, width=16).pack(side='left')
        ttk.Label(controls, textvariable=self.count).pack(side='right')
        body = ttk.Panedwindow(self.window, orient='horizontal')
        body.pack(fill='both', expand=True, padx=8)
        listing, preview = ttk.Frame(body), ttk.Frame(body)
        body.add(listing, weight=1)
        body.add(preview, weight=1)
        style = ttk.Style(self.window)
        style.configure('AssetPalette.Treeview', rowheight=64)
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
        ys = ttk.Scrollbar(image_frame, orient='vertical', command=self.canvas.yview)
        ys.pack(side='right', fill='y')
        self.canvas.configure(yscrollcommand=ys.set)
        self.canvas.pack(fill='both', expand=True)
        xs = ttk.Scrollbar(preview, orient='horizontal', command=self.canvas.xview)
        xs.pack(fill='x')
        self.canvas.configure(xscrollcommand=xs.set)
        ttk.Label(preview, textvariable=self.detail, wraplength=345,
                  justify='left').pack(fill='x', padx=8, pady=8)
        opts = ttk.Frame(preview)
        opts.pack(fill='x', padx=8)
        self.rotate_button = ttk.Button(opts, text='Rotation 90°', command=self.rotate)
        self.rotate_button.pack(side='left')
        ttk.Label(opts, text='Échelle').pack(side='left', padx=8)
        scale_box = ttk.Combobox(opts, state='readonly', textvariable=self.scale,
                                values=tuple(range(24, 97, 6)), width=4)
        scale_box.pack(side='left')
        scale_box.bind('<<ComboboxSelected>>', self.preview)
        ttk.Button(preview, text='Échelle de la carte', command=self.map_scale).pack(
            anchor='w', padx=8, pady=4)
        self.use_button = ttk.Button(preview, text='Utiliser sur la carte', command=self.use)
        self.use_button.pack(fill='x', padx=8, pady=8)
        ttk.Label(self.window, text='Choisir → Utiliser → cliquer sur la carte. '
                  'Annuler/Rétablir restent disponibles dans l’éditeur.').pack(pady=8)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind('<Double-1>', lambda _e: self.use())
        self.tree.bind('<Return>', lambda _e: self.use())
        self.query.trace_add('write', self.populate)
        self.category.trace_add('write', self.populate)
        self.populate()
        entry.focus_set()

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def sprite(self, entry, size, turns=0):
        terrain, props, buildings, fortifications = self.loaders
        if entry.kind == 'surface':
            loader, photo = terrain, terrain.tile(entry.value, size)
        elif entry.kind == 'feature':
            loader, photo = props, props.sprite(entry.value, size)
        else:
            loader = buildings if (entry.value, 0) in BUILDING_FRAMES else fortifications
            photo = loader.sprite(entry.value, turns, size)
        if photo is not None:
            return photo, 'PNG disponible', loader.path.name
        reason = ('PNG absent' if not loader.path.is_file()
                  else 'PNG invalide ou non lisible par Tk')
        return None, reason + ' — rendu de secours sur la carte', loader.path.name

    def populate(self, *_args):
        old = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        rows = search_entries(self.query.get(), self.category.get())
        for entry in rows:
            photo, state, _path = self.sprite(entry, 8 if entry.kind == 'structure' else 22)
            options = {}
            if photo is not None:
                self.images[entry.id] = photo
                options['image'] = photo
            self.tree.insert('', 'end', iid=entry.id,
                             text=entry.name + (' ⚠' if photo is None else ''), **options)
        self.count.set(f'{len(rows)} / {len(ENTRIES)}')
        if rows:
            selected = old[0] if old and any(e.id == old[0] for e in rows) else rows[0].id
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.select()
        else:
            self.canvas.delete('all')
            self.detail.set('Aucun asset ne correspond à la recherche.')
            self.use_button.state(['disabled'])
            self.rotate_button.state(['disabled'])

    def selected(self):
        selected = self.tree.selection()
        return self.entries[selected[0]] if selected else None

    def select(self, _event=None):
        self.turns = 0
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
        self.use_button.state(['!disabled'])
        self.rotate_button.state(['!disabled'] if entry.kind == 'structure' else ['disabled'])
        self.canvas.delete('all')
        photo, state, path = self.sprite(entry, self.scale.get(), self.turns)
        self.preview_image = photo
        if photo is not None:
            self.canvas.create_image(12, 12, anchor='nw', image=photo)
            self.canvas.configure(scrollregion=(0, 0, photo.width()+24, photo.height()+24))
        else:
            self.canvas.create_text(20, 30, anchor='nw', text=state, width=330)
            self.canvas.configure(scrollregion=(0, 0, 360, 100))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        w, h = entry.footprint(self.turns)
        rotation = (f'\nRotation du terrain : {self.turns*90}° ; 2 vues PNG partagées.'
                    if entry.kind == 'structure' else '')
        self.detail.set(f'{entry.name} — {entry.category}\n{entry.id}\n'
                        f'Emprise : {w} × {h} case(s) · {path}\n{state}'
                        f'{rotation}\n{entry.effect}')

    def use(self):
        entry = self.selected()
        if entry is not None and self.choose(entry, self.turns):
            self.window.withdraw()
