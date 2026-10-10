"""Tk Class Progression & AI Studio 2.5.3.3.

Two visual editors project the existing class prerequisite DAG, talent DAG and
tactical patrol routes without inventing new battle algorithms.
"""
from . import class_ai_authoring as edit
from .character_authoring import parse_bonuses
from .model import require


class ClassAIStudio:
    def __init__(self, parent, notebook):
        self.parent = parent
        self.owner = parent.owner
        self.tk, self.ttk = self.owner.tk, self.owner.ttk
        self.selected_job = None
        self.selected_talent = None
        self.selected_unit = None
        self.mission_id = None
        self._classes_tab(notebook)
        self._ai_tab(notebook)

    def _field(self, parent, label, variable, row, *, values=None,
               editable=False, column=0, width=22):
        ttk = self.ttk
        ttk.Label(parent, text=label).grid(
            row=row, column=column*2, sticky='w', padx=4, pady=3)
        if values is None:
            widget = ttk.Entry(parent, textvariable=variable, width=width)
        else:
            widget = ttk.Combobox(parent, textvariable=variable, values=values,
                                  state='normal' if editable else 'readonly',
                                  width=width)
        widget.grid(row=row, column=column*2+1, sticky='ew', padx=4, pady=3)
        parent.grid_columnconfigure(column*2+1, weight=1)
        return widget

    def _button(self, parent, label, fn):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.owner._run(fn)).pack(
                            side='left', padx=3, pady=3)

    def _data(self):
        return self.owner.doc().data

    def _edit(self, fn):
        self.parent._apply(fn)

    @staticmethod
    def _ids(value):
        return [v.strip() for v in value.split(',') if v.strip()]

    def _classes_tab(self, notebook):
        ttk, tk = self.ttk, self.tk
        page = ttk.Frame(notebook)
        notebook.add(page, text='Graphe des classes')
        self.classes_page = page
        header = ttk.Frame(page)
        header.pack(fill='x', padx=7, pady=4)
        ttk.Label(header, text='Classe').pack(side='left', padx=4)
        self.job_id = tk.StringVar()
        self.job_box = ttk.Combobox(header, textvariable=self.job_id,
                                    width=24, state='readonly')
        self.job_box.pack(side='left', padx=4)
        self.job_box.bind('<<ComboboxSelected>>', lambda e: self.select_job())
        self._button(header, 'Ouvrir la classe', self.open_job_tab)
        graph_frame = ttk.Frame(page)
        graph_frame.pack(fill='both', expand=True, padx=7, pady=3)
        graph_left = ttk.LabelFrame(graph_frame, text='Pré requis entre classes')
        graph_left.pack(side='left', fill='both', expand=True)
        self.job_canvas = tk.Canvas(graph_left, bg='#f8fafc',
                                    height=210, highlightthickness=0)
        self.job_canvas.pack(fill='both', expand=True)
        graph_right = ttk.LabelFrame(graph_frame, text='Talents et spécialisations')
        graph_right.pack(side='right', fill='both', expand=True, padx=(7,0))
        self.talent_canvas = tk.Canvas(graph_right, bg='#f8fafc',
                                       height=210, highlightthickness=0)
        self.talent_canvas.pack(fill='both', expand=True)
        forms = ttk.Frame(page)
        forms.pack(fill='x', padx=7, pady=5)
        class_form = ttk.LabelFrame(forms, text='Déverrouillage de classe')
        class_form.pack(side='left', fill='both', expand=True)
        self.parent_id = tk.StringVar()
        self.parent_box = self._field(class_form, 'Classe requise', self.parent_id, 0,
                                      values=[], editable=False)
        self.parent_level = tk.StringVar(value='1')
        self._field(class_form, 'Niveau requis', self.parent_level, 1)
        buttons = ttk.Frame(class_form)
        buttons.grid(row=2, column=0, columnspan=2, sticky='w')
        self._button(buttons, 'Relier / retirer le prérequis', self.save_job_link)
        talent_form = ttk.LabelFrame(forms, text='Talents du métier')
        talent_form.pack(side='right', fill='both', expand=True, padx=(7,0))
        self.talent_id = tk.StringVar()
        self.talent_box = self._field(talent_form, 'Talent / nouvel ID',
                                       self.talent_id, 0, values=[], editable=True)
        self.talent_box.bind('<<ComboboxSelected>>', lambda e: self.select_talent())
        self.talent_jp = tk.StringVar(value='1')
        self._field(talent_form, 'Coût JP (1..20)', self.talent_jp, 1)
        self.talent_requires = tk.StringVar()
        self._field(talent_form, 'Prérequis talents', self.talent_requires, 2)
        self.talent_exclusive = tk.StringVar()
        self._field(talent_form, 'Spécialisation exclusive', self.talent_exclusive, 3)
        self.talent_bonuses = tk.StringVar()
        self._field(talent_form, 'Bonus (ex. attack=2)', self.talent_bonuses, 4)
        self.talent_skills = tk.StringVar()
        self._field(talent_form, 'Compétences', self.talent_skills, 5)
        buttons = ttk.Frame(talent_form)
        buttons.grid(row=6, column=0, columnspan=2, sticky='w')
        self._button(buttons, 'Créer talent', self.create_talent)
        self._button(buttons, 'Modifier talent', self.save_talent)
        self._button(buttons, 'Supprimer talent', self.delete_talent)
        self.classes_info = tk.StringVar(value='Sélectionner une classe.')
        ttk.Label(page, textvariable=self.classes_info, wraplength=900).pack(
            fill='x', padx=8, pady=4)

    def _talents(self):
        return self._data()['jobs'][self.job_id.get()].get('talents', {})

    def _talent_spec(self):
        return edit.make_talent(
            jp=int(self.talent_jp.get()),
            requires=self._ids(self.talent_requires.get()),
            exclusive=self.talent_exclusive.get(),
            bonuses=parse_bonuses(self.talent_bonuses.get(), equipment=True),
            skills=self._ids(self.talent_skills.get()))

    def select_job(self):
        jid = self.job_id.get()
        if jid not in self._data()['jobs']:
            return
        job = self._data()['jobs'][jid]
        self.parent_id.set(job.get('requires',''))
        self.parent_level.set(str(job.get('requires_level',1)))
        self.talent_box['values'] = sorted(job.get('talents', {}))
        if self.talent_id.get() not in job.get('talents', {}):
            self.talent_id.set('')
        else:
            self.select_talent()
        self.draw_classes()
        self.draw_talents()

    def select_talent(self):
        spec = self._talents().get(self.talent_id.get())
        if spec is None:
            return
        self.talent_jp.set(str(spec.get('jp',1)))
        self.talent_requires.set(', '.join(spec.get('requires',[])))
        self.talent_exclusive.set(spec.get('exclusive',''))
        self.talent_bonuses.set(', '.join(f'{k}={v}' for k,v in spec.get('bonuses',{}).items()))
        self.talent_skills.set(', '.join(spec.get('skills',[])))
        self.draw_talents()

    def save_job_link(self):
        jid, prereq = self.job_id.get(), self.parent_id.get()
        self._edit(lambda data: edit.link_job(
            data, jid, prereq, int(self.parent_level.get())))
        self.classes_info.set('Prérequis validé pour ' + jid)

    def create_talent(self):
        jid, tid = self.job_id.get(), self.talent_id.get()
        self._edit(lambda data: edit.save_talent(
            data, jid, tid, self._talent_spec(), creating=True))
        self.talent_id.set(tid)
        self.draw_talents()

    def save_talent(self):
        jid, tid = self.job_id.get(), self.talent_id.get()
        spec = self._talent_spec()
        self._edit(lambda data: edit.save_talent(data, jid, tid, spec))

    def delete_talent(self):
        jid, tid = self.job_id.get(), self.talent_id.get()
        self._edit(lambda data: edit.delete_talent(data, jid, tid))
        self.talent_id.set('')
        self.refresh()

    def open_job_tab(self):
        # Open the existing class form rather than duplicating its contract.
        self.parent.tabs.select(self.parent.jobs_tab)
        self.parent.j_id.set(self.job_id.get())
        self.parent._load_job()

    def _draw_dag(self, canvas, graph, *, job=False):
        canvas.delete('all')
        positions = {row['id']: (row['x'], row['y'])
                     for row in graph['nodes']}
        for edge in graph['edges']:
            start, end = positions[edge['from']], positions[edge['to']]
            canvas.create_line(start[0]+145, start[1]+25,
                               end[0], end[1]+25, arrow='last',
                               fill='#64748b', width=2)
        for node in graph['nodes']:
            x,y = node['x'],node['y']
            selected = node['id'] == (self.job_id.get() if job
                                      else self.talent_id.get())
            tag = 'item_' + node['id']
            canvas.create_rectangle(x,y,x+145,y+55,
                                    fill='#c7d2fe' if selected else '#eff6ff',
                                    outline='#2563eb', tags=(tag,))
            label = node['label'] if job else (
                node['id'] + '\n' + str(node['jp']) + ' JP' +
                (' · ' + node['exclusive'] if node['exclusive'] else ''))
            canvas.create_text(x+72,y+27,text=label,
                               width=135, justify='center',
                               tags=(tag,))
            canvas.tag_bind(tag, '<Button-1>',
                            lambda e,ident=node['id'],which=job:
                            self._click_node(ident,which))
        canvas.configure(scrollregion=(0,0,graph['width'],graph['height']))

    def _click_node(self, ident, job):
        if job:
            self.job_id.set(ident)
            self.select_job()
        else:
            self.talent_id.set(ident)
            self.select_talent()

    def draw_classes(self):
        self._draw_dag(self.job_canvas,
                       edit.job_graph(self._data()), job=True)

    def draw_talents(self):
        if self.job_id.get() in self._data()['jobs']:
            self._draw_dag(self.talent_canvas,
                           edit.talent_graph(self._data(), self.job_id.get()))
        else:
            self.talent_canvas.delete('all')

    def _ai_tab(self, notebook):
        ttk,tk = self.ttk,self.tk
        page = ttk.Frame(notebook)
        notebook.add(page, text='IA & patrouilles')
        self.ai_page = page
        header = ttk.Frame(page)
        header.pack(fill='x', padx=7, pady=5)
        ttk.Label(header, text='Unité de la mission active').pack(side='left')
        self.unit_id = tk.StringVar()
        self.unit_box = ttk.Combobox(header, textvariable=self.unit_id,
                                    state='readonly', width=25)
        self.unit_box.pack(side='left', padx=6)
        self.unit_box.bind('<<ComboboxSelected>>', lambda e: self.select_unit())
        body = ttk.Frame(page)
        body.pack(fill='both', expand=True, padx=8, pady=5)
        left = ttk.LabelFrame(body, text='Route tactique (clic sur la grille)')
        left.pack(side='left', fill='both', expand=True)
        self.map_canvas = tk.Canvas(left, bg='#f8fafc',
                                    height=410, highlightthickness=0)
        self.map_canvas.pack(fill='both', expand=True)
        self.map_canvas.bind('<Button-1>', self.add_point_from_map)
        right = ttk.LabelFrame(body, text='Comportement & rôles')
        right.pack(side='right', fill='y', padx=(8,0))
        self.ai_behavior = tk.StringVar(value='tactical')
        self._field(right,'Comportement',self.ai_behavior,0,values=['tactical'])
        self.ai_roles = tk.StringVar()
        self._field(right,'Étiquettes / rôles',self.ai_roles,1)
        self.ai_route = tk.StringVar()
        self._field(right,'Route x,y; x,y',self.ai_route,2)
        ttk.Label(right, text='Rôles conseillés : '+', '.join(edit.ROLES),
                  wraplength=280).grid(row=3,column=0,columnspan=2,
                                       padx=5,pady=8,sticky='w')
        controls = ttk.Frame(right)
        controls.grid(row=4,column=0,columnspan=2,sticky='w')
        self._button(controls,'Appliquer IA et route',self.save_ai)
        self._button(controls,'Effacer route',self.clear_route)
        self._button(controls,'Ajouter case sélectionnée',self.add_selected_point)
        self.ai_status = tk.StringVar(value='IA standard ; la route sera suivie hors combat.')
        ttk.Label(right,textvariable=self.ai_status,wraplength=280).grid(
            row=5,column=0,columnspan=2,sticky='w',padx=5,pady=5)

    def _mission(self):
        return next(m for m in self._data()['missions']
                    if m['id'] == self.owner.mission())

    def select_unit(self):
        uid = self.unit_id.get()
        if not uid:
            return
        info = edit.ai_preview(self._data(), self.owner.mission(), uid)
        self.ai_behavior.set(info['behavior'])
        self.ai_roles.set(', '.join(info['roles']))
        self.ai_route.set('; '.join(','.join(map(str, pt))
                                     for pt in info['waypoints']))
        self.draw_map()

    def _points(self):
        return edit.parse_cells(self.ai_route.get())

    def _append_point(self, point):
        current = self.ai_route.get().strip()
        addition = ','.join(str(x) for x in point)
        self.ai_route.set((current+'; ' if current else '')+addition)
        self.draw_map()

    def add_point_from_map(self, event):
        if not self.unit_id.get():
            return
        x = int(self.map_canvas.canvasx(event.x)//self.tile_size)
        y = int(self.map_canvas.canvasy(event.y)//self.tile_size)
        m = self._mission()
        if 0 <= x < m['board']['width'] and 0 <= y < m['board']['height']:
            self._append_point((x,y))

    def add_selected_point(self):
        self._append_point(self.owner.selection())

    def clear_route(self):
        self.ai_route.set('')
        self.draw_map()

    def save_ai(self):
        mid, uid = self.owner.mission(), self.unit_id.get()
        roles = self._ids(self.ai_roles.get())
        route = self._points()
        self._edit(lambda data: edit.set_unit_ai(
            data, mid, uid, behavior=self.ai_behavior.get(),
            roles=roles, route=route))
        self.ai_status.set('Profil IA de ' + uid + ' validé et annulable.')

    def draw_map(self):
        canvas = self.map_canvas
        canvas.delete('all')
        m = self._mission()
        w,h = m['board']['width'],m['board']['height']
        self.tile_size = max(12, min(46, 540//max(w,1), 375//max(h,1)))
        tile = self.tile_size
        blocked = {tuple(x['pos']) for x in m['board'].get('tiles',[])
                   if x.get('blocked')}
        for y in range(h):
            for x in range(w):
                canvas.create_rectangle(x*tile,y*tile,(x+1)*tile,(y+1)*tile,
                                         fill='#cbd5e1' if (x,y) in blocked else '#f8fafc',
                                         outline='#e2e8f0')
        actor = next((u for u in m['units'] if u['id']==self.unit_id.get()),None)
        if actor is not None:
            ax,ay=actor['pos']
            canvas.create_oval(ax*tile+4,ay*tile+4,
                               (ax+1)*tile-4,(ay+1)*tile-4,fill='#93c5fd')
            canvas.create_text((ax+.5)*tile,(ay+.5)*tile,text='U',
                               fill='#1e3a8a')
        coords = []
        raw = self.ai_route.get()
        for text in raw.split(';'):
            xy = [value.strip() for value in text.split(',')]
            if len(xy)==2 and all(value.isdecimal() for value in xy):
                x,y = map(int,xy)
                if 0<=x<w and 0<=y<h:
                    coords.append((x,y))
        for i,(x,y) in enumerate(coords):
            px,py=(x+.5)*tile,(y+.5)*tile
            if i:
                prev=coords[i-1]
                canvas.create_line((prev[0]+.5)*tile,(prev[1]+.5)*tile,
                                   px,py,fill='#2563eb',width=3,arrow='last')
            canvas.create_oval(px-10,py-10,px+10,py+10,
                               fill='#fbbf24',outline='#92400e')
            canvas.create_text(px,py,text=str(i+1))
        canvas.configure(scrollregion=(0,0,w*tile,h*tile))

    def refresh(self):
        if self.owner.project is None:
            return
        jobs = self._data().get('jobs',{})
        self.job_box['values'] = sorted(jobs)
        if self.job_id.get() not in jobs:
            self.job_id.set(next(iter(sorted(jobs)),''))
        self.parent_box['values'] = [''] + [
            jid for jid in sorted(jobs) if jid != self.job_id.get()]
        if self.job_id.get():
            self.select_job()
        else:
            self.draw_classes()
        mission = self.owner.mission()
        units = [u['id'] for u in self._mission()['units']]
        self.unit_box['values'] = units
        if self.unit_id.get() not in units or self.mission_id != mission:
            self.unit_id.set(units[0] if units else '')
            self.mission_id = mission
            if self.unit_id.get():
                self.select_unit()
        else:
            self.draw_map()
