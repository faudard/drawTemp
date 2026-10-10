"""2.5.4.4 visual campaign routes, diplomacy and recovery authoring.

The editor is a thin Tk frontend for routes_authoring and therefore for the
existing CampaignRoutesPolicy.  It never writes a fabricated battle result.
"""
from copy import deepcopy

from . import routes_authoring as edit
from .model import require


class RoutesStudio:
    def __init__(self, parent, frame):
        self.parent = parent
        self.ttk, self.tk = parent.ttk, parent.tk
        self.route_id = self.tk.StringVar(value="direct")
        self.route_requires = self.tk.StringVar()
        self.route_outcomes = self.tk.StringVar(value="victory")
        self.route_supplies = self.tk.StringVar(value="3")
        self.route_losses = self.tk.StringVar(value="4")
        self.front = self.tk.StringVar()
        self.target = self.tk.StringVar()
        self.choice = self.tk.StringVar(value="negotiation")
        self.event = self.tk.StringVar(value="interact")
        self.object = self.tk.StringVar()
        self.choice_supplies = self.tk.StringVar(value="2")
        self.choice_losses = self.tk.StringVar(value="1")
        self.treaty_source = self.tk.StringVar()
        self.treaty_event = self.tk.StringVar(value="interact")
        self.treaty_object = self.tk.StringVar()
        self.treaty_units = self.tk.StringVar()
        self.recovery_front = self.tk.StringVar()
        self.recovery_mission = self.tk.StringVar()
        self.recovery_supplies = self.tk.StringVar(value="1")
        self.recovery_losses = self.tk.StringVar(value="1")
        self.recovery_strength = self.tk.StringVar(value="2")
        self.counter_turn = self.tk.StringVar(value="5")
        self.counter_mission = self.tk.StringVar()
        self.counter_losses = self.tk.StringVar(value="2")
        self.counter_gain = self.tk.StringVar(value="3")
        self.status = self.tk.StringVar(
            value="Créer une finale dans Fronts et finale, puis activer les itinéraires.")
        self._build(frame)

    def _field(self, frame, row, caption, var, choices=None, width=20):
        self.ttk.Label(frame, text=caption).grid(
            row=row, column=0, padx=4, pady=3, sticky="w")
        field = (self.ttk.Entry(frame, textvariable=var, width=width)
                 if choices is None else self.ttk.Combobox(
                     frame, textvariable=var, values=choices, width=width,
                     state="readonly"))
        field.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
        frame.columnconfigure(1, weight=1)
        return field

    def _button(self, frame, label, method):
        self.ttk.Button(frame, text=label,
                        command=lambda: self.parent.owner._run(method)).pack(
                            side="left", padx=3, pady=3)

    def _build(self, frame):
        ttk = self.ttk
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=4)
        self._button(toolbar, "Activer itinéraires", self.enable)
        self._button(toolbar, "Désactiver itinéraires", self.disable)
        self._button(toolbar, "Prévisualiser conditions", self.preview)
        self.graph = self.tk.Canvas(frame, height=115, background="#f8fafc")
        self.graph.pack(fill="x", padx=8, pady=4)
        pages = ttk.Notebook(frame)
        pages.pack(fill="both", expand=True, padx=6, pady=3)
        routes = ttk.Frame(pages)
        choices = ttk.Frame(pages)
        treaties = ttk.Frame(pages)
        recoveries = ttk.Frame(pages)
        pages.add(routes, text="Itinéraires")
        pages.add(choices, text="Issues tactiques")
        pages.add(treaties, text="Traités")
        pages.add(recoveries, text="Reconquête / riposte")

        route_columns = ("needs", "vivres", "pertes")
        self.route_tree = ttk.Treeview(
            routes, show="tree headings", columns=route_columns, height=7)
        for col, title in (("#0", "Approche"), ("needs", "Prérequis"),
                           ("vivres", "Vivres"), ("pertes", "Pertes")):
            self.route_tree.heading(col, text=title)
            self.route_tree.column(col, width=170 if col == "needs" else 100)
        self.route_tree.pack(side="left", fill="both", expand=True, padx=4, pady=5)
        self.route_tree.bind("<<TreeviewSelect>>", self._selected_route)
        route_form = ttk.Frame(routes)
        route_form.pack(side="right", fill="y", padx=5)
        self._field(route_form, 0, "Nom d'itinéraire", self.route_id)
        self.route_front_box = self._field(
            route_form, 1, "Front requis (facultatif)", self.route_requires, [])
        self._field(route_form, 2, "Issues autorisées", self.route_outcomes)
        self._field(route_form, 3, "Coût vivres", self.route_supplies)
        self._field(route_form, 4, "Pertes alliées", self.route_losses)
        rb = ttk.Frame(route_form)
        rb.grid(row=5, columnspan=2)
        self._button(rb, "Enregistrer itinéraire", self.save_route)
        self._button(rb, "Supprimer itinéraire", self.delete_route)
        ttk.Label(route_form, text="La voie breach reste gratuite.\n"
                  "Les choix directs sans prérequis doivent coûter\n"
                  "des vivres ET des combattants.",
                  justify="left").grid(row=6, columnspan=2, pady=8)

        self.choice_tree = ttk.Treeview(
            choices, show="tree headings", columns=("type", "target", "effect"),
            height=7)
        for col, title in (("#0", "Front"), ("type", "Issue"),
                           ("target", "Cible"), ("effect", "Pertes")):
            self.choice_tree.heading(col, text=title)
            self.choice_tree.column(col, width=125)
        self.choice_tree.pack(side="left", fill="both", expand=True, padx=4)
        self.choice_tree.bind("<<TreeviewSelect>>", self._selected_choice)
        choice_form = ttk.Frame(choices)
        choice_form.pack(side="right", fill="y", padx=6)
        self.front_box = self._field(
            choice_form, 0, "Front concerné", self.front, [])
        self.choice_box = self._field(
            choice_form, 1, "Type", self.choice,
            ["partial", "negotiation", "retreat"])
        self.target_box = self._field(
            choice_form, 2, "Front impacté", self.target, [])
        self._field(choice_form, 3, "Coût / vivres", self.choice_supplies)
        self._field(choice_form, 4, "Pertes au front cible", self.choice_losses)
        self._field(choice_form, 5, "Événement réel", self.event,
                    ["interact", "defense_sabotaged"])
        self.choice_object_box = self._field(
            choice_form, 6, "Objet déclencheur", self.object, [])
        self.front_box.bind("<<ComboboxSelected>>",
                            lambda _e: self._objects())
        self.event.trace_add("write", lambda *_: self._objects())
        cb = ttk.Frame(choice_form)
        cb.grid(row=7, columnspan=2)
        self._button(cb, "Enregistrer issue", self.save_choice)
        self._button(cb, "Supprimer issue", self.delete_choice)

        treaty_form = ttk.Frame(treaties)
        treaty_form.pack(side="right", fill="y", padx=7)
        self.treaty_tree = ttk.Treeview(
            treaties, show="tree headings",
            columns=("proof", "trigger", "standdown"), height=8)
        for col, title in (("#0", "Accord"), ("proof", "Preuve"),
                           ("trigger", "Événement"), ("standdown", "Retrait final")):
            self.treaty_tree.heading(col, text=title)
            self.treaty_tree.column(col, width=140)
        self.treaty_tree.pack(side="left", fill="both", expand=True, padx=4)
        self.treaty_tree.bind("<<TreeviewSelect>>", self._selected_treaty)
        self.treaty_front_box = self._field(
            treaty_form, 0, "Front négocié", self.treaty_front(), [])
        self.treaty_source_box = self._field(
            treaty_form, 1, "Front source de preuve", self.treaty_source, [])
        self.treaty_event_box = self._field(
            treaty_form, 2, "Événement", self.treaty_event,
            ["interact", "defense_sabotaged"])
        self.treaty_object_box = self._field(
            treaty_form, 3, "Objet de preuve", self.treaty_object, [])
        self._field(treaty_form, 4, "Gardes démobilisés (IDs, virgules)",
                    self.treaty_units, width=24)
        self.treaty_source_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._objects())
        self.treaty_event.trace_add("write", lambda *_: self._objects())
        tb = ttk.Frame(treaty_form)
        tb.grid(row=5, columnspan=2)
        self._button(tb, "Enregistrer traité", self.save_treaty)
        self._button(tb, "Supprimer traité", self.delete_treaty)
        ttk.Label(treaty_form, text="Une négociation exige d'abord une\n"
                  "preuve tactique réellement acquise.",
                  justify="left").grid(row=6, columnspan=2, pady=7)

        self.recovery_tree = ttk.Treeview(
            recoveries, show="tree headings",
            columns=("mission", "cost", "counter"), height=7)
        for col, title in (("#0", "Front"), ("mission", "Mission de reconquête"),
                           ("cost", "Vivres"), ("counter", "Riposte T")):
            self.recovery_tree.heading(col, text=title)
            self.recovery_tree.column(col, width=145)
        self.recovery_tree.pack(side="left", fill="both", expand=True, padx=3)
        self.recovery_tree.bind("<<TreeviewSelect>>", self._selected_recovery)
        recovery_form = ttk.Frame(recoveries)
        recovery_form.pack(side="right", fill="y", padx=7)
        self.recovery_front_box = self._field(
            recovery_form, 0, "Front à reprendre", self.recovery_front, [])
        self.recovery_mission_box = self._field(
            recovery_form, 1, "Mission tactique", self.recovery_mission, [])
        self._field(recovery_form, 2, "Vivres reconquête", self.recovery_supplies)
        self._field(recovery_form, 3, "Pertes alliées", self.recovery_losses)
        self._field(recovery_form, 4, "Force reconquise", self.recovery_strength)
        rbuttons = ttk.Frame(recovery_form)
        rbuttons.grid(row=5, columnspan=2)
        self._button(rbuttons, "Enregistrer reconquête", self.save_recovery)
        self._button(rbuttons, "Supprimer reconquête", self.delete_recovery)
        self._field(recovery_form, 6, "Tour de riposte", self.counter_turn)
        self.counter_mission_box = self._field(
            recovery_form, 7, "Mission de riposte", self.counter_mission, [])
        self._field(recovery_form, 8, "Pertes défensives", self.counter_losses)
        self._field(recovery_form, 9, "Opposition ennemie +", self.counter_gain)
        cbuttons = ttk.Frame(recovery_form)
        cbuttons.grid(row=10, columnspan=2)
        self._button(cbuttons, "Enregistrer riposte", self.save_counter)
        self._button(cbuttons, "Supprimer riposte", self.delete_counter)

        ttk.Label(frame, textvariable=self.status, wraplength=1000).pack(
            fill="x", padx=7, pady=3)

    def treaty_front(self):
        if not hasattr(self, "_treaty_front"):
            self._treaty_front = self.tk.StringVar()
        return self._treaty_front

    def _bp(self):
        return self.parent._require()

    def _content(self):
        return self.parent.owner._content()

    def _apply(self, bp):
        self.parent._apply(bp)
        self.status.set("Politique validée par MultiFrontSession. Enregistrer le projet.")

    def enable(self):
        self._apply(edit.enable(self._bp(), self._content(),
                                alternative=self.route_id.get()))

    def disable(self):
        self._apply(edit.disable(self._bp(), self._content()))

    def save_route(self):
        bp = self._bp()
        spec = bp["campaign"] or {}
        old = spec.get("routes", {}).get(self.route_id.get(), {})
        required = deepcopy(old.get("required", {}))
        front = self.route_requires.get()
        if front:
            outcomes = [x.strip() for x in self.route_outcomes.get().split(",") if x.strip()]
            required[front] = outcomes
        # Choose "none" to clear prerequisite lists intentionally.
        if self.route_requires.get() == "none":
            required = {}
        self._apply(edit.route(bp, self._content(), self.route_id.get(), required,
                               int(self.route_supplies.get()),
                               int(self.route_losses.get())))

    def delete_route(self):
        self._apply(edit.delete_route(self._bp(), self._content(), self.route_id.get()))

    def save_choice(self):
        args = (self._bp(), self._content(), self.front.get())
        kind = self.choice.get()
        if kind == "partial":
            next_bp = edit.partial(*args, self.event.get(), self.object.get(),
                                   int(self.choice_supplies.get()),
                                   self.target.get(), int(self.choice_losses.get()))
        elif kind == "negotiation":
            next_bp = edit.negotiation(*args, int(self.choice_supplies.get()),
                                       self.target.get(), int(self.choice_losses.get()))
        elif kind == "retreat":
            next_bp = edit.retreat(*args, self.target.get(),
                                   int(self.choice_losses.get()))
        else:
            raise ValueError("Unknown campaign outcome")
        self._apply(next_bp)

    def delete_choice(self):
        self._apply(edit.delete_choice(
            self._bp(), self._content(), self.choice.get(), self.front.get()))

    def save_treaty(self):
        units = [x.strip() for x in self.treaty_units.get().split(",") if x.strip()]
        self._apply(edit.treaty(
            self._bp(), self._content(), self.treaty_front().get(),
            self.treaty_source.get(), self.treaty_event.get(),
            self.treaty_object.get(), units))

    def delete_treaty(self):
        self._apply(edit.delete_treaty(
            self._bp(), self._content(), self.treaty_front().get()))

    def save_recovery(self):
        self._apply(edit.recovery(
            self._bp(), self._content(), self.recovery_front.get(),
            self.recovery_mission.get(), int(self.recovery_supplies.get()),
            int(self.recovery_losses.get()),
            int(self.recovery_strength.get())))

    def delete_recovery(self):
        self._apply(edit.delete_recovery(
            self._bp(), self._content(), self.recovery_front.get()))

    def save_counter(self):
        self._apply(edit.counteroffensive(
            self._bp(), self._content(), self.recovery_front.get(),
            int(self.counter_turn.get()), self.counter_mission.get(),
            int(self.counter_losses.get()), int(self.counter_gain.get())))

    def delete_counter(self):
        self._apply(edit.delete_counteroffensive(
            self._bp(), self._content(), self.recovery_front.get()))

    def preview(self):
        info = edit.preview(self._bp(), self._content())
        self.status.set(
            "Approches : " + ", ".join(info["available"]) +
            " | requis : " + str(info["required"]) +
            " | vivres : " + str(info["supply_pool"]) +
            " | traités : " + ", ".join(info["treaties"]) +
            " | reconquêtes : " + ", ".join(info["recovery"]))

    def _selected_route(self, _event=None):
        selected = self.route_tree.selection()
        spec = (self._bp().get("campaign") or {}).get("routes", {})
        if not selected or selected[0] not in spec:
            return
        name = selected[0]
        row = spec[name]
        self.route_id.set(name)
        self.route_supplies.set(str(row["supplies"]))
        self.route_losses.set(str(row["strength_loss"]))
        if row["required"]:
            front, outcomes = next(iter(row["required"].items()))
            self.route_requires.set(front)
            self.route_outcomes.set(",".join(outcomes))
        else:
            self.route_requires.set("")

    def _selected_choice(self, _event=None):
        selected = self.choice_tree.selection()
        if not selected:
            return
        front, kind = selected[0].split(":", 1)
        rule = self._bp()["campaign"][kind][front]
        self.front.set(front)
        self.choice.set(kind)
        self.target.set(rule["target"])
        self.choice_losses.set(str(rule["target_loss"]))
        self.choice_supplies.set(str(rule.get("supplies", rule.get("cost", 0))))
        self.event.set(rule.get("event", "interact"))
        self._objects()
        self.object.set(rule.get("object", ""))

    def _selected_treaty(self, _event=None):
        selected = self.treaty_tree.selection()
        if not selected:
            return
        front = selected[0]
        row = self._bp()["campaign"]["treaties"][front]
        self.treaty_front().set(front)
        self.treaty_source.set(row["requires_front"])
        self.treaty_event.set(row["event"])
        self._objects()
        self.treaty_object.set(row["object"])
        self.treaty_units.set(",".join(row.get("final_stand_down", [])))

    def _selected_recovery(self, _event=None):
        selected = self.recovery_tree.selection()
        if not selected:
            return
        front = selected[0]
        spec = self._bp()["campaign"]
        rule = spec["recovery"][front]
        self.recovery_front.set(front)
        self.recovery_mission.set(rule["mission"])
        self.recovery_supplies.set(str(rule["supplies"]))
        self.recovery_losses.set(str(rule["strength_loss"]))
        self.recovery_strength.set(str(rule["reclaimed_strength"]))
        if front in spec.get("counteroffensives", {}):
            row = spec["counteroffensives"][front]
            self.counter_turn.set(str(row["after_turn"]))
            self.counter_mission.set(row["mission"])
            self.counter_losses.set(str(row["strength_loss"]))
            self.counter_gain.set(str(row["opposition_gain"]))

    def _objects(self):
        bp = self.parent.blueprint()
        if bp is None:
            return
        content = self._content()
        front = self.front.get()
        source = self.treaty_source.get()
        def compatible(source_front, event):
            mid = bp["fronts"].get(source_front)
            if not mid:
                return []
            return sorted(obj["id"] for obj in content.missions[mid].objects
                          if (obj["kind"] == "defense") ==
                             (event == "defense_sabotaged")
                          and obj["kind"] != "passage")
        self.choice_object_box["values"] = compatible(front, self.event.get())
        self.treaty_object_box["values"] = compatible(source, self.treaty_event.get())

    def _draw(self, bp):
        self.graph.delete("all")
        if bp is None or bp.get("campaign") is None:
            self.graph.create_text(350, 50, text="Créer une finale pour éditer les itinéraires",
                                   fill="#334155")
            return
        routes = bp["campaign"].get("routes", {})
        names = list(routes) if routes else ["breach"]
        final = bp["campaign"]["final_front"]
        width = 700
        self.graph.create_text(width / 2, 18, text="Accès final : " + final,
                               fill="#1e293b", font=("TkDefaultFont", 10, "bold"))
        for i, name in enumerate(names):
            x = (i + 1) * width / (len(names) + 1)
            self.graph.create_line(x, 80, width / 2, 35, arrow="last", fill="#64748b")
            self.graph.create_rectangle(x-55, 66, x+55, 99,
                                        fill="#dbeafe" if name == "breach" else "#fde68a",
                                        outline="#64748b")
            self.graph.create_text(x, 81, text=name[:15], fill="#1e293b")
        self.graph.configure(scrollregion=(0, 0, width, 125))

    def refresh(self, bp):
        fronts = sorted(bp["fronts"]) if bp else []
        missions = sorted(self._content().missions)
        self.route_front_box["values"] = ["", *fronts]
        for box in (self.front_box, self.target_box, self.treaty_front_box,
                    self.treaty_source_box, self.recovery_front_box):
            box["values"] = fronts
        for box in (self.recovery_mission_box, self.counter_mission_box):
            box["values"] = missions
        if fronts:
            for var in (self.front, self.target, self.treaty_front(),
                        self.treaty_source, self.recovery_front):
                if var.get() not in fronts:
                    var.set(fronts[0])
            if self.recovery_mission.get() not in missions:
                self.recovery_mission.set(missions[0])
            if self.counter_mission.get() not in missions:
                self.counter_mission.set(missions[0])
        for tree in (self.route_tree, self.choice_tree, self.treaty_tree, self.recovery_tree):
            for item in tree.get_children():
                tree.delete(item)
        if bp and bp.get("campaign"):
            spec = bp["campaign"]
            for name, row in spec.get("routes", {}).items():
                needed = ", ".join(front + ":" + "/".join(outcome)
                                   for front, outcome in row["required"].items()) or "aucun"
                self.route_tree.insert("", "end", iid=name, text=name,
                                       values=(needed, row["supplies"],
                                               row["strength_loss"]))
            for kind in ("partial", "negotiation", "retreat"):
                for front, row in spec[kind].items():
                    self.choice_tree.insert(
                        "", "end", iid=front + ":" + kind, text=front,
                        values=(kind, row["target"], row["target_loss"]))
            for front, rule in spec.get("treaties", {}).items():
                self.treaty_tree.insert(
                    "", "end", iid=front, text=front,
                    values=(rule["requires_front"], rule["event"] + ":" + rule["object"],
                            ",".join(rule.get("final_stand_down", []))))
            for front, rule in spec.get("recovery", {}).items():
                counter = spec.get("counteroffensives", {}).get(front, {})
                self.recovery_tree.insert(
                    "", "end", iid=front, text=front,
                    values=(rule["mission"], rule["supplies"],
                            counter.get("after_turn", "-")))
        self._objects()
        self._draw(bp)
