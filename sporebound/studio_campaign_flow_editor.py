"""R5.13 Campaign Flow visual authoring, using existing GameProject and Studio undo.

Everything here is a Tk view/controller. Business logic and validation live in
campaign_flow_authoring; no duplicate progression engine or JSON text editor.
"""
from __future__ import annotations

from . import campaign_flow_authoring as commands
from .campaign_flow import audit_campaign
from .story_conditions import rows
from .story_graph import condition_label


_KINDS = {
    "Flag =": "flag_eq", "Flag ≥": "flag_gte",
    "Flag ≤": "flag_lte", "Mission terminée": "completed_mission",
    "Or ≥": "gold_gte",
}
_EFFECT_LABELS = {
    "set_flag": ("Variable", "Valeur"),
    "add_flag": ("Variable", "Delta entier"),
    "unlock_mission": ("Mission", "—"),
    "recruit_hero": ("Héros", "—"),
    "grant_item": ("Équipement", "Quantité"),
    "equip_hero": ("Héros", "Équipement"),
    "gold": ("—", "Delta or"),
    "wound": ("Héros", "Blessure"),
    "heal_wound": ("Héros", "Blessure"),
}


class CampaignFlowEditor:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.notebook = notebook
        self._refreshing = False
        self._paths = {}
        self._build(notebook)

    def _button(self, parent, title, callback):
        self.ttk.Button(parent, text=title,
                        command=lambda: self.owner._run(callback)).pack(
                            side="left", padx=3, pady=3)

    def _build(self, notebook):
        tk, ttk = self.tk, self.ttk
        root = ttk.Frame(notebook)
        notebook.add(root, text="Campaign Flow 3.0")
        self.tab = root
        ttk.Label(root, text="Progression conditionnelle et conséquences — édition visuelle, Undo/Redo global",
                  ).pack(anchor="w", padx=8, pady=6)
        panes = ttk.Panedwindow(root, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=4)

        conditions = ttk.LabelFrame(panes, text="Conditions de mission / fins")
        panes.add(conditions, weight=2)
        top = ttk.Frame(conditions)
        top.pack(fill="x", padx=7, pady=4)
        self.target_kind = tk.StringVar(value="gate")
        ttk.Label(top, text="Type").pack(side="left")
        box = ttk.Combobox(top, textvariable=self.target_kind, state="readonly",
                           values=("gate", "ending"), width=11)
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self._switch_target())
        ttk.Label(top, text="Mission ou ID de fin").pack(side="left")
        self.target_name = tk.StringVar()
        self.target_box = ttk.Combobox(top, textvariable=self.target_name, width=29)
        self.target_box.pack(side="left", padx=5)
        self.target_box.bind("<<ComboboxSelected>>", lambda _e: self._draw_conditions())
        self._button(top, "Voir condition", self._draw_conditions)
        self._button(top, "Tester sur la campagne", self.preview)
        self._button(top, "Analyser parcours", self.analyze)

        condition_area = ttk.Frame(conditions)
        condition_area.pack(fill="both", expand=True, padx=7, pady=3)
        left = ttk.Frame(condition_area)
        left.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", height=8)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selected_condition())
        right = ttk.Frame(condition_area)
        right.pack(side="right", fill="y", padx=(12, 0))
        self.pred_kind = tk.StringVar(value="Flag =")
        ttk.Label(right, text="Prédicat").pack(anchor="w")
        ttk.Combobox(right, state="readonly", textvariable=self.pred_kind,
                     values=list(_KINDS), width=27).pack(fill="x", pady=2)
        self.pred_key = tk.StringVar(value="reputation_village")
        ttk.Label(right, text="Variable ou mission").pack(anchor="w")
        self.pred_key_box = ttk.Combobox(right, textvariable=self.pred_key, width=28)
        self.pred_key_box.pack(fill="x", pady=2)
        self.pred_value = tk.StringVar(value="1")
        ttk.Label(right, text="Valeur (true / false / entier / texte)").pack(anchor="w")
        ttk.Entry(right, textvariable=self.pred_value).pack(fill="x", pady=2)
        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=3)
        self._button(controls, "Créer / remplacer", self.replace)
        self._button(controls, "+ Enfant", self.append)
        controls = ttk.Frame(right)
        controls.pack(fill="x")
        self._button(controls, "ET", lambda: self.wrap("all"))
        self._button(controls, "OU", lambda: self.wrap("any"))
        self._button(controls, "NON", lambda: self.wrap("not"))
        self._button(controls, "Supprimer", self.delete)

        outcome = ttk.LabelFrame(panes, text="Conséquences victoire / défaite (ordre d'application)")
        panes.add(outcome, weight=2)
        header = ttk.Frame(outcome)
        header.pack(fill="x", padx=7, pady=4)
        self.mission = tk.StringVar()
        self.mission_box = ttk.Combobox(header, textvariable=self.mission,
                                       state="readonly", width=29)
        self.mission_box.pack(side="left", padx=4)
        self.mission_box.bind("<<ComboboxSelected>>", lambda _e: self._draw_effects())
        self.outcome = tk.StringVar(value="victory")
        ttk.Combobox(header, textvariable=self.outcome, state="readonly",
                     values=commands.OUTCOMES, width=11).pack(side="left", padx=4)
        ttk.Button(header, text="Actualiser", command=self._draw_effects).pack(side="left", padx=4)
        middle = ttk.Frame(outcome)
        middle.pack(fill="both", expand=True, padx=7)
        self.effects = tk.Listbox(middle, height=7, exportselection=False)
        self.effects.pack(side="left", fill="both", expand=True)
        self.effects.bind("<<ListboxSelect>>", lambda _e: self._selected_effect())
        form = ttk.Frame(middle)
        form.pack(side="right", fill="y", padx=(12, 0))
        self.effect_kind = tk.StringVar(value="set_flag")
        ttk.Label(form, text="Effet").pack(anchor="w")
        effect_box = ttk.Combobox(form, textvariable=self.effect_kind,
                                  state="readonly", values=commands.EFFECTS, width=24)
        effect_box.pack(fill="x", pady=2)
        effect_box.bind("<<ComboboxSelected>>", lambda _e: self._effect_labels())
        self.effect_a_label = ttk.Label(form, text="Variable")
        self.effect_a_label.pack(anchor="w")
        self.effect_a = tk.StringVar()
        self.effect_a_box = ttk.Combobox(form, textvariable=self.effect_a, width=26)
        self.effect_a_box.pack(fill="x", pady=2)
        self.effect_b_label = ttk.Label(form, text="Valeur")
        self.effect_b_label.pack(anchor="w")
        self.effect_b = tk.StringVar()
        self.effect_b_box = ttk.Combobox(form, textvariable=self.effect_b, width=26)
        self.effect_b_box.pack(fill="x", pady=2)
        controls = ttk.Frame(form)
        controls.pack(fill="x", pady=3)
        self._button(controls, "Ajouter", self.add_effect)
        self._button(controls, "Modifier", self.replace_effect)
        self._button(controls, "Supprimer", self.delete_effect)
        controls = ttk.Frame(form)
        controls.pack(fill="x")
        self._button(controls, "Monter", lambda: self.move_effect(-1))
        self._button(controls, "Descendre", lambda: self.move_effect(1))

        self.status = tk.StringVar(value="Sélectionner une mission ou une fin.")
        ttk.Label(root, textvariable=self.status, wraplength=1050).pack(
            fill="x", padx=10, pady=(5, 7))

    def _project(self):
        return self.owner.project

    def _content(self):
        return self.owner._content()

    def _commit(self, operation):
        """One validated GameProject update, one owner-level history event."""
        updated = operation(self._project(), self._content())
        self.owner.project = updated
        self.owner.project_status.config(
            text="Campaign Flow modifié — enregistrer le projet de jeu.")
        self.refresh()

    def _switch_target(self):
        self.target_name.set("")
        self.refresh()

    def _selected_path(self):
        selected = self.tree.selection()
        return self._paths.get(selected[0], ()) if selected else ()

    def _expression(self):
        return commands.condition_for(self._project(), self.target_kind.get(),
                                      self.target_name.get())

    def _draw_conditions(self):
        if self._refreshing:
            return
        self._refreshing = True
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        tree_rows = rows(self._expression())
        indices = {}
        for index, row in enumerate(tree_rows):
            path = row["path"]
            parent = indices.get(path[:-1], "") if path else ""
            iid = "p" + str(index)
            self.tree.insert(parent, "end", iid=iid,
                             text=condition_label(row["expression"]), open=True)
            self._paths[iid] = path
            indices[path] = iid
        if tree_rows:
            self.tree.selection_set("p0")
        self._refreshing = False
        self.status.set("Condition : " + condition_label(self._expression())
                        if tree_rows else "Aucune condition : entrée libre / fin sans critère.")

    def _selected_condition(self):
        if self._refreshing:
            return
        path = self._selected_path()
        found = next((r for r in rows(self._expression()) if r["path"] == path),
                     None)
        if found is None:
            return
        node = found["expression"]
        if "flag" in node:
            comparison = next(k for k in ("eq", "gte", "lte") if k in node)
            self.pred_kind.set({"eq": "Flag =", "gte": "Flag ≥",
                                "lte": "Flag ≤"}[comparison])
            self.pred_key.set(node["flag"])
            value = node[comparison]
            self.pred_value.set(str(value).lower() if type(value) is bool else str(value))
        elif "completed_mission" in node:
            self.pred_kind.set("Mission terminée")
            self.pred_key.set(node["completed_mission"])
        elif "gold_gte" in node:
            self.pred_kind.set("Or ≥")
            self.pred_value.set(str(node["gold_gte"]))

    def _change_condition(self, action, operator="all"):
        target, name = self.target_kind.get(), self.target_name.get().strip()
        # Deleting an absent entry is not a creative action.
        def command(project, content):
            return commands.change_condition(
                project, content, target, name, action,
                path=self._selected_path(),
                kind=_KINDS[self.pred_kind.get()],
                key=self.pred_key.get(), value=self.pred_value.get(),
                operator=operator)
        self._commit(command)

    def replace(self):
        self._change_condition("replace")

    def append(self):
        self._change_condition("append")

    def wrap(self, operator):
        self._change_condition("wrap", operator)

    def delete(self):
        self._change_condition("delete")

    def preview(self):
        name = self.target_name.get().strip()
        target = self.target_kind.get()
        progress = (self.owner.session
                    if self.owner.session is not None and
                    self.owner.session_campaign == self.owner.campaign_id.get()
                    else self._project().new_game(self.owner.campaign_id.get(), self._content()))
        from .campaign_flow import verify_save
        verify_save(progress, self._project().campaign_flow)
        report = commands.preview_condition(self._project(), target, name, progress)
        self.status.set(("SATISFAITE" if report["matches"] else "NON SATISFAITE")
                        + (" (condition définie)" if report["defined"] else " (sans condition)")
                        + " — aperçu, sans modifier la campagne.")

    def analyze(self):
        report = audit_campaign(self._content(), self._project(),
                                self.owner.campaign_id.get())
        self.status.set(
            f"QA : {len(report['errors'])} erreurs, {len(report['warnings'])} avertissements, "
            f"{report['states_explored']} états explorés"
            + (" (limite atteinte)" if report["truncated"] else ""))

    def _effects(self):
        return commands.outcome_effects(self._project(), self.mission.get(),
                                        self.outcome.get())

    def _draw_effects(self, select=None):
        if self._refreshing:
            return
        self._refreshing = True
        self.effects.delete(0, "end")
        for index, row in enumerate(self._effects()):
            kind, a, b = commands.effect_fields(row)
            self.effects.insert("end", f"{index + 1}. {kind} : {a} {b}")
        if select is not None and 0 <= select < self.effects.size():
            self.effects.selection_set(select)
        self._refreshing = False

    def _selected_index(self):
        selection = self.effects.curselection()
        return selection[0] if selection else None

    def _selected_effect(self):
        if self._refreshing:
            return
        index = self._selected_index()
        if index is None:
            return
        kind, a, b = commands.effect_fields(self._effects()[index])
        self.effect_kind.set(kind)
        self.effect_a.set(a)
        self.effect_b.set(b)
        self._effect_labels()

    def _effect_labels(self):
        kind = self.effect_kind.get()
        a_label, b_label = _EFFECT_LABELS[kind]
        self.effect_a_label.config(text=a_label)
        self.effect_b_label.config(text=b_label)
        content = self._content()
        missions = list(content.missions)
        heroes = list(dict.fromkeys(unit.id for mission in content.missions.values()
                                   for unit in mission.units if unit.team == "player"))
        equipment = list(content.equipment)
        from .character_growth31 import WOUNDS
        self.effect_a_box["values"] = (
            missions if kind == "unlock_mission" else
            heroes if kind in {"recruit_hero", "equip_hero", "wound", "heal_wound"}
            else equipment if kind == "grant_item" else [])
        self.effect_b_box["values"] = (
            equipment if kind == "equip_hero" else
            list(WOUNDS) if kind in {"wound", "heal_wound"} else [])

    def _form_effect(self):
        return commands.build_effect(
            self.effect_kind.get(), self.effect_a.get(), self.effect_b.get(),
            content=self._content())

    def _change_effect(self, action, destination=None):
        mid, result = self.mission.get(), self.outcome.get()
        index = self._selected_index()
        effect = self._form_effect() if action in {"add", "replace"} else None
        self._commit(lambda project, content: commands.change_effect(
            project, content, mid, result, action,
            index=index, effect=effect, destination=destination))
        if action != "delete":
            self._draw_effects(select=(destination if action == "move"
                                       else index if action == "replace"
                                       else len(self._effects()) - 1))

    def add_effect(self):
        self._change_effect("add")

    def replace_effect(self):
        self._change_effect("replace")

    def delete_effect(self):
        self._change_effect("delete")

    def move_effect(self, direction):
        index = self._selected_index()
        # Invalid selections are rejected in the pure model, not swallowed.
        self._change_effect("move", destination=(index + direction
                                                  if index is not None else -1))

    def refresh(self):
        if self.owner.project is None:
            return
        self._refreshing = True
        missions = list(self._content().missions)
        endings = sorted(self._project().campaign_flow.get("endings", {}))
        self.target_box["values"] = (missions if self.target_kind.get() == "gate"
                                      else endings)
        if self.target_kind.get() == "gate":
            if self.target_name.get() not in missions:
                self.target_name.set(missions[0] if missions else "")
        # An editable ending ID is preserved even before its creation.
        self.mission_box["values"] = missions
        if self.mission.get() not in missions:
            self.mission.set(missions[0] if missions else "")
        self.pred_key_box["values"] = missions
        self._refreshing = False
        self._draw_conditions()
        self._draw_effects()
        self._effect_labels()
