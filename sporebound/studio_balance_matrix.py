"""3.8.2 Studio Balance Matrix — editable scenarios, not new gameplay rules.

The user adds named cases using guided presets and named authored missions.
All simulations use one immutable Content/RuleSet snapshot captured on the Tk
thread; the worker communicates only through Queue.
"""
from __future__ import annotations

from queue import Queue, Empty
from threading import Thread

from .balance_matrix import run_matrix, compare_matrices, save_matrix
from .model import RuleError
from .tactical_rpg3 import authored_rules_for_document


PRESETS = (
    "Témoin sans modification",
    "Joueurs +5 PV",
    "Ennemis +5 PV",
    "Ennemis +1 défense",
    "Ennemis -1 attaque",
    "Retirer unité sélectionnée",
    "Unité choisie +2 attaque",
)


class BalanceMatrixStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.ttk, self.tk = owner.ttk, owner.tk
        self.notebook = notebook
        self.cases = []
        self.current = None
        self._run_snapshot = None
        self.baseline = None
        self.comparison = None
        self.busy = False
        self.mailbox = Queue()
        self.frame = self.ttk.Frame(notebook, padding=10)
        self.tab = self.frame
        notebook.add(self.frame, text="Balance Matrix")

        self.ttk.Label(self.frame, text="Balance Matrix · 3.8.2",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.ttk.Label(
            self.frame, text="Missions, compositions et variantes : même seed et "
            "même Battle pour chaque scénario. Comparaison descriptive, sans "
            "modifier la carte ni les règles sauvegardées.",
            wraplength=900).pack(anchor="w", pady=(3, 9))
        options = self.ttk.Frame(self.frame)
        options.pack(fill="x", pady=4)
        self.mission = self.tk.StringVar(value=owner.mission())
        self.preset = self.tk.StringVar(value=PRESETS[1])
        self.unit = self.tk.StringVar()
        self.seeds = self.tk.StringVar(value="1,7,42,99")
        self.limit = self.tk.StringVar(value="100")
        for col, (caption, value, choices) in enumerate((
                ("Mission", self.mission, []),
                ("Variante", self.preset, PRESETS),
                ("Unité cible", self.unit, []))):
            self.ttk.Label(options, text=caption).grid(
                row=0, column=col, sticky="w", padx=5)
            widget = self.ttk.Combobox(
                options, textvariable=value, values=choices, state="readonly",
                width=(22 if col == 1 else 19))
            widget.grid(row=1, column=col, sticky="ew", padx=5, pady=4)
            if col == 0:
                self.mission_box = widget
                widget.bind("<<ComboboxSelected>>", self._mission_changed)
            if col == 2:
                self.unit_box = widget
        for col, (caption, value) in enumerate((
                ("Seeds (max. 64)", self.seeds), ("Commandes max.", self.limit)), start=3):
            self.ttk.Label(options, text=caption).grid(
                row=0, column=col, sticky="w", padx=5)
            self.ttk.Entry(options, textvariable=value, width=18).grid(
                row=1, column=col, sticky="ew", padx=5, pady=4)
        for col in range(5):
            options.columnconfigure(col, weight=1)

        actions = self.ttk.Frame(self.frame)
        actions.pack(fill="x", pady=4)
        self.ttk.Button(actions, text="Ajouter scénario",
                        command=self.add_case).pack(side="left", padx=3)
        self.ttk.Button(actions, text="Retirer scénario",
                        command=self.remove_case).pack(side="left", padx=3)
        self.ttk.Button(actions, text="Ajouter témoins de toutes les missions",
                        command=self.add_all_missions).pack(side="left", padx=3)
        self.run_button = self.ttk.Button(actions, text="Comparer les scénarios",
                                          command=self.start)
        self.run_button.pack(side="left", padx=3)

        self.scenarios = self.ttk.Treeview(
            self.frame, columns=("id", "mission", "preset", "target"),
            show="headings", height=5)
        for col, title, width in zip(("id", "mission", "preset", "target"),
                                     ("ID", "Mission", "Variante", "Unité"),
                                     (170, 160, 210, 125)):
            self.scenarios.heading(col, text=title)
            self.scenarios.column(col, width=width)
        self.scenarios.pack(fill="x", pady=(5, 3))
        results = self.ttk.Frame(self.frame)
        results.pack(fill="x", pady=4)
        self.ttk.Button(results, text="Référence = matrice courante",
                        command=self.set_baseline).pack(side="left", padx=3)
        self.ttk.Button(results, text="Charger matrice de référence",
                        command=self.load_baseline).pack(side="left", padx=3)
        self.ttk.Button(results, text="Exporter matrice JSON",
                        command=self.export).pack(side="left", padx=3)
        self.ttk.Button(results, text="Inspecter mission dans Battle Lab",
                        command=self.inspect_mission).pack(side="left", padx=3)
        self.status = self.ttk.Label(self.frame, text="Prêt · aucun scénario exécuté.")
        self.status.pack(anchor="w", pady=2)
        self.rows = self.ttk.Treeview(
            self.frame,
            columns=("case", "mission", "win", "delta", "p95", "ct", "limit"),
            show="headings", height=9)
        for col, title, width in zip(
                ("case", "mission", "win", "delta", "p95", "ct", "limit"),
                ("Scénario", "Mission", "Victoires", "Δ victoires",
                 "Commandes p95", "CT p95", "Non conclus"),
                (195, 145, 90, 110, 120, 100, 100)):
            self.rows.heading(col, text=title)
            self.rows.column(col, width=width, anchor="center")
        self.rows.pack(fill="both", expand=True, pady=(3, 6))
        self.output = self.tk.Text(self.frame, height=8, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        missions = [m["id"] for m in self.owner.doc().data["missions"]]
        self.mission_box["values"] = missions
        if self.mission.get() not in missions and missions:
            self.mission.set(missions[0])
        self._mission_changed()

    def _mission_changed(self, _event=None):
        record = next((m for m in self.owner.doc().data["missions"]
                       if m["id"] == self.mission.get()), None)
        ids = [u["id"] for u in record["units"]] if record else []
        self.unit_box["values"] = ids
        if self.unit.get() not in ids:
            self.unit.set(ids[0] if ids else "")

    def _case(self, mid, preset, uid, ordinal):
        result = {"id": "{}::case{:02d}".format(mid, ordinal),
                  "mission": mid}
        if preset == PRESETS[1]:
            result["team_deltas"] = {"player": {"max_hp": 5}}
        elif preset == PRESETS[2]:
            result["team_deltas"] = {"enemy": {"max_hp": 5}}
        elif preset == PRESETS[3]:
            result["team_deltas"] = {"enemy": {"defense": 1}}
        elif preset == PRESETS[4]:
            result["team_deltas"] = {"enemy": {"attack": -1}}
        elif preset == PRESETS[5]:
            result["remove_units"] = [uid]
        elif preset == PRESETS[6]:
            result["unit_deltas"] = {uid: {"attack": 2}}
        return result

    def _add(self, mid, preset, uid=""):
        ordinal = len(self.cases) + 1
        while any(row["id"] == "{}::case{:02d}".format(mid, ordinal)
                  for row in self.cases):
            ordinal += 1
        case = self._case(mid, preset, uid, ordinal)
        self.cases.append(case)
        self.scenarios.insert("", "end", iid=case["id"], values=(
            case["id"], mid, preset, uid))
        return case

    def add_case(self):
        if self.busy:
            return
        mid, preset, uid = self.mission.get(), self.preset.get(), self.unit.get()
        if preset in (PRESETS[5], PRESETS[6]) and not uid:
            self.owner.dialogs.showerror("Balance Matrix", "Choisir une unité cible.")
            return
        if len(self.cases) >= 24:
            self.owner.dialogs.showerror("Balance Matrix", "Maximum 24 scénarios.")
            return
        self._add(mid, preset, uid)

    def add_all_missions(self):
        if self.busy:
            return
        missions = [m["id"] for m in self.owner.doc().data["missions"]]
        if len(self.cases) + len(missions) > 24:
            self.owner.dialogs.showerror("Balance Matrix", "Maximum 24 scénarios.")
            return
        for mid in missions:
            self._add(mid, PRESETS[0])

    def remove_case(self):
        if self.busy:
            return
        for iid in self.scenarios.selection():
            self.cases = [row for row in self.cases if row["id"] != iid]
            self.scenarios.delete(iid)

    def start(self):
        if self.busy:
            return
        try:
            seeds = [int(part.strip()) for part in self.seeds.get().split(",")]
            cap = int(self.limit.get())
            if not self.cases:
                raise RuleError("Ajouter au moins un scénario.")
            if not (1 <= len(seeds) <= 64 and len(seeds) == len(set(seeds))
                    and all(0 <= s < 2**32 for s in seeds)):
                raise RuleError("Seeds uniques 0..2^32-1 (max. 64).")
            if not 1 <= cap <= 10000:
                raise RuleError("Commandes max. entre 1 et 10000.")
            content = self.owner._content()
            rules = authored_rules_for_document(self.owner.doc().data)
            cases = [dict(row) for row in self.cases]
        except (RuleError, ValueError, TypeError) as exc:
            self.owner.dialogs.showerror("Balance Matrix", str(exc))
            return
        self.busy = True
        self.run_button.configure(state="disabled")
        self.status.configure(text="Simulations matricielles en cours…")
        def worker():
            try:
                report = run_matrix(content, cases, seeds=seeds,
                                    max_commands=cap, rulesets={"authored": rules})
                self.mailbox.put(("ok", report))
            except Exception as exc:
                self.mailbox.put(("error", str(exc)))
        Thread(target=worker, daemon=True).start()
        self.tab.after(80, self._poll)

    def _poll(self):
        try:
            kind, data = self.mailbox.get_nowait()
        except Empty:
            if self.busy and self.tab.winfo_exists():
                self.tab.after(80, self._poll)
            return
        self.busy = False
        self.run_button.configure(state="normal")
        if kind == "error":
            self.status.configure(text="Échec matrice")
            self.owner.dialogs.showerror("Balance Matrix", data)
        else:
            self.current = data
            self._render()

    def _render(self):
        if self.current is None:
            return
        self.rows.delete(*self.rows.get_children())
        for row in self.current["cases"]:
            report = row["report"]
            self.rows.insert("", "end", iid=row["id"], values=(
                row["id"], row["mission"],
                "{:.0%}".format(report["victory_rate"]),
                "{:+.0%}".format(row["victory_delta"]),
                report["commands_p95"], report["ticks_p95"],
                report["outcomes"]["limit"]))
        lines = [
            "{} missions · {} scénarios · {} seeds identiques · replays vérifiés : {}".format(
                self.current["mission_count"], self.current["case_count"],
                self.current["runs_per_case"],
                self.current["all_replays_verified"]),
            "Les Δ sont appariés au témoin de la même mission ; pas de "
            "comparaison directe entre missions différentes."
        ]
        self.comparison = None
        if self.baseline is not None:
            try:
                self.comparison = compare_matrices(self.baseline, self.current)
                lines.append("Gate inter-versions : " +
                             self.comparison["status"].upper())
                lines.append("Scénarios KO : " + ", ".join(
                    self.comparison["failures"]))
            except (RuleError, ValueError, KeyError) as exc:
                lines.append("Référence incompatible : " + str(exc))
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", "\n".join(lines))
        self.output.configure(state="disabled")
        self.status.configure(text="Terminé · matrice reproductible.")

    def set_baseline(self):
        if self.current is None:
            self.owner.dialogs.showerror("Balance Matrix", "Exécuter la matrice d'abord.")
            return
        self.baseline = self.current
        self._render()

    def load_baseline(self):
        from tkinter import filedialog
        import json
        path = filedialog.askopenfilename(parent=self.tab,
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as stream:
                report = json.load(stream)
            if report.get("kind") != "balance_matrix" or report.get("schema") != 1:
                raise RuleError("Référence Balance Matrix invalide.")
            self.baseline = report
            if self.current:
                self._render()
        except (OSError, ValueError, TypeError, AttributeError, RuleError) as exc:
            self.owner.dialogs.showerror("Balance Matrix", str(exc))

    def export(self):
        from tkinter import filedialog
        if self.current is None:
            self.owner.dialogs.showerror("Balance Matrix", "Aucun résultat à exporter.")
            return
        path = filedialog.asksaveasfilename(parent=self.tab,
                                            defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            try:
                save_matrix(path, self.current)
            except (OSError, RuleError) as exc:
                self.owner.dialogs.showerror("Balance Matrix", str(exc))

    def inspect_mission(self):
        if not self.rows.selection():
            return
        case_id = self.rows.selection()[0]
        match = next((row for row in self.current["cases"]
                      if row["id"] == case_id), None) if self.current else None
        if match is None:
            return
        self.owner.battle_lab.mission.set(match["mission"])
        self.notebook.select(self.owner.battle_lab.tab)
        # The Battle Lab runs the authored mission. It does not pretend the
        # variant has become part of the editable Content.
