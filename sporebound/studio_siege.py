"""Tk Campaign & Siege Studio 2.5.4.1 — map fronts and supply routes.

Project settings are validated transactionally. The strategic forecast consumes
only immutable copies of FrontDirector and never starts a live tactical battle.
"""
from copy import deepcopy
import json

from .game_project import GameProject
from .model import RuleError
from .siege_authoring import (
    delete_front, delete_route, new_plan, put_front, put_route,
    set_focus, set_logistics, strategy_preview)


class SiegeStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self._stamp = None
        self._loading = False
        self._front_ids = []
        self._route_keys = []
        self.undo_stack = []
        self.redo_stack = []
        self._build(notebook)

    def _button(self, parent, text, action):
        control = self.ttk.Button(parent, text=text,
                                  command=lambda: self.owner._run(action))
        control.pack(side="left", padx=3, pady=3)
        return control

    def _field(self, frame, row, caption, value="", choices=None):
        variable = self.tk.StringVar(value=value)
        self.ttk.Label(frame, text=caption).grid(
            row=row, column=0, padx=5, pady=3, sticky="w")
        if choices is None:
            widget = self.ttk.Entry(frame, textvariable=variable, width=23)
        else:
            widget = self.ttk.Combobox(frame, textvariable=variable,
                                       values=choices, state="readonly", width=21)
        widget.grid(row=row, column=1, padx=5, pady=3, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)
        return variable, widget

    def _build(self, notebook):
        ttk = self.ttk
        page = ttk.Frame(notebook)
        notebook.add(page, text="Campagne & sièges")
        self.page = page
        top = ttk.Frame(page)
        top.pack(fill="x", padx=8, pady=6)
        self.title = ttk.Label(top, text="Plan de siège", font=("TkDefaultFont", 11, "bold"))
        self.title.pack(side="left")
        self._button(top, "Créer siège", self.create)
        self._button(top, "Supprimer siège", self.remove)
        self._button(top, "Annuler siège", self.undo)
        self._button(top, "Rétablir siège", self.redo)

        main = ttk.Panedwindow(page, orient="horizontal")
        main.pack(fill="both", expand=True, padx=9)
        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=2)
        main.add(right, weight=3)

        ttk.Label(left, text="Fronts tactiques (mission unique par front)").pack(anchor="w")
        self.front_list = self.tk.Listbox(left, exportselection=False, height=7)
        self.front_list.pack(fill="x", pady=(2, 5))
        self.front_list.bind("<<ListboxSelect>>", self._select_front)
        form = ttk.LabelFrame(left, text="Édition d'un front")
        form.pack(fill="x")
        self.front, _ = self._field(form, 0, "ID du front", "")
        self.mission, self.mission_box = self._field(form, 1, "Mission", choices=[])
        self.strength, _ = self._field(form, 2, "Force", "10")
        self.opposition, _ = self._field(form, 3, "Opposition", "10")
        self.doctrine, _ = self._field(
            form, 4, "Doctrine", "hold",
            choices=["hold", "assault", "delay", "retreat"])
        commands = ttk.Frame(left)
        commands.pack(fill="x")
        self._button(commands, "Créer / modifier front", self.save_front)
        self._button(commands, "Supprimer front", self.remove_front)
        self._button(commands, "Définir focus", self.focus_front)
        self.focus_info = ttk.Label(left, text="")
        self.focus_info.pack(anchor="w", pady=4)

        route_section = ttk.LabelFrame(right, text="Routes et ravitaillement")
        route_section.pack(fill="x")
        self.route_list = ttk.Treeview(
            route_section, columns=("origin", "target", "turns"),
            show="headings", height=5, selectmode="browse")
        for col, title in (("origin", "Depuis"), ("target", "Vers"),
                           ("turns", "Tours")):
            self.route_list.heading(col, text=title)
            self.route_list.column(col, width=100, stretch=True)
        self.route_list.pack(fill="x", padx=5, pady=4)
        self.route_list.bind("<<TreeviewSelect>>", self._select_route)
        route_fields = ttk.Frame(route_section)
        route_fields.pack(fill="x")
        self.origin, self.origin_box = self._field(
            route_fields, 0, "Origine", "reserve", choices=[])
        self.destination, self.destination_box = self._field(
            route_fields, 1, "Destination", choices=[])
        self.travel, _ = self._field(route_fields, 2, "Temps (1..100)", "2")
        route_commands = ttk.Frame(route_fields)
        route_commands.grid(row=3, column=0, columnspan=2, sticky="w")
        self._button(route_commands, "Ajouter / modifier route", self.save_route)
        self._button(route_commands, "Supprimer route", self.remove_route)

        reserves = ttk.LabelFrame(right, text="Logistique")
        reserves.pack(fill="x", pady=5)
        self.player_reserves, _ = self._field(reserves, 0, "Réserves alliées", "3")
        self.enemy_reserves, _ = self._field(reserves, 1, "Réserves adverses", "0")
        self.capacity, _ = self._field(reserves, 2, "Capacité du convoi", "4")
        ttk.Button(reserves, text="Appliquer logistique",
                   command=lambda: self.owner._run(self.save_logistics)).grid(
                       row=3, column=0, columnspan=2, pady=4)

        preview = ttk.LabelFrame(page, text="Chronologie stratégique hors combat")
        preview.pack(fill="both", expand=True, padx=9, pady=5)
        buttons = ttk.Frame(preview)
        buttons.pack(fill="x", padx=5)
        self._button(buttons, "Simuler 5 tours", self.simulate)
        ttk.Label(buttons, text="Projection indicative, aucune sauvegarde modifiée").pack(
            side="left", padx=10)
        self.forecast = self.tk.Text(preview, height=8, wrap="none",
                                    state="disabled")
        self.forecast.pack(fill="both", expand=True, padx=5, pady=4)
        self.status = ttk.Label(page, text="Choisir une campagne et créer un siège.")
        self.status.pack(fill="x", padx=10, pady=5)

    def _cid(self):
        return self.owner.campaign_id.get()

    def _plan(self):
        return self.owner.project.sieges.get(self._cid())

    def _required_plan(self):
        plan = self._plan()
        if plan is None:
            raise RuleError("Créer un siège pour cette campagne avant de l'éditer")
        return plan

    def _commit(self, plan):
        data = self.owner.project.to_dict()
        data.setdefault("sieges", {})
        if plan is None:
            data["sieges"].pop(self._cid(), None)
        else:
            data["sieges"][self._cid()] = plan
        project = GameProject.from_dict(data, self.owner._content())
        self.undo_stack.append(deepcopy(self.owner.project.to_dict()))
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        self.owner.project = project
        self.owner.project_status.config(
            text="Siège modifié — enregistrer le projet de jeu.")
        self._stamp = None
        self.refresh()

    def undo(self):
        if not self.undo_stack:
            raise RuleError("Aucune modification de siège à annuler")
        before = self.undo_stack[-1]
        project = GameProject.from_dict(before, self.owner._content())
        self.undo_stack.pop()
        self.redo_stack.append(self.owner.project.to_dict())
        self.owner.project = project
        self._stamp = None
        self.refresh()

    def redo(self):
        if not self.redo_stack:
            raise RuleError("Aucune modification de siège à rétablir")
        future = self.redo_stack[-1]
        project = GameProject.from_dict(future, self.owner._content())
        self.redo_stack.pop()
        self.undo_stack.append(self.owner.project.to_dict())
        self.owner.project = project
        self._stamp = None
        self.refresh()

    def create(self):
        if self._plan() is not None:
            raise RuleError("Un siège existe déjà pour cette campagne")
        missions = list(self.owner._content().missions)
        if len(missions) < 2:
            raise RuleError("Créer au moins deux missions pour ce siège")
        campaign = self.owner.project.campaign(self._cid())
        first = campaign["start_mission"]
        second = next(mid for mid in missions if mid != first)
        self._commit(new_plan(self.owner._content(), first, second))

    def remove(self):
        self._required_plan()
        self._commit(None)

    def save_front(self):
        self._commit(put_front(
            self._required_plan(), self.owner._content(),
            self.front.get().strip(), self.mission.get(),
            int(self.strength.get()), int(self.opposition.get()),
            self.doctrine.get()))

    def remove_front(self):
        self._commit(delete_front(
            self._required_plan(), self.owner._content(),
            self.front.get().strip()))

    def focus_front(self):
        self._commit(set_focus(self._required_plan(), self.owner._content(),
                               self.front.get().strip()))

    def save_route(self):
        self._commit(put_route(
            self._required_plan(), self.owner._content(),
            self.origin.get(), self.destination.get(), int(self.travel.get())))

    def remove_route(self):
        self._commit(delete_route(
            self._required_plan(), self.owner._content(),
            self.origin.get(), self.destination.get()))

    def save_logistics(self):
        self._commit(set_logistics(
            self._required_plan(), self.owner._content(),
            int(self.player_reserves.get()), int(self.enemy_reserves.get()),
            int(self.capacity.get())))

    def _select_front(self, _event=None):
        if self._loading:
            return
        indices = self.front_list.curselection()
        plan = self._plan()
        if not indices or plan is None:
            return
        fid = self._front_ids[indices[0]]
        self.front.set(fid)
        self.mission.set(plan["missions"][fid])
        spec = plan["specs"][fid]
        self.strength.set(str(spec["strength"]))
        self.opposition.set(str(spec["opposition"]))
        self.doctrine.set(spec["doctrine"])

    def _select_route(self, _event=None):
        if self._loading or not self.route_list.selection():
            return
        index = int(self.route_list.selection()[0][1:])
        origin, destination = self._route_keys[index]
        route = next(x for x in self._required_plan()["logistics"]["routes"]
                     if x["from"] == origin and x["to"] == destination)
        self.origin.set(origin)
        self.destination.set(destination)
        self.travel.set(str(route["turns"]))

    def simulate(self):
        plan = self._required_plan()
        timeline = strategy_preview(plan, self.owner._content(), 5)
        lines = []
        for frame in timeline:
            states = " | ".join(
                "{}: {} F{} E{}".format(front, row["status"], row["strength"],
                                       row["opposition"])
                for front, row in sorted(frame["fronts"].items()))
            lines.append("Tour {} (focus {}) — {}".format(
                frame["turn"], frame["focused"], states))
        self.forecast.configure(state="normal")
        self.forecast.delete("1.0", "end")
        self.forecast.insert("1.0", "\n".join(lines))
        self.forecast.configure(state="disabled")

    def refresh(self):
        if self.owner.project is None:
            return
        plan = self._plan()
        cid = self._cid()
        signature = cid, json.dumps(plan, sort_keys=True)
        if signature == self._stamp:
            return
        self._stamp = signature
        self._loading = True
        self.title.config(text="Campagne {} — plan de siège".format(cid))
        missions = list(self.owner._content().missions)
        self.mission_box["values"] = missions
        self.front_list.delete(0, "end")
        if self.route_list.get_children():
            self.route_list.delete(*self.route_list.get_children())
        self._front_ids = []
        self._route_keys = []
        if plan is None:
            self.focus_info.config(text="Aucun siège configuré.")
            self.status.config(text="Créer un siège (minimum deux missions).")
        else:
            self._front_ids = sorted(plan["missions"])
            for fid in self._front_ids:
                spec = plan["specs"][fid]
                self.front_list.insert(
                    "end", "{} → {} [{}]".format(
                        fid, plan["missions"][fid], spec["doctrine"]))
            for i, row in enumerate(plan["logistics"]["routes"]):
                self._route_keys.append((row["from"], row["to"]))
                self.route_list.insert("", "end", iid="r" + str(i),
                                       values=(row["from"], row["to"], row["turns"]))
            self.origin_box["values"] = ["reserve", *self._front_ids]
            self.destination_box["values"] = self._front_ids
            self.focus_info.config(text="Focus initial : " + plan["focused"])
            logistics = plan["logistics"]
            self.player_reserves.set(str(logistics["reserves"].get("player", 0)))
            self.enemy_reserves.set(str(logistics["reserves"].get("enemy", 0)))
            self.capacity.set(str(logistics["capacity"]))
            self.status.config(text="Édition transactionnelle — enregistrer le projet .game.json.")
            index = self._front_ids.index(plan["focused"])
            self.front_list.selection_set(index)
        self._loading = False
        if plan is not None:
            self._select_front()
