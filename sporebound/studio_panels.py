"""Tk authoring panels for units, interactables, events and whole-game setup.

Tk stays optional: importing gameplay without a display does not import it.
"""
from copy import deepcopy
import json
from pathlib import Path

from . import authoring
from .entity_event_studio import author_gate_sequence, gate_context, probe_gate_sequence
from .event_context import format_preview_report
from .game_project import GameProject, load_slot, save_slot
from .campaign_flow import available_missions as flow_available_missions
from .studio_campaign_flow import open_campaign_inspector, open_campaign_qa
from .model import Content, RuleError
from .tactical_rpg3 import authored_rules_for_document
from .studio_transaction import StudioHistory, StudioTransactionStore


class StudioPanels:
    def __init__(self, notebook, tk, ttk, dialogs, *, doc, content_path,
                 mission, selection, design_change, play_campaign, status, mission_change=None,
                 select_mission=None, on_project_saved=None, set_active_mission=None,
                 focus_map_cell=None, workspace_edit=None, workspace_rename=None,
                 workspace_delete=None):
        self.tk, self.ttk, self.dialogs = tk, ttk, dialogs
        self.notebook = notebook
        self.doc, self.content_path = doc, content_path
        self.mission, self.selection = mission, selection
        self.design_change, self.play_campaign = design_change, play_campaign
        self.mission_change = mission_change or self.refresh
        self.select_mission = select_mission or (lambda _mid: None)
        self.set_active_mission = set_active_mission or self.select_mission
        self.focus_map_cell = focus_map_cell or (lambda mid, cell: None)
        self.workspace_edit = workspace_edit
        self.workspace_rename = workspace_rename
        self.workspace_delete = workspace_delete
        self.status = status
        self.on_project_saved = on_project_saved or (lambda _path: None)
        self.project = None
        self.project_path = None
        self.project_saved = ''
        self.history = None
        self._history_busy = 0
        self.session = None
        self.session_campaign = ''
        from .studio_workspace import ProjectWorkspaceTab
        self.workspace = ProjectWorkspaceTab(self, notebook)
        self._entities_tab(notebook)
        self._project_tab(notebook)
        from .studio_world_map import WorldMapStudio
        self.world_studio = WorldMapStudio(self, notebook)
        from .studio_advanced import AdvancedStudio
        self.advanced=AdvancedStudio(self, notebook)
        from .studio_character_rules import CharacterRulesStudio
        self.character_rules=CharacterRulesStudio(self, notebook)
        from .studio_story import StoryEditor
        self.story_editor=StoryEditor(self, notebook)
        from .studio_siege import SiegeStudio
        self.siege_studio=SiegeStudio(self, notebook)
        from .studio_cinematics import CinematicStudio
        self.cinematic_studio = CinematicStudio(self, notebook)
        from .studio_audio import AudioStudio
        self.audio_studio = AudioStudio(self, notebook)
        from .studio_battle_lab import BattleLabStudio
        self.battle_lab = BattleLabStudio(self, notebook)
        from .studio_balance_matrix import BalanceMatrixStudio
        self.balance_matrix = BalanceMatrixStudio(self, notebook)
        from .studio_battle_visual import VisualBattleLabStudio
        self.visual_battle_lab = VisualBattleLabStudio(self, notebook)
        from .studio_playtest import PlaytestStudio
        self.playtest_studio = PlaytestStudio(self, notebook)
        self._last_mission_signature=None
        self._deferred_map_refresh = False
        self.reload_project()
        self.refresh()
        # Map-only brush strokes do not need to rebuild hidden editors.
        # A tab switch flushes them before their data is inspected.
        self.notebook.bind('<<NotebookTabChanged>>',
                           self._flush_deferred_map_refresh, add='+')

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
        # Nested editor commands publish one coordinated snapshot after the
        # complete user action, not one snapshot for each internal sub-edit.
        self._history_busy += 1
        try:
            operation()
        except (RuleError, ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
            self.dialogs.showerror('Édition refusée', str(exc))
        finally:
            self._history_busy -= 1
            if self._history_busy == 0:
                self.capture_history()

    def capture_history(self):
        if self._history_busy == 0 and self.history is not None and self.project is not None:
            return self.history.record(self.doc().data, self.project)
        return False

    def _restore_history(self, redo=False):
        document, project = (self.history.redo() if redo else self.history.undo())
        current = self.doc()
        # Preserve the monotonic edit lease when the snapshot returns to the
        # exact same bytes after Undo/Redo (ABA).
        current.restore_snapshot(document)
        self.project = project
        # An undo may delete the mission selected in the canvas. Restore a
        # valid mission before refreshing any dependent Studio panel.
        if self.mission() not in {m['id'] for m in document['missions']}:
            self.set_active_mission(document['missions'][0]['id'])
        # Rebuild project-dependent models and preview registries. Simply
        # changing the owner.project pointer leaves stale storyboard/asset
        # caches visible after a global undo.
        self.story_editor.reset_project()
        self.cinematic_studio.reset_project()
        self.audio_studio.stop()
        self.title.set(project.title)
        self.subtitle.set(project.subtitle)
        self.language.set(project.options['language'])
        self.music.set(str(project.options['music_volume']))
        self.effects.set(str(project.options['effects_volume']))
        self.slots.set(str(project.save_slots))
        self.fullscreen.set(project.options['fullscreen'])
        if project.campaign(self.campaign_id.get()) is None:
            self.campaign_id.set(project.campaigns[0]['id'])
        self._show_campaign()
        self._last_mission_signature = None
        self.project_status.config(text='Historique Studio restauré (contenu + projet).')

    def undo_global(self):
        self._restore_history()

    def redo_global(self):
        self._restore_history(redo=True)

    def _change(self, operation):
        self.design_change(lambda: self.doc().replace(operation(self.doc().data, self.mission())))
        self.refresh()

    def _entities_tab(self, notebook):
        ttk = self.ttk
        outer = ttk.Frame(notebook)
        notebook.add(outer, text='Personnages et événements')
        self.entities_tab = outer
        ttk.Label(outer, text='Les coordonnées suivent la case sélectionnée sur la carte. Chaque modification est validée et annulable.').pack(anchor='w', padx=10, pady=8)
        self.cell_label = ttk.Label(outer, text='')
        self.cell_label.pack(anchor='w', padx=10)
        groups = ttk.Notebook(outer)
        groups.pack(fill='both', expand=True, padx=8, pady=8)
        self.entities_groups = groups

        units = ttk.Frame(groups)
        groups.add(units, text='Personnages / monstres')
        self.units_page = units
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
        self.tactical_role, _ = self._field(
            units, 6, 'Rôle tactique', 'none',
            choices=['none', 'medic', 'protector'])
        self.initial_formation, _ = self._field(
            units, 7, 'Formation initiale', 'none',
            choices=['none', 'shield_wall', 'phalanx', 'escort'])
        self.escort_id, _ = self._field(units, 8, 'Protéger le personnage ID')
        ttk.Button(units, text='Appliquer rôle et formation', command=lambda: self._run(
            lambda: self._change(lambda d, m: authoring.set_unit_combat_role(
                d, m, self._selected(self.unit_list),
                role=self.tactical_role.get(),
                formation=self.initial_formation.get(),
                escort_target=self.escort_id.get().strip())))).grid(
                    row=9, column=0, columnspan=2, pady=5)
        units.columnconfigure(1,weight=1); units.rowconfigure(4,weight=1)

        # Declarative JP talent graph: Treeview nodes and structured fields,
        # never a free-form JSON editor. Stored in the global job catalogue.
        talents = ttk.Frame(groups)
        groups.add(talents, text='Talents / classes')
        self.talent_job, self.talent_job_box = self._field(
            talents, 0, 'Classe', choices=[])
        self.talent_id, _ = self._field(talents, 1, 'Talent ID')
        self.talent_jp, _ = self._field(talents, 2, 'Coût JP', '1')
        self.talent_requires, _ = self._field(
            talents, 3, 'Prérequis (ID, ID)')
        self.talent_exclusive, _ = self._field(
            talents, 4, 'Spécialisation')
        from .builds3 import STATS
        self.talent_stat, _ = self._field(
            talents, 5, 'Stat modifiée', '',
            choices=['', *sorted(STATS)])
        self.talent_bonus, _ = self._field(talents, 6, 'Bonus', '0')
        self.talent_skills, _ = self._field(
            talents, 7, 'Compétences (ID, ID)')
        self.talent_tree = ttk.Treeview(talents, show='tree', height=7)
        self.talent_tree.grid(row=8, column=0, columnspan=2,
                              sticky='nsew', padx=6, pady=6)
        self.talent_tree.bind('<<TreeviewSelect>>', self._select_talent_node)
        self.talent_job_box.bind('<<ComboboxSelected>>',
                                 lambda _e: self._refresh_talent_tree())
        talent_buttons = ttk.Frame(talents)
        talent_buttons.grid(row=9, column=0, columnspan=2, pady=6)
        ttk.Button(talent_buttons, text='Créer / mettre à jour',
                   command=lambda: self._run(self._save_talent)).pack(
                       side='left', padx=4)
        ttk.Button(talent_buttons, text='Supprimer le talent',
                   command=lambda: self._run(self._delete_talent)).pack(
                       side='left', padx=4)
        talents.columnconfigure(1, weight=1)
        talents.rowconfigure(8, weight=1)

        objects = ttk.Frame(groups)
        groups.add(objects, text='Objets interactifs')
        self.objects_page = objects
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
        # One contextual path inside the existing entity tab, not another modal
        # palette or an independent trigger/scene schema.
        gate = ttk.LabelFrame(objects, text='Entity & Event Studio · porte → levier → événement')
        gate.grid(row=7, column=0, columnspan=2, sticky='ew', padx=6, pady=8)
        self.gate_door, self.gate_door_box = self._field(
            gate, 0, 'Porte sélectionnée', choices=[])
        self.gate_lever, _ = self._field(gate, 1, 'Levier (ID nouveau/existant)', 'lever_gate')
        self.gate_lever_cell, _ = self._field(gate, 2, 'Case levier (x,y)')
        ttk.Button(gate, text='Depuis la carte',
                   command=lambda: self.gate_lever_cell.set(
                       ','.join(map(str, self.selection())))).grid(
                           row=2, column=2, padx=4)
        self.gate_event_id, _ = self._field(gate, 3, 'Identifiant événement', 'gate_interact')
        self.gate_danger_cell, _ = self._field(gate, 4, 'Case danger (x,y)')
        ttk.Button(gate, text='Depuis la carte',
                   command=lambda: self.gate_danger_cell.set(
                       ','.join(map(str, self.selection())))).grid(
                           row=4, column=2, padx=4)
        self.gate_danger, _ = self._field(gate, 5, 'Danger tactique', '4')
        self.gate_dialogue, _ = self._field(
            gate, 6, 'Dialogue cinématique', 'La porte s’ouvre !')
        self.gate_cinematic_id, _ = self._field(gate, 7, 'ID cinématique (facultatif)')
        self.gate_min_tick, _ = self._field(
            gate, 10, 'Tick minimum (optionnel)', '')
        self.gate_scene, self.gate_scene_box = self._field(
            gate, 11, 'Scène narrative (optionnelle)', choices=[])
        gate_buttons = ttk.Frame(gate)
        gate_buttons.grid(row=8, column=0, columnspan=3, sticky='ew', pady=6)
        ttk.Button(gate_buttons, text='Créer et simuler',
                   command=lambda: self._run(self.create_gate_event)).pack(
                       side='left', padx=4)
        ttk.Button(gate_buttons, text='Simuler événement',
                   command=lambda: self._run(self.preview_gate_event)).pack(
                       side='left', padx=4)
        ttk.Label(gate, text='Choisir les cases sur la carte. Après création, ajouter '
                  'des conditions ET/OU/NON et plusieurs effets dans le Graphe '
                  'existant, puis simuler, vérifier et rejouer.',
                  wraplength=620).grid(
                      row=9, column=0, columnspan=3, sticky='w', padx=6, pady=4)
        gate.columnconfigure(1, weight=1)

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
        ttk.Button(
            events, text='Créer un embranchement narratif sur la case',
            command=lambda: self._run(
                lambda: self.advanced.event_graph.launch_branch_wizard(
                    origin_id=''))).grid(
                        row=9, column=0, columnspan=2,
                        sticky='ew', padx=6, pady=4)
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
            choices=['eliminate','survive','extract','hold','crown',
                      'capture','escort','defend','sabotage','retreat'])
        self.reward,_=self._field(mission_form,2,'Récompense','100')
        self.next_missions,_=self._field(mission_form,3,'Missions suivantes (id,id)')
        ttk.Button(mission_form,text='Appliquer la mission',command=lambda: self._run(
            lambda: self._change(lambda d,m: authoring.set_mission_properties(
                d,m,name=self.mission_name.get(),objective=self.objective.get(),
                reward=int(self.reward.get()),
                next_missions=[s.strip() for s in self.next_missions.get().split(',') if s.strip()])))).grid(
                    row=4,column=0,columnspan=2,pady=5)
        mission_form.columnconfigure(1,weight=1)

    @staticmethod
    def _gate_point(raw):
        parts = [part.strip() for part in raw.split(',')]
        if len(parts) != 2 or any(not part or not part.lstrip('-').isdigit()
                                  for part in parts):
            raise RuleError('Position attendue au format x,y')
        return [int(value) for value in parts]

    def focus_gate_event(self, door_id):
        """Open the existing contextual inspector for the selected map gate."""
        door, levers = gate_context(self.doc().data, self.mission(), door_id)
        self.focus_map_entity('object', door['id'])
        self.gate_door.set(door['id'])
        if levers:
            self.gate_lever.set(levers[0]['id'])
            self.gate_lever_cell.set(','.join(map(str, levers[0]['pos'])))
        else:
            self.gate_lever.set('lever_' + door_id)
            self.gate_lever_cell.set('')
        self.gate_event_id.set('open_' + door_id)
        self.gate_danger_cell.set('')
        self.entities_groups.select(self.objects_page)

    def create_gate_event(self):
        """Single coordinated Studio history entry for Content + GameProject."""
        mid, eid = self.mission(), self.gate_event_id.get().strip()
        initial = self.doc().data
        updated, project = author_gate_sequence(
            initial, self.project, mid,
            door_id=self.gate_door.get(),
            lever_id=self.gate_lever.get().strip(),
            lever_cell=self._gate_point(self.gate_lever_cell.get()),
            event_id=eid,
            danger_cell=self._gate_point(self.gate_danger_cell.get()),
            danger=int(self.gate_danger.get()),
            dialogue=self.gate_dialogue.get(),
            cinematic_id=self.gate_cinematic_id.get().strip(),
            min_tick=(int(self.gate_min_tick.get())
                      if self.gate_min_tick.get().strip() else None),
            scene_id=self.gate_scene.get().strip())
        # If pending raw JSON made design_change abort, do NOT update the
        # manifest: otherwise the scene would reference an uncommitted trigger.
        self.design_change(lambda: self.doc().replace(updated))
        if self.doc().data != updated:
            raise RuleError('Enregistrement du contenu annulé ; projet inchangé.')
        self.project = project
        self.refresh()
        self.gate_event_id.set(eid)
        self.preview_gate_event()

    def preview_gate_event(self):
        """Reuse the existing graph/scene preview; no separate simulator."""
        graph = self.advanced.event_graph
        eid = self.gate_event_id.get().strip()
        context = probe_gate_sequence(
            self.doc().data, self.project, self.mission(),
            eid, self.gate_door.get())
        graph.event_id.set(eid)
        graph.preview_scenario.set('Condition vraie')
        graph.refresh()
        graph.preview_selected()
        graph._set_context_text(
            ['PORTE : ' + ('ouverte, traversable' if context['gate_opened']
                           else 'inchangée'),
             'CONSÉQUENCE : ' + ('terrain modifié' if context['tactical_effect']
                                else 'aucune modification'),
             'CINÉMATIQUE PLAYER : ' +
             (', '.join(context['cinematic_ids']) or 'aucune'),
             'SCÈNE NARRATIVE : ' + (context['narrative_scene_id'] or 'aucune'),
             'GATE : ' + ('OK' if context['gate_scenario_ok'] else 'À CORRIGER'),
             '', *format_preview_report(context['event'])], show_end=True)
        self.notebook.select(graph.tab)

    def focus_map_entity(self, kind, entity_id):
        """Navigate to the selected map entity in the existing editing form."""
        if kind not in ('unit', 'object'):
            raise RuleError('Type de ressource non éditable depuis la carte.')
        self.refresh()
        mission = next(m for m in self.doc().data['missions']
                       if m['id'] == self.mission())
        entries = mission['units'] if kind == 'unit' else mission.get('objects', [])
        index = next((i for i, entry in enumerate(entries)
                      if entry['id'] == entity_id), None)
        if index is None:
            raise RuleError('Élément introuvable dans la mission : ' + entity_id)
        self.notebook.select(self.entities_tab)
        self.entities_groups.select(
            self.units_page if kind == 'unit' else self.objects_page)
        listing = self.unit_list if kind == 'unit' else self.object_list
        listing.selection_clear(0, 'end')
        listing.selection_set(index)
        listing.activate(index)
        listing.see(index)
        listing.focus_set()

    def _refresh_talent_tree(self):
        jobs = self.doc().data.get('jobs', {})
        values = sorted(jobs)
        self.talent_job_box['values'] = values
        if self.talent_job.get() not in jobs:
            self.talent_job.set(values[0] if values else '')
        current = self.talent_job.get()
        talents = jobs.get(current, {}).get('talents', {})
        self.talent_tree.delete(*self.talent_tree.get_children())
        inserted = set()
        def add_node(tid):
            if tid in inserted:
                return
            spec = talents[tid]
            deps = spec.get('requires', [])
            parent = sorted(dep for dep in deps if dep in talents)[0] if deps else ''
            if parent:
                add_node(parent)
            suffix = '  ← ' + ', '.join(deps) if deps else ''
            self.talent_tree.insert(parent, 'end', iid=tid,
                text=f"{tid}  —  {spec.get('jp', 1)} JP{suffix}")
            inserted.add(tid)
        for tid in sorted(talents):
            add_node(tid)

    def _select_talent_node(self, _event):
        chosen = self.talent_tree.selection()
        if not chosen:
            return
        tid = chosen[0]
        spec = self.doc().data.get('jobs', {}).get(
            self.talent_job.get(), {}).get('talents', {}).get(tid)
        if spec is None:
            return
        bonuses = spec.get('bonuses', {})
        stat = sorted(bonuses)[0] if bonuses else ''
        self.talent_id.set(tid)
        self.talent_jp.set(str(spec.get('jp', 1)))
        self.talent_requires.set(', '.join(spec.get('requires', [])))
        self.talent_exclusive.set(spec.get('exclusive', ''))
        self.talent_stat.set(stat)
        self.talent_bonus.set(str(bonuses.get(stat, 0)))
        self.talent_skills.set(', '.join(spec.get('skills', [])))

    def _save_talent(self):
        deps = [v.strip() for v in self.talent_requires.get().split(',')
                if v.strip()]
        skills = [v.strip() for v in self.talent_skills.get().split(',')
                  if v.strip()]
        job, tid = self.talent_job.get(), self.talent_id.get().strip()
        def action(data, _mission):
            return authoring.upsert_job_talent(
                data, job, tid, jp=int(self.talent_jp.get()),
                requires=deps, exclusive=self.talent_exclusive.get().strip(),
                stat=self.talent_stat.get(),
                bonus=int(self.talent_bonus.get()), skills=skills)
        self._change(action)

    def _delete_talent(self):
        selection = self.talent_tree.selection()
        if not selection:
            raise RuleError('Sélectionnez un talent à supprimer')
        job, tid = self.talent_job.get(), selection[0]
        self._change(lambda data, _mission: authoring.remove_job_talent(
            data, job, tid))

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
        cb.bind('<<ComboboxSelected>>',lambda _event: (self._show_campaign(), self.advanced.draw_graph()))
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
        ttk.Button(right,text='Inspecter état R5.8',
                   command=lambda: self._run(lambda: open_campaign_inspector(self))).grid(row=10,column=0,pady=5)
        ttk.Button(right,text='Analyser parcours R5.11',
                   command=lambda: self._run(lambda: open_campaign_qa(self))).grid(row=10,column=1,pady=5)
        self.project_status=ttk.Label(right,text='',wraplength=450)
        self.project_status.grid(row=9,column=0,columnspan=2,sticky='w',padx=8,pady=12)
        right.columnconfigure(1,weight=1)

    def _content(self):
        return Content.from_dict(self.doc().data,
                                 rules=authored_rules_for_document(self.doc().data))

    def _show_campaign(self):
        if self.project is None:
            return
        camp=self.project.campaign(self.campaign_id.get())
        if camp:
            self.cname.set(camp['name'])
            self.cdesc.set(camp['description'])
            self.cstart.set(camp['start_mission'])

    def restore_unsaved_project(self, raw):
        """Adopt an explicitly recovered GameProject without saving to disk."""
        self.project = GameProject.from_dict(raw, self._content())
        self.history.reset(self.doc().data, self.project)
        self.title.set(self.project.title)
        self.subtitle.set(self.project.subtitle)
        self.language.set(self.project.options['language'])
        self.music.set(str(self.project.options['music_volume']))
        self.effects.set(str(self.project.options['effects_volume']))
        self.fullscreen.set(self.project.options['fullscreen'])
        self.slots.set(str(self.project.save_slots))
        self.campaign_id.set(self.project.campaigns[0]['id'])
        self._show_campaign()
        self.story_editor.reset_project()
        self.cinematic_studio.reset_project()
        self.audio_studio.stop()
        self.audio_studio.refresh()
        self._last_mission_signature = None
        self.project_status.config(text='Travail récupéré : enregistrer pour conserver.')
        self.refresh()

    def reload_project(self):
        # A different project may reuse mission/entity IDs; navigation
        # positions belong to the current editor session, not saved content.
        self.workspace.clear_navigation()
        content=self._content()
        self.project_path=Path(self.content_path()).with_suffix('.game.json')
        self.project=(GameProject.load(self.project_path,content) if self.project_path.exists()
                      else GameProject.default(content))
        self.project_saved=json.dumps(self.project.to_dict(),sort_keys=True)
        if self.history is None:
            self.history = StudioHistory(self.doc().data, self.project)
        else:
            self.history.reset(self.doc().data, self.project)
        self.story_editor.reset_project()
        self.cinematic_studio.reset_project()
        self.audio_studio.stop()
        self.audio_studio.refresh()
        self._last_mission_signature=None
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
        if StudioTransactionStore(self.content_path()).pending:
            raise RuleError('Récupérer la sauvegarde Studio interrompue avant toute écriture')
        self.apply_project()
        filename=self.dialogs.asksaveasfilename(initialfile=self.project_path.name,
            defaultextension='.json',filetypes=[('Projet de jeu JSON','*.json')])
        if filename:
            self.project.save(filename,self._content())
            self.project_path=Path(filename)
            self.project_saved=json.dumps(self.project.to_dict(),sort_keys=True)
            self.on_project_saved(self.project_path)
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
        if self.session.story_pending:
            raise RuleError('Un dialogue narratif est en attente : utiliser le client joueur pour répondre.')
        available = flow_available_missions(self.session, self.project.campaign_flow)
        if not available:
            raise RuleError('Aucune mission jouable : résoudre les conditions ou dialogues dans le Player')
        self.play_campaign(self.session, available[0])

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

    def defer_map_refresh(self):
        """Postpone heavy invisible Studio panels after a terrain-only edit."""
        self._deferred_map_refresh = True
        self.refresh_selection()

    def _flush_deferred_map_refresh(self, _event=None):
        if self._deferred_map_refresh:
            self.refresh()

    def refresh_selection(self):
        """Update only map-context controls; no Studio-wide editor rebuild."""
        if self.project is None:
            return
        chosen = next((m for m in self.doc().data['missions']
                       if m['id'] == self.mission()), None)
        if chosen is not None:
            self.cell_label.config(
                text=f'Case choisie : {self.selection()} | Mission : {chosen["name"]}')

    def refresh(self):
        if self.project is None:
            return
        missions=self.doc().data['missions']
        chosen=next((m for m in missions if m['id']==self.mission()), missions[0])
        signature=json.dumps(chosen,sort_keys=True)
        if signature!=self._last_mission_signature:
            self.mission_name.set(chosen['name'])
            self.objective.set(chosen['objective'])
            self.reward.set(str(chosen['reward']))
            self.next_missions.set(', '.join(chosen.get('next_missions',[])))
            self.width.set(str(chosen['board']['width']))
            self.height.set(str(chosen['board']['height']))
            self._last_mission_signature=signature
        self.cell_label.config(text=f'Case choisie : {self.selection()} | Mission : {chosen["name"]}')
        for listing,items in ((self.unit_list,chosen['units']),
                              (self.object_list,chosen.get('objects',[])),
                              (self.event_list,chosen.get('triggers',[]))):
            selected = {listing.get(i).split('  —  ', 1)[0]
                        for i in listing.curselection()}
            listing.delete(0,'end')
            for index, item in enumerate(items):
                listing.insert('end',f"{item['id']}  —  {item.get('name',item.get('kind',item.get('condition','')))}")
                if item['id'] in selected:
                    listing.selection_set(index)
        doors = [obj['id'] for obj in chosen.get('objects', ())
                 if obj['kind'] == 'door']
        self.gate_door_box['values'] = doors
        scene_ids = [''] + [row['id'] for row in
                            self.project.story.get('scenes', [])]
        self.gate_scene_box['values'] = scene_ids
        if self.gate_scene.get() not in scene_ids:
            self.gate_scene.set('')
        if self.gate_door.get() not in doors:
            self.gate_door.set(doors[0] if doors else '')
        self.start_box['values']=[m['id'] for m in missions]
        self.campaign_box['values']=[c['id'] for c in self.project.campaigns]
        if self.session is not None:
            self.project_status.config(text=f'Campagne active : {self.session_campaign} | Missions : {len(self.session.completed)} terminées | Or : {self.session.gold}')
        self._refresh_talent_tree()
        self.advanced.refresh()
        self.character_rules.refresh()
        self.story_editor.refresh()
        self.siege_studio.refresh()
        self.cinematic_studio.refresh()
        self.audio_studio.refresh()
        self.workspace.refresh()
        self.world_studio.refresh()
        self.battle_lab.refresh()
        self._deferred_map_refresh = False
