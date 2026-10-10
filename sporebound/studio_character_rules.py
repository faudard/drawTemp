"""Tk Character & Rules Studio 2.5.3.

Five guided panels share the Content document and the existing Document
undo/redo stack. No gameplay import or secondary mutable actor registry.
"""
from . import actor_catalog, character_authoring as edit
from .model import REACTIONS, SUPPORTS, MOVEMENTS, RuleError
from .rules import default_rules


class CharacterRulesStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self._loading = False
        self.last_mission = ''
        page = self.ttk.Frame(notebook)
        notebook.add(page, text='Personnages & règles 3.0')
        self.page = page
        self.tabs = self.ttk.Notebook(page)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=6)
        self._units_tab()
        self._archetypes_tab()
        self._skills_tab()
        self._jobs_tab()
        self._equipment_tab()
        from .studio_class_ai import ClassAIStudio
        self.class_ai = ClassAIStudio(self, self.tabs)
        self.status = self.tk.StringVar(value='Édits vérifiés et annulables par le Studio.')
        self.ttk.Label(page, textvariable=self.status, wraplength=1000).pack(
            fill='x', padx=8, pady=4)

    def _field(self, parent, label, *, default='', values=None, editable=False, row=0, col=0, width=24):
        ttk = self.ttk
        variable = self.tk.StringVar(value=default)
        ttk.Label(parent, text=label).grid(row=row, column=col*2,
                                           sticky='w', padx=5, pady=3)
        if values is not None:
            control = ttk.Combobox(parent, textvariable=variable, width=width,
                                   state='normal' if editable else 'readonly', values=values)
        else:
            control = ttk.Entry(parent, textvariable=variable, width=width)
        control.grid(row=row, column=col*2+1, sticky='ew', padx=5, pady=3)
        parent.grid_columnconfigure(col*2+1, weight=1)
        return variable, control

    def _button(self, parent, label, callback):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.owner._run(callback)).pack(
                            side='left', padx=3, pady=4)

    def _apply(self, operation):
        self.owner.design_change(
            lambda: self.owner.doc().replace(operation(self.owner.doc().data)))
        self.owner.refresh()

    def _data(self):
        return self.owner.doc().data

    def _mission(self):
        return next(m for m in self._data()['missions']
                    if m['id'] == self.owner.mission())

    @staticmethod
    def _ids(value):
        return [token.strip() for token in value.split(',') if token.strip()]

    def _units_tab(self):
        ttk = self.ttk
        page = ttk.Frame(self.tabs)
        self.tabs.add(page, text='Héros / monstres')
        header = ttk.Frame(page)
        header.pack(fill='x', padx=7, pady=6)
        ttk.Label(header, text='Personnage placé dans la mission courante :').pack(side='left')
        self.unit_id = self.tk.StringVar()
        self.unit_box = ttk.Combobox(header, textvariable=self.unit_id,
                                    state='readonly', width=24)
        self.unit_box.pack(side='left', padx=4)
        self.unit_box.bind('<<ComboboxSelected>>', lambda e: self._load_unit())
        form = ttk.LabelFrame(page, text='Instance de mission (pas les autres occurrences)')
        form.pack(fill='x', padx=8, pady=6)
        self.u_name, _ = self._field(form, 'Nom', row=0)
        self.u_kind, _ = self._field(form, 'Type', default='character',
                                      values=['character', 'monster', 'summon'], row=0, col=1)
        self.u_team, _ = self._field(form, 'Camp', default='player',
                                      values=['player', 'enemy'], row=1)
        self.u_weapon, _ = self._field(form, 'Arme', default='melee',
                                        values=['melee', 'spear', 'ranged', 'focus', 'unarmed'], row=1, col=1)
        self.u_hp, _ = self._field(form, 'PV max', row=2)
        self.u_mp, _ = self._field(form, 'PM max', row=2, col=1)
        self.u_attack, _ = self._field(form, 'Attaque', row=3)
        self.u_magic, _ = self._field(form, 'Magie', row=3, col=1)
        self.u_speed, _ = self._field(form, 'Vitesse', row=4)
        self.u_move, _ = self._field(form, 'Mouvement', row=4, col=1)
        self.u_defense, _ = self._field(form, 'Défense', row=5)
        self.u_mdef, _ = self._field(form, 'Défense magique', row=5, col=1)
        self.u_reaction, _ = self._field(form, 'Réaction', default='none',
                                          values=sorted(REACTIONS), row=6)
        self.u_support, _ = self._field(form, 'Support', default='none',
                                         values=sorted(SUPPORTS), row=6, col=1)
        self.u_movement, _ = self._field(form, 'Passif mouvement', default='none',
                                          values=sorted(MOVEMENTS), row=7)
        self.u_behavior, self.u_behavior_box = self._field(
            form, 'Profil IA', default='tactical', values=['tactical', 'patrol'],
            row=7, col=1)
        self.u_skills, _ = self._field(form, 'Compétences (IDs séparés par ,)', row=8)
        self.u_tactics, _ = self._field(form, 'Synergies (IDs séparés par ,)', row=8, col=1)
        buttons = ttk.Frame(page)
        buttons.pack(fill='x', padx=7)
        self._button(buttons, 'Appliquer personnage', self.save_unit)
        ttk.Label(page, text='Positions / empreintes / routes de patrouille : éditeur de carte. '
                  'Le modèle est vérifié avant chaque commit.', wraplength=900).pack(
                      anchor='w', padx=9, pady=6)

    def _load_unit(self):
        unit = next((u for u in self._mission()['units']
                     if u['id'] == self.unit_id.get()), None)
        if unit is None:
            return
        values = {'name': self.u_name, 'kind': self.u_kind, 'team': self.u_team,
                  'weapon': self.u_weapon, 'max_hp': self.u_hp, 'max_mp': self.u_mp,
                  'attack': self.u_attack, 'magic': self.u_magic,
                  'speed': self.u_speed, 'move': self.u_move,
                  'defense': self.u_defense, 'magic_defense': self.u_mdef,
                  'reaction': self.u_reaction, 'support': self.u_support,
                  'movement': self.u_movement, 'behavior': self.u_behavior}
        for key, var in values.items():
            var.set(str(unit.get(key, '')))
        self.u_skills.set(', '.join(unit.get('skills', [])))
        self.u_tactics.set(', '.join(unit.get('tactics', [])))

    def save_unit(self):
        mid, uid = self.owner.mission(), self.unit_id.get()
        changes = dict(name=self.u_name.get(), kind=self.u_kind.get(),
                       team=self.u_team.get(), weapon=self.u_weapon.get(),
                       max_hp=int(self.u_hp.get()), max_mp=int(self.u_mp.get()),
                       attack=int(self.u_attack.get()), magic=int(self.u_magic.get()),
                       speed=int(self.u_speed.get()), move=int(self.u_move.get()),
                       defense=int(self.u_defense.get()),
                       magic_defense=int(self.u_mdef.get()),
                       reaction=self.u_reaction.get(), support=self.u_support.get(),
                       movement=self.u_movement.get(), behavior=self.u_behavior.get(),
                       skills=self._ids(self.u_skills.get()),
                       tactics=self._ids(self.u_tactics.get()))
        self._apply(lambda data: edit.update_mission_unit(data, mid, uid, **changes))
        self.status.set('Personnage mis à jour sur la mission '+mid+' uniquement.')

    def _archetypes_tab(self):
        page = self.ttk.Frame(self.tabs)
        self.tabs.add(page, text='Archétypes')
        header = self.ttk.Frame(page)
        header.pack(fill='x', padx=8, pady=7)
        self.a_id, self.a_box = self._field(header, 'Modèle', row=0, values=[], editable=True)
        self.a_box.bind('<<ComboboxSelected>>', lambda e: self._load_archetype())
        form = self.ttk.LabelFrame(page, text='Fiche de modèle réutilisable')
        form.pack(fill='x', padx=8, pady=5)
        self.a_kind, _ = self._field(form, 'Type', default='monster',
                                      values=['character', 'monster', 'summon'], row=0)
        self.a_weapon, _ = self._field(form, 'Arme', default='melee',
                                        values=['melee', 'spear', 'ranged', 'focus', 'unarmed'],
                                        row=0, col=1)
        self.a_hp, _ = self._field(form, 'PV max', default='40', row=1)
        self.a_attack, _ = self._field(form, 'Attaque', default='5', row=1, col=1)
        self.a_speed, _ = self._field(form, 'Vitesse', default='10', row=2)
        self.a_move, _ = self._field(form, 'Mouvement', default='4', row=2, col=1)
        self.a_skills, _ = self._field(form, 'Compétences (IDs)', row=3)
        self.a_reaction, _ = self._field(form, 'Réaction', default='none',
                                          values=sorted(REACTIONS), row=3, col=1)
        self.a_behavior, _ = self._field(form, 'IA', default='tactical',
                                          values=['tactical', 'patrol'], row=4)
        buttons = self.ttk.Frame(page)
        buttons.pack(fill='x', padx=8)
        self._button(buttons, 'Créer modèle', self.create_archetype)
        self._button(buttons, 'Modifier modèle', self.save_archetype)
        self._button(buttons, 'Supprimer modèle', self.delete_archetype)
        self.ttk.Label(page, text='Un archétype modifié ne rétroagit pas sur '
                       'les combattants déjà placés.', wraplength=930).pack(
                           anchor='w', padx=8, pady=8)

    def _load_archetype(self):
        data = self._data().get('archetypes', {}).get(self.a_id.get())
        if data is None:
            return
        for key, var in (('kind', self.a_kind), ('weapon', self.a_weapon),
                         ('max_hp', self.a_hp), ('attack', self.a_attack),
                         ('speed', self.a_speed), ('move', self.a_move),
                         ('reaction', self.a_reaction), ('behavior', self.a_behavior)):
            var.set(str(data.get(key, {'kind': 'character', 'weapon': 'melee',
                                       'max_hp': 40, 'attack': 5, 'speed': 10,
                                       'move': 4, 'reaction': 'none',
                                       'behavior': 'tactical'}[key])))
        self.a_skills.set(', '.join(data.get('skills', [])))

    def create_archetype(self):
        aid = self.a_id.get()
        self._apply(lambda data: actor_catalog.create_archetype(
            data, aid, kind=self.a_kind.get(), max_hp=int(self.a_hp.get()),
            attack=int(self.a_attack.get()), speed=int(self.a_speed.get()),
            move=int(self.a_move.get()), weapon=self.a_weapon.get(),
            skills=self._ids(self.a_skills.get())))
        self.a_id.set(aid)

    def save_archetype(self):
        aid = self.a_id.get()
        changes = dict(kind=self.a_kind.get(), weapon=self.a_weapon.get(),
                       max_hp=int(self.a_hp.get()), attack=int(self.a_attack.get()),
                       speed=int(self.a_speed.get()), move=int(self.a_move.get()),
                       reaction=self.a_reaction.get(), behavior=self.a_behavior.get(),
                       skills=self._ids(self.a_skills.get()))
        self._apply(lambda data: edit.update_archetype(data, aid, **changes))

    def delete_archetype(self):
        self._apply(lambda data: actor_catalog.remove_archetype(data, self.a_id.get()))

    def _skills_tab(self):
        page = self.ttk.Frame(self.tabs)
        self.tabs.add(page, text='Compétences')
        header = self.ttk.Frame(page)
        header.pack(fill='x', padx=7, pady=5)
        self.s_id, self.s_box = self._field(header, 'Compétence / nouvel ID', row=0, values=[], editable=True)
        self.s_box.bind('<<ComboboxSelected>>', lambda e: self._load_skill())
        form = self.ttk.LabelFrame(page, text='Paramètres de la compétence')
        form.pack(fill='x', padx=8, pady=4)
        self.s_name, _ = self._field(form, 'Nom', default='Nouvelle compétence', row=0)
        self.s_cost, _ = self._field(form, 'Coût MP', default='0', row=0, col=1)
        self.s_range, _ = self._field(form, 'Portée maxi', default='1', row=1)
        self.s_min, _ = self._field(form, 'Portée mini', default='0', row=1, col=1)
        self.s_radius, _ = self._field(form, 'Rayon de zone', default='0', row=2)
        self.s_accuracy, _ = self._field(form, 'Précision (%)', default='100', row=2, col=1)
        self.s_target, _ = self._field(form, 'Cible', default='enemy',
            values=['enemy', 'ally', 'unit', 'self', 'ground', 'downed'], row=3)
        self.s_shape, _ = self._field(form, 'Forme', default='diamond',
            values=['diamond', 'cross', 'square'], row=3, col=1)
        self.s_magical = self.tk.BooleanVar(value=False)
        self.ttk.Checkbutton(form, text='Sort magique', variable=self.s_magical).grid(
            row=4, column=0, sticky='w', padx=5, pady=3)
        effectframe = self.ttk.LabelFrame(page, text='Effets ordonnés')
        effectframe.pack(fill='both', expand=True, padx=8, pady=4)
        self.effects = self.tk.Listbox(effectframe, height=6, exportselection=False)
        self.effects.pack(fill='x', padx=7, pady=4)
        self.effects.bind('<<ListboxSelect>>', lambda e: self._load_effect())
        ef = self.ttk.Frame(effectframe)
        ef.pack(fill='x')
        self.e_kind, _ = self._field(ef, 'Type effet', default='damage',
            values=['damage','heal','revive','status','cleanse','mp','push','pull','zone'], row=0)
        self.e_power, _ = self._field(ef, 'Puissance', default='5', row=0, col=1)
        self.e_status, _ = self._field(ef, 'Statut', default='haste', row=1)
        self.e_duration, _ = self._field(ef, 'Durée', default='24', row=1, col=1)
        self.e_element, _ = self._field(ef, 'Élément', default='physical', row=2)
        self.e_scope, _ = self._field(ef, 'Zone', default='target',
            values=['target','allies','enemies','all'], row=2, col=1)
        buttons = self.ttk.Frame(effectframe)
        buttons.pack(fill='x', padx=8)
        self._button(buttons, 'Ajouter effet', self.add_effect)
        self._button(buttons, 'Remplacer effet', self.replace_effect)
        self._button(buttons, 'Supprimer effet', self.delete_effect)
        self._button(buttons, '↑', lambda: self.move_effect(-1))
        self._button(buttons, '↓', lambda: self.move_effect(1))
        foot = self.ttk.Frame(page)
        foot.pack(fill='x', padx=7)
        self._button(foot, 'Créer compétence', self.create_skill)
        self._button(foot, 'Appliquer compétence', self.save_skill)
        self._button(foot, 'Supprimer compétence', self.delete_skill)

    def _selected_effect(self):
        selected = self.effects.curselection()
        if not selected:
            raise RuleError('Sélectionner un effet')
        return selected[0]

    def _get_skill(self):
        return next((row for row in self._data()['skills']
                     if row['id'] == self.s_id.get()), None)

    def _load_skill(self):
        item = self._get_skill()
        if item is None:
            return
        for key, var in (('name',self.s_name),('cost',self.s_cost),
                         ('range',self.s_range),('min_range',self.s_min),
                         ('radius',self.s_radius),('accuracy',self.s_accuracy),
                         ('target',self.s_target),('shape',self.s_shape)):
            var.set(str(item.get(key, {'min_range':0, 'radius':0, 'accuracy':100,
                                        'cost':0,'target':'enemy','shape':'diamond'} .get(key,''))))
        self.s_magical.set(bool(item.get('magical',False)))
        self._render_effects()

    def _render_effects(self):
        item = self._get_skill()
        self.effects.delete(0, 'end')
        if item is not None:
            for i, effect in enumerate(item['effects']):
                self.effects.insert('end', f"{i+1}. {effect['kind']} | "
                                    f"{effect.get('power',0)} | "
                                    f"{effect.get('status','')}")

    def _load_effect(self):
        item = self._get_skill()
        if item is None or not self.effects.curselection():
            return
        effect = item['effects'][self.effects.curselection()[0]]
        for key, var in (('kind',self.e_kind),('power',self.e_power),
                         ('status',self.e_status),('duration',self.e_duration),
                         ('element',self.e_element),('scope',self.e_scope)):
            var.set(str(effect.get(key, {'power':1,'status':'','duration':24,
                                         'element':'physical','scope':'target'}.get(key,''))))

    def _effect_data(self):
        return edit.make_effect(self.e_kind.get(), power=int(self.e_power.get()),
                                status=self.e_status.get(),
                                duration=int(self.e_duration.get()),
                                element=self.e_element.get(), scope=self.e_scope.get())

    def create_skill(self):
        sid = self.s_id.get()
        self._apply(lambda data: edit.create_skill(
            data, sid, self.s_name.get(), effect=self._effect_data(),
            target=self.s_target.get(), range=int(self.s_range.get()),
            cost=int(self.s_cost.get())))
        self.s_id.set(sid)
        self._load_skill()

    def save_skill(self):
        sid = self.s_id.get()
        self._apply(lambda data: edit.update_skill(
            data, sid, name=self.s_name.get(), cost=int(self.s_cost.get()),
            range=int(self.s_range.get()), min_range=int(self.s_min.get()),
            radius=int(self.s_radius.get()), accuracy=int(self.s_accuracy.get()),
            target=self.s_target.get(), shape=self.s_shape.get(),
            magical=bool(self.s_magical.get())))

    def delete_skill(self):
        self._apply(lambda data: edit.remove_skill(data, self.s_id.get()))

    def add_effect(self):
        sid = self.s_id.get()
        self._apply(lambda data: edit.set_skill_effect(
            data, sid, len(self._get_skill()['effects']), self._effect_data(),
            insert=True))

    def replace_effect(self):
        sid, index = self.s_id.get(), self._selected_effect()
        self._apply(lambda data: edit.set_skill_effect(
            data, sid, index, self._effect_data()))

    def delete_effect(self):
        sid, index = self.s_id.get(), self._selected_effect()
        self._apply(lambda data: edit.remove_skill_effect(data, sid, index))

    def move_effect(self, direction):
        sid, index = self.s_id.get(), self._selected_effect()
        self._apply(lambda data: edit.move_skill_effect(data, sid, index, direction))
        self.effects.selection_set(index+direction)

    def _jobs_tab(self):
        page = self.ttk.Frame(self.tabs)
        self.jobs_tab = page
        self.tabs.add(page, text='Classes')
        self.j_id, self.j_box = self._field(page, 'Classe / nouvel ID', row=0, values=[], editable=True)
        self.j_box.bind('<<ComboboxSelected>>', lambda e: self._load_job())
        self.j_name, _ = self._field(page, 'Nom', default='Nouvelle classe', row=1)
        self.j_requires, self.j_requires_box = self._field(
            page, 'Classe préalable', default='', values=[''], row=2)
        self.j_level, _ = self._field(page, 'Niveau requis', default='1', row=3)
        self.j_bonuses, _ = self._field(page, 'Bonus stat=nombre, …', row=4)
        self.j_skills, _ = self._field(page, 'Sort=niveau, …', row=5)
        row = self.ttk.Frame(page)
        row.grid(row=6, column=0, columnspan=2, sticky='w', padx=7, pady=4)
        self._button(row, 'Créer classe', self.create_job)
        self._button(row, 'Modifier classe', self.save_job)
        self._button(row, 'Supprimer classe', self.delete_job)
        self.ttk.Label(page, text='Exemple : max_hp=10, defense=2 et heal=3. '
                       'Une classe requise par une autre ne peut être supprimée.',
                       wraplength=950).grid(row=7, column=0, columnspan=2,
                                            sticky='w', padx=8, pady=7)

    def _load_job(self):
        job = self._data().get('jobs', {}).get(self.j_id.get())
        if job is None:
            return
        self.j_name.set(job.get('name',''))
        self.j_requires.set(job.get('requires',''))
        self.j_level.set(str(job.get('requires_level',1)))
        self.j_bonuses.set(', '.join(f'{k}={v}' for k,v in job.get('bonuses',{}).items()))
        self.j_skills.set(', '.join(f'{k}={v}' for k,v in job.get('skills',{}).items()))

    def _job_data(self):
        skills = (s['id'] for s in self._data()['skills'])
        return dict(name=self.j_name.get(), requires=self.j_requires.get(),
                    requires_level=int(self.j_level.get()),
                    bonuses=edit.parse_bonuses(self.j_bonuses.get()),
                    skills=edit.parse_skill_levels(self.j_skills.get(), skills))

    def create_job(self):
        jid, params = self.j_id.get(), self._job_data()
        self._apply(lambda data: edit.create_job(data, jid, **params))
        self.j_id.set(jid)

    def save_job(self):
        jid, params = self.j_id.get(), self._job_data()
        self._apply(lambda data: edit.update_job(data, jid, **params))

    def delete_job(self):
        self._apply(lambda data: edit.remove_job(data, self.j_id.get()))

    def _equipment_tab(self):
        page = self.ttk.Frame(self.tabs)
        self.tabs.add(page, text='Équipement')
        self.i_id, self.i_box = self._field(page, 'Objet / nouvel ID', row=0, values=[], editable=True)
        self.i_box.bind('<<ComboboxSelected>>', lambda e: self._load_item())
        self.i_name, _ = self._field(page, 'Nom', default='Nouvel équipement', row=1)
        self.i_slot, _ = self._field(page, 'Emplacement', default='weapon',
                                      values=['weapon','armor','accessory'], row=2)
        self.i_price, _ = self._field(page, 'Prix', default='50', row=3)
        self.i_bonuses, _ = self._field(page, 'Bonus stat=nombre, …', row=4)
        row = self.ttk.Frame(page)
        row.grid(row=5, column=0, columnspan=2, sticky='w', padx=7)
        self._button(row, 'Créer équipement', self.create_item)
        self._button(row, 'Modifier équipement', self.save_item)
        self._button(row, 'Supprimer équipement', self.delete_item)
        self.ttk.Label(page, text='Exemple : weapon_power=2, attack=3. '
                       'Les équipements utilisent les propriétés déjà reconnues '
                       'par le moteur.', wraplength=950).grid(
                           row=6, column=0, columnspan=2, sticky='w', padx=8, pady=7)

    def _load_item(self):
        item = self._data().get('equipment', {}).get(self.i_id.get())
        if item is None:
            return
        self.i_name.set(item.get('name',''))
        self.i_slot.set(item['slot'])
        self.i_price.set(str(item.get('price',0)))
        self.i_bonuses.set(', '.join(f'{k}={v}' for k,v in item.get('bonuses',{}).items()))

    def _item_data(self):
        return dict(name=self.i_name.get(), slot=self.i_slot.get(),
                    price=int(self.i_price.get()),
                    bonuses=edit.parse_bonuses(self.i_bonuses.get(),equipment=True))

    def create_item(self):
        item_id, params = self.i_id.get(), self._item_data()
        self._apply(lambda data: edit.create_equipment(data, item_id, **params))
        self.i_id.set(item_id)

    def save_item(self):
        item_id, params = self.i_id.get(), self._item_data()
        self._apply(lambda data: edit.update_equipment(data, item_id, **params))

    def delete_item(self):
        self._apply(lambda data: edit.remove_equipment(data, self.i_id.get()))

    def refresh(self):
        if self.owner.project is None:
            return
        data = self._data()
        mission = self._mission()
        uid = self.unit_id.get()
        units = [u['id'] for u in mission['units']]
        self.unit_box['values'] = units
        if uid not in units or self.last_mission != self.owner.mission():
            self.unit_id.set(units[0] if units else '')
            self._load_unit()
        self.last_mission = self.owner.mission()
        ids = sorted(data.get('archetypes',{}))
        self.a_box['values'] = ids
        skill_ids = [s['id'] for s in data['skills']]
        self.s_box['values'] = skill_ids
        job_ids = list(data.get('jobs',{}))
        self.j_box['values'] = job_ids
        self.j_requires_box['values'] = ['', *[j for j in job_ids if j != self.j_id.get()]]
        self.i_box['values'] = list(data.get('equipment',{}))
        if self.a_id.get() in ids:
            self._load_archetype()
        if self.s_id.get() in skill_ids:
            self._load_skill()
        if self.j_id.get() in job_ids:
            self._load_job()
        if self.i_id.get() in data.get('equipment',{}):
            self._load_item()
        self.class_ai.refresh()
