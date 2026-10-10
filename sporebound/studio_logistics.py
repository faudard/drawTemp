"""Tk Logistics Studio embedded in Campaign & Siege Studio.

This panel edits only GameProject.sieges[*].logistics.  Tactical rescue maps,
actors and campaign story live in the existing editors.
"""
from math import cos, pi, sin

from . import logistics_authoring as edit
from .model import require


class LogisticsStudio:
    def __init__(self, siege_studio, frame):
        self.parent = siege_studio
        self.tk, self.ttk = siege_studio.tk, siege_studio.ttk
        self.from_front = self.tk.StringVar(value="reserve")
        self.to_front = self.tk.StringVar()
        self.route_turns = self.tk.StringVar(value="2")
        self.player_reserves = self.tk.StringVar(value="3")
        self.enemy_reserves = self.tk.StringVar(value="0")
        self.capacity = self.tk.StringVar(value="6")
        self.player_supplies = self.tk.StringVar(value="5")
        self.enemy_supplies = self.tk.StringVar(value="0")
        self.escorts = self.tk.StringVar(value="1")
        self.casualties = self.tk.StringVar(value="0")
        self.delay = self.tk.StringVar(value="2")
        self.charges = self.tk.StringVar(value="1")
        self.rescue = self.tk.StringVar()
        self.status = self.tk.StringVar(value="Aucune logistique définie.")
        self._build(frame)

    def _field(self, parent, row, caption, var, choices=None):
        ttk = self.ttk
        ttk.Label(parent, text=caption).grid(
            row=row, column=0, sticky="w", padx=5, pady=3)
        widget = (ttk.Entry(parent, textvariable=var, width=17)
                  if choices is None else ttk.Combobox(
                      parent, textvariable=var, values=choices,
                      state="readonly", width=17))
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        parent.columnconfigure(1, weight=1)
        return widget

    def _button(self, parent, label, action):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.parent.owner._run(action)).pack(
                            side="left", padx=3, pady=3)

    def _build(self, root):
        ttk = self.ttk
        header = ttk.Frame(root)
        header.pack(fill="x", padx=7, pady=3)
        self._button(header, "Activer / enregistrer ressources", self.save_resources)
        self._button(header, "Désactiver logistique", self.disable)
        self._button(header, "Aperçu moteur", self.preview)
        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=7)
        visual = ttk.Frame(body)
        form = ttk.Frame(body)
        body.add(visual, weight=3)
        body.add(form, weight=2)
        self.graph = self.tk.Canvas(visual, background="#f8fafc", height=255)
        self.graph.pack(fill="both", expand=True, pady=4)
        self.graph.bind("<Button-1>", self._graph_click)
        self.routes = ttk.Treeview(
            visual, show="headings", columns=("origin", "target", "turns", "risk"),
            height=6, selectmode="browse")
        for col, title, width in (("origin", "Origine", 125),
                                  ("target", "Destination", 140),
                                  ("turns", "Tours", 65),
                                  ("risk", "Embuscade", 110)):
            self.routes.heading(col, text=title)
            self.routes.column(col, width=width)
        self.routes.pack(fill="both", expand=True, pady=4)
        self.routes.bind("<<TreeviewSelect>>", self._selected_route)
        pages = ttk.Notebook(form)
        pages.pack(fill="both", expand=True)
        roads = ttk.Frame(pages)
        economy = ttk.Frame(pages)
        hazards = ttk.Frame(pages)
        pages.add(roads, text="Routes")
        pages.add(economy, text="Ressources")
        pages.add(hazards, text="Embuscades")
        self.origins = self._field(roads, 0, "Depuis", self.from_front, [])
        self.destinations = self._field(roads, 1, "Vers", self.to_front, [])
        self._field(roads, 2, "Durée (tours)", self.route_turns)
        buttons = ttk.Frame(roads)
        buttons.grid(row=3, columnspan=2)
        self._button(buttons, "Créer / modifier route", self.save_route)
        self._button(buttons, "Supprimer route", self.delete_route)
        ttk.Label(roads, text="Route orientée, 1 à 100 tours.\n"
                  "« reserve » est une origine stratégique, pas un front.",
                  wraplength=290, justify="left").grid(
                      row=4, columnspan=2, sticky="w", padx=5, pady=6)

        for row, label, variable in (
                (0, "Réserves alliées", self.player_reserves),
                (1, "Réserves ennemies", self.enemy_reserves),
                (2, "Capacité totale", self.capacity),
                (3, "Vivres alliés", self.player_supplies),
                (4, "Vivres ennemis", self.enemy_supplies),
                (5, "Escortes", self.escorts)):
            self._field(economy, row, label, variable)
        self.rescue_box = self._field(
            economy, 6, "Mission de secours", self.rescue, [])
        resources_buttons = ttk.Frame(economy)
        resources_buttons.grid(row=7, columnspan=2)
        self._button(resources_buttons, "Enregistrer ressources", self.save_resources)
        self._button(resources_buttons, "Mission de secours", self.save_rescue)
        ttk.Label(economy, text="La mission de secours doit être un vrai combat "
                  "validé par le moteur.", wraplength=290).grid(
                      row=8, columnspan=2, sticky="w", padx=5, pady=6)

        self._field(hazards, 0, "Victimes (0–14)", self.casualties)
        self._field(hazards, 1, "Retard (1–100)", self.delay)
        self._field(hazards, 2, "Charges (1–100)", self.charges)
        ab = ttk.Frame(hazards)
        ab.grid(row=3, columnspan=2)
        self._button(ab, "Créer / modifier", self.save_ambush)
        self._button(ab, "Supprimer", self.delete_ambush)
        ttk.Label(hazards, text="Sélectionner d'abord une route à gauche.\n"
                  "Une embuscade peut bloquer le convoi ; le jeu applique les "
                  "pertes réelles et la mission de secours optionnelle.",
                  wraplength=290, justify="left").grid(
                      row=4, columnspan=2, sticky="w", padx=5, pady=6)
        ttk.Label(root, textvariable=self.status, wraplength=1050).pack(
            fill="x", padx=9, pady=4)

    def _blueprint(self):
        return self.parent._require()

    def _content(self):
        return self.parent.owner._content()

    def _apply(self, updated):
        self.parent._apply(updated)
        self.status.set("Logistique validée. Sauvegarder le projet .game.json.")

    def save_resources(self):
        bp = self._blueprint()
        return self._apply(edit.resources(
            bp, self._content(),
            player_reserves=int(self.player_reserves.get()),
            enemy_reserves=int(self.enemy_reserves.get()),
            capacity=int(self.capacity.get()),
            player_supplies=int(self.player_supplies.get()),
            enemy_supplies=int(self.enemy_supplies.get()),
            escorts=int(self.escorts.get())))

    def disable(self):
        self._apply(edit.disable(self._blueprint(), self._content()))

    def save_route(self):
        self._apply(edit.upsert_route(
            self._blueprint(), self._content(), self.from_front.get(),
            self.to_front.get(), int(self.route_turns.get())))

    def delete_route(self):
        self._apply(edit.delete_route(
            self._blueprint(), self._content(), self.from_front.get(),
            self.to_front.get()))

    def save_ambush(self):
        self._apply(edit.upsert_ambush(
            self._blueprint(), self._content(), self.from_front.get(),
            self.to_front.get(), casualties=int(self.casualties.get()),
            delay=int(self.delay.get()), charges=int(self.charges.get())))

    def delete_ambush(self):
        self._apply(edit.delete_ambush(
            self._blueprint(), self._content(),
            self.from_front.get(), self.to_front.get()))

    def save_rescue(self):
        self._apply(edit.rescue_mission(
            self._blueprint(), self._content(), self.rescue.get()))

    def preview(self):
        result = edit.preview(self._blueprint(), self._content())
        self.status.set(
            "Moteur : " + str(len(result["routes"])) + " routes ; "
            "réserves " + str(result["reserves"]) + " ; capacité " +
            str(result["capacity"]) + " ; convois initiaux : " +
            str(len(result["in_transit"])) + " ; tours passés : 0")

    def _selected_route(self, _event=None):
        chosen = self.routes.selection()
        if not chosen:
            return
        origin, target = chosen[0].split("→", 1)
        self.from_front.set(origin)
        self.to_front.set(target)
        config = edit.configuration(self._blueprint())
        route = next((r for r in config["routes"]
                      if r["from"] == origin and r["to"] == target), None)
        if route:
            self.route_turns.set(str(route["turns"]))
        ambush = next((r for r in config.get("ambushes", [])
                       if r["from"] == origin and r["to"] == target), None)
        if ambush:
            self.casualties.set(str(ambush["casualties"]))
            self.delay.set(str(ambush["delay"]))
            self.charges.set(str(ambush["charges"]))

    def _graph_click(self, _event=None):
        tags = self.graph.gettags("current")
        name = next((tag[5:] for tag in tags if tag.startswith("road_")), "")
        if name and self.routes.exists(name):
            self.routes.selection_set(name)
            self._selected_route()

    def _draw(self, bp):
        self.graph.delete("all")
        if bp is None or "logistics" not in bp:
            self.graph.create_text(210, 100, text="Activer la logistique pour tracer des routes",
                                   fill="#334155")
            return
        routes = bp["logistics"].get("routes", [])
        nodes = sorted(set(bp["fronts"]) | {"reserve"})
        center_x, center_y = 230, 132
        count = max(1, len(nodes))
        positions = {name: (center_x + 155 * cos(2 * pi * index / count),
                            center_y + 95 * sin(2 * pi * index / count))
                     for index, name in enumerate(nodes)}
        hazards = {(a["from"], a["to"])
                   for a in bp["logistics"].get("ambushes", [])}
        for route in routes:
            src, dst = route["from"], route["to"]
            a, b = positions[src], positions[dst]
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = max(1.0, (dx * dx + dy * dy) ** .5)
            unit_x, unit_y = dx / length, dy / length
            key = src + "→" + dst
            self.graph.create_line(
                a[0] + 34 * unit_x, a[1] + 19 * unit_y,
                b[0] - 39 * unit_x, b[1] - 22 * unit_y,
                arrow="last", width=2,
                fill="#dc2626" if (src, dst) in hazards else "#475569",
                tags=("road_" + key,))
            self.graph.create_text(
                (a[0] + b[0]) / 2 + 8, (a[1] + b[1]) / 2 - 8,
                text=str(route["turns"]) + "t",
                fill="#b45309" if (src, dst) in hazards else "#334155",
                tags=("road_" + key,))
        for name, (x, y) in positions.items():
            fill = "#bbf7d0" if name == "reserve" else "#dbeafe"
            self.graph.create_rectangle(
                x - 43, y - 17, x + 43, y + 17,
                fill=fill, outline="#64748b")
            self.graph.create_text(x, y, text=name[:14], fill="#1e293b",
                                   font=("TkDefaultFont", 9, "bold"))

    def refresh(self, bp):
        fronts = sorted(bp["fronts"]) if bp else []
        self.origins["values"] = ["reserve", *fronts]
        self.destinations["values"] = fronts
        self.rescue_box["values"] = ["", *sorted(self._content().missions)]
        if self.from_front.get() not in ["reserve", *fronts]:
            self.from_front.set("reserve")
        if self.to_front.get() not in fronts:
            self.to_front.set(fronts[0] if fronts else "")
        for row in self.routes.get_children():
            self.routes.delete(row)
        if bp is not None and "logistics" in bp:
            config = edit.configuration(bp)
            hazards = {(a["from"], a["to"])
                       for a in config.get("ambushes", [])}
            for route in config["routes"]:
                src, dst = route["from"], route["to"]
                self.routes.insert("", "end", iid=src + "→" + dst,
                                  values=(src, dst, route["turns"],
                                          "Oui" if (src, dst) in hazards else "Non"))
            self.player_reserves.set(str(config.get("reserves", {}).get("player", 0)))
            self.enemy_reserves.set(str(config.get("reserves", {}).get("enemy", 0)))
            self.capacity.set(str(config.get("capacity", 6)))
            self.player_supplies.set(str(config.get("supplies", {}).get("player", 0)))
            self.enemy_supplies.set(str(config.get("supplies", {}).get("enemy", 0)))
            self.escorts.set(str(config.get("escorts", 0)))
            self.rescue.set(config.get("rescue_mission") or "")
        self._draw(bp)
