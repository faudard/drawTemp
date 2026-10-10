"""Tk Campaign & Siege Studio (2.5.4).

All changes use the canonical GameProject siege blueprint or Content triggers.
No extra save format for combat rules, no JSON editing in the authoring UI.
"""
from copy import deepcopy

from . import front_links, siege_authoring as edit
from .model import RuleError, require


class SiegeStudio:
    def __init__(self, owner, notebook):
        self.owner, self.tk, self.ttk = owner, owner.tk, owner.ttk
        self.session = None
        self.session_id = ""
        self._refreshing = False
        self.siege_id = self.tk.StringVar()
        self.parent_campaign = self.tk.StringVar()
        self.front_id = self.tk.StringVar(value="gate")
        self.mission_id = self.tk.StringVar()
        self.strength = self.tk.StringVar(value="10")
        self.opposition = self.tk.StringVar(value="10")
        self.doctrine = self.tk.StringVar(value="hold")
        self.final = self.tk.StringVar()
        self.required = self.tk.StringVar()
        self.outcomes = self.tk.StringVar(value="victory")
        self.link_id = self.tk.StringVar(value="link_1")
        self.link_source = self.tk.StringVar()
        self.link_event = self.tk.StringVar(value="interact")
        self.link_match = self.tk.StringVar()
        self.link_target = self.tk.StringVar()
        self.effect_kind = self.tk.StringVar(value="reduce_opposition")
        self.effect_value = self.tk.StringVar(value="2")
        self.wave_front = self.tk.StringVar()
        self.wave_id = self.tk.StringVar(value="wave_turn_3")
        self.wave_turn = self.tk.StringVar(value="3")
        self.wave_actor = self.tk.StringVar(value="enemy_reinforcement")
        self.wave_arch = self.tk.StringVar()
        self.wave_team = self.tk.StringVar(value="enemy")
        self.wave_x = self.tk.StringVar(value="1")
        self.wave_y = self.tk.StringVar(value="1")
        self.wave_life = self.tk.StringVar(value="")
        self.slot = self.tk.StringVar(value="1")
        self.log_reserves = self.tk.StringVar(value="3")
        self.log_supplies = self.tk.StringVar(value="5")
        self.log_capacity = self.tk.StringVar(value="4")
        self.log_escorts = self.tk.StringVar(value="1")
        self.log_origin = self.tk.StringVar(value="reserve")
        self.log_destination = self.tk.StringVar()
        self.log_turns = self.tk.StringVar(value="2")
        self.log_casualties = self.tk.StringVar(value="0")
        self.log_delay = self.tk.StringVar(value="2")
        self.log_charges = self.tk.StringVar(value="1")
        self.log_rescue = self.tk.StringVar()
        self.log_pursuit = self.tk.StringVar()
        self.log_ransom = self.tk.StringVar(value="2")
        self.log_reward = self.tk.StringVar(value="2")
        self.status = self.tk.StringVar(value="Créer un siège ou sélectionner un siège existant.")
        self._build(notebook)

    def _button(self, root, name, callback):
        self.ttk.Button(root, text=name,
                        command=lambda: self.owner._run(callback)).pack(
                            side="left", padx=3, pady=3)

    def _entry(self, parent, row, name, var, options=None, width=22):
        self.ttk.Label(parent, text=name).grid(row=row, column=0, sticky="w", padx=4, pady=3)
        if options is None:
            widget = self.ttk.Entry(parent, textvariable=var, width=width)
        else:
            widget = self.ttk.Combobox(parent, textvariable=var, values=options,
                                        width=width, state="readonly")
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        parent.columnconfigure(1, weight=1)
        return widget

    def _build(self, notebook):
        ttk = self.ttk
        root = ttk.Frame(notebook)
        self.tab = root
        notebook.add(root, text="Campagne & siège")
        header = ttk.Frame(root)
        header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text="Campagne / siège").pack(side="left")
        self.siege_box = ttk.Combobox(header, textvariable=self.siege_id,
                                       state="readonly", width=20)
        self.siege_box.pack(side="left", padx=5)
        self.siege_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(header, text="Campagne parente").pack(side="left", padx=(12, 2))
        self.campaign_box = ttk.Combobox(header, textvariable=self.parent_campaign,
                                          state="readonly", width=17)
        self.campaign_box.pack(side="left", padx=4)
        self._button(header, "Nouveau siège", self.new_siege)
        self._button(header, "Supprimer siège", self.delete_siege)
        self._button(header, "Branches", lambda: self._open_tab("Graphe des missions"))
        self._button(header, "Prologue / fins", lambda: self._open_tab("Scénario & dialogues"))

        pages = ttk.Notebook(root)
        pages.pack(fill="both", expand=True, padx=8, pady=4)
        fronts = ttk.Frame(pages)
        links = ttk.Frame(pages)
        waves = ttk.Frame(pages)
        timeline = ttk.Frame(pages)
        logistics = ttk.Frame(pages)
        visual_logistics = ttk.Frame(pages)
        route_policy = ttk.Frame(pages)
        strategic = ttk.Frame(pages)
        pages.add(fronts, text="Fronts et finale")
        pages.add(links, text="Événements inter-fronts")
        pages.add(waves, text="Vagues de renforts")
        pages.add(timeline, text="Chronologie / jouer")
        pages.add(logistics, text="Logistique & convois")
        pages.add(visual_logistics, text="Routes & ressources")
        from .studio_logistics import LogisticsStudio
        self.logistics_editor = LogisticsStudio(self, visual_logistics)

        pages.add(route_policy, text="Itinéraires & diplomatie")
        from .studio_routes import RoutesStudio
        self.routes_editor = RoutesStudio(self, route_policy)
        pages.add(strategic, text="Graphe stratégique")
        from .studio_strategic_events import StrategicEventsStudio
        self.strategic_editor = StrategicEventsStudio(self, strategic)

        lside = ttk.Frame(fronts)
        lside.pack(side="left", fill="both", expand=True)
        self.front_tree = ttk.Treeview(lside, columns=("mission", "force", "enemy", "doctrine"),
                                       show="tree headings", height=9, selectmode="browse")
        for col, caption, size in (("#0", "Front", 115),
                                    ("mission", "Mission", 170),
                                    ("force", "Alliés", 65),
                                    ("enemy", "Ennemis", 65),
                                    ("doctrine", "Doctrine", 75)):
            self.front_tree.heading(col, text=caption)
            self.front_tree.column(col, width=size, stretch=(col == "mission"))
        self.front_tree.pack(fill="x", padx=4, pady=4)
        self.front_tree.bind("<<TreeviewSelect>>", self._selected_front)
        self.graph = self.tk.Canvas(lside, height=280, background="#f8fafc")
        self.graph.pack(fill="both", expand=True, padx=5, pady=6)
        self.graph.bind("<Button-1>", self._graph_click)
        side = ttk.Frame(fronts)
        side.pack(side="right", fill="y", padx=6)
        self._entry(side, 0, "Front / identifiant", self.front_id)
        self.front_missions = self._entry(side, 1, "Mission tactique", self.mission_id, [])
        self._entry(side, 2, "Force alliée", self.strength)
        self._entry(side, 3, "Opposition", self.opposition)
        self._entry(side, 4, "Doctrine", self.doctrine, list(edit.DOCTRINES))
        fb = ttk.Frame(side)
        fb.grid(row=5, column=0, columnspan=2)
        self._button(fb, "+ Front", self.add_front)
        self._button(fb, "Mettre à jour", self.update_front)
        self._button(fb, "− Front", self.remove_front)
        self._button(fb, "Contrôler ce front", self.set_focus)
        ttk.Separator(side).grid(row=6, column=0, columnspan=2, sticky="ew", pady=9)
        self.final_box = self._entry(side, 7, "Secteur final", self.final, [])
        self.required_box = self._entry(side, 8, "Front préalable", self.required, [])
        self._entry(side, 9, "Issues acceptées", self.outcomes)
        ttk.Label(side, text="Ex. victory,partial (séparés par virgules)",
                  wraplength=260).grid(row=10, column=0, columnspan=2)
        cb = ttk.Frame(side)
        cb.grid(row=11, column=0, columnspan=2)
        self._button(cb, "Enregistrer finale / prérequis", self.save_final)
        self._button(cb, "Retirer finale", self.clear_final)

        top = ttk.Frame(links)
        top.pack(fill="both", expand=True, padx=5, pady=5)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)
        self.link_tree = ttk.Treeview(left, columns=("source", "trigger", "target", "effect"),
                                      show="tree headings", selectmode="browse", height=14)
        for col, name in (("#0", "Lien"), ("source", "Origine"),
                          ("trigger", "Événement"), ("target", "Cible"), ("effect", "Effet(s)")):
            self.link_tree.heading(col, text=name)
            self.link_tree.column(col, width=118)
        self.link_tree.pack(fill="both", expand=True)
        self.link_tree.bind("<<TreeviewSelect>>", self._selected_link)
        form = ttk.Frame(top)
        form.pack(side="right", fill="y", padx=10)
        self._entry(form, 0, "ID lien", self.link_id)
        self.link_source_box = self._entry(form, 1, "Origine", self.link_source, [])
        self.link_event_box = self._entry(form, 2, "Événement", self.link_event,
                                          sorted(front_links.EVENTS))
        self.link_source_box.bind("<<ComboboxSelected>>", lambda e: self._object_choices())
        self.link_event_box.bind("<<ComboboxSelected>>", lambda e: self._object_choices())
        self.match_box = self._entry(form, 3, "Objet / résultat", self.link_match, [])
        self.link_target_box = self._entry(form, 4, "Cible", self.link_target, [])
        self.effect_kind_box = self._entry(form, 5, "Conséquence", self.effect_kind,
                                           sorted(front_links.EFFECTS))
        self.effect_kind_box.bind("<<ComboboxSelected>>", lambda e: self._object_choices())
        self.link_target_box.bind("<<ComboboxSelected>>", lambda e: self._object_choices())
        self.effect_box = self._entry(form, 6, "Objet / quantité", self.effect_value, [])
        buttons = ttk.Frame(form)
        buttons.grid(row=7, column=0, columnspan=2, pady=5)
        self._button(buttons, "Créer / modifier", self.save_link)
        self._button(buttons, "+ Conséquence", self.append_effect)
        self._button(buttons, "Supprimer", self.delete_link)
        ttk.Label(form, text="Les liens réagissent à des événements tactiques réels.\n"
                  "La source et la cible doivent être deux fronts distincts.",
                  wraplength=320, justify="left").grid(
                      row=8, column=0, columnspan=2, pady=10)

        wave_top = ttk.Frame(waves)
        wave_top.pack(fill="both", expand=True, padx=8, pady=8)
        self.wave_tree = ttk.Treeview(wave_top, columns=("event", "turn", "actor", "arch"),
                                      show="tree headings", height=10)
        for col, name in (("#0", "Front"), ("event", "Événement"),
                          ("turn", "Tour"), ("actor", "Unité"), ("arch", "Archétype")):
            self.wave_tree.heading(col, text=name)
            self.wave_tree.column(col, width=130)
        self.wave_tree.pack(side="left", fill="both", expand=True)
        wave_form = ttk.Frame(wave_top)
        wave_form.pack(side="right", fill="y", padx=12)
        self.wave_front_box = self._entry(wave_form, 0, "Front", self.wave_front, [])
        self._entry(wave_form, 1, "ID événement", self.wave_id)
        self._entry(wave_form, 2, "Déclenchement au tour", self.wave_turn)
        self._entry(wave_form, 3, "ID unité", self.wave_actor)
        self.wave_arch_box = self._entry(wave_form, 4, "Archétype", self.wave_arch, [])
        self._entry(wave_form, 5, "Équipe", self.wave_team, ["enemy", "player"])
        self._entry(wave_form, 6, "Case X", self.wave_x)
        self._entry(wave_form, 7, "Case Y", self.wave_y)
        self._entry(wave_form, 8, "Durée (vide = illimitée)", self.wave_life)
        wbuttons = ttk.Frame(wave_form)
        wbuttons.grid(row=9, column=0, columnspan=2)
        self._button(wbuttons, "Ajouter vague", self.add_wave)
        self._button(wbuttons, "Supprimer vague", self.delete_wave)

        logistic_top = ttk.LabelFrame(
            logistics, text="Ressources et convois réels (optionnels)", padding=10)
        logistic_top.pack(fill="x", pady=5)
        for i, (title, variable) in enumerate((
                ("Réservistes joueurs", self.log_reserves),
                ("Provisions joueurs", self.log_supplies),
                ("Capacité convoyage", self.log_capacity),
                ("Escortes disponibles", self.log_escorts))):
            self.ttk.Label(logistic_top, text=title).grid(
                row=i // 2, column=2 * (i % 2), sticky="w", padx=5)
            self.ttk.Entry(logistic_top, textvariable=variable, width=7).grid(
                row=i // 2, column=2 * (i % 2) + 1, padx=6)
        lbuttons = ttk.Frame(logistics)
        lbuttons.pack(fill="x")
        self._button(lbuttons, "Activer / modifier logistique", self.save_logistics)
        self._button(lbuttons, "Désactiver logistique", self.clear_logistics)
        routes = ttk.LabelFrame(logistics, text="Routes / Embuscades", padding=10)
        routes.pack(fill="x", pady=7)
        self.log_origin_box = self._entry(routes, 0, "Départ", self.log_origin, [])
        self.log_destination_box = self._entry(routes, 1, "Arrivée", self.log_destination, [])
        self._entry(routes, 2, "Durée / tours", self.log_turns)
        routebuttons = ttk.Frame(routes)
        routebuttons.grid(row=3, column=0, columnspan=2)
        self._button(routebuttons, "Ajouter / modifier route", self.save_log_route)
        self._button(routebuttons, "Supprimer route", self.delete_log_route)
        self._entry(routes, 4, "Pertes en embuscade", self.log_casualties)
        self._entry(routes, 5, "Retard en embuscade", self.log_delay)
        self._entry(routes, 6, "Charges d'embuscade", self.log_charges)
        ab = ttk.Frame(routes)
        ab.grid(row=7, column=0, columnspan=2)
        self._button(ab, "Créer embuscade", self.save_ambush)
        self._button(ab, "Supprimer embuscade", self.remove_ambush)
        self.log_route_tree = self.ttk.Treeview(
            logistics, columns=("depart", "arrivee", "tours", "embuscade"),
            show="headings", height=5)
        for key, label in (("depart", "Départ"), ("arrivee", "Arrivée"),
                           ("tours", "Tours"), ("embuscade", "Embuscade")):
            self.log_route_tree.heading(key, text=label)
        self.log_route_tree.pack(fill="x", pady=6)
        rescue = ttk.LabelFrame(logistics, text="Missions de secours et poursuite", padding=8)
        rescue.pack(fill="x", pady=5)
        self.log_rescue_box = self._entry(rescue, 0, "Carte de secours", self.log_rescue, [])
        self.log_pursuit_box = self._entry(rescue, 1, "Carte de poursuite", self.log_pursuit, [])
        self._entry(rescue, 2, "Rançon en provisions", self.log_ransom)
        self._entry(rescue, 3, "Récompense de poursuite", self.log_reward)
        side_buttons = ttk.Frame(rescue)
        side_buttons.grid(row=4, column=0, columnspan=2, sticky="ew")
        self._button(side_buttons, "Appliquer les missions annexes",
                     self.save_side_missions)
        self.ttk.Label(logistics, text="Les combats annexes sont de vraies missions "
                       "tactiques préalablement dessinées dans Carte et combat. "
                       "Les convois exigent une route et des réservistes.").pack(
                           anchor="w", padx=8, pady=3)

        toolbar = ttk.Frame(timeline)
        toolbar.pack(fill="x", padx=6, pady=5)
        self._button(toolbar, "Simuler 8 tours", self.preview)
        self._button(toolbar, "Démarrer / rejouer", self.start_siege)
        self._button(toolbar, "Jouer dans Command Center", self.play_siege)
        self._button(toolbar, "Jouer dans Player 2.8", self.play_in_player)
        ttk.Label(toolbar, text="Slot (1–9)").pack(side="left", padx=(12, 2))
        ttk.Entry(toolbar, textvariable=self.slot, width=4).pack(side="left")
        self._button(toolbar, "Sauver partie", self.save_session)
        self._button(toolbar, "Charger siège", self.load_session)
        self.timeline_text = self.tk.Text(timeline, wrap="none", height=18)
        self.timeline_text.pack(fill="both", expand=True, padx=7, pady=6)
        ttk.Label(timeline, text="Aperçu stratégique sans IA tactique : les résultats de mission "
                  "et les déblocages du final exigent une véritable partie.",
                  wraplength=880).pack(fill="x", padx=8)
        ttk.Label(root, textvariable=self.status, wraplength=1050).pack(
            fill="x", padx=10, pady=5)

    def _open_tab(self, title):
        for tab in self.owner.workspace.notebook.tabs():
            if self.owner.workspace.notebook.tab(tab, "text") == title:
                self.owner.workspace.notebook.select(tab)
                return
        raise RuleError("Studio introuvable : " + title)

    def blueprint(self):
        sid = self.siege_id.get()
        return next((row for row in self.owner.project.sieges if row["id"] == sid), None)

    def _require(self):
        row = self.blueprint()
        require(row is not None, "Sélectionner ou créer un siège.")
        return row

    def _apply(self, blueprint):
        self.owner.project = edit.replace_siege(
            self.owner.project, self.owner._content(), blueprint)
        self.status.set("Siège validé. Enregistrer le projet .game.json pour le conserver.")
        self.owner.refresh()

    def new_siege(self):
        sid = self.owner.dialogs.askstring("Nouveau siège", "Identifiant du siège :")
        if sid is None:
            return
        cid = self.parent_campaign.get() or self.owner.campaign_id.get()
        new = edit.new_blueprint(sid, cid, self.owner.mission())
        self._apply(new)
        self.siege_id.set(sid)
        self.refresh()

    def delete_siege(self):
        sid = self._require()["id"]
        self.owner.project = edit.delete_siege(self.owner.project, self.owner._content(), sid)
        self.session = None
        self.session_id = ""
        self.siege_id.set("")
        self.owner.refresh()

    def _selected_front(self, _event=None):
        if self._refreshing:
            return
        chosen = self.front_tree.selection()
        bp = self.blueprint()
        if not chosen or bp is None:
            return
        front = chosen[0]
        row = bp["specs"][front]
        self.front_id.set(front)
        self.mission_id.set(bp["fronts"][front])
        self.strength.set(str(row["strength"]))
        self.opposition.set(str(row["opposition"]))
        self.doctrine.set(row["doctrine"])

    def _front_settings(self):
        return {"strength": int(self.strength.get()),
                "opposition": int(self.opposition.get()),
                "doctrine": self.doctrine.get()}

    def add_front(self):
        bp = edit.add_front(self._require(), self.front_id.get(),
                            self.mission_id.get(), **self._front_settings())
        self._apply(bp)

    def update_front(self):
        bp = deepcopy(self._require())
        front = self.front_id.get()
        require(front in bp["fronts"], "Unknown front; use + Front first")
        bp["fronts"][front] = self.mission_id.get()
        bp["specs"][front] = self._front_settings()
        self._apply(bp)

    def remove_front(self):
        self._apply(edit.remove_front(self._require(), self.front_id.get()))

    def set_focus(self):
        bp = deepcopy(self._require())
        require(self.front_id.get() in bp["fronts"], "Unknown front")
        bp["focused"] = self.front_id.get()
        self._apply(bp)

    def save_final(self):
        bp = deepcopy(self._require())
        target = self.final.get()
        prior = self.required.get()
        values = [s.strip() for s in self.outcomes.get().split(",") if s.strip()]
        require(values and len(set(values)) == len(values)
                and set(values) <= set(edit.OUTCOMES), "Invalid accepted outcomes")
        require(prior in bp["fronts"] and prior != target,
                "Choose a non-final prerequisite front")
        current = (bp["campaign"]["required_fronts"]
                   if bp["campaign"] is not None else {})
        reqs = deepcopy(current)
        if bp["campaign"] is not None and bp["campaign"]["final_front"] != target:
            reqs = {}
        reqs[prior] = values
        self._apply(edit.set_finale(bp, target, reqs))

    def clear_final(self):
        self._apply(edit.set_finale(self._require(), "", {}))

    def _selected_link(self, _event=None):
        if self._refreshing:
            return
        selected = self.link_tree.selection()
        bp = self.blueprint()
        if not selected or bp is None:
            return
        link = next((l for l in bp["links"] if l["id"] == selected[0]), None)
        if link is None:
            return
        effect = link["effects"][0]
        self.link_id.set(link["id"])
        self.link_source.set(link["source"])
        self.link_event.set(link["event"])
        self.link_match.set(next(iter(link["match"].values())))
        self.link_target.set(effect["front"])
        self.effect_kind.set(effect["kind"])
        self.effect_value.set(str(effect.get("amount", effect.get("object", ""))))
        self._object_choices()

    def _object_choices(self):
        bp = self.blueprint()
        if bp is None:
            return
        field = front_links.EVENT_FIELDS.get(self.link_event.get(), "object")
        source = bp["fronts"].get(self.link_source.get())
        target = bp["fronts"].get(self.link_target.get())
        content = self.owner._content()
        values = (["victory", "defeat"] if field == "result" else
                  [obj["id"] for obj in content.missions[source].objects] if source else [])
        self.match_box["values"] = values
        self.effect_box["values"] = ([obj["id"] for obj in content.missions[target].objects]
                                     if target else [])

    def _effect(self):
        kind = self.effect_kind.get()
        effect = {"kind": kind, "front": self.link_target.get()}
        if kind in ("reduce_opposition", "reduce_strength"):
            effect["amount"] = int(self.effect_value.get())
        elif kind in ("open_door", "disable_defense"):
            effect["object"] = self.effect_value.get()
        return effect

    def _link(self, effects):
        event = self.link_event.get()
        require(event in front_links.EVENT_FIELDS, "Unknown trigger event")
        return {"id": self.link_id.get(), "source": self.link_source.get(),
                "event": event,
                "match": {front_links.EVENT_FIELDS[event]: self.link_match.get()},
                "effects": effects}

    def save_link(self):
        # Editing first effect preserves additional effects of that same link.
        bp = self._require()
        existing = next((l for l in bp["links"] if l["id"] == self.link_id.get()), None)
        effects = [self._effect()] + (deepcopy(existing["effects"][1:])
                                      if existing is not None else [])
        self._apply(edit.upsert_link(bp, self._link(effects)))

    def append_effect(self):
        bp = self._require()
        existing = next((l for l in bp["links"] if l["id"] == self.link_id.get()), None)
        require(existing is not None, "Créer le lien avant d'ajouter une conséquence")
        replacement = deepcopy(existing)
        replacement["effects"].append(self._effect())
        self._apply(edit.upsert_link(bp, replacement))

    def delete_link(self):
        self._apply(edit.remove_link(self._require(), self.link_id.get()))

    def add_wave(self):
        bp = self._require()
        mid = bp["fronts"][self.wave_front.get()]
        lifetime = int(self.wave_life.get()) if self.wave_life.get().strip() else None
        def change():
            self.owner.doc().replace(edit.add_wave(
                self.owner.doc().data, mid, self.wave_id.get(), int(self.wave_turn.get()),
                self.wave_actor.get(), self.wave_arch.get(),
                [int(self.wave_x.get()), int(self.wave_y.get())],
                team=self.wave_team.get(), lifetime=lifetime))
        self.owner.design_change(change)
        self.owner.refresh()

    def delete_wave(self):
        bp = self._require()
        selected = self.wave_tree.selection()
        require(bool(selected), "Sélectionner une vague")
        front, event_id = selected[0].split(":", 1)
        mid = bp["fronts"][front]
        self.owner.design_change(lambda: self.owner.doc().replace(
            edit.remove_wave(self.owner.doc().data, mid, event_id)))
        self.owner.refresh()

    def preview(self):
        bp = self._require()
        history = edit.timeline_preview(bp)
        lines = [f"Siège {bp['id']} — 1 tour global = 1 synchronisation stratégique",
                 f"Contrôle initial : {bp['focused']}",
                 f"Finale : {(bp['campaign'] or {}).get('final_front', 'libre')}", ""]
        for state in history:
            lines.append("TOUR " + str(state["turn"]))
            for front, row in sorted(state["fronts"].items()):
                lines.append(f"  {front:16} {row['strength']:3} vs "
                             f"{row['opposition']:3} · {row['doctrine']:7} · {row['status']}")
        self.timeline_text.delete("1.0", "end")
        self.timeline_text.insert("1.0", "\n".join(lines))

    def _logistics(self):
        bp = self._require()
        require("logistics" in bp, "Activer la logistique d'abord")
        return deepcopy(bp), deepcopy(bp["logistics"])

    def save_logistics(self):
        bp = deepcopy(self._require())
        config = deepcopy(bp.get("logistics", {}))
        config.update(
            reserves={"player": int(self.log_reserves.get()), "enemy": 0},
            supplies={"player": int(self.log_supplies.get()), "enemy": 0},
            capacity=int(self.log_capacity.get()), escorts=int(self.log_escorts.get()))
        bp["logistics"] = config
        self._apply(bp)

    def clear_logistics(self):
        bp = deepcopy(self._require())
        bp.pop("logistics", None)
        self._apply(bp)

    def save_log_route(self):
        bp, config = self._logistics()
        src, dst = self.log_origin.get(), self.log_destination.get()
        rows = [row for row in config.get("routes", [])
                if (row["from"], row["to"]) != (src, dst)]
        rows.append({"from": src, "to": dst, "turns": int(self.log_turns.get())})
        config["routes"] = rows
        bp["logistics"] = config
        self._apply(bp)

    def delete_log_route(self):
        bp, config = self._logistics()
        src, dst = self.log_origin.get(), self.log_destination.get()
        config["routes"] = [row for row in config.get("routes", [])
                            if (row["from"], row["to"]) != (src, dst)]
        config["ambushes"] = [row for row in config.get("ambushes", [])
                              if (row["from"], row["to"]) != (src, dst)]
        bp["logistics"] = config
        self._apply(bp)

    def save_ambush(self):
        bp, config = self._logistics()
        src, dst = self.log_origin.get(), self.log_destination.get()
        rows = [row for row in config.get("ambushes", [])
                if (row["from"], row["to"]) != (src, dst)]
        rows.append({"from": src, "to": dst, "casualties": int(self.log_casualties.get()),
                     "delay": int(self.log_delay.get()),
                     "charges": int(self.log_charges.get())})
        config["ambushes"] = rows
        bp["logistics"] = config
        self._apply(bp)

    def remove_ambush(self):
        bp, config = self._logistics()
        src, dst = self.log_origin.get(), self.log_destination.get()
        config["ambushes"] = [row for row in config.get("ambushes", [])
                              if (row["from"], row["to"]) != (src, dst)]
        bp["logistics"] = config
        self._apply(bp)

    def save_side_missions(self):
        bp, config = self._logistics()
        rescue, pursuit = self.log_rescue.get(), self.log_pursuit.get()
        if rescue:
            config["rescue_mission"] = rescue
        else:
            config.pop("rescue_mission", None)
        if pursuit:
            require(bool(rescue), "Une poursuite exige une mission de secours")
            config["choices"] = {"ransom": int(self.log_ransom.get()),
                                 "pursuit_mission": pursuit,
                                 "pursuit_reward": int(self.log_reward.get())}
        else:
            config.pop("choices", None)
        bp["logistics"] = config
        self._apply(bp)

    def start_siege(self):
        from .tactical_rpg3 import authored_rules_for_document
        self.session = edit.make_session(
            self._require(), self.owner._content(),
            rules=authored_rules_for_document(self.owner.doc().data))
        self.session_id = self.siege_id.get()
        self.status.set("Siège prêt. Jouer puis sauver la session via un emplacement.")

    def _session(self):
        bp = self._require()
        require(self.session is not None and self.session_id == bp["id"],
                "Démarrer ou charger d'abord ce siège")
        return bp, self.session

    def play_siege(self):
        if self.session is None or self.session_id != self.siege_id.get():
            self.start_siege()
        from .strategic_ui import launch
        self.session = launch(self.session)
        self.status.set("Retour du Command Center. Sauvegarder la partie si nécessaire.")

    def play_in_player(self):
        """Launch the same authored siege in 2D Player, with verified slots."""
        from .authored_siege_player import AuthoredSiegeController
        from .studio_siege_player_app import launch
        from .tactical_rpg3 import authored_rules_for_document

        bp = self._require()
        content = self.owner._content()
        rules = authored_rules_for_document(self.owner.doc().data)
        slot = int(self.slot.get())
        controller = AuthoredSiegeController(
            content, bp, self.owner.project_path, slot, rules=rules,
            project=self.owner.project)
        if self.session is not None and self.session_id == bp["id"]:
            exists = controller.save_path.exists()
            from tkinter import messagebox
            if (exists and not messagebox.askyesno(
                    "Écraser le slot ?",
                    "Lancer l'état actuellement chargé dans le Studio remplacera "
                    "le checkpoint du slot. Continuer ?",
                    parent=self.tab)):
                return
            controller.adopt(self.session, overwrite=exists)
        app = launch(content, bp, self.owner.project, self.owner.project_path,
                     slot, rules=rules, master=self.tab.winfo_toplevel(),
                     controller=controller)
        app.root.wait_window()
        if controller.session is not None:
            self.session = controller.session.fronts
            self.session_id = bp["id"]
            self.status.set("Retour du Player. Siège et checkpoint vérifiés ; "
                            "le slot est automatiquement sauvegardé.")

    def save_session(self):
        bp, session = self._session()
        path = edit.save_siege_slot(self.owner.project_path, bp,
                                     int(self.slot.get()), session)
        self.status.set(f"Siège enregistré : {path}")

    def load_session(self):
        bp = self._require()
        from .tactical_rpg3 import authored_rules_for_document
        self.session = edit.load_siege_slot(
            self.owner.project_path, bp, int(self.slot.get()),
            self.owner._content(),
            rules=authored_rules_for_document(self.owner.doc().data))
        self.session_id = bp["id"]
        self.status.set("Siège chargé et journal vérifié. Reprendre dans Command Center.")

    def _graph_click(self, _event=None):
        tags = self.graph.gettags("current")
        key = next((t[5:] for t in tags if t.startswith("node_")), "")
        if key and self.front_tree.exists(key):
            self.front_tree.selection_set(key)
            self._selected_front()

    def _draw(self, bp):
        self.graph.delete("all")
        if bp is None:
            return
        names = list(bp["fronts"])
        positions = {front: (25 + i % 3 * 225, 18 + i // 3 * 106)
                     for i, front in enumerate(names)}
        for link in bp["links"]:
            start = positions[link["source"]]
            for effect in link["effects"]:
                end = positions[effect["front"]]
                self.graph.create_line(start[0] + 90, start[1] + 65,
                                       end[0] + 90, end[1],
                                       arrow="last", fill="#64748b", width=2)
        if bp["campaign"] is not None:
            final = positions[bp["campaign"]["final_front"]]
            for req in bp["campaign"]["required_fronts"]:
                point = positions[req]
                self.graph.create_line(point[0] + 170, point[1] + 34,
                                       final[0], final[1] + 34,
                                       dash=(4, 3), arrow="last", fill="#16a34a")
        for front, (x, y) in positions.items():
            active = front == bp["focused"]
            final = bp["campaign"] is not None and front == bp["campaign"]["final_front"]
            fill = "#bbf7d0" if active else "#fde68a" if final else "#dbeafe"
            tag = "node_" + front
            self.graph.create_rectangle(x, y, x + 185, y + 66,
                                        fill=fill, outline="#475569", tags=(tag,))
            self.graph.create_text(x + 92, y + 22, text=front,
                                   font=("TkDefaultFont", 10, "bold"), tags=(tag,))
            self.graph.create_text(x + 92, y + 44, text=bp["fronts"][front],
                                   tags=(tag,))
        self.graph.configure(scrollregion=(0, 0, 710,
                              max(280, 140 + (len(names) + 2) // 3 * 106)))

    def refresh(self):
        if self._refreshing or self.owner.project is None:
            return
        self._refreshing = True
        try:
            sieges = self.owner.project.sieges
            ids = [row["id"] for row in sieges]
            self.siege_box["values"] = ids
            if self.siege_id.get() not in ids:
                self.siege_id.set(ids[0] if ids else "")
            bp = self.blueprint()
            campaigns = [row["id"] for row in self.owner.project.campaigns]
            self.campaign_box["values"] = campaigns
            if bp:
                self.parent_campaign.set(bp["campaign_id"])
            elif self.parent_campaign.get() not in campaigns:
                self.parent_campaign.set(campaigns[0] if campaigns else "")
            missions = sorted(self.owner._content().missions)
            self.front_missions["values"] = missions
            fronts = list(bp["fronts"]) if bp else []
            for field in (self.final_box, self.required_box, self.link_source_box,
                          self.link_target_box, self.wave_front_box):
                field["values"] = fronts
            self.wave_arch_box["values"] = sorted(self.owner.doc().data.get("archetypes", {}))
            self.log_origin_box["values"] = ["reserve", *fronts]
            self.log_destination_box["values"] = fronts
            self.log_rescue_box["values"] = ["", *missions]
            self.log_pursuit_box["values"] = ["", *missions]
            for child in self.log_route_tree.get_children():
                self.log_route_tree.delete(child)
            if bp and "logistics" in bp:
                config = bp["logistics"]
                self.log_reserves.set(str(config.get("reserves", {}).get("player", 0)))
                self.log_supplies.set(str(config.get("supplies", {}).get("player", 0)))
                self.log_capacity.set(str(config.get("capacity", 6)))
                self.log_escorts.set(str(config.get("escorts", 0)))
                self.log_rescue.set(config.get("rescue_mission", "") or "")
                choices = config.get("choices", {})
                self.log_pursuit.set(choices.get("pursuit_mission", ""))
                self.log_ransom.set(str(choices.get("ransom", 2)))
                self.log_reward.set(str(choices.get("pursuit_reward", 2)))
                ambushes = {(row["from"], row["to"]) for row in config.get("ambushes", [])}
                for i, route in enumerate(config.get("routes", [])):
                    src, dst = route["from"], route["to"]
                    self.log_route_tree.insert(
                        "", "end", iid=str(i),
                        values=(src, dst, route["turns"],
                                "oui" if (src, dst) in ambushes else "non"))
            if fronts and self.log_destination.get() not in fronts:
                self.log_destination.set(fronts[0])
            if fronts:
                if self.front_id.get() not in fronts:
                    self.front_id.set(fronts[0])
                if self.wave_front.get() not in fronts:
                    self.wave_front.set(fronts[0])
                if self.link_source.get() not in fronts:
                    self.link_source.set(fronts[0])
                if self.link_target.get() not in fronts:
                    self.link_target.set(fronts[-1])
                if self.mission_id.get() not in missions:
                    self.mission_id.set(bp["fronts"][fronts[0]])
                if self.final.get() not in ["", *fronts]:
                    self.final.set("")
                if bp["campaign"] is not None:
                    self.final.set(bp["campaign"]["final_front"])
                    if self.required.get() not in bp["campaign"]["required_fronts"]:
                        self.required.set(next(iter(bp["campaign"]["required_fronts"])))
                    self.outcomes.set(",".join(bp["campaign"]["required_fronts"]
                                                   [self.required.get()]))
                elif self.required.get() not in fronts:
                    self.required.set(fronts[0])
            for child in self.front_tree.get_children():
                self.front_tree.delete(child)
            if bp:
                for name, mission in bp["fronts"].items():
                    spec = bp["specs"][name]
                    self.front_tree.insert("", "end", iid=name, text=name,
                        values=(mission, spec["strength"], spec["opposition"], spec["doctrine"]))
            for child in self.link_tree.get_children():
                self.link_tree.delete(child)
            if bp:
                for link in bp["links"]:
                    self.link_tree.insert("", "end", iid=link["id"], text=link["id"],
                        values=(link["source"], link["event"],
                                ",".join(a["front"] for a in link["effects"]),
                                ",".join(a["kind"] for a in link["effects"])))
            for child in self.wave_tree.get_children():
                self.wave_tree.delete(child)
            if bp:
                for front, eid, tick, actor, arch in edit.waves_for(
                        self.owner._content(), bp["fronts"]):
                    self.wave_tree.insert("", "end", iid=front + ":" + eid,
                        text=front, values=(eid, tick, actor, arch))
            self._draw(bp)
            self.logistics_editor.refresh(bp)
            self.routes_editor.refresh(bp)
            self.strategic_editor.refresh(bp)
            self._object_choices()
        finally:
            self._refreshing = False
