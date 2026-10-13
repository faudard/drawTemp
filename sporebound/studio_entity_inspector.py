"""Tk inspector for already-placed actors and tactical objects.

Pure presentation, delegates every mutation to entity_editing via Editor.Document.
"""
from types import SimpleNamespace

from .entity_editing import entities_at, get_entity
from .iso_actor_atlas import actor_direction, actor_style

OBJECT_FIELDS = {
    'door': ('hp', 'locked'),
    'chest': ('amount',),
    'switch': ('link',),
    'ram': ('link', 'power', 'team'),
    'catapult': ('link', 'power', 'team', 'ammo'),
    'passage': ('destination', 'cost', 'enabled', 'bidirectional'),
    'defense': ('team', 'power', 'charges', 'disabled'),
}
FIELD_LABELS = {
    'name': 'Nom', 'team': 'Équipe', 'facing': 'Orientation',
    'hp': 'PV de la porte', 'locked': 'Porte verrouillée',
    'amount': 'Contenu du coffre', 'link': 'Porte cible',
    'power': 'Puissance', 'ammo': 'Munitions',
    'destination': 'Sortie passage (x,y)', 'cost': 'Coût de traversée',
    'enabled': 'Passage actif', 'bidirectional': 'Bidirectionnel',
    'charges': 'Charges', 'disabled': 'Défense désactivée',
}
BOOL_FIELDS = {'locked', 'enabled', 'bidirectional', 'disabled'}
INT_FIELDS = {'hp', 'amount', 'power', 'ammo', 'cost', 'charges'}


