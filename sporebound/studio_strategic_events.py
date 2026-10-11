"""2.5.4.5 visual strategic event DAG editor (no JSON hand editing)."""
from copy import deepcopy
from . import strategic_events as events
from . import story_conditions as conditions
from .model import require


def label(expr):
    kind, data = next(iter(expr.items()))
    if kind in ("all", "any"):
        return ("ET" if kind == "all" else "OU") + " (" + str(len(data)) + ")"
    if kind == "not":
        return "NON"
    if kind == "turn_at_least":
        return "Tour global ≥ " + str(data)
    if kind == "front_status":
        return data["front"] + " est " + data["status"]
    if kind == "battle_event":
        return data["front"] + " : " + data["kind"] + " = " + data["value"]
    if kind == "timeline_event":
        return data["front"] + " : " + data["kind"]
    return "Après " + str(data)


class StrategicEventsStudio:
    def __init__(self, parent, root):
        self.parent, self.tk, self.ttk = parent, parent.tk, parent.ttk
        self.id = self.tk.StringVar(value="reinforcements_delayed")
        self.leaf_kind = self.tk.StringVar(value="turn_at_least")
        self.leaf_front = self.tk.StringVar()
        self.leaf_value = self.tk.StringVar(value="3")
        self.leaf_event = self.tk.StringVar(value="interact")
        self.operator = self.tk.StringVar(value="all")
        self.effect_kind = self.tk.StringVar(value="reduce_opposition")
        self.effect_front = self.tk.StringVar()
        self.effect_value = self.tk.StringVar(value="2")
        self.note = self.tk.StringVar(value="Sélectionner un nœud pour éditer ses conditions.")
        self.condition_paths = {}
        self._build(root)

    def _button(self, root, label, callback):
        self.ttk.Button(root, text=label,
                        command=lambda: self.parent.owner._run(callback)).pack(
                            side="left", padx=3, pady=3)

    def _field(self, root, row, label, value, values=None):
        self.ttk.Label(root, text=label).grid(
            row=row, column=0, padx=4, pady=3, sticky="w")
        control = (self.ttk.Entry(root, textvariable=value, width=22)
                   if values is None else self.ttk.Combobox(
                       root, textvariable=value, values=values, width=22,
                       state="readonly"))
        control.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
        root.columnconfigure(1, weight=1)
        return control

    def _build(self, root):
        ttk = self.ttk
        columns = ttk.Panedwindow(root, orient="horizontal")
        columns.pack(fill="both", expand=True, padx=5, pady=5)
        left, right = ttk.Frame(columns), ttk.Frame(columns)
        columns.add(left, weight=2)
        columns.add(right, weight=4)
        ttk.Label(left, text="Événements stratégiques — exécution unique").pack(
            anchor="w", padx=5)
        self.nodes = ttk.Treeview(
            left, columns=("condition", "effects"), show="tree headings",
            selectmode="browse", height=7)
        for column, caption, width in (
                ("#0", "ID", 135), ("condition", "Déclencheur", 150),
                ("effects", "Effets", 65)):
            self.nodes.heading(column, text=caption)
            self.nodes.column(column, width=width)
        self.nodes.pack(fill="x", expand=True, padx=5, pady=5)
        self.nodes.bind("<<TreeviewSelect>>", self._select_node)
        row = ttk.Frame(left)
        row.pack(fill="x")
        self._button(row, "Nouveau", self.new_node)
        self._button(row, "Supprimer", self.delete_node)
        self.graph = self.tk.Canvas(left, height=200, background="#f8fafc")
        self.graph.pack(fill="both", expand=True, pady=8)
        self.preview_text = self.tk.Text(left, height=9, wrap="word")
        self.preview_text.pack(fill="x", padx=5)
        self._button(left, "Simuler 8 tours", self.preview)
        self._button(left, "Scène associée…", self.open_story)

        tabs = ttk.Notebook(right)
        tabs.pack(fill="both", expand=True)
        conditions_page, effects_page = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(conditions_page, text="Conditions ET / OU / NON")
        tabs.add(effects_page, text="Conséquences")

        self.condition_tree = ttk.Treeview(
            conditions_page, columns=("details",), show="tree headings", height=8)
        self.condition_tree.heading("#0", text="Expression")
        self.condition_tree.heading("details", text="Valeur")
        self.condition_tree.column("#0", width=260)
        self.condition_tree.column("details", width=185)
        self.condition_tree.pack(fill="both", expand=True, padx=5, pady=5)
        editor = ttk.Frame(conditions_page)
        editor.pack(fill="x", padx=4)
        self._field(editor, 0, "Nœud", self.id)
        self.leaf_type_box = self._field(
            editor, 1, "Prédicat", self.leaf_kind,
            ["turn_at_least", "front_status", "battle_event",
             "timeline_event", "fired"])
        self.front_box = self._field(editor, 2, "Front", self.leaf_front, [])
        self._field(editor, 3, "Valeur / objet / ID", self.leaf_value)
        self.kind_box = self._field(editor, 4, "Événement / état", self.leaf_event, [])
        self.leaf_type_box.bind("<<ComboboxSelected>>", lambda _e: self._choices())
        self._field(editor, 5, "Opérateur", self.operator, ["all", "any", "not"])
        actions = ttk.Frame(conditions_page)
        actions.pack(fill="x", pady=5)
        self._button(actions, "Remplacer", self.replace_condition)
        self._button(actions, "+ Dans ET/OU", self.append_condition)
        self._button(actions, "Envelopper", self.wrap_condition)
        self._button(actions, "Retirer", self.delete_condition)

        self.effect_tree = ttk.Treeview(
            effects_page, columns=("front", "param"), show="tree headings", height=8)
        for column, caption, width in (("#0", "Effet", 185),
                                       ("front", "Cible", 110),
                                       ("param", "Argument", 210)):
            self.effect_tree.heading(column, text=caption)
            self.effect_tree.column(column, width=width)
        self.effect_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.effect_tree.bind("<<TreeviewSelect>>", self._select_effect)
        ef = ttk.Frame(effects_page)
        ef.pack(fill="x", padx=4)
        self.effect_kind_box = self._field(
            ef, 0, "Effet", self.effect_kind, sorted(events.EFFECTS))
        self.effect_front_box = self._field(ef, 1, "Cible", self.effect_front, [])
        self._field(ef, 2, "Intensité / doctrine / objet / texte", self.effect_value)
        self.effect_kind_box.bind("<<ComboboxSelected>>", lambda _e: self._choices())
        buttons = ttk.Frame(effects_page)
        buttons.pack(fill="x")
        self._button(buttons, "Ajouter effet", self.add_effect)
        self._button(buttons, "Modifier effet", self.replace_effect)
        self._button(buttons, "Supprimer effet", self.remove_effect)
        ttk.Label(root, textvariable=self.note, wraplength=990).pack(
            fill="x", padx=6, pady=3)

    def _bp(self):
        return self.parent._require()

    def _active(self):
        bp = self._bp()
        chosen = self.nodes.selection()
        require(bool(chosen), "Sélectionner d'abord un événement")
        return next(node for node in bp.get("event_graph", [])
                    if node["id"] == chosen[0])

    def open_story(self):
        node = self._active()
        reference = self._bp()['id'] + '/' + node['id']
        editor = self.parent.owner.story_editor
        editor.strategic_key.set(reference)
        editor.strategic_scene.set(
            self.parent.owner.project.story.get(
                'after_strategic_event', {}).get(reference, ''))
        editor.notebook.select(editor.tab)

    def _save(self, node):
        bp = events.upsert(self._bp(), self.parent.owner._content(), node)
        self.parent._apply(bp)
        self.nodes.selection_set(node["id"])
        self._select_node()
        self.note.set("Graphe vérifié. Sauvegarder le projet .game.json.")

    def new_node(self):
        nid = self.id.get()
        require(not any(row["id"] == nid for row in
                        self._bp().get("event_graph", [])), "Identifiant déjà utilisé")
        self._save({"id": nid, "when": self._leaf(),
                    "effects": [{"kind": "signal",
                                 "text": "Strategic milestone: " + nid[:60]}]})

    def delete_node(self):
        bp = self._bp()
        node = self._active()
        self.parent._apply(events.remove(
            bp, self.parent.owner._content(), node["id"]))

    def _leaf(self):
        kind = self.leaf_kind.get()
        front = self.leaf_front.get()
        val = self.leaf_value.get()
        event = self.leaf_event.get()
        if kind == "turn_at_least":
            return {kind: int(val)}
        if kind == "front_status":
            return {kind: {"front": front, "status": event}}
        if kind == "battle_event":
            return {kind: {"front": front, "kind": event, "value": val}}
        if kind == "timeline_event":
            return {kind: {"front": front, "kind": event}}
        return {"fired": val}

    def _path(self):
        chosen = self.condition_tree.selection()
        return self.condition_paths[chosen[0]] if chosen else ()

    def _update_condition(self, action):
        node = deepcopy(self._active())
        root = conditions.update_expression(
            node["when"], action, path=self._path(),
            leaf=self._leaf() if action in {"replace", "append"} else None,
            operator=self.operator.get())
        require(root is not None, "A strategic event must keep a condition")
        node["when"] = root
        self._save(node)

    def replace_condition(self):
        self._update_condition("replace")

    def append_condition(self):
        self._update_condition("append")

    def wrap_condition(self):
        self._update_condition("wrap")

    def delete_condition(self):
        self._update_condition("delete")

    def _effect(self):
        kind, front, value = (self.effect_kind.get(),
                              self.effect_front.get(),
                              self.effect_value.get())
        if kind == "signal":
            return {"kind": kind, "text": value}
        result = {"kind": kind, "front": front}
        if kind in {"reduce_opposition", "reduce_strength"}:
            result["amount"] = int(value)
        elif kind in {"open_door", "disable_defense"}:
            result["object"] = value
        elif kind == "set_doctrine":
            result["doctrine"] = value
        return result

    def add_effect(self):
        node = deepcopy(self._active())
        node["effects"].append(self._effect())
        self._save(node)

    def replace_effect(self):
        node = deepcopy(self._active())
        selected = self.effect_tree.selection()
        require(selected, "Sélectionner un effet")
        node["effects"][int(selected[0])] = self._effect()
        self._save(node)

    def remove_effect(self):
        node = deepcopy(self._active())
        selected = self.effect_tree.selection()
        require(selected, "Sélectionner un effet")
        node["effects"].pop(int(selected[0]))
        self._save(node)

    def _choices(self):
        bp = self.parent.blueprint()
        if bp is None:
            return
        self.front_box["values"] = sorted(bp["fronts"])
        self.effect_front_box["values"] = sorted(bp["fronts"])
        kind = self.leaf_kind.get()
        self.kind_box["values"] = (
            sorted(events.FRONT_STATES) if kind == "front_status"
            else sorted(events.TIMELINE_EVENTS) if kind == "timeline_event"
            else sorted(events.front_links.EVENTS) if kind == "battle_event"
            else [])
        if self.leaf_front.get() not in bp["fronts"]:
            self.leaf_front.set(next(iter(bp["fronts"])))
        if self.effect_front.get() not in bp["fronts"]:
            self.effect_front.set(next(iter(bp["fronts"])))

    def _select_node(self, _event=None):
        selected = self.nodes.selection()
        if not selected:
            return
        node = self._active()
        self.id.set(node["id"])
        self.condition_paths = {}
        for row in self.condition_tree.get_children():
            self.condition_tree.delete(row)
        def visit(cond, parent="", path=()):
            key = str(len(self.condition_paths))
            kind, value = next(iter(cond.items()))
            self.condition_paths[key] = path
            self.condition_tree.insert(
                parent, "end", iid=key, text=label(cond),
                values=(str(value)[:85],), open=True)
            if kind in {"all", "any"}:
                for i, child in enumerate(value):
                    visit(child, key, path+((kind, i),))
            elif kind == "not":
                visit(value, key, path+("not",))
        visit(node["when"])
        for row in self.effect_tree.get_children():
            self.effect_tree.delete(row)
        for i, effect in enumerate(node["effects"]):
            self.effect_tree.insert(
                "", "end", iid=str(i), text=effect["kind"],
                values=(effect.get("front", "—"),
                        str(effect.get("amount", effect.get(
                            "text", effect.get("object", effect.get("doctrine", "")))))))
        self._choices()

    def _select_effect(self, _event=None):
        selected = self.effect_tree.selection()
        if not selected:
            return
        effect = self._active()["effects"][int(selected[0])]
        self.effect_kind.set(effect["kind"])
        self.effect_front.set(effect.get("front", ""))
        self.effect_value.set(str(effect.get(
            "amount", effect.get("text", effect.get(
                "object", effect.get("doctrine", ""))))))

    def _draw(self, graph):
        self.graph.delete("all")
        if not graph:
            self.graph.create_text(200, 80, text="Créer des événements puis les relier avec « Après »",
                                   fill="#334155")
            return
        names = [row["id"] for row in graph]
        positions = {name: (95+220*(i%2), 37+62*(i//2))
                     for i, name in enumerate(names)}
        for node in graph:
            target = positions[node["id"]]
            def walk(cond):
                key, value = next(iter(cond.items()))
                if key == "fired":
                    if value in positions:
                        x, y = positions[value]
                        self.graph.create_line(x+52, y, target[0]-52, target[1],
                                               arrow="last", fill="#64748b")
                elif key in {"all", "any"}:
                    for child in value:
                        walk(child)
                elif key == "not":
                    walk(value)
            walk(node["when"])
        for name, (x, y) in positions.items():
            self.graph.create_rectangle(x-60, y-16, x+60, y+16,
                                        fill="#dbeafe", outline="#64748b")
            self.graph.create_text(x, y, text=name[:17])
        self.graph.configure(scrollregion=(0, 0, 460, max(200, 85+62*(len(names)//2))))

    def refresh(self, bp):
        chosen = self.nodes.selection()
        old = chosen[0] if chosen else ""
        for row in self.nodes.get_children():
            self.nodes.delete(row)
        graph = bp.get("event_graph", []) if bp is not None else []
        for node in graph:
            self.nodes.insert("", "end", iid=node["id"], text=node["id"],
                              values=(label(node["when"]), len(node["effects"])))
        self._draw(graph)
        self._choices()
        if graph:
            self.nodes.selection_set(
                old if old in {n["id"] for n in graph} else graph[0]["id"])
            self._select_node()
        else:
            self.condition_paths.clear()
            for tree in (self.condition_tree, self.effect_tree):
                for row in tree.get_children():
                    tree.delete(row)

    def preview(self):
        projection = events.preview(self._bp(), self.parent.owner._content())
        lines = ["Aperçu (sans résolutions tactiques simulées)"]
        for row in projection:
            lines.append("Tour " + str(row["turn"]) + ": " +
                         (", ".join(row["fired"]) if row["fired"] else "aucun nœud activé"))
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", "\n".join(lines))
