"""Game Studio Battle Lab tab (3.8); the simulation remains headless.

Worker threads never access Tk or mutable Studio documents. A snapshot is
validated on the UI thread, then measured with the canonical Battle pipeline.
"""
from __future__ import annotations

import json
from queue import Empty, Queue
from threading import Thread

from .battle_lab import compare_reports, run_lab, save_report
from .model import RuleError
from .tactical_rpg3 import authored_rules_for_document


class BattleLabStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.current = None
        self.baseline = None
        self.comparison = None
        self.trace = None
        self._run_snapshot = None
        self.busy = False
        self.mailbox = Queue()

        frame = self.ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Battle Lab")
        self.tab = frame
        self.ttk.Label(frame, text="Battle Lab · équilibrage 3.8",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.ttk.Label(
            frame, text="IA et règles réelles, seeds appariées, replay vérifié. "
            "Ticks CT et commandes ne mesurent pas les minutes de jeu.",
            wraplength=850).pack(anchor="w", pady=(3, 10))
        options = self.ttk.Frame(frame)
        options.pack(fill="x")
        self.mission = self.tk.StringVar(value=owner.mission())
        self.seeds = self.tk.StringVar(value="1,7,42,99")
        self.limit = self.tk.StringVar(value="500")
        for col, (label, var, width) in enumerate((
                ("Mission", self.mission, 20),
                ("Seeds (séparées par virgule)", self.seeds, 20),
                ("Commandes max / seed", self.limit, 10))):
            self.ttk.Label(options, text=label).grid(row=0, column=col, sticky="w", padx=5)
            if col == 0:
                self.mission_box = self.ttk.Combobox(options, textvariable=var,
                                                     state="readonly", width=width)
                widget = self.mission_box
            else:
                widget = self.ttk.Entry(options, textvariable=var, width=width)
            widget.grid(row=1, column=col, sticky="ew", padx=5, pady=4)
        options.columnconfigure(0, weight=2)
        options.columnconfigure(1, weight=1)

        actions = self.ttk.Frame(frame)
        actions.pack(fill="x", pady=6)
        self.run_button = self.ttk.Button(actions, text="Simuler",
                                          command=self.start)
        self.run_button.pack(side="left", padx=4)
        self.ttk.Button(actions, text="Charger référence JSON",
                        command=self.load_baseline).pack(side="left", padx=4)
        self.ttk.Button(actions, text="Référence = résultat courant",
                        command=self.use_as_baseline).pack(side="left", padx=4)
        self.ttk.Button(actions, text="Exporter JSON",
                        command=self.export).pack(side="left", padx=4)
        self.ttk.Button(actions, text="Afficher sur la carte",
                        command=self.open_map).pack(side="left", padx=4)
        self.diagnose_button = self.ttk.Button(
            actions, text="Diagnostiquer seed", command=self.diagnose_selected)
        self.diagnose_button.pack(side="left", padx=4)
        self.replay_button = self.ttk.Button(
            actions, text="Rejouer la trace", command=self.replay_selected,
            state="disabled")
        self.replay_button.pack(side="left", padx=4)
        self.status = self.ttk.Label(frame, text="Prêt · aucune simulation en cours.")
        self.status.pack(anchor="w", pady=4)
        columns = ("seed", "issue", "ticks", "commands", "ct", "stall")
        self.rows = self.ttk.Treeview(frame, columns=columns,
                                      show="headings", height=8)
        headings = ("Seed", "Issue", "Ticks CT", "Commandes", "Activations", "Blocage ?")
        widths = (65, 110, 90, 100, 100, 100)
        for key, title, width in zip(columns, headings, widths):
            self.rows.heading(key, text=title)
            self.rows.column(key, width=width, anchor="center")
        self.rows.pack(fill="x", pady=(8, 4))
        self.rows.bind("<<TreeviewSelect>>", self._select_seed)
        self.output = self.tk.Text(frame, height=15, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=True)

    def refresh(self):
        missions = [row["id"] for row in self.owner.doc().data["missions"]]
        self.mission_box["values"] = missions
        if self.mission.get() not in missions:
            self.mission.set(self.owner.mission())

    def _write(self, message):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", message)
        self.output.configure(state="disabled")

    def start(self):
        if self.busy:
            return
        try:
            values = [int(value.strip()) for value in self.seeds.get().split(",")]
            limit = int(self.limit.get())
            content = self.owner._content()
            mission = self.mission.get()
            if mission not in content.missions:
                raise RuleError("Sélectionner une mission existante")
            if not (1 <= len(values) <= 1000 and len(set(values)) == len(values)
                    and all(0 <= s < 2**32 for s in values)):
                raise RuleError("Seeds uniques 0..2^32-1, maximum 1000")
            if not 1 <= limit <= 100000:
                raise RuleError("Limite de commandes : 1..100000")
            rules = authored_rules_for_document(self.owner.doc().data)
        except (ValueError, RuleError, TypeError) as exc:
            self.owner.dialogs.showerror("Battle Lab", str(exc))
            return
        self.busy = True
        self._run_snapshot = (content, rules)
        self.trace = None
        self.replay_button.configure(state="disabled")
        self.run_button.configure(state="disabled")
        self.diagnose_button.configure(state="disabled")
        self.status.configure(text="Simulation en cours sur une copie du contenu…")
        # Capture all input values before entering the worker, with no Tk calls
        # from the thread (including document access and error dialogs).
        def worker():
            try:
                result = run_lab(content, mission, seeds=values,
                                 max_commands=limit, rules=rules)
                self.mailbox.put(("ok", result))
            except Exception as exc:
                self.mailbox.put(("error", str(exc)))
        Thread(target=worker, daemon=True).start()
        self.tab.after(80, self._poll)

    def _poll(self):
        try:
            kind, value = self.mailbox.get_nowait()
        except Empty:
            if self.busy and self.tab.winfo_exists():
                self.tab.after(80, self._poll)
            return
        self.busy = False
        self.run_button.configure(state="normal")
        self.diagnose_button.configure(state="normal")
        if kind == "trace_error":
            self.status.configure(text="Diagnostic échoué")
            self.owner.dialogs.showerror("Battle Lab · diagnostic", value)
            return
        if kind == "trace":
            self.trace = value
            self.replay_button.configure(state="normal")
            self.status.configure(text="Trace vérifiée · {} décisions · {} constats".format(
                value["commands"], len(value["diagnostics"]["findings"])))
            self.replay_selected()
            return
        if kind == "error":
            self.status.configure(text="Simulation échouée")
            self.owner.dialogs.showerror("Battle Lab", value)
            return
        self.current = value
        self._render()

    def _render(self):
        report = self.current
        if report is None:
            return
        self.rows.delete(*self.rows.get_children())
        for sample in report["samples"]:
            self.rows.insert("", "end", values=(
                sample["seed"], sample["result"], sample["ticks"],
                sample["commands"], sample["activations_ct"],
                "oui" if sample["possible_stall"] else "non"))
        output = [
            "Mission : " + report["mission"],
            "Victoires : {:.1%} | Résultats : {}".format(
                report["victory_rate"], report["outcomes"]),
            "Ticks CT p50/p95/p99 : {}/{}/{}".format(
                report["ticks_p50"], report["ticks_p95"], report["ticks_p99"]),
            "Commandes p50/p95/p99 : {}/{}/{}".format(
                report["commands_p50"], report["commands_p95"], report["commands_p99"]),
            "Activations CT : {} | Blocages suspects : {}".format(
                report["activations_ct"], report["possible_stalls"]),
            "Dégâts : " + json.dumps(report["damage"], ensure_ascii=False),
            "Soins reçus : " + json.dumps(report["healing_received"], ensure_ascii=False),
            "Réactions : " + json.dumps(report["reactions"], ensure_ascii=False),
            "Survie par classe : " + json.dumps(
                report["class_survival"], ensure_ascii=False),
            "Décisions IA : " + json.dumps(report["class_decisions"], ensure_ascii=False),
            "Objectifs : " + json.dumps(
                {str(s["seed"]): s["objective"] for s in report["samples"]},
                ensure_ascii=False),
        ]
        if self.baseline is not None:
            try:
                self.comparison = compare_reports(self.baseline, report)
                comparison = self.comparison
                output.extend((
                    "",
                    "COMPARAISON : " + comparison["status"].upper(),
                    "Différences : " + json.dumps(comparison["deltas"],
                                                 ensure_ascii=False),
                    "Alertes : " + ("; ".join(comparison["issues"]) or "Aucune"),
                ))
            except (RuleError, KeyError, ValueError) as exc:
                self.comparison = None
                output.append("Référence incompatible : " + str(exc))
        self._write("\n".join(output))
        self.status.configure(text="Terminé, replays vérifiés."
                              + (" Gate : " + self.comparison["status"]
                                 if self.comparison else ""))

    def _select_seed(self, _event=None):
        self.replay_button.configure(state="disabled")

    def diagnose_selected(self):
        """Re-run one seed against the *same snapshot* as the original sweep."""
        if self.busy or self.current is None or self._run_snapshot is None:
            return
        selection = self.rows.selection()
        if not selection:
            self.owner.dialogs.showerror(
                "Battle Lab", "Sélectionner une seed dans le tableau.")
            return
        try:
            seed = int(self.rows.item(selection[0], "values")[0])
            max_commands = self.current["max_commands"]
            if max_commands > 5000:
                raise RuleError("Tracer une seed exige au plus 5000 commandes.")
            expected = next(sample for sample in self.current["samples"]
                            if sample["seed"] == seed)
        except (RuleError, KeyError, ValueError, StopIteration) as exc:
            self.owner.dialogs.showerror("Battle Lab", str(exc))
            return
        content, rules = self._run_snapshot
        self.busy = True
        self.trace = None
        self.run_button.configure(state="disabled")
        self.diagnose_button.configure(state="disabled")
        self.replay_button.configure(state="disabled")
        self.status.configure(text="Relecture détaillée de la seed {}…".format(seed))

        def worker():
            try:
                from .battle_diagnostics import trace_seed
                trace = trace_seed(content, self.current["mission"], seed=seed,
                                   max_commands=max_commands, rules=rules)
                if trace["digest"] != expected["digest"] or (
                        trace["result"] != expected["result"]):
                    raise RuleError("Le replay détaillé diverge du rapport initial.")
                self.mailbox.put(("trace", trace))
            except Exception as exc:
                self.mailbox.put(("trace_error", str(exc)))

        Thread(target=worker, daemon=True).start()
        self.tab.after(80, self._poll)

    def replay_selected(self):
        if self.trace is None:
            return
        from .studio_battle_replay import show_trace
        show_trace(self, self.trace)

    def load_baseline(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.tab, title="Référence Battle Lab",
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as stream:
                reference = json.load(stream)
            if reference.get("kind") != "battle_lab" or reference.get("schema") != 1:
                raise RuleError("Ce fichier n'est pas un rapport Battle Lab 3.8")
            self.baseline = reference
            if self.current:
                self._render()
            else:
                self.status.configure(text="Référence chargée : " + path)
        except (OSError, ValueError, AttributeError, RuleError) as exc:
            self.owner.dialogs.showerror("Battle Lab", str(exc))

    def use_as_baseline(self):
        if self.current is None:
            self.owner.dialogs.showerror("Battle Lab", "Exécuter une simulation d'abord.")
            return
        self.baseline = self.current
        self._render()

    def export(self):
        from tkinter import filedialog
        if self.current is None:
            self.owner.dialogs.showerror("Battle Lab", "Aucun rapport à exporter.")
            return
        path = filedialog.asksaveasfilename(parent=self.tab, title="Exporter Battle Lab",
                                            defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            save_report(path, self.current)
            self.status.configure(text="Rapport exporté : " + path)
        except OSError as exc:
            self.owner.dialogs.showerror("Battle Lab", str(exc))

    def open_map(self):
        mid = self.mission.get()
        self.owner.select_mission(mid)
        self.owner.workspace._show_tab("Carte et combat")
