"""Tk narrative storyboard: dialogue writing, conditional choices and rewards.

GameProject remains the source of truth; every edit is validated before
replacing its manifest and is undoable inside this tab.
"""
from copy import deepcopy

from . import story_authoring as edit
from .campaign import Campaign
from .model import RuleError
from .narrative import StoryBook


class StoryEditor:
    def __init__(self, studio, notebook):
        self.owner=studio
        self.tk,self.ttk=studio.tk,studio.ttk
        self.undo_stack=[]
        self.redo_stack=[]
        self.scene_id=''
        self.choice_id=''
        self._refreshing=False
        self._build(notebook)

    def _field(self, parent, row, label, default='', choices=None):
        return self.owner._field(parent,row,label,default,choices=choices,width=28)

    def _button(self, parent, name, operation):
        self.ttk.Button(parent,text=name,
                        command=lambda:self.owner._run(operation)).pack(side='left',padx=4,pady=4)

    def _build(self, notebook):
        ttk=self.ttk
        root=ttk.Frame(notebook)
        notebook.add(root,text='Scénario & dialogues')
        header=ttk.Frame(root);header.pack(fill='x',padx=8,pady=6)
        ttk.Label(header,text='Narration conditionnelle, sauvegardée avec la campagne.').pack(side='left')
        self._button(header,'Annuler scénario',self.undo)
        self._button(header,'Rétablir scénario',self.redo)
        self._button(header,'Aperçu interactif',self.preview)

        upper=ttk.Frame(root);upper.pack(fill='both',expand=True,padx=8)
        scenes=ttk.LabelFrame(upper,text='Scènes')
        scenes.pack(side='left',fill='both',expand=True,padx=5,pady=4)
        self.scene_list=self.tk.Listbox(scenes,height=9,exportselection=False)
        self.scene_list.pack(fill='x',padx=5,pady=5)
        self.scene_list.bind('<<ListboxSelect>>',self._select_scene)
        sf=ttk.Frame(scenes);sf.pack(fill='x')
        self.sid,_=self._field(sf,0,'Identifiant','new_scene')
        self.stitle,_=self._field(sf,1,'Titre','Nouvelle scène')
        self.sspeaker,_=self._field(sf,2,'Interlocuteur')
        ttk.Label(scenes,text='Dialogue').pack(anchor='w',padx=7)
        self.stext=self.tk.Text(scenes,height=6,wrap='word')
        self.stext.pack(fill='both',expand=True,padx=6,pady=4)
        controls=ttk.Frame(scenes);controls.pack(fill='x')
        self._button(controls,'Créer scène',self.create_scene)
        self._button(controls,'Appliquer texte',self.update_scene)
        self._button(controls,'Supprimer scène',self.delete_scene)

        choices=ttk.LabelFrame(upper,text='Choix & conséquences')
        choices.pack(side='left',fill='both',expand=True,padx=5,pady=4)
        self.choice_list=self.tk.Listbox(choices,height=9,exportselection=False)
        self.choice_list.pack(fill='x',padx=5,pady=5)
        self.choice_list.bind('<<ListboxSelect>>',self._select_choice)
        cf=ttk.Frame(choices);cf.pack(fill='x')
        self.cid,_=self._field(cf,0,'ID choix','choice')
        self.clabel,_=self._field(cf,1,'Texte bouton','Faire ce choix')
        self.condition,self.condition_box=self._field(cf,2,'Condition','toujours',
            choices=['toujours','flag =','flag ≥','mission terminée','or ≥','avancée (conservée)'])
        self.cond_flag,_=self._field(cf,3,'Flag / mission')
        self.cond_value,_=self._field(cf,4,'Valeur','true')
        self.cnext,self.cnext_box=self._field(cf,5,'Scène suivante',choices=[])
        cbuttons=ttk.Frame(choices);cbuttons.pack(fill='x')
        self._button(cbuttons,'Ajouter choix',self.add_choice)
        self._button(cbuttons,'Appliquer choix',self.update_choice)
        self._button(cbuttons,'Supprimer choix',self.delete_choice)

        effects=ttk.LabelFrame(choices,text='Ajouter une conséquence au choix sélectionné')
        effects.pack(fill='x',padx=5,pady=5)
        ef=ttk.Frame(effects);ef.pack(fill='x')
        self.effect,self.effect_box=self._field(ef,0,'Action','set_flag',
            choices=['set_flag','add_flag','unlock_mission','gold'])
        self.effect_key,_=self._field(ef,1,'Flag')
        self.effect_value,_=self._field(ef,2,'Valeur / montant','1')
        self.effect_mission,self.effect_mission_box=self._field(
            ef,3,'Mission à débloquer',choices=[])
        buttons=ttk.Frame(effects);buttons.pack(fill='x')
        self._button(buttons,'Ajouter conséquence',self.add_effect)
        self._button(buttons,'Supprimer dernière conséquence',self.remove_effect)
        self.effects_label=ttk.Label(effects,text='',wraplength=420,justify='left')
        self.effects_label.pack(anchor='w',padx=6,pady=4)

        routes=ttk.LabelFrame(root,text='Déclenchement : début de campagne / après victoire')
        routes.pack(fill='x',padx=10,pady=6)
        rf=ttk.Frame(routes);rf.pack(fill='x')
        self.entry_campaign,self.entry_campaign_box=self._field(rf,0,'Campagne',choices=[])
        self.entry_scene,self.entry_scene_box=self._field(rf,1,'Scène introductive',choices=[])
        self.after_mission,self.after_mission_box=self._field(rf,2,'Après victoire de',choices=[])
        self.after_scene,self.after_scene_box=self._field(rf,3,'Dialogue de conséquence',choices=[])
        line=ttk.Frame(routes);line.pack(fill='x')
        self._button(line,'Appliquer introduction',self.set_intro)
        self._button(line,'Appliquer suite de victoire',self.set_outcome)
        self._button(line,'Retirer introduction',lambda:self.set_intro(clear=True))
        self._button(line,'Retirer suite',lambda:self.set_outcome(clear=True))
        ttk.Label(routes,text='Sur une mission avec dialogue de victoire, seul le choix narratif débloque la suite (et non tous les liens classiques).',
                  wraplength=950).pack(anchor='w',padx=5,pady=3)

    def _project(self):
        return self.owner.project

    def _apply(self, operation):
        before=self._project()
        updated=operation(before,self.owner._content())
        self.undo_stack.append(deepcopy(before.to_dict()))
        self.undo_stack=self.undo_stack[-50:]
        self.redo_stack=[]
        self.owner.project=updated
        self.owner.project_status.config(text='Scénario modifié — enregistrer le projet de jeu.')
        self.refresh()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.owner.project.to_dict())
            previous=self.undo_stack.pop()
            from .game_project import GameProject
            self.owner.project=GameProject.from_dict(previous,self.owner._content())
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.owner.project.to_dict())
            following=self.redo_stack.pop()
            from .game_project import GameProject
            self.owner.project=GameProject.from_dict(following,self.owner._content())
            self.refresh()

    def _scenes(self):
        return self._project().story.get('scenes',[])

    def _selected(self):
        scene=next((s for s in self._scenes() if s['id']==self.scene_id),None)
        if scene is None:
            raise RuleError('Choisir une scène')
        return scene

    def _selected_choice(self):
        scene=self._selected()
        choice=next((c for c in scene['choices'] if c['id']==self.choice_id),None)
        if choice is None:
            raise RuleError('Choisir un choix')
        return choice

    def _set_dialogue(self,text):
        self.stext.delete('1.0','end')
        self.stext.insert('1.0',text)

    def _select_scene(self,_event=None):
        if self._refreshing or not self.scene_list.curselection():
            return
        self.scene_id=self.scene_list.get(self.scene_list.curselection()[0]).split('  — ',1)[0]
        scene=self._selected()
        self.sid.set(scene['id'])
        self.stitle.set(scene['title'])
        self.sspeaker.set(scene['speaker'])
        self._set_dialogue(scene['text'])
        self.choice_id=''
        self._choices()

    def _choices(self):
        self._refreshing=True
        scene=next((s for s in self._scenes() if s['id']==self.scene_id),None)
        self.choice_list.delete(0,'end')
        if scene is not None:
            for index,choice in enumerate(scene['choices']):
                self.choice_list.insert('end',choice['id']+'  — '+choice['label'])
                if choice['id']==self.choice_id:
                    self.choice_list.selection_set(index)
        self._refreshing=False
        self._display_effects()

    def _select_choice(self,_event=None):
        if self._refreshing or not self.choice_list.curselection():
            return
        self.choice_id=self.choice_list.get(self.choice_list.curselection()[0]).split('  — ',1)[0]
        choice=self._selected_choice()
        self.cid.set(choice['id'])
        self.clabel.set(choice['label'])
        self.cnext.set(choice.get('next_scene',''))
        when=choice.get('when')
        self.condition.set('toujours')
        self.cond_flag.set('')
        self.cond_value.set('true')
        if when:
            if 'flag' in when:
                self.condition.set('flag ≥' if 'gte' in when else 'flag =')
                self.cond_flag.set(when['flag'])
                self.cond_value.set(str(when.get('gte',when.get('eq'))).lower()
                                    if type(when.get('gte',when.get('eq'))) is bool
                                    else str(when.get('gte',when.get('eq'))))
            elif 'completed_mission' in when:
                self.condition.set('mission terminée')
                self.cond_flag.set(when['completed_mission'])
            elif 'gold_gte' in when:
                self.condition.set('or ≥')
                self.cond_value.set(str(when['gold_gte']))
            else:
                self.condition.set('avancée (conservée)')
        self._display_effects()

    def _display_effects(self):
        try:
            choice=self._selected_choice()
            effects=choice.get('effects',[])
            self.effects_label.config(text='\n'.join(str(effect) for effect in effects)
                                      if effects else 'Aucune conséquence.')
        except RuleError:
            self.effects_label.config(text='Sélectionner un choix.')

    def _condition(self):
        mode=self.condition.get()
        if mode=='toujours':
            return None
        if mode=='mission terminée':
            return {'completed_mission':self.cond_flag.get()}
        if mode=='or ≥':
            return {'gold_gte':int(self.cond_value.get())}
        if mode in ('flag =','flag ≥'):
            text=self.cond_value.get()
            value=(True if text=='true' else False if text=='false' else
                   int(text) if text.lstrip('-').isdigit() else text)
            return {'flag':self.cond_flag.get(),
                    'eq' if mode=='flag =' else 'gte':value}
        raise RuleError('Condition non reconnue')

    def create_scene(self):
        sid=self.sid.get()
        self._apply(lambda project,content:edit.create_scene(
            project,content,sid,self.stitle.get(),
            self.stext.get('1.0','end-1c') or 'Dialogue',self.sspeaker.get()))
        self._highlight_scene(sid)

    def update_scene(self):
        self._apply(lambda project,content:edit.update_scene(
            project,content,self.scene_id,title=self.stitle.get(),
            speaker=self.sspeaker.get(),text=self.stext.get('1.0','end-1c')))

    def delete_scene(self):
        deleted=self.scene_id
        self._apply(lambda project,content:edit.delete_scene(project,content,deleted))
        self.scene_id=''
        self.choice_id=''
        self.refresh()

    def add_choice(self):
        cid=self.cid.get()
        self._apply(lambda project,content:edit.add_choice(
            project,content,self.scene_id,cid,self.clabel.get(),
            when=self._condition(),next_scene=self.cnext.get()))
        self.choice_id=cid
        self._choices()

    def update_choice(self):
        condition = (None if self.condition.get()=='avancée (conservée)'
                     else self._condition())
        self._apply(lambda project,content:edit.update_choice(
            project,content,self.scene_id,self.choice_id,
            label=self.clabel.get(),when=condition,clear_condition=(
                self.condition.get()=='toujours'),next_scene=self.cnext.get()))

    def delete_choice(self):
        self._apply(lambda project,content:edit.remove_choice(
            project,content,self.scene_id,self.choice_id))
        self.choice_id=''
        self._choices()

    def _effect_spec(self):
        kind=self.effect.get()
        value=self.effect_value.get()
        if kind=='set_flag':
            typed=(True if value=='true' else False if value=='false' else
                   int(value) if value.lstrip('-').isdigit() else value)
            return {'kind':kind,'flag':self.effect_key.get(),'value':typed}
        if kind=='add_flag':
            return {'kind':kind,'flag':self.effect_key.get(),'amount':int(value)}
        if kind=='unlock_mission':
            return {'kind':kind,'mission':self.effect_mission.get()}
        if kind=='gold':
            return {'kind':kind,'amount':int(value)}
        raise RuleError('Conséquence inconnue')

    def add_effect(self):
        spec=self._effect_spec()
        self._apply(lambda project,content:edit.add_effect(
            project,content,self.scene_id,self.choice_id,spec))

    def remove_effect(self):
        effects=deepcopy(self._selected_choice().get('effects',[]))
        if not effects:
            raise RuleError('Aucune conséquence à supprimer')
        effects.pop()
        self._apply(lambda project,content:edit.update_choice(
            project,content,self.scene_id,self.choice_id,effects=effects))

    def set_intro(self,clear=False):
        self._apply(lambda project,content:edit.set_scene_entry(
            project,content,self.entry_campaign.get(),
            '' if clear else self.entry_scene.get()))

    def set_outcome(self,clear=False):
        self._apply(lambda project,content:edit.set_mission_outcome(
            project,content,self.after_mission.get(),
            '' if clear else self.after_scene.get()))

    def _highlight_scene(self,scene_id):
        for index,scene in enumerate(self._scenes()):
            if scene['id']==scene_id:
                self._refreshing=True
                self.scene_list.selection_clear(0,'end')
                self.scene_list.selection_set(index)
                self._refreshing=False
                self._select_scene()
                break

    def refresh(self):
        if self.owner.project is None:
            return
        scenes=self._scenes()
        scene_ids=[row['id'] for row in scenes]
        self._refreshing=True
        self.scene_list.delete(0,'end')
        for index,scene in enumerate(scenes):
            self.scene_list.insert('end',scene['id']+'  — '+scene['title'])
            if scene['id']==self.scene_id:
                self.scene_list.selection_set(index)
        self.cnext_box['values']=['',*scene_ids]
        self.entry_scene_box['values']=['',*scene_ids]
        self.after_scene_box['values']=['',*scene_ids]
        self.entry_campaign_box['values']=[row['id'] for row in self.owner.project.campaigns]
        self.after_mission_box['values']=[row['id'] for row in self.owner.doc().data['missions']]
        self.effect_mission_box['values']=[row['id'] for row in self.owner.doc().data['missions']]
        self._refreshing=False
        if self.scene_id and self.scene_id not in scene_ids:
            self.scene_id=''
            self.choice_id=''
        if self.scene_id:
            self._choices()
        if not self.entry_campaign.get() and self.owner.project.campaigns:
            self.entry_campaign.set(self.owner.project.campaigns[0]['id'])
        if not self.after_mission.get() and self.owner.doc().data['missions']:
            self.after_mission.set(self.owner.doc().data['missions'][0]['id'])
        if not self.effect_mission.get() and self.owner.doc().data['missions']:
            self.effect_mission.set(self.owner.doc().data['missions'][0]['id'])

    def reset_project(self):
        self.undo_stack=[]
        self.redo_stack=[]
        self.scene_id=''
        self.choice_id=''
        self.refresh()

    def preview(self):
        scene=self._selected()
        book=StoryBook(self._project().story,self.owner._content(),self._project().campaigns)
        campaign_id=self.entry_campaign.get() or self._project().campaigns[0]['id']
        progress=Campaign(unlocked=[self._project().campaign(campaign_id)['start_mission']])
        book.initialize(progress,campaign_id)
        progress.story_pending=scene['id']
        window=self.tk.Toplevel()
        window.title('Aperçu interactif des dialogues')
        window.geometry('620x460')
        def show():
            for child in window.winfo_children():
                child.destroy()
            current=book.active_scene(progress)
            if current is None:
                self.ttk.Label(window,text='Fin du dialogue.').pack(pady=30)
                self.ttk.Button(window,text='Fermer',command=window.destroy).pack(pady=10)
                return
            self.ttk.Label(window,text=current['title'],
                           font=('TkDefaultFont',18,'bold')).pack(pady=18)
            self.ttk.Label(window,text=current['speaker']).pack(pady=6)
            self.ttk.Label(window,text=current['text'],wraplength=560).pack(padx=20,pady=15)
            for choice in book.choices(progress):
                self.ttk.Button(window,text=choice['label'],
                                command=lambda cid=choice['id']:choose(cid)).pack(
                                    fill='x',padx=70,pady=5)
        def choose(cid):
            nonlocal progress
            progress=book.choose(progress,cid)
            show()
        show()
