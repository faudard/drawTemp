"""Tk actor/object chooser reusing the project's authoritative actor atlas.

This is a presentation layer only; placement is handled by entity_palette.
"""
from .entity_palette import entity_entries, OBJECT_LABELS


class EntityPalette:
    def __init__(self, parent, *, snapshot, actors, choose, cell_size):
        import tkinter as tk
        from tkinter import ttk
        self.snapshot, self.actors = snapshot, actors
        self.choose, self.cell_size = choose, cell_size
        self.window = tk.Toplevel(parent)
        self.window.title('Acteurs et objets — palette de mission')
        self.window.geometry('720x510')
        self.window.minsize(560, 420)
        self.window.transient(parent)
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.query = tk.StringVar(self.window)
        self.category = tk.StringVar(self.window, value='Tous')
        self.facing = tk.StringVar(self.window, value='south')
        self.moving = tk.BooleanVar(self.window, value=False)
        self.link = tk.StringVar(self.window)
        self.destination = tk.StringVar(self.window)
        self.detail = tk.StringVar(self.window)
        self.counter = tk.StringVar(self.window)
        self.entries = {}
        top = ttk.Frame(self.window, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text='Rechercher').pack(side='left')
        ttk.Entry(top, textvariable=self.query, width=24).pack(side='left', padx=6)
        ttk.Combobox(top, textvariable=self.category, state='readonly', width=13,
                     values=('Tous', 'Acteurs', 'Objets')).pack(side='left', padx=6)
        ttk.Label(top, textvariable=self.counter).pack(side='right')
        body = ttk.Panedwindow(self.window, orient='horizontal')
        body.pack(fill='both', expand=True, padx=8)
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse')
        scrollbar = ttk.Scrollbar(left, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(right, width=230, height=170,
                                background='#e6e1d7', highlightthickness=0)
        self.canvas.pack(fill='x')
        ttk.Label(right, textvariable=self.detail, wraplength=270).pack(
            fill='x', pady=8)
        actor_controls = ttk.Frame(right)
        actor_controls.pack(fill='x')
        ttk.Label(actor_controls, text='Orientation').pack(side='left')
        self.facing_box = ttk.Combobox(actor_controls, textvariable=self.facing,
                                      state='readonly', width=8,
                                      values=('south', 'north', 'east', 'west'))
        self.facing_box.pack(side='left', padx=4)
        self.pose_button = ttk.Checkbutton(right, text='Prévisualiser la marche',
                                           variable=self.moving)
        self.pose_button.pack(anchor='w', pady=4)
        ttk.Label(right, text='Porte liée (levier, bélier, catapulte)').pack(anchor='w')
        self.link_box = ttk.Combobox(right, textvariable=self.link, state='readonly')
        self.link_box.pack(fill='x')
        ttk.Label(right, text='Destination du passage (x,y)').pack(anchor='w', pady=(6, 0))
        self.destination_entry = ttk.Entry(right, textvariable=self.destination)
        self.destination_entry.pack(fill='x')
        self.use_button = ttk.Button(right, text='Placer sur la carte', command=self.use)
        self.use_button.pack(fill='x', pady=12)
        ttk.Label(self.window, text='Utiliser → cliquer sur la carte ; '
                  'la pose est validée par les règles et annulable.').pack(pady=6)
        self.tree.bind('<<TreeviewSelect>>', self.preview)
        self.tree.bind('<Double-1>', lambda _e: self.use())
        self.query.trace_add('write', self.populate)
        self.category.trace_add('write', self.populate)
        self.facing.trace_add('write', self.preview)
        self.moving.trace_add('write', self.preview)
        self.refresh()

    def show(self):
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def refresh(self):
        data, mid = self.snapshot()
        self.entries = {entry.id: entry for entry in entity_entries(data, mid)}
        mission = next(m for m in data['missions'] if m['id'] == mid)
        doors = [row['id'] for row in mission.get('objects', ())
                 if row['kind'] == 'door']
        self.link_box['values'] = doors
        if self.link.get() not in doors:
            self.link.set(doors[0] if len(doors) == 1 else '')
        self.populate()

    def populate(self, *_args):
        old = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        query = self.query.get().casefold().strip()
        category = self.category.get()
        visible = [entry for entry in self.entries.values()
                   if (category == 'Tous'
                       or category == 'Acteurs' and entry.kind == 'actor'
                       or category == 'Objets' and entry.kind == 'object')
                   and query in (entry.label + ' ' + entry.id).casefold()]
        for entry in visible:
            self.tree.insert('', 'end', iid=entry.id,
                             text=entry.label + (' · ' + entry.team
                                                 if entry.kind == 'actor' else ''))
        self.counter.set(f'{len(visible)} / {len(self.entries)}')
        if visible:
            preferred = old[0] if old and old[0] in {v.id for v in visible} else visible[0].id
            self.tree.selection_set(preferred)
            self.preview()
        else:
            self.canvas.delete('all')
            self.detail.set('Aucun élément trouvé.')
            self.use_button.state(['disabled'])

    def selected(self):
        current = self.tree.selection()
        return self.entries.get(current[0]) if current else None

    def preview(self, *_args):
        entry = self.selected()
        if entry is None:
            return
        self.use_button.state(['!disabled'])
        self.canvas.delete('all')
        is_actor = entry.kind == 'actor'
        self.facing_box.configure(state='readonly' if is_actor else 'disabled')
        self.pose_button.configure(state='normal' if is_actor else 'disabled')
        is_linked = entry.id in ('object:switch', 'object:ram', 'object:catapult')
        self.link_box.configure(state='readonly' if is_linked else 'disabled')
        self.destination_entry.configure(state='normal' if entry.id == 'object:passage'
                                         else 'disabled')
        self.preview_image = None
        if is_actor:
            self.preview_image = self.actors.sprite(
                entry.style, self.facing.get(), int(self.moving.get()),
                self.cell_size())
        if self.preview_image is not None:
            self.canvas.create_image(120, 152, image=self.preview_image, anchor='s')
        else:
            self.canvas.create_oval(88, 48, 153, 114, fill='#829cba' if is_actor
                                    else '#9070b1', outline='#4b5261', width=2)
            self.canvas.create_text(120, 137, text=entry.label)
        self.detail.set(f'{entry.label} — {entry.id}\n{entry.description}'
                        + (f'\nÉquipe : {entry.team}' if is_actor else ''))

    def use(self):
        from tkinter import messagebox
        entry = self.selected()
        if entry is None:
            return
        destination = None
        if entry.id == 'object:passage':
            try:
                x, y = (int(part.strip()) for part in self.destination.get().split(','))
                destination = (x, y)
            except (ValueError, TypeError):
                messagebox.showerror('Passage', 'Saisir une destination x,y.')
                return
        if entry.id in ('object:switch', 'object:ram', 'object:catapult') and not self.link.get():
            messagebox.showerror('Lien', 'Créer et sélectionner une porte cible.')
            return
        if self.choose(entry, self.facing.get(), self.link.get(), destination):
            self.window.withdraw()
