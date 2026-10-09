"""Advanced Tk Studio: campaign graph, actor catalogue and event blocks.

The module is presentation-only; edits go through validated, undoable
authoring transactions. No Tk import occurs outside the editor process.
"""
from copy import deepcopy
import json

from . import actor_catalog, campaign_graph, event_composer
from .model import RuleError


class AdvancedStudio:
    def __init__(self, studio, notebook):
        self.owner = studio
        self.tk, self.ttk = studio.tk, studio.ttk
        self.graph_nodes = {}
        self.blocks = []
        self._graph_tab(notebook)
        self._catalog_tab(notebook)
        self._events_tab(notebook)

    def _field(self, parent, row, title, default='', choices=None):
        return self.owner._field(parent, row, title, default, choices=choices)

    def _edit(self, fn):
        self.owner.design_change(lambda: self.owner.doc().replace(fn(self.owner.doc().data)))
        self.owner.refresh()

    def _protected(self, fn):
        self.owner._run(fn)

    def _graph_tab(self, notebook):
        ttk = self.ttk
        outer = ttk.Frame(notebook)
        notebook.add(outer, text='Graphe des missions')
        top = ttk.Frame(outer)
        top.pack(fill='x', padx=8, pady=8)
        self.from_var = self.tk.StringVar()
        self.to_var = self.tk.StringVar()
        ttk.Label(top, text='Départ').pack(side='left')
        self.from_box = ttk.Combobox(top, textvariable=self.from_var, width=16, state='readonly')
        self.from_box.pack(side='left', padx=5)
        ttk.Label(top, text='Arrivée').pack(side='left')
        self.to_box = ttk.Combobox(top, textvariable=self.to_var, width=16, state='readonly')
        self.to_box.pack(side='left', padx=5)
        ttk.Button(top, text='Relier →', command=lambda: self._protected(
            lambda: self._link(True))).pack(side='left', padx=4)
        ttk.Button(top, text='Retirer lien', command=lambda: self._protected(
            lambda: self._link(False))).pack(side='left')
        ttk.Button(top, text='Afficher mission', command=self._open_selected).pack(side='left', padx=5)
        frame = ttk.Frame(outer)
        frame.pack(fill='both', expand=True)
        self.graph_canvas = self.tk.Canvas(frame, background='#f7f7f7', height=420)
        xs = ttk.Scrollbar(frame, orient='horizontal', command=self.graph_canvas.xview)
        ys = ttk.Scrollbar(frame, orient='vertical', command=self.graph_canvas.yview)
        self.graph_canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        xs.pack(side='bottom', fill='x')
        ys.pack(side='right', fill='y')
        self.graph_canvas.pack(fill='both', expand=True)
        self.graph_canvas.bind('<Button-1>', self._click_graph)
        self.graph_info = self.tk.StringVar(value='')
        ttk.Label(outer, textvariable=self.graph_info, wraplength=1000).pack(fill='x', padx=8, pady=6)

    def _graph_analysis(self):
        content = self.owner._content()
        campaign = self.owner.project.campaign(self.owner.campaign_id.get())
        start = campaign['start_mission'] if campaign else next(iter(content.missions))
        return campaign_graph.inspect_graph(content, [start])

    def _link(self, enabled):
        origin, target = self.from_var.get(), self.to_var.get()
        self._edit(lambda data: campaign_graph.set_link(data, origin, target, enabled))

    def _open_selected(self):
        if self.from_var.get():
            self.owner.mission.set(self.from_var.get())
            self.owner.mission_change()

    def _click_graph(self, event):
        tag_ids = self.graph_canvas.gettags('current')
        chosen = next((tag[5:] for tag in tag_ids if tag.startswith('node_')), '')
        if not chosen:
            return
        if self.from_var.get() == chosen:
            self.to_var.set(chosen)
        else:
            self.from_var.set(chosen)
        self.draw_graph()

    def draw_graph(self):
        if self.owner.project is None:
            return
        graph = self._graph_analysis()
        canvas = self.graph_canvas
        canvas.delete('all')
        positions = graph['positions']
        blocked = set(graph['unreachable'])
        for source, target in graph['edges']:
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            canvas.create_line(x1 + 125, y1 + 26, x2, y2 + 26,
                               fill='#64748b', width=2, arrow='last',
                               smooth=True)
        for mid, (x,y) in positions.items():
            color = '#e7e7e7' if mid in blocked else '#dbeafe'
            if mid in graph['starts']:
                color='#bbf7d0'
            if mid == self.from_var.get():
                color='#fde68a'
            tag='node_'+mid
            canvas.create_rectangle(x,y,x+125,y+52,fill=color,outline='#475569',
                                    width=2,tags=(tag,))
            canvas.create_text(x+62,y+26,text=mid[:23],width=118,
                               tags=(tag,),font=('TkDefaultFont',10,'bold'))
        max_x=max((x for x,y in positions.values()),default=0)+240
        max_y=max((y for x,y in positions.values()),default=0)+140
        canvas.configure(scrollregion=(0,0,max(700,max_x),max(400,max_y)))
        cycles=[' → '.join(c) for c in graph['cycles']]
        self.graph_info.set(
            f"Campagne {self.owner.campaign_id.get()} : "
            f"{len(graph['reachable'])} accessibles, {len(blocked)} isolées. "
            f"Cycles : {', '.join(cycles) if cycles else 'aucun'}. "
            f"Isolées : {', '.join(graph['unreachable']) or 'aucune'}. "
            "Cliquer un nœud pour le sélectionner, puis choisir la destination.")

    def _catalog_tab(self, notebook):
        ttk=self.ttk
        outer=ttk.Frame(notebook)
        notebook.add(outer,text='Bibliothèque d’acteurs')
        ttk.Label(outer,text='Les archétypes sont réutilisables. Les unités déjà placées sont des instantanés indépendants.').pack(anchor='w',padx=8,pady=7)
        self.library_list=self.tk.Listbox(outer, height=7,exportselection=False)
        self.library_list.pack(fill='x',padx=8)
        form=ttk.Frame(outer)
        form.pack(fill='both',padx=8,pady=6)
        self.arch_id,_=self._field(form,0,'ID archétype','new_monster')
        self.arch_kind,_=self._field(form,1,'Type','monster',choices=['character','monster','summon'])
        self.arch_hp,_=self._field(form,2,'PV max','40')
        self.arch_attack,_=self._field(form,3,'Attaque','5')
        self.arch_speed,_=self._field(form,4,'Vitesse','10')
        self.arch_move,_=self._field(form,5,'Déplacement','4')
        self.arch_from,self.arch_from_box=self._field(form,6,'Copier unité existante',choices=[])
        self.arch_unit,_=self._field(form,7,'Nouvelle unité ID','catalog_actor')
        self.arch_name,_=self._field(form,8,'Nom de l’unité','Créature')
        self.arch_team,_=self._field(form,9,'Équipe','enemy',choices=['player','enemy'])
        buttons=ttk.Frame(outer)
        buttons.pack(fill='x',padx=8,pady=6)
        ttk.Button(buttons,text='Créer archétype',command=lambda:self._protected(self._create_actor)).pack(side='left',padx=3)
        ttk.Button(buttons,text='Capturer unité',command=lambda:self._protected(self._capture_actor)).pack(side='left',padx=3)
        ttk.Button(buttons,text='Placer sur carte',command=lambda:self._protected(self._place_actor)).pack(side='left',padx=3)
        ttk.Button(buttons,text='Supprimer archétype',command=lambda:self._protected(self._delete_actor)).pack(side='left',padx=3)

    def _selected_arch(self):
        selected=self.library_list.curselection()
        if selected:
            return self.library_list.get(selected[0]).split('  — ',1)[0]
        return self.arch_id.get()

    def _create_actor(self):
        self._edit(lambda data: actor_catalog.create_archetype(
            data,self.arch_id.get(),kind=self.arch_kind.get(),
            max_hp=int(self.arch_hp.get()),attack=int(self.arch_attack.get()),
            speed=int(self.arch_speed.get()),move=int(self.arch_move.get())))

    def _capture_actor(self):
        self._edit(lambda data: actor_catalog.capture_actor(
            data,self.owner.mission(),self.arch_from.get(),self.arch_id.get()))

    def _place_actor(self):
        self._edit(lambda data: actor_catalog.place_archetype(
            data,self.owner.mission(),self._selected_arch(),self.arch_unit.get(),
            self.arch_name.get(),self.arch_team.get(),self.owner.selection()))

    def _delete_actor(self):
        self._edit(lambda data: actor_catalog.remove_archetype(data,self._selected_arch()))

    def _events_tab(self,notebook):
        ttk=self.ttk
        outer=ttk.Frame(notebook)
        notebook.add(outer,text='Événements par blocs')
        ttk.Label(outer,text='Composer des conditions et plusieurs actions séquentielles, puis valider en une opération.').pack(anchor='w',padx=8,pady=6)
        form=ttk.Frame(outer);form.pack(fill='x',padx=8)
        self.event_id,self.event_box=self._field(form,0,'ID événement','new_script',choices=[])
        self.event_box['state']='normal'
        self.event_box.bind('<<ComboboxSelected>>',lambda e:self._load_event())
        self.cond_kind,_=self._field(form,1,'Condition','enter',choices=['tick','enter','defeated','hp_below'])
        self.cond_value,_=self._field(form,2,'Tick / % PV','20')
        self.cond_unit,self.cond_unit_box=self._field(form,3,'Unité surveillée',choices=[])
        self.action_kind,_=self._field(form,4,'Nouvelle action','message',
                                         choices=['message','hazard','status','spawn','despawn'])
        self.action_text,_=self._field(form,5,'Texte / Nom spawn','Événement')
        self.action_value,_=self._field(form,6,'Puissance / Durée','4')
        self.action_unit,_=self._field(form,7,'Unité / ID spawn')
        self.action_status,self.action_status_box=self._field(form,8,'Statut / archétype',choices=[])
        self.action_team,_=self._field(form,9,'Camp spawn','enemy',choices=['player','enemy'])
        self.event_pos,_=self._field(form,10,'Position événement (x,y)','0,0')
        ttk.Button(form,text='Case sélectionnée',command=lambda:self.event_pos.set(
            ','.join(str(c) for c in self.owner.selection()))).grid(row=10,column=2,padx=4)
        ttk.Label(outer,text='Actions (dans l’ordre d’exécution)').pack(anchor='w',padx=8,pady=(7,0))
        self.blocks_list=self.tk.Listbox(outer,height=7,exportselection=False)
        self.blocks_list.pack(fill='both',expand=True,padx=8,pady=3)
        controls=ttk.Frame(outer);controls.pack(fill='x',padx=8,pady=7)
        for label,fn in [('Ajouter bloc',self._add_block),
                         ('Supprimer bloc',self._remove_block),
                         ('↑',lambda:self._move_block(-1)),
                         ('↓',lambda:self._move_block(1)),
                         ('Valider événement',self._save_event)]:
            ttk.Button(controls,text=label,command=lambda task=fn:self._protected(task)).pack(side='left',padx=3)

    def _read_action(self):
        kind=self.action_kind.get()
        params={'pos':self.owner.selection(),'text':self.action_text.get(),
                'name':self.action_text.get(),'actor_id':self.action_unit.get(),
                'archetype':self.action_status.get(),'team':self.action_team.get(),
                'unit':self.action_unit.get(),'status':self.action_status.get()}
        if kind in ('hazard','status'):
            params['amount']=int(self.action_value.get())
            params['duration']=int(self.action_value.get())
        return event_composer.action(kind,**params)

    def _add_block(self):
        self.blocks.append(self._read_action())
        self._render_blocks()

    def _selected_block(self):
        selections=self.blocks_list.curselection()
        if not selections:
            raise RuleError('Sélectionner un bloc')
        return selections[0]

    def _remove_block(self):
        del self.blocks[self._selected_block()]
        self._render_blocks()

    def _move_block(self, offset):
        index=self._selected_block()
        self.blocks=event_composer.move_action(self.blocks,index,offset)
        self._render_blocks()
        self.blocks_list.selection_set(index+offset)

    def _render_blocks(self):
        self.blocks_list.delete(0,'end')
        for index,action in enumerate(self.blocks):
            self.blocks_list.insert('end',f"{index+1}. {action['kind']} — "+json.dumps(
                {k:v for k,v in action.items() if k!='kind'},ensure_ascii=False))

    def _load_event(self):
        mission=next(m for m in self.owner.doc().data['missions'] if m['id']==self.owner.mission())
        trigger=next((t for t in mission.get('triggers',[]) if t['id']==self.event_id.get()),None)
        if trigger is None:
            self.blocks=[]
            self._render_blocks()
            return
        self.cond_kind.set(trigger['condition'])
        self.cond_value.set(str(trigger.get('value',trigger.get('percent',20))))
        self.cond_unit.set(trigger.get('unit',''))
        self.event_pos.set(','.join(str(v) for v in trigger.get('pos',self.owner.selection())))
        self.blocks=deepcopy(trigger['actions'])
        self._render_blocks()

    def _save_event(self):
        kind=self.cond_kind.get()
        position=self.owner.selection()
        if kind=='enter':
            position=[int(x.strip()) for x in self.event_pos.get().split(',')]
            if len(position)!=2:
                raise RuleError('Position de déclencheur : saisir x,y')
        spec=event_composer.condition(kind,pos=position,
                                      tick=int(self.cond_value.get()),
                                      unit=self.cond_unit.get(),
                                      percent=int(self.cond_value.get()))
        self._edit(lambda data: event_composer.save_event(
            data,self.owner.mission(),self.event_id.get(),spec,self.blocks))

    def refresh(self):
        if self.owner.project is None:
            return
        data=self.owner.doc().data
        missions=data['missions']
        ids=[mission['id'] for mission in missions]
        self.from_box['values']=ids
        self.to_box['values']=ids
        if self.from_var.get() not in ids:
            self.from_var.set(self.owner.mission())
        if self.to_var.get() not in ids:
            self.to_var.set(ids[min(1,len(ids)-1)])
        current=next(m for m in missions if m['id']==self.owner.mission())
        actor_ids=[unit['id'] for unit in current['units']]
        self.arch_from_box['values']=actor_ids
        if self.arch_from.get() not in actor_ids:
            self.arch_from.set(actor_ids[0] if actor_ids else '')
        self.cond_unit_box['values']=actor_ids
        self.cond_unit.set(self.cond_unit.get() if self.cond_unit.get() in actor_ids else (actor_ids[0] if actor_ids else ''))
        status_choices=['haste','poison','slow','protect','regen',*data.get('archetypes',{})]
        self.action_status_box['values']=status_choices
        self.action_status.set(self.action_status.get() if self.action_status.get() in status_choices else status_choices[0])
        # Combobox entry may be a new event name: preserve it.
        self.event_box['values']=[row['id'] for row in current.get('triggers',[])]
        self.library_list.delete(0,'end')
        for name,definition in sorted(data.get('archetypes',{}).items()):
            self.library_list.insert('end',f"{name}  — {definition.get('kind','character')}")
        self.draw_graph()
