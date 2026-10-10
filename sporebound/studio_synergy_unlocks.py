"""Visual Synergy & Unlock Studio for tactical bonds, no JSON editing.

The tree edits only Content.tactic_unlocks through fully validated Content
transactions. Preview reuses bonds.unlock_rule_met/unlock_progress unchanged.
"""
from . import synergy_authoring as edit
from .model import RuleError, require


class SynergyUnlockStudio:
    def __init__(self, character_studio, notebook):
        self.parent = character_studio
        self.owner = character_studio.owner
        self.tk, self.ttk = self.owner.tk, self.owner.ttk
        self.index = None
        self.path_map = {}
        self.condition = edit.leaf("stat", stat="missions_together", threshold=1)
        self.sequence = []
        self._loading = False
        self._build(notebook)

    def _button(self, frame, label, callback):
        self.ttk.Button(frame, text=label,
                        command=lambda: self.owner._run(callback)).pack(
                            side="left", padx=3, pady=3)

    def _field(self, frame, row, label, default="", choices=None):
        ttk = self.ttk
        var = self.tk.StringVar(value=default)
        ttk.Label(frame, text=label).grid(row=row, column=0, padx=5,
                                          pady=3, sticky="w")
        if choices is None:
            widget = ttk.Entry(frame, textvariable=var, width=28)
        else:
            widget = ttk.Combobox(frame, textvariable=var, values=choices,
                                  state="readonly", width=26)
        widget.grid(row=row, column=1, padx=5, pady=3, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)
        return var, widget

    def _build(self, notebook):
        ttk = self.ttk
        page = ttk.Frame(notebook)
        notebook.add(page, text="Synergies & secrets")
        self.page = page
        top = ttk.Frame(page)
        top.pack(fill="x", padx=7, pady=5)
        ttk.Label(top, text="Combos connus / secrets").pack(side="left")
        self.combo_list = self.tk.Listbox(page, height=5, exportselection=False)
        self.combo_list.pack(fill="x", padx=8, pady=3)
        self.combo_list.bind("<<ListboxSelect>>", lambda e: self._selected())
        actions = ttk.Frame(page)
        actions.pack(fill="x", padx=7)
        self._button(actions, "Nouveau combo", self.new_combo)
        self._button(actions, "Créer / enregistrer", self.save_combo)
        self._button(actions, "Supprimer combo", self.delete_combo)

        setup = ttk.LabelFrame(page, text="Membres et découverte")
        setup.pack(fill="x", padx=8, pady=5)
        self.tactic, self.tactic_box = self._field(
            setup, 0, "Tactique", "pincer",
            choices=["pincer", "crossfire", "encirclement", "relay"])
        self.members, _ = self._field(setup, 1, "Membres (IDs séparés par ,)",
                                      "ziggy,momo")
        self.hints = {}
        for row, label in enumerate(("hidden", "clue", "near", "unlocked"), 2):
            self.hints[label], _ = self._field(setup, row,
                                               "Indice " + label, "")

        middle = ttk.Frame(page)
        middle.pack(fill="both", expand=True, padx=8, pady=4)
        treepane = ttk.LabelFrame(middle, text="Arbre de conditions")
        treepane.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(treepane, show="tree", selectmode="browse",
                                 height=12)
        self.tree.pack(fill="both", expand=True, padx=6, pady=5)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._choose_node())
        treebuttons = ttk.Frame(treepane)
        treebuttons.pack(fill="x", padx=5, pady=3)
        self._button(treebuttons, "ET", lambda: self.modify_tree("wrap", "all"))
        self._button(treebuttons, "OU", lambda: self.modify_tree("wrap", "any"))
        self._button(treebuttons, "+ Enfant", lambda: self.modify_tree("append"))
        self._button(treebuttons, "Remplacer", lambda: self.modify_tree("replace"))
        self._button(treebuttons, "Supprimer nœud", lambda: self.modify_tree("delete"))

        editor = ttk.LabelFrame(middle, text="Prédicat / séquence")
        editor.pack(side="right", fill="both", padx=(8, 0))
        self.kind, _ = self._field(editor, 0, "Type", "stat",
            choices=["stat", "mission", "completed_mission", "sequence"])
        self.stat, self.stat_box = self._field(editor, 1, "Statistique",
            "shared_kills", choices=list(edit.STAT_PRESETS))
        self.amount, _ = self._field(editor, 2, "Objectif / répétitions", "2")
        self.mission, self.mission_box = self._field(
            editor, 3, "Mission", "", choices=[])
        self.max_ticks, _ = self._field(editor, 4, "Fenêtre en ticks", "10")
        self.same_target = self.tk.BooleanVar(value=False)
        self.all_members = self.tk.BooleanVar(value=False)
        ttk.Checkbutton(editor, text="Même cible", variable=self.same_target).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=7)
        ttk.Checkbutton(editor, text="Action de tous les membres",
                        variable=self.all_members).grid(
                            row=6, column=0, columnspan=2, sticky="w", padx=7)
        ttk.Label(editor, text="Événements ordonnés").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=5)
        self.sequence_list = self.tk.Listbox(editor, height=4, exportselection=False)
        self.sequence_list.grid(row=8, column=0, columnspan=2,
                                sticky="nsew", padx=6, pady=3)
        self.sequence_list.bind("<<ListboxSelect>>", lambda e: self._pick_step())
        self.event_kind, _ = self._field(editor, 9, "Événement", "damage",
            choices=["damage", "downed", "status", "forced_move", "heal",
                     "revive", "tactic", "intercept", "message"])
        self.event_field, _ = self._field(editor, 10, "Champ optionnel", "",
            choices=["", "source", "unit", "status", "mode", "tactic"])
        self.event_value, _ = self._field(editor, 11, "Valeur de champ", "")
        steps = ttk.Frame(editor)
        steps.grid(row=12, column=0, columnspan=2, sticky="w")
        self._button(steps, "+ Étape", self.add_step)
        self._button(steps, "− Étape", self.delete_step)
        self._button(steps, "↑", lambda: self.move_step(-1))
        self._button(steps, "↓", lambda: self.move_step(1))

        preview = ttk.LabelFrame(page, text="Simulation isolée de la progression")
        preview.pack(fill="x", padx=8, pady=5)
        self.preview_stats, _ = self._field(preview, 0,
            "Stats, ex. shared_kills=2", "shared_kills=2")
        self.preview_mission, self.preview_mission_box = self._field(
            preview, 1, "Mission actuelle", "", choices=[])
        self.preview_completed, _ = self._field(
            preview, 2, "Missions terminées", "")
        self.preview_events, _ = self._field(
            preview, 3, "Événements: kind@tick@source@target",
            "")
        preview_controls = ttk.Frame(preview)
        preview_controls.grid(row=4, column=0, columnspan=2, sticky="w")
        self._button(preview_controls, "Simuler découverte", self.run_preview)
        self.status = self.tk.StringVar(value="Sélectionner un combo ou en créer un.")
        ttk.Label(page, textvariable=self.status, wraplength=1050).pack(
            fill="x", padx=8, pady=5)

    def _data(self):
        return self.owner.doc().data

    def _members(self):
        return [s.strip() for s in self.members.get().split(",") if s.strip()]

    def _hints(self):
        return {k: v.get().strip() for k, v in self.hints.items()
                if v.get().strip()}

    def _selected(self):
        if self._loading:
            return
        chosen = self.combo_list.curselection()
        if not chosen:
            return
        self.index = chosen[0]
        record = self._data()["tactic_unlocks"][self.index]
        self.tactic.set(record["id"])
        self.members.set(", ".join(record["members"]))
        for key, var in self.hints.items():
            var.set(record.get("hints", {}).get(key, ""))
        self.condition = record["unlock"].copy()
        self._draw_tree()
        self.status.set("Édition de " + record["id"] + " — changements validés.")

    def new_combo(self):
        self.index = None
        self.combo_list.selection_clear(0, "end")
        self.condition = edit.leaf("stat", stat="missions_together", threshold=1)
        for v in self.hints.values():
            v.set("")
        self._draw_tree()
        self.status.set("Nouveau combo : choisir la tactique et ses membres.")

    def _draw_tree(self):
        self._loading = True
        self.tree.delete(*self.tree.get_children())
        self.path_map = {}
        ids = {}
        for index, row in enumerate(edit.rows(self.condition)):
            path = row["path"]
            parent = ids.get(path[:-1], "") if path else ""
            key = "n" + str(index)
            self.tree.insert(parent, "end", iid=key,
                             text=row["label"], open=True)
            ids[path] = key
            self.path_map[key] = path
        if self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])
        self._loading = False

    def _path(self):
        selected = self.tree.selection()
        return self.path_map[selected[0]] if selected else ()

    def _choose_node(self):
        if self._loading:
            return
        node = next((row["rule"] for row in edit.rows(self.condition)
                     if row["path"] == self._path()), None)
        if node is None:
            return
        if "stat" in node:
            self.kind.set("stat")
            self.stat.set(node["stat"])
            self.amount.set(str(node.get("gte", 1)))
        elif "mission" in node or "completed_mission" in node:
            self.kind.set("mission" if "mission" in node else "completed_mission")
            self.mission.set(node.get("mission", node.get("completed_mission", "")))
        elif "sequence" in node:
            self.kind.set("sequence")
            self.sequence = list(node["sequence"])
            self.amount.set(str(node.get("count", 1)))
            self.max_ticks.set(str(node.get("max_ticks", 10)))
            self.same_target.set(bool(node.get("same_target", False)))
            self.all_members.set(node.get("require_sources") == "all_members")
            self._draw_steps()

    def _leaf(self):
        kind = self.kind.get()
        if kind == "stat":
            return edit.leaf(kind, stat=self.stat.get(),
                             threshold=int(self.amount.get()))
        if kind in ("mission", "completed_mission"):
            return edit.leaf(kind, mission=self.mission.get())
        return edit.leaf("sequence", sequence=self.sequence,
                         count=int(self.amount.get()),
                         max_ticks=int(self.max_ticks.get()),
                         same_target=bool(self.same_target.get()),
                         require_sources=bool(self.all_members.get()))

    def modify_tree(self, action, operator="all"):
        condition = edit.change_tree(
            self.condition, action, path=self._path(),
            operator=operator,
            value=self._leaf() if action in ("replace", "append") else None)
        self._save_condition(condition)

    def _save_condition(self, condition):
        if self.index is None:
            self.condition = condition
            self._draw_tree()
            self.status.set("Nouvelle condition prête : créer le combo pour l'enregistrer.")
            return
        index = self.index
        tactic, members, hints = self.tactic.get(), self._members(), self._hints()
        self.parent._apply(lambda data: edit.save_unlock(
            data, tactic, members, condition, hints=hints, index=index))
        self.condition = condition
        self.refresh()
        self.status.set("Condition sauvegardée et validée.")

    def save_combo(self):
        tactic, members, hints = self.tactic.get(), self._members(), self._hints()
        index = self.index
        self.parent._apply(lambda data: edit.save_unlock(
            data, tactic, members, self.condition, hints=hints, index=index))
        if index is None:
            self.index = len(self._data()["tactic_unlocks"]) - 1
        self.refresh()
        self.status.set("Combo enregistré dans Content.tactic_unlocks.")

    def delete_combo(self):
        require(self.index is not None, "Sélectionner un combo à supprimer")
        index = self.index
        self.parent._apply(lambda data: edit.delete_unlock(data, index))
        self.index = None
        self.new_combo()
        self.refresh()

    def _draw_steps(self):
        self.sequence_list.delete(0, "end")
        for i, step in enumerate(self.sequence):
            self.sequence_list.insert("end", str(i + 1) + ". " +
                                      str(step.get("kind", "")) + " — " +
                                      ", ".join(k + "=" + str(v)
                                                for k, v in step.items()
                                                if k != "kind"))

    def _pick_step(self):
        index = self.sequence_list.curselection()
        if not index:
            return
        step = self.sequence[index[0]]
        self.event_kind.set(step["kind"])
        key = next((k for k in step if k != "kind"), "")
        self.event_field.set(key)
        self.event_value.set(step.get(key, ""))

    def add_step(self):
        spec = edit.event_spec(self.event_kind.get(),
                               **({self.event_field.get(): self.event_value.get()}
                                  if self.event_field.get() else {}))
        self.sequence.append(spec)
        self._draw_steps()

    def delete_step(self):
        selection = self.sequence_list.curselection()
        require(selection, "Sélectionner une étape")
        require(len(self.sequence) > 1,
                "Une séquence conserve au moins un événement")
        del self.sequence[selection[0]]
        self._draw_steps()

    def move_step(self, direction):
        selection = self.sequence_list.curselection()
        require(selection and 0 <= selection[0] + direction < len(self.sequence),
                "Déplacement d'étape impossible")
        i = selection[0]
        self.sequence[i], self.sequence[i + direction] = (
            self.sequence[i + direction], self.sequence[i])
        self._draw_steps()
        self.sequence_list.selection_set(i + direction)

    def _stats(self):
        result = {}
        for chunk in self.preview_stats.get().split(","):
            if not chunk.strip():
                continue
            require(chunk.count("=") == 1, "Stat attendue : clé=nombre")
            key, value = [v.strip() for v in chunk.split("=")]
            require(key and key not in result and value.isdecimal(),
                    "Stat simulée invalide ou dupliquée")
            result[key] = int(value)
        return result

    def _events(self):
        result = []
        for item in self.preview_events.get().split(";"):
            if not item.strip():
                continue
            parts = [v.strip() for v in item.split("@")]
            require(1 <= len(parts) <= 4 and parts[0], "Événement attendu : kind@tick@source@target")
            row = {"kind": parts[0]}
            if len(parts) >= 2 and parts[1]:
                require(parts[1].isdecimal(), "Tick d'événement invalide")
                row["tick"] = int(parts[1])
            if len(parts) >= 3 and parts[2]:
                row["source"] = parts[2]
            if len(parts) == 4 and parts[3]:
                row["unit"] = parts[3]
            result.append(row)
        return result

    def run_preview(self):
        if self.index is None:
            raise RuleError("Enregistrer le combo avant la simulation")
        result = edit.preview(
            self._data(), self.index, stats=self._stats(),
            mission_id=self.preview_mission.get(),
            completed=[s.strip() for s in self.preview_completed.get().split(",")
                       if s.strip()], events=self._events())
        self.status.set(
            ("DÉBLOQUÉ" if result["met"] else "VERROUILLÉ") +
            " · progression estimée : " +
            str(round(result["progress"] * 100)) +
            "% · simulation uniquement, aucune sauvegarde modifiée.")
        return result

    def refresh(self):
        if self.owner.project is None:
            return
        data = self._data()
        rules = data.get("tactic_unlocks", [])
        self._loading = True
        self.combo_list.delete(0, "end")
        for i, rule in enumerate(rules):
            self.combo_list.insert(
                "end", str(i + 1) + ". " + rule["id"] + " (" +
                ", ".join(rule["members"]) + ")")
        if self.index is not None and self.index < len(rules):
            self.combo_list.selection_set(self.index)
            self.condition = rules[self.index]["unlock"].copy()
        else:
            self.index = None
        missions = [m["id"] for m in data["missions"]]
        self.mission_box["values"] = missions
        self.preview_mission_box["values"] = ["", *missions]
        self._loading = False
        self._draw_tree()