class EntityInspector:
    def __init__(self, parent, *, snapshot, actors, commit, begin_target, cell_size):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk = tk
        self.messagebox = messagebox
        self.snapshot, self.actors = snapshot, actors
        self.commit, self.begin_target = commit, begin_target
        self.cell_size = cell_size
        self.window = tk.Toplevel(parent)
        self.window.title('Inspecteur — Acteurs et objets')
        self.window.geometry('520x700')
        self.window.minsize(480, 620)
        self.window.transient(parent)
        self.window.withdraw()
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.cell = None
        self.items = {}
        self.current = None
        self.selection = tk.StringVar(self.window)
        self.detail = tk.StringVar(self.window)
        self.pose = tk.StringVar(self.window, value='idle')
        self.vars = {}
        self.rows = {}
        self.baseline = {}
        top = ttk.Frame(self.window, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text='Entité sélectionnée').pack(anchor='w')
        self.selector = ttk.Combobox(top, textvariable=self.selection,
                                     state='readonly')
        self.selector.pack(fill='x', pady=3)
        self.selector.bind('<<ComboboxSelected>>', self.select)
        ttk.Label(top, textvariable=self.detail, wraplength=465).pack(
            fill='x', pady=4)
        preview = ttk.Frame(self.window)
        preview.pack(fill='x', padx=8)
        self.canvas = tk.Canvas(preview, height=136, width=180,
                                background='#e6e1d7', highlightthickness=0)
        self.canvas.pack(side='left', padx=(0, 8))
        ttk.Label(preview, text='Pose (aperçu)').pack(side='top', anchor='w')
        self.pose_box = ttk.Combobox(
            preview, textvariable=self.pose, values=('idle', 'move'),
            state='readonly', width=10)
        self.pose_box.pack(side='top', anchor='w')
        self.pose.trace_add('write', lambda *_: self.redraw())
        form = ttk.LabelFrame(self.window, text='Propriétés')
        form.pack(fill='both', expand=True, padx=8, pady=6)
        for key, label in FIELD_LABELS.items():
            row = ttk.Frame(form)
            ttk.Label(row, text=label, width=23).pack(side='left', padx=(5, 2))
            variable = tk.BooleanVar(self.window) if key in BOOL_FIELDS else tk.StringVar(self.window)
            if key in BOOL_FIELDS:
                widget = ttk.Checkbutton(row, variable=variable)
            elif key in ('team', 'facing', 'link'):
                options = (('player', 'enemy') if key == 'team'
                           else ('south', 'north', 'east', 'west') if key == 'facing'
                           else ())
                widget = ttk.Combobox(row, textvariable=variable, values=options,
                                      state='readonly')
            else:
                widget = ttk.Entry(row, textvariable=variable)
            widget.pack(side='left', fill='x', expand=True, padx=5)
            self.vars[key], self.rows[key] = variable, row
        self.vars['facing'].trace_add('write', lambda *_: self.redraw())
        actions = ttk.Frame(self.window, padding=8)
        actions.pack(fill='x')
        for label, command in (
            ('Appliquer', self.apply), ('Déplacer au clic', lambda: self.target('move')),
            ('Dupliquer au clic', lambda: self.target('duplicate')),
            ('Supprimer', self.remove),
        ):
            ttk.Button(actions, text=label, command=command).pack(
                side='left', padx=3)

    def show_at(self, cell):
        data, mid = self.snapshot()
        matches = entities_at(data, mid, cell)
        if not matches:
            from .model import RuleError
            raise RuleError('Aucun acteur ou objet sur cette case.')
        self.cell = tuple(cell)
        self.items = {f'{entry.kind}:{entry.id}': entry for entry in matches}
        self.selector['values'] = tuple(self.items)
        self.selection.set(next(iter(self.items)))
        self.select()
        self.window.deiconify()
        self.window.lift()

    def select(self, _event=None):
        key = self.selection.get()
        self.current = self.items.get(key)
        if self.current is None:
            return
        data, mid = self.snapshot()
        record = get_entity(data, mid, self.current.kind, self.current.id)
        if self.current.kind == 'actor':
            fields = ('name', 'team', 'facing')
            self.detail.set(f"Acteur {record['id']} · position {record['pos']} · "
                            f"archétype {record.get('archetype') or 'libre'}")
        else:
            fields = OBJECT_FIELDS[record['kind']]
            self.detail.set(f"Objet {record['id']} ({record['kind']}) · "
                            f"position {record['pos']}")
        self.baseline = {}
        for key, row in self.rows.items():
            row.pack_forget()
            if key not in fields:
                continue
            row.pack(fill='x', pady=2)
            if key == 'facing':
                self.vars[key].set(actor_direction(SimpleNamespace(**record)))
            elif key == 'destination':
                self.vars[key].set(','.join(map(str, record.get('destination', ()))))
            elif key in BOOL_FIELDS:
                defaults = {'locked': False, 'enabled': True,
                            'bidirectional': True, 'disabled': False}
                self.vars[key].set(record.get(key, defaults[key]))
            else:
                defaults = {'hp': 1, 'amount': 1, 'power': 15,
                            'ammo': 0, 'charges': 2, 'cost': 2}
                if key == 'team' and self.current.kind == 'object':
                    defaults[key] = ('enemy' if record['kind'] == 'defense'
                                     else 'player')
                if key == 'power' and record.get('kind') in ('ram', 'catapult'):
                    defaults[key] = 1
                self.vars[key].set(str(record.get(key, defaults.get(key, ''))))
            self.baseline[key] = self.vars[key].get()
            if key == 'link':
                mission = next(m for m in data['missions'] if m['id'] == mid)
                doors = [o['id'] for o in mission['objects'] if o['kind'] == 'door']
                self.rows[key].winfo_children()[1]['values'] = doors
        self.pose_box.configure(state='readonly' if self.current.kind == 'actor' else 'disabled')
        self.redraw()

    def redraw(self):
        self.canvas.delete('all')
        if self.current is None:
            return
        data, mid = self.snapshot()
        try:
            record = get_entity(data, mid, self.current.kind, self.current.id)
        except ValueError:
            return
        if self.current.kind == 'actor':
            direction = self.vars['facing'].get()
            photo = self.actors.sprite(actor_style(SimpleNamespace(**record)),
                                       direction, int(self.pose.get() == 'move'),
                                       self.cell_size())
            self.photo = photo
            if photo is not None:
                self.canvas.create_image(90, 122, anchor='s', image=photo)
                return
        self.photo = None
        self.canvas.create_text(90, 68,
                                text=self.current.label, width=165,
                                font=('TkDefaultFont', 12, 'bold'))

    def changes(self):
        if self.current.kind == 'actor':
            keys = ('name', 'team', 'facing')
        else:
            data, mid = self.snapshot()
            record = get_entity(data, mid, self.current.kind, self.current.id)
            keys = OBJECT_FIELDS[record['kind']]
        result = {}
        for key in keys:
            value = self.vars[key].get()
            if value == self.baseline.get(key):
                continue
            if key in INT_FIELDS:
                value = int(value)
            result[key] = value
        return result

    def apply(self):
        if self.current is None:
            return
        try:
            payload = self.changes()
            if not payload:
                self.detail.set('Aucune propriété modifiée.')
                return
            if self.commit('edit', self.current.kind, self.current.id, payload):
                self.select()
        except (ValueError, KeyError) as exc:
            self.messagebox.showerror('Propriété invalide', str(exc))

    def target(self, operation):
        if self.current is not None and self.begin_target(
                operation, self.current.kind, self.current.id):
            self.window.withdraw()

    def remove(self):
        if self.current is None:
            return
        if not self.messagebox.askyesno('Suppression', 'Supprimer cette entité ?'):
            return
        if self.commit('remove', self.current.kind, self.current.id, {}):
            self.window.withdraw()
