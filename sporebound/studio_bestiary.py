"""Tk bestiary panel: opt-in medieval presets and safe mission placement."""
from . import medieval_catalog as medieval
from .model import require


class MedievalBestiaryStudio:
    def __init__(self, parent, tabs):
        self.parent = parent
        ttk, tk = parent.ttk, parent.tk
        page = ttk.Frame(tabs)
        tabs.add(page, text="Bestiaire 4.0")
        ttk.Label(page, text="Catalogue Jeanne d'Arc — loups, brigands, soldats et créatures de siège. "
                  "Installer est annulable; aucun scénario existant n'est remplacé.",
                  wraplength=900).pack(fill="x", padx=8, pady=5)
        columns = ("family", "tier", "role")
        frame = ttk.Frame(page)
        frame.pack(fill="both", expand=True, padx=8, pady=3)
        self.tree = ttk.Treeview(frame, columns=columns, show="tree headings",
                                 selectmode="browse", height=11)
        self.tree.heading("#0", text="Personnage / créature")
        self.tree.heading("family", text="Famille")
        self.tree.heading("tier", text="Palier")
        self.tree.heading("role", text="Rôle")
        self.tree.column("#0", width=185)
        self.tree.column("family", width=130)
        self.tree.column("tier", width=55, anchor="center")
        self.tree.column("role", width=240)
        self.tree.pack(side="left", fill="both", expand=True)
        scroller = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroller.set)
        scroller.pack(side="right", fill="y")
        for entry in medieval.entries():
            self.tree.insert("", "end", iid=entry["id"], text=entry["name"],
                             values=(entry["family"], entry["tier"], entry["role"]))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._select())
        self.details = tk.StringVar(value="Sélectionnez une fiche du bestiaire.")
        ttk.Label(page, textvariable=self.details, wraplength=950).pack(
            fill="x", padx=8, pady=7)
        form = ttk.LabelFrame(page, text="Placer dans la mission active")
        form.pack(fill="x", padx=8, pady=5)
        self.unit_id = tk.StringVar()
        self.unit_name = tk.StringVar()
        self.team = tk.StringVar(value="enemy")
        self.rank = tk.StringVar(value="normal")
        self.position = tk.StringVar(value="auto")
        fields = (
            ("ID unique", ttk.Entry(form, textvariable=self.unit_id)),
            ("Nom", ttk.Entry(form, textvariable=self.unit_name)),
            ("Camp", ttk.Combobox(form, textvariable=self.team, state="readonly",
                                   values=("player", "enemy"))),
            ("Grade", ttk.Combobox(form, textvariable=self.rank, state="readonly",
                                    values=tuple(medieval.RANKS))),
            ("Case x,y ou auto", ttk.Entry(form, textvariable=self.position)),
        )
        for index, (label, widget) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=index // 2, column=2*(index % 2),
                                             sticky="w", padx=5, pady=3)
            widget.grid(row=index // 2, column=2*(index % 2)+1,
                        sticky="ew", padx=5, pady=3)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)
        buttons = ttk.Frame(page)
        buttons.pack(fill="x", padx=8)
        parent._button(buttons, "Installer le catalogue", self.install)
        parent._button(buttons, "Placer le personnage", self.place)
        variant = ttk.LabelFrame(page, text="Fiches indépendantes — IA et compagnons")
        variant.pack(fill="x", padx=8, pady=5)
        self.variant_id = tk.StringVar(value="med_variant_01")
        self.variant_kind = tk.StringVar(value="character")
        self.variant_doctrine = tk.StringVar(value="pack_hunt")
        ttk.Label(variant, text="ID variante").grid(row=0, column=0, padx=4)
        ttk.Entry(variant, textvariable=self.variant_id).grid(row=0, column=1, padx=4)
        ttk.Combobox(variant, textvariable=self.variant_kind, state="readonly",
                     values=("character", "monster")).grid(row=0, column=2)
        from .bestiary_studio4 import DOCTRINE_OPTIONS
        ttk.Combobox(variant, textvariable=self.variant_doctrine, state="readonly",
                     values=DOCTRINE_OPTIONS).grid(row=0, column=3)
        actions = ttk.Frame(variant)
        actions.grid(row=1, column=0, columnspan=4)
        parent._button(actions, "Créer variante", self.create_variant)
        parent._button(actions, "Changer doctrine", self.change_doctrine)
        parent._button(actions, "Placer variante", self.place_variant)
        ttk.Label(page, text="Modifiez ensuite statistiques, compétences, classes "
                  "et arbres d'évolution dans les onglets du Studio. "
                  "Les instances déjà placées ne sont pas réécrites.",
                  wraplength=930).pack(fill="x", padx=8)
        balance = ttk.LabelFrame(page, text="Rencontres 3.1.6 — composition et difficulté")
        balance.pack(fill="x", padx=8, pady=5)
        self.budget_missions = tk.StringVar()
        ttk.Label(balance, text="3 missions (IDs séparés par une virgule)").pack(
            side="left", padx=5)
        ttk.Entry(balance, textvariable=self.budget_missions, width=35).pack(
            side="left", fill="x", expand=True, padx=4)
        parent._button(balance, "Analyser les rencontres", self.analyze_three)
        self.budget_result = tk.StringVar(value="Budget, rôles et alertes de composition.")
        ttk.Label(page, textvariable=self.budget_result, wraplength=930).pack(
            fill="x", padx=8)
        self.pack_state = tk.StringVar()
        ttk.Label(page, textvariable=self.pack_state).pack(fill="x", padx=8, pady=3)
        ttk.Label(page, text="Évolution : Recrue → Écuyer → Épéiste / Garde "
                  "→ Duelliste / Chevalier. Filières alternatives : Archer → "
                  "Tireur d'élite, Éclaireur → Rôdeur, Soigneur. "
                  "Les niveaux, JP et talents sont gérés par la progression de campagne.",
                  wraplength=900).pack(fill="x", padx=8, pady=7)

    def _selected(self):
        ids = self.tree.selection()
        require(bool(ids), "Choisir un personnage dans le bestiaire")
        return ids[0]

    def _select(self):
        identifier = self._selected()
        entry = medieval.BESTIARY[identifier]
        self.details.set(entry["description"] + " — " + entry["role"])
        self.unit_id.set("med_" + identifier + "_01")
        self.unit_name.set(entry["name"])

    def install(self):
        self.parent._apply(medieval.install_pack)
        self.parent.status.set("Bestiaire médiéval importé et vérifié.")

    def place(self):
        identifier = self._selected()
        raw = self.position.get().strip().lower()
        if raw == "auto":
            pos = medieval.find_free_cell(self.parent._data(),
                                          self.parent.owner.mission(), identifier)
        else:
            parts = raw.split(",")
            require(len(parts) == 2, "Case attendue : x,y ou auto")
            try:
                pos = [int(part.strip()) for part in parts]
            except ValueError as exc:
                from .model import RuleError
                raise RuleError("Case attendue : x,y ou auto") from exc
        mission_id = self.parent.owner.mission()
        self.parent._apply(lambda data: medieval.place_entry(
            data, mission_id, identifier, self.unit_id.get(),
            self.team.get(), pos, rank=self.rank.get(),
            name=self.unit_name.get()))
        self.parent.status.set("Combattant placé dans " + mission_id +
                               " ; modèle conservé indépendamment.")

    def create_variant(self):
        from .bestiary_studio4 import create_variant
        source = medieval.archetype_id(self._selected())
        self.parent._apply(lambda data: create_variant(
            data, source, self.variant_id.get(),
            kind=self.variant_kind.get(), doctrine=self.variant_doctrine.get()))
        self.parent.status.set("Variante créée sans JSON : " + self.variant_id.get())

    def change_doctrine(self):
        from .bestiary_studio4 import edit_doctrine
        self.parent._apply(lambda data: edit_doctrine(
            data, self.variant_id.get(), self.variant_doctrine.get()))
        self.parent.status.set("Doctrine du modèle mise à jour.")

    def place_variant(self):
        from .bestiary_studio4 import place_variant
        from .model import Content, require
        aid = self.variant_id.get()
        mid = self.parent.owner.mission()
        raw = self.position.get().strip().lower()
        if raw == "auto":
            model = Content.from_dict(self.parent._data())
            mission = model.missions[mid]
            size = self.parent._data().get("archetypes", {}).get(aid, {}).get("footprint", [1, 1])
            occupied = set().union(*(u.occupied_cells() for u in mission.units))
            occupied.update(tuple(o["pos"]) for o in mission.objects)
            pos = next((list(c) for c in mission.board.cells()
                        if all(mission.board.contains((c[0]+dx,c[1]+dy))
                               and (c[0]+dx,c[1]+dy) not in occupied
                               and not mission.board.tile((c[0]+dx,c[1]+dy)).blocked
                               for dx in range(size[0]) for dy in range(size[1]))), None)
            require(pos is not None, "Aucune position valide pour la variante")
        else:
            coords = raw.split(",")
            require(len(coords) == 2, "Position attendue : x,y")
            pos = [int(value.strip()) for value in coords]
        self.parent._apply(lambda data: place_variant(
            data, mid, aid, self.unit_id.get(),
            self.unit_name.get() or aid, self.team.get(), pos))
        self.parent.status.set("Variante placée : " + aid)

    def analyze_three(self):
        from .encounter_balance31 import analyze_three
        from .tactical_rpg3 import authored_rules_for_document
        from .model import Content, require
        data = self.parent._data()
        ids = [name.strip() for name in self.budget_missions.get().split(",")
               if name.strip()]
        require(len(ids) == 3, "Indiquer trois missions distinctes")
        content = Content.from_dict(data, rules=authored_rules_for_document(data))
        report = analyze_three(content, ids)
        lines = []
        for item in report["encounters"]:
            note = "; ".join(item["warnings"]) or "budget cohérent"
            lines.append("{} : ratio {} — rôles {} — {}".format(
                item["mission"], item["ratio"], ", ".join(item["enemy_roles"]), note))
        self.budget_result.set(" | ".join(lines))
        self.parent.status.set(
            "Diagnostic indicatif : {}. Simuler les trois combats pour certifier.".format(
                "équilibré" if report["balanced"] else "à revoir"))

    def refresh(self):
        if self.parent.owner.project is None:
            return
        archetypes = self.parent._data().get("archetypes", {})
        count = sum(medieval.archetype_id(entry["id"]) in archetypes
                    for entry in medieval.entries())
        self.pack_state.set(str(count) + "/" + str(len(medieval.BESTIARY)) +
                            " archétypes installés.")
