"""Tk view of versioned editor group prefabs.

Visual thumbnails are painted with Canvas primitives from headless catalog
metadata: no image files, asset-library duplication, external DnD extensions
or changes to the Map Editor document format.
"""


class VisualPrefabPalette:
    def __init__(self, parent, tk, ttk, *, on_select, on_preview,
                 on_drop, on_cancel, map_canvas, status):
        self.tk, self.ttk = tk, ttk
        self.on_select = on_select
        self.on_preview = on_preview
        self.on_drop = on_drop
        self.on_cancel = on_cancel
        self.map_canvas = map_canvas
        self.status = status
        self.entries = {}
        self.cards = ()
        self.selected = ''
        self.drag = None
        self.query = tk.StringVar(value='')
        self.category = tk.StringVar(value='Tous')
        self.frame = ttk.Frame(parent)

        controls = ttk.Frame(self.frame)
        controls.pack(fill='x', padx=2, pady=(2, 4))
        ttk.Label(controls, text='Rechercher').pack(side='left', padx=2)
        entry = ttk.Entry(controls, textvariable=self.query, width=14)
        entry.pack(side='left', fill='x', expand=True, padx=2)
        self.search_entry = entry
        categories = ttk.Combobox(self.frame, textvariable=self.category,
                                  values=('Tous', 'Quartiers', 'Bâtiments',
                                          'Fortifications', 'Décors',
                                          'Interactifs', 'Personnages'),
                                  state='readonly', width=24)
        categories.pack(fill='x', padx=5, pady=(0, 3))
        self.categories_box = categories
        self.gallery = tk.Canvas(self.frame, background='#f6f7f8',
                                 height=248, highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient='vertical',
                               command=self.gallery.yview)
        self.gallery.configure(yscrollcommand=scroll.set)
        self.gallery.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.grid = ttk.Frame(self.gallery)
        self.grid_window = self.gallery.create_window((0, 0),
                                                       window=self.grid,
                                                       anchor='nw')
        self.grid.bind('<Configure>', lambda e: self.gallery.configure(
            scrollregion=self.gallery.bbox('all')))
        self.gallery.bind('<Configure>', lambda e: self.gallery.itemconfigure(
            self.grid_window, width=e.width))
        self.query.trace_add('write', lambda *_: self.render())
        self.category.trace_add('write', lambda *_: self.render())
        self.gallery.bind('<MouseWheel>', self._scroll)
        self.gallery.bind('<Button-4>', self._scroll)
        self.gallery.bind('<Button-5>', self._scroll)

    def _scroll(self, event):
        step = -1 if (getattr(event, 'num', None) == 4 or
                      getattr(event, 'delta', 0) > 0) else 1
        self.gallery.yview_scroll(step, 'units')

    def update(self, cards):
        self.cards = tuple(cards)
        self.entries = {item.filename: item for item in self.cards}
        if self.selected not in self.entries:
            self.selected = ''
        self.render()

    def choose(self, filename):
        if filename not in self.entries:
            return
        self.selected = filename
        self.on_select(filename)
        self.render()

    def render(self):
        from .prefab_catalog import filter_prefab_cards, thumbnail_rectangles
        for child in self.grid.winfo_children():
            child.destroy()
        visible = filter_prefab_cards(self.cards, self.query.get(),
                                     self.category.get())
        if not visible:
            self.ttk.Label(self.grid,
                           text='Aucun préfab dans cette catégorie.'
                           ).grid(row=0, column=0, sticky='w', padx=7, pady=7)
            return
        for index, card in enumerate(visible):
            col, row = index % 2, index // 2
            selected = card.filename == self.selected
            bg = '#dceafc' if selected else '#ffffff'
            tile = self.tk.Frame(self.grid, background=bg,
                                 highlightthickness=2 if selected else 1,
                                 highlightbackground=('#3c77bf' if selected
                                                      else '#d3dce3'),
                                 cursor='hand2')
            tile.grid(row=row, column=col, sticky='nw', padx=3, pady=3)
            picture = self.tk.Canvas(tile, width=132, height=78,
                                     background='#f1f5f4',
                                     highlightthickness=0,
                                     cursor='hand2')
            picture.pack(padx=3, pady=(3, 1))
            for x0, y0, x1, y1, color in thumbnail_rectangles(
                    card, width=132, height=78, pad=5):
                picture.create_rectangle(x0, y0, x1, y1, fill=color,
                                         outline='', tags='thumbnail')
            # Reference grid and accent are meaningful even when the selected
            # tiles represent a completely empty/free-standing terrain patch.
            picture.create_rectangle(4, 4, 128, 74,
                                     outline='#c3cdd1', width=1)
            if card.error:
                picture.create_text(66, 39, text='!', fill='#b64242',
                                    font=('TkDefaultFont', 20, 'bold'))
            label = self.tk.Label(
                tile, text=card.name[:21], background=bg,
                foreground='#223348', width=19, anchor='w')
            label.pack(anchor='w', padx=4)
            detail = (f'{card.category}  ·  {card.width}×{card.height}'
                      if not card.error else 'JSON invalide')
            small = self.tk.Label(tile, text=detail,
                                  background=bg, foreground='#5b6976',
                                  width=19, anchor='w',
                                  font=('TkDefaultFont', 8))
            small.pack(anchor='w', padx=4, pady=(0, 4))
            for widget in (picture, label, small, tile):
                widget.bind('<ButtonPress-1>',
                            lambda e, name=card.filename: self._press(e, name))
                widget.bind('<B1-Motion>', self._motion)
                widget.bind('<ButtonRelease-1>', self._release)

    def _press(self, event, filename):
        card = self.entries.get(filename)
        if card is None or card.error:
            if card and card.error:
                self.status('Préfab invalide : '+card.error)
            return
        self.drag = {'filename': filename, 'x': event.x_root,
                     'y': event.y_root, 'active': False}

    def _map_anchor(self, event):
        x = event.x_root - self.map_canvas.winfo_rootx()
        y = event.y_root - self.map_canvas.winfo_rooty()
        if not (0 <= x < self.map_canvas.winfo_width() and
                0 <= y < self.map_canvas.winfo_height()):
            return None
        return int(x), int(y)

    def _motion(self, event):
        gesture = self.drag
        if gesture is None:
            return
        distance = abs(event.x_root - gesture['x']) + abs(
            event.y_root - gesture['y'])
        if distance < 10 and not gesture['active']:
            return
        gesture['active'] = True
        point = self._map_anchor(event)
        if point is None:
            if gesture.get('point') is not None:
                self.on_cancel()
            gesture['point'] = None
            return
        if point != gesture.get('point'):
            gesture['point'] = point
            self.on_preview(gesture['filename'], point)

    def _release(self, event):
        gesture = self.drag
        self.drag = None
        if gesture is None:
            return
        if not gesture['active']:
            self.choose(gesture['filename'])
            return
        point = self._map_anchor(event)
        self.on_cancel()
        if point is not None:
            self.choose(gesture['filename'])
            self.on_drop(gesture['filename'], point)

    def cancel(self):
        self.drag = None
        self.on_cancel()
