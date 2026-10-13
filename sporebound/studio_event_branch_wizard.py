"""Map-contextual two-route authoring UI; reuses Studio Event/Story models.

This is a transient form within the existing Studio, not a separate editor
or serialized graph. Nothing changes before one coordinated Save.
"""
from .event_branch_builder import author_choice_fork, branch_recipe
from .event_branches import preview_choice_routes, format_choice_routes
from .model import RuleError, require


class VisualChoiceWizard:
    def __init__(self, graph, *, origin_id=''):
        self.graph = graph
        self.owner = graph.owner
        tk, ttk = self.owner.tk, self.owner.ttk
        self.tk, self.ttk = tk, ttk
        self.mission_id = self.owner.mission()
        self.cell = tuple(self.owner.selection())
        self.window = tk.Toplevel(graph.tab)
        self.window.title('Embranchements — création depuis la carte')
        self.window.geometry('765x635')
        self.window.minsize(570, 490)
        self.window.transient(graph.tab.winfo_toplevel())
        self.vars = {}
        container = ttk.Frame(self.window, padding=12)
        container.pack(fill='both', expand=True)
        ttk.Label(
            container,
            text=f'Mission {self.mission_id} · Case {self.cell[0]},{self.cell[1]}',
            font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        ttk.Label(
            container,
            text='Créer une scène, deux réponses, leurs événements tactiques '
                 'et un éventuel point de réunion, sans ouvrir les éditeurs spécialisés.',
            wraplength=720).pack(anchor='w', pady=(2, 7))

        form = ttk.Frame(container)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        def field(row, label, key, default, *, choices=None):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky='w', pady=2, padx=(0, 9))
            var = tk.StringVar(value=default)
            self.vars[key] = var
            if choices:
                widget = ttk.Combobox(form, textvariable=var, values=choices,
                                       width=40, state='normal')
            else:
                widget = ttk.Entry(form, textvariable=var, width=40)
            widget.grid(row=row, column=1, sticky='ew', pady=2)
            return widget
        origin = origin_id or f'choice_at_{self.cell[0]}_{self.cell[1]}'
        field(0, 'Événement source (nouveau ou existant)', 'origin',
              origin, choices=[x['id'] for x in
                               graph._mission().get('triggers', [])])
        field(1, 'ID scène initiale', 'scene', 'choice_' + str(self.cell[0]) +
              '_' + str(self.cell[1]))
        field(2, 'Titre', 'title', 'Que décide le groupe ?')
        field(3, 'Dialogue', 'text', 'Comment devons-nous agir ?')
        field(4, 'Interlocuteur', 'speaker', 'Jeanne')

        branch_frame = ttk.Frame(container)
        branch_frame.pack(fill='x', pady=(9, 3))
        for col in (0, 1):
            branch_frame.columnconfigure(col, weight=1)
        presets = [
            ('attack', 'Attaquer', 'branch_attack', 'hazard',
             'Les défenseurs sont attaqués', '6'),
            ('parley', 'Négocier', 'branch_parley', 'message',
             'Un accord est proposé', '0'),
        ]
        for index, (cid, label, event, kind, desc, amount) in enumerate(presets):
            group = ttk.LabelFrame(branch_frame, text='Voie ' + str(index + 1))
            group.grid(row=0, column=index, sticky='nsew',
                       padx=(0, 4) if index == 0 else (4, 0))
            def short_field(key, caption, default, *, combo=None):
                row = len(group.grid_slaves()) // 2
                ttk.Label(group, text=caption).grid(
                    row=row, column=0, sticky='w', padx=5, pady=2)
                var = tk.StringVar(value=default)
                self.vars[str(index) + '_' + key] = var
                if combo:
                    wid = ttk.Combobox(group, textvariable=var,
                                       values=combo, state='readonly', width=21)
                else:
                    wid = ttk.Entry(group, textvariable=var, width=24)
                wid.grid(row=row, column=1, sticky='ew', padx=4, pady=2)
                group.columnconfigure(1, weight=1)
            short_field('id', 'ID réponse', cid)
            short_field('label', 'Choix affiché', label)
            short_field('event', 'Événement', event + '_' +
                        str(self.cell[0]) + '_' + str(self.cell[1]))
            short_field('kind', 'Action', kind, combo=('hazard', 'message'))
            short_field('message', 'Texte / scène', desc)
            short_field('amount', 'Danger (0..)', amount)
        join = ttk.LabelFrame(container, text='Retour vers une étape commune (facultatif)')
        join.pack(fill='x', pady=(7, 4))
        line = ttk.Frame(join)
        line.pack(fill='x')
        ttk.Label(line, text='Événement commun').pack(side='left', padx=5)
        self.vars['reunion'] = tk.StringVar(value='')
        ttk.Entry(line, textvariable=self.vars['reunion'],
                  width=27).pack(side='left', padx=6)
        self.vars['reunion_text'] = tk.StringVar(
            value='Le groupe se retrouve après le choix.')
        ttk.Entry(line, textvariable=self.vars['reunion_text'],
                  width=38).pack(side='left', padx=6, fill='x', expand=True)

        commands = ttk.Frame(container)
        commands.pack(fill='x', pady=5)
        ttk.Button(commands, text='Prévisualiser les deux chemins',
                   command=lambda: self.owner._run(self.preview)).pack(
                       side='left', padx=3)
        ttk.Button(commands, text='Créer sur la carte',
                   command=lambda: self.owner._run(self.commit)).pack(
                       side='left', padx=3)
        ttk.Button(commands, text='Annuler', command=self.window.destroy).pack(
            side='right', padx=3)
        viewer = ttk.LabelFrame(container, text='Aperçu des chemins')
        viewer.pack(fill='both', expand=True)
        self.report = tk.Text(viewer, height=9, wrap='word', state='disabled')
        scroller = ttk.Scrollbar(viewer, command=self.report.yview)
        self.report.config(yscrollcommand=scroller.set)
        scroller.pack(side='right', fill='y')
        self.report.pack(side='left', fill='both', expand=True)
        self._report(['Sélectionner les conséquences et prévisualiser avant '
                      'de créer les ressources.'])

    def _report(self, lines):
        self.report.config(state='normal')
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', '\n'.join(lines))
        self.report.config(state='disabled')

    def _plan(self):
        v = self.vars
        branches = branch_recipe(
            first_id=v['0_id'].get().strip(),
            first_label=v['0_label'].get().strip(),
            first_event=v['0_event'].get().strip(),
            first_action=v['0_kind'].get(),
            first_text=v['0_message'].get(),
            first_amount=int(v['0_amount'].get()),
            second_id=v['1_id'].get().strip(),
            second_label=v['1_label'].get().strip(),
            second_event=v['1_event'].get().strip(),
            second_action=v['1_kind'].get(),
            second_text=v['1_message'].get(),
            second_amount=int(v['1_amount'].get()))
        return author_choice_fork(
            self.owner.doc().data, self.owner.project,
            self.mission_id, origin_event_id=v['origin'].get().strip(),
            origin_cell=self.cell, scene_id=v['scene'].get().strip(),
            title=v['title'].get(), text=v['text'].get(),
            speaker=v['speaker'].get(), branches=branches,
            reunion_event_id=v['reunion'].get().strip(),
            reunion_message=v['reunion_text'].get())

    def preview(self):
        data, project = self._plan()
        report = preview_choice_routes(
            data, project, self.mission_id,
            self.vars['origin'].get().strip(), scenario='satisfied')
        self._report(format_choice_routes(report))
        self.graph.status.set('Aperçu isolé, sans aucune modification des fichiers.')

    def commit(self):
        data, project = self._plan()
        self.owner.design_change(lambda: self.owner.doc().replace(data))
        require(self.owner.doc().data == data,
                'Enregistrement de Content annulé ; projet inchangé.')
        self.owner.project = project
        self.owner.story_editor.reset_project()
        self.owner.refresh()
        self.graph.event_id.set(self.vars['origin'].get().strip())
        self.graph.refresh()
        self.graph.status.set('Embranchements créés dans un seul historique '
                              'Studio : carte + narration + événements.')
        self.window.destroy()
        self.graph.notebook.select(self.graph.tab)
        self.graph.preview_branches()
