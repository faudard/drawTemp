"""Tk authoring panels for units, interactables, events and whole-game setup.

Tk stays optional: importing gameplay without a display does not import it.
"""
from copy import deepcopy
import json
from pathlib import Path

from . import authoring
from .game_project import GameProject, load_slot, save_slot
from .model import Content, RuleError


class StudioPanels:
    def __init__(self, notebook, tk, ttk, dialogs, *, doc, content_path,
                 mission, selection, design_change, play_campaign, status):
        self.tk, self.ttk, self.dialogs = tk, ttk, dialogs
        self.doc, self.content_path = doc, content_path
        self.mission, self.selection = mission, selection
        self.design_change, self.play_campaign = design_change, play_campaign
        self.status = status
        self.project = None
        self.project_path = None
        self.project_saved = ''
        self.session = None
        self.session_campaign = ''
        self._entities_tab(notebook)
        self._project_tab(notebook)
        self.reload_project()
        self.refresh()

    def _field(self, parent, row, caption, value='', *, choices=None, width=22):
        ttk = self.ttk
        var = self.tk.StringVar(value=value)
        ttk.Label(parent, text=caption).grid(row=row, column=0, sticky='w', padx=6, pady=3)
        if choices is None:
            widget = ttk.Entry(parent, textvariable=var, width=width)
        else:
            widget = ttk.Combobox(parent, textvariable=var, state='readonly',
                                  values=choices, width=width)
        widget.grid(row=row, column=1, sticky='ew', padx=6, pady=3)
        return var, widget

    def _run(self, operation):
        try:
            operation()
        except (ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
            self.dialogs.showerror('Édition refusée', str(exc))

    def _change(self, operation):
        self.design_change(lambda: self.doc().replace(operation(self.doc().data, self.mission())))
        self.refresh()

    def _entities_tab(self, notebook):
        ttk = self.ttk
        outer = ttk.Frame(notebook)
        notebook.add(outer, text='Personnages et événements')
        ttk.Label(outer, text='Les coordonnées suivent la case sélectionnée sur la carte. Chaque modification est validée et annulable.').pack(anchor='w', padx=10, pady=8)
        self.cell_label = ttk.Label(outer, text='')
        self.cell_label.pack(anchor='w', padx=10)
        groups = ttk.Notebook(outer)
        groups.pack(fill='both', expand=True, padx=8, pady=8)

        units = ttk.Frame(groups)
        groups.add(units, text='Personnages / monstres')
        self.uid, _ = self._field(units, 0, 'Identifiant', 'new_actor')
        self.uname, _ = self._field(units, 1, 'Nom', 'Nouveau personnage')
        self.uteam, _ = self._field(units, 2, 'Équipe', 'enemy', choices=['player','enemy','neutral'])
        ttk.Button(units, text='Ajouter sur la case', command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.add_unit(
                d,m,self.uid.get(),self.uname.get(),self.uteam.get(),self.selection())))).grid(row=3,column=0,columnspan=2,pady=5)
        self.unit_list = self.tk.Listbox(units, height=8, exportselection=False)
        self.unit_list.grid(row=4,column=0,columnspan=2,sticky='nsew',padx=6,pady=4)
        ttk.Button(units,text='Supprimer le personnage sélectionné',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.remove_unit(d,m,self._selected(self.unit_list))))).grid(row=5,column=0,columnspan=2,pady=4)
        units.columnconfigure(1,weight=1); units.rowconfigure(4,weight=1)

        objects = ttk.Frame(groups)
        groups.add(objects, text='Objets interactifs')
        self.oid, _ = self._field(objects,0,'Identifiant','new_object')
        self.okind, _ = self._field(objects,1,'Type','chest',choices=['chest','door','switch','ram','catapult','passage','defense'])
        self.olink, _ = self._field(objects,2,'Porte liée (si besoin)')
        self.odest, _ = self._field(objects,3,'Destination passage (x,y)','0,0')
        ttk.Button(objects,text='Placer sur la carte',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.add_object(
                d,m,self.oid.get(),self.okind.get(),self.selection(),link=self.olink.get(),
                destination=self._destination())))).grid(row=4,column=0,columnspan=2,pady=5)
        self.object_list = self.tk.Listbox(objects, height=8, exportselection=False)
        self.object_list.grid(row=5,column=0,columnspan=2,sticky='nsew',padx=6,pady=4)
        ttk.Button(objects,text='Supprimer l’objet sélectionné',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.remove_object(d,m,self._selected(self.object_list))))).grid(row=6,column=0,columnspan=2,pady=4)
        objects.columnconfigure(1,weight=1); objects.rowconfigure(5,weight=1)

        events = ttk.Frame(groups)
        groups.add(events,text='Événements / triggers')
        self.eid, _ = self._field(events,0,'Identifiant','new_event')
        self.econdition, _ = self._field(events,1,'Condition','enter',choices=['enter','tick','defeated','hp_below'])
        self.eaction, _ = self._field(events,2,'Action','message',choices=['message','hazard'])
        self.etick, _ = self._field(events,3,'Tick ou quantité','10')
        self.eunit, _ = self._field(events,4,'Unité surveillée')
        self.etext, _ = self._field(events,5,'Message','Un événement survient.')
        ttk.Button(events,text='Créer événement sur la case',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.add_event(
                d,m,self.eid.get(),condition=self.econdition.get(),action=self.eaction.get(),
                pos=self.selection(),tick=int(self.etick.get()),unit=self.eunit.get(),
                text=self.etext.get(),amount=int(self.etick.get()))))).grid(row=6,column=0,columnspan=2,pady=5)
        self.event_list = self.tk.Listbox(events,height=8,exportselection=False)
        self.event_list.grid(row=7,column=0,columnspan=2,sticky='nsew',padx=6,pady=4)
        ttk.Button(events,text='Supprimer l’événement sélectionné',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.remove_event(d,m,self._selected(self.event_list))))).grid(row=8,column=0,columnspan=2,pady=4)
        events.columnconfigure(1,weight=1); events.rowconfigure(7,weight=1)

        resize = ttk.Frame(outer)
        resize.pack(fill='x',padx=10,pady=8)
        self.width = self.tk.StringVar(value='8')
        self.height = self.tk.StringVar(value='8')
        ttk.Label(resize,text='Taille carte').pack(side='left')
        ttk.Entry(resize,textvariable=self.width,width=5).pack(side='left',padx=3)
        ttk.Label(resize,text='×').pack(side='left')
        ttk.Entry(resize,textvariable=self.height,width=5).pack(side='left',padx=3)
        ttk.Button(resize,text='Redimensionner (sans perdre les entités)',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.resize_map(
                d,m,int(self.width.get()),int(self.height.get()))))).pack(side='left',padx=10)
        mission_form=ttk.LabelFrame(outer,text='Mission : titre, objectif et progression')
        mission_form.pack(fill='x',padx=10,pady=5)
        self.mission_name,_=self._field(mission_form,0,'Titre mission')
        self.objective,_=self._field(mission_form,1,'Objectif','eliminate',
            choices=['eliminate','survive','extract','hold','crown'])
        self.reward,_=self._field(mission_form,2,'Récompense','100')
        self.next_missions,_=self._field(mission_form,3,'Missions suivantes (id,id)')
        ttk.Button(mission_form,text='Appliquer la mission',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.set_mission_properties(
                d,m,name=self.mission_name.get(),objective=self.objective.get(),
                reward=int(self.reward.get()),
                next_missions=[s.strip() for s in self.next_missions.get().split(',') if s.strip()])))).grid(
                    row=4,column=0,columnspan=2,pady=5)
        mission_form.columnconfigure(1,weight=1)

    def _selected(self, listing):
        choices = listing.curselection()
        if not choices:
            raise RuleError('Sélectionnez un élément dans la liste')
        return listing.get(choices[0]).split('  —  ',1)[0]

    def _destination(self):
        values = self.odest.get().split(',')
        if len(values) != 2:
            raise RuleError('Destination: utiliser x,y')
        return [int(v.strip()) for v in values]

    def _project_tab(self, notebook):
        ttk = self.ttk
        outer=ttk.Frame(notebook)
        notebook.add(outer,text='Jeu, campagnes et sauvegardes')
        left=ttk.LabelFrame(outer,text='Écran titre et configuration')
        right=ttk.LabelFrame(outer,text='Campagnes / parties')
        left.pack(side='left',fill='both',expand=True,padx=8,pady=8)
        right.pack(side='left',fill='both',expand=True,padx=8,pady=8)
        self.title, _ = self._field(left,0,'Titre')
        self.subtitle, _ = self._field(left,1,'Sous-titre')
        self.language, _ = self._field(left,2,'Langue','fr',choices=['fr','en'])
        self.music, _ = self._field(left,3,'Musique (%)','70')
        self.effects, _ = self._field(left,4,'Effets (%)','70')
        self.slots, _ = self._field(left,5,'Emplacements','3')
        self.fullscreen=self.tk.BooleanVar(value=False)
        ttk.Checkbutton(left,text='Plein écran',variable=self.fullscreen).grid(row=6,column=0,columnspan=2,sticky='w',padx=6)
        ttk.Button(left,text='Appliquer configuration',command=lambda: self._run(self.apply_project)).grid(row=7,column=0,columnspan=2,pady=6)
        ttk.Button(left,text='Enregistrer projet de jeu…',command=lambda: self._run(self.save_project)).grid(row=8,column=0,columnspan=2,pady=6)
        ttk.Button(left,text='Aperçu écran titre',command=lambda: self._run(self.preview)).grid(row=9,column=0,columnspan=2,pady=6)
        left.columnconfigure(1,weight=1)

        self.campaign_id, cb = self._field(right,0,'Campagne','main',choices=[])
        cb.bind('<<ComboboxSelected>>',lambda _event: self._show_campaign())
        self.campaign_box=cb
        self.cname, _ = self._field(right,1,'Nom campagne')
        self.cdesc, _ = self._field(right,2,'Description')
        self.cstart, start_box = self._field(right,3,'Mission de départ',choices=[])
        self.start_box=start_box
        ttk.Button(right,text='Nouvelle campagne',command=lambda: self._run(self.add_campaign)).grid(row=4,column=0,pady=5)
        ttk.Button(right,text='Supprimer campagne',command=lambda: self._run(self.remove_campaign)).grid(row=4,column=1,pady=5)
        ttk.Button(right,text='Appliquer campagne',command=lambda: self._run(self.apply_project)).grid(row=5,column=0,columnspan=2,pady=4)
        self.slot, _ = self._field(right,6,'Slot (1 à 9)','1')
        ttk.Button(right,text='Nouvelle partie',command=lambda: self._run(self.new_game)).grid(row=7,column=0,pady=5)
        ttk.Button(right,text='Charger partie',command=lambda: self._run(self.load_game)).grid(row=7,column=1,pady=5)
        ttk.Button(right,text='Enregistrer partie',command=lambda: self._run(self.save_game)).grid(row=8,column=0,pady=5)
        ttk.Button(right,text='Jouer campagne',command=lambda: self._run(self.start_game)).grid(row=8,column=1,pady=5)
        self.project_status=ttk.Label(right,text='',wraplength=450)
        self.project_status.grid(row=9,column=0,columnspan=2,sticky='w',padx=8,pady=12)
        right.columnconfigure(1,weight=1)

    def _content(self):
        return Content.from_dict(self.doc().data)

    def _show_campaign(self):
        if self.project is None:
            return
        camp=self.project.campaign(self.campaign_id.get())
        if camp:
            self.cname.set(camp['name'])
            self.cdesc.set(camp['description'])
            self.cstart.set(camp['start_mission'])

    def reload_project(self):
        content=self._content()
        self.project_path=Path(self.content_path()).with_suffix('.game.json')
        self.project=(GameProject.load(self.project_path,content) if self.project_path.exists()
                      else GameProject.default(content))
        self.project_saved=json.dumps(self.project.to_dict(),sort_keys=True)
        self.session=None
        self.session_campaign=''
        self.title.set(self.project.title);self.subtitle.set(self.project.subtitle)
        self.language.set(self.project.options['language'])
        self.music.set(str(self.project.options['music_volume']))
        self.effects.set(str(self.project.options['effects_volume']))
        self.fullscreen.set(self.project.options['fullscreen'])
        self.slots.set(str(self.project.save_slots))
        self.campaign_id.set(self.project.campaigns[0]['id'])
        self._show_campaign()
        self.refresh()

    def _pending_fields(self):
        if self.project is None:
            return False
        c=self.project.campaign(self.campaign_id.get())
        if c is None:
            return False
        return any((self.title.get()!=self.project.title,
                    self.subtitle.get()!=self.project.subtitle,
                    self.language.get()!=self.project.options['language'],
                    self.music.get()!=str(self.project.options['music_volume']),
                    self.effects.get()!=str(self.project.options['effects_volume']),
                    self.slots.get()!=str(self.project.save_slots),
                    self.fullscreen.get()!=self.project.options['fullscreen'],
                    self.cname.get()!=c['name'],self.cdesc.get()!=c['description'],
                    self.cstart.get()!=c['start_mission']))

    def dirty(self):
        return (self._pending_fields() or
                json.dumps(self.project.to_dict(),sort_keys=True)!=self.project_saved)

    def apply_project(self):
        data=deepcopy(self.project.to_dict())
        data['title']=self.title.get()
        data['subtitle']=self.subtitle.get()
        data['options']={'language':self.language.get(),
                         'music_volume':int(self.music.get()),
                         'effects_volume':int(self.effects.get()),
                         'fullscreen':self.fullscreen.get()}
        data['save_slots']=int(self.slots.get())
        camp=next(c for c in data['campaigns'] if c['id']==self.campaign_id.get())
        camp.update(name=self.cname.get(),description=self.cdesc.get(),
                    start_mission=self.cstart.get())
        self.project=GameProject.from_dict(data,self._content())
        self.project_status.config(text='Configuration appliquée, projet non encore enregistré.')

    def add_campaign(self):
        self.apply_project()
        cid=self.dialogs.askstring('Nouvelle campagne','Identifiant unique (lettres/chiffres) :')
        if not cid:
            return
        data=deepcopy(self.project.to_dict())
        data['campaigns'].append({'id':cid,'name':cid,'description':'',
                                  'start_mission':self.mission()})
        self.project=GameProject.from_dict(data,self._content())
        self.campaign_id.set(cid);self._show_campaign();self.refresh()

    def remove_campaign(self):
        self.apply_project()
        cid=self.campaign_id.get()
        data=deepcopy(self.project.to_dict())
        data['campaigns']=[c for c in data['campaigns'] if c['id']!=cid]
        self.project=GameProject.from_dict(data,self._content())
        self.campaign_id.set(self.project.campaigns[0]['id'])
        self._show_campaign();self.refresh()

    def save_project(self):
        self.apply_project()
        filename=self.dialogs.asksaveasfilename(initialfile=self.project_path.name,
            defaultextension='.json',filetypes=[('Projet de jeu JSON','*.json')])
        if filename:
            self.project.save(filename,self._content())
            self.project_path=Path(filename)
            self.project_saved=json.dumps(self.project.to_dict(),sort_keys=True)
            self.project_status.config(text=f'Projet enregistré : {filename}')

    def new_game(self):
        self.apply_project()
        self.session=self.project.new_game(self.campaign_id.get(),self._content())
        self.session_campaign=self.campaign_id.get()
        self.project_status.config(text='Nouvelle campagne prête. Démarrer avec « Jouer campagne ».')
        self.refresh()

    def save_game(self):
        self.apply_project()
        if self.session is None or self.session_campaign!=self.campaign_id.get():
            raise RuleError('Créer ou charger une partie de cette campagne avant de sauvegarder')
        path=save_slot(self.project_path,self.project,self._content(),
                       self.session_campaign,int(self.slot.get()),self.session)
        self.project_status.config(text=f'Partie enregistrée dans {path}')

    def load_game(self):
        self.apply_project()
        self.session=load_slot(self.project_path,self.project,self._content(),
                               self.campaign_id.get(),int(self.slot.get()))
        self.session_campaign=self.campaign_id.get()
        self.project_status.config(text='Partie chargée. Progression et personnages restaurés.')

    def start_game(self):
        self.apply_project()
        if self.session is None or self.session_campaign!=self.campaign_id.get():
            self.new_game()
        mid=next((m for m in self.session.unlocked if m not in self.session.completed),
                 self.project.campaign(self.campaign_id.get())['start_mission'])
        self.play_campaign(self.session,mid)

    def preview(self):
        self.apply_project()
        window=self.tk.Toplevel()
        window.title('Aperçu — '+self.project.title)
        window.geometry('540x420')
        self.ttk.Label(window,text=self.project.title,font=('TkDefaultFont',24,'bold')).pack(pady=(35,12))
        self.ttk.Label(window,text=self.project.subtitle).pack(pady=(0,25))
        for label,callback in [('Nouvelle partie',self.new_game),
                               ('Continuer / jouer',self.start_game),
                               ('Charger',self.load_game)]:
            self.ttk.Button(window,text=label,command=lambda action=callback: self._run(action)).pack(fill='x',padx=140,pady=5)
        self.ttk.Button(window,text='Options',command=lambda:self.ttk.Label(
            window,text=f"Langue : {self.project.options['language']} | Musique : {self.project.options['music_volume']}%").pack()).pack(pady=5)
        self.ttk.Button(window,text='Quitter l’aperçu',command=window.destroy).pack(pady=7)

    def refresh(self):
        if self.project is None:
            return
        missions=self.doc().data['missions']
        chosen=next((m for m in missions if m['id']==self.mission()), missions[0])
        self.mission_name.set(chosen['name'])
        self.objective.set(chosen['objective'])
        self.reward.set(str(chosen['reward']))
        self.next_missions.set(', '.join(chosen.get('next_missions',[])))
        self.width.set(str(chosen['board']['width']))
        self.height.set(str(chosen['board']['height']))
        self.cell_label.config(text=f'Case choisie : {self.selection()} | Mission : {chosen["name"]}')
        for listing,items in ((self.unit_list,chosen['units']),
                              (self.object_list,chosen.get('objects',[])),
                              (self.event_list,chosen.get('triggers',[]))):
            listing.delete(0,'end')
            for item in items:
                listing.insert('end',f"{item['id']}  —  {item.get('name',item.get('kind',item.get('condition','')))}")
        self.start_box['values']=[m['id'] for m in missions]
        self.campaign_box['values']=[c['id'] for c in self.project.campaigns]
        if self.session is not None:
            self.project_status.config(text=f'Campagne active : {self.session_campaign} | Missions : {len(self.session.completed)} terminées | Or : {self.session.gold}')
