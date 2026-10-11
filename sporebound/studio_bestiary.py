"""Tk bestiary panel: opt-in medieval presets and safe mission placement."""
from . import medieval_catalog as medieval
from .model import require


class MedievalBestiaryStudio:
    def __init__(self, parent, tabs):
        self.parent = parent
        ttk, tk = parent.ttk, parent.tk
        page = ttk.Frame(tabs)
        tabs.add(page, text="Bestiaire médiéval")
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

    def refresh(self):
        if self.parent.owner.project is None:
            return
        archetypes = self.parent._data().get("archetypes", {})
        count = sum(medieval.archetype_id(entry["id"]) in archetypes
                    for entry in medieval.entries())
        self.pack_state.set(str(count) + "/" + str(len(medieval.BESTIARY)) +
                            " archétypes installés.")
