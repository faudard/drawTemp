"""3.8.4 Playtest Lab — local opt-in human reports, no game mechanics.

Import-only Studio analysis. Human minutes are measured independently from
headless Battle Lab CT ticks; never convert or fuse their distributions.
"""
from __future__ import annotations

import json

from .encounter_balance6 import human_variant_breakdown
from .playtest_telemetry import analyze_playtests, validate_report
from .model import RuleError


class PlaytestStudio:
    def __init__(self, owner, notebook):
        self.owner, self.notebook = owner, notebook
        self.tk, self.ttk = owner.tk, owner.ttk
        self.report = None
        self.ai_report = None
        self.chart_background = '#E8EEF7'
        self.chart_foreground = '#152338'
        self.chart_success = '#176448'
        self.chart_failure = '#A62439'
        self.chart_other = '#905514'
        self.annotations = []
        self.tab = self.ttk.Frame(notebook, padding=10)
        notebook.add(self.tab, text="Playtest Lab")

        self.ttk.Label(self.tab, text="Human Playtest Lab · 3.8.4",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.ttk.Label(
            self.tab, text="Import local volontaire · durée humaine réelle · "
            "choix du joueur · abandons · objectifs. "
            "Les ticks CT automatisés ne sont pas des minutes humaines.",
            wraplength=900).pack(anchor="w", pady=(3, 8))
        actions = self.ttk.Frame(self.tab)
        actions.pack(fill="x")
        self.ttk.Button(
            actions, text="Importer playtests JSON",
            command=self.load).pack(side="left", padx=3)
        self.ttk.Button(
            actions, text="Importer référence Battle Lab",
            command=self.load_ai).pack(side="left", padx=3)
        self.mission = self.tk.StringVar(value="Toutes missions")
        self.mission_box = self.ttk.Combobox(
            actions, textvariable=self.mission, state="readonly", width=22)
        self.mission_box.pack(side="right", padx=3)
        self.ttk.Label(actions, text="Mission :").pack(side="right")
        self.mission_box.bind("<<ComboboxSelected>>", lambda _e: self.render())
        tuning = self.ttk.Frame(self.tab)
        tuning.pack(fill="x", pady=3)
        self.variant_name = self.tk.StringVar(value="authored")
        self.confusion_tag = self.tk.StringVar(value="aucune")
        self.exit_reason = self.tk.StringVar(value="unknown")
        self.ttk.Label(tuning, text="Variante").pack(side="left", padx=2)
        self.ttk.Entry(tuning, textvariable=self.variant_name,
                       width=18).pack(side="left", padx=3)
        self.ttk.Label(tuning, text="Incompréhension").pack(side="left", padx=2)
        self.ttk.Combobox(
            tuning, textvariable=self.confusion_tag, state="readonly",
            values=("aucune", "objective", "positioning", "controls",
                    "resources", "tutorial", "other"), width=15).pack(
                    side="left", padx=3)
        self.ttk.Label(tuning, text="Abandon").pack(side="left", padx=2)
        self.ttk.Combobox(
            tuning, textvariable=self.exit_reason, state="readonly",
            values=("unknown", "difficulty", "unclear_objective",
                    "technical", "voluntary"), width=16).pack(
                    side="left", padx=3)
        self.ttk.Button(tuning, text="Annoter session",
                        command=self.annotate).pack(side="left", padx=3)
        self.ttk.Button(tuning, text="Exporter annotations",
                        command=self.export_annotations).pack(side="left", padx=3)
        self.ttk.Button(tuning, text="Importer annotations",
                        command=self.import_annotations).pack(side="left", padx=3)

        self.summary = self.ttk.Label(self.tab, text="Aucun rapport chargé.",
                                      wraplength=920, justify="left")
        self.summary.pack(anchor="w", pady=7)
        # The report uses a two-column analysis workbench rather than
        # stacking three full-width widgets down the window.
        self.report_panels = self.ttk.Panedwindow(self.tab, orient="horizontal")
        sessions = self.ttk.LabelFrame(self.report_panels, text="Sessions")
        chart = self.ttk.LabelFrame(self.report_panels, text="Durées réelles")
        self.report_panels.add(sessions, weight=3)
        self.report_panels.add(chart, weight=2)
        columns = ("mission", "outcome", "duration", "commands", "ct", "hold")
        self.rows = self.ttk.Treeview(
            sessions, columns=columns, show="headings", height=9)
        for name, title, width in zip(
                columns,
                ("Mission", "Résultat", "Durée réelle (min)", "Commandes",
                 "CT fin", "Progression objectif"),
                (135, 90, 145, 100, 80, 150)):
            self.rows.heading(name, text=title)
            self.rows.column(name, width=width, anchor="center",
                             stretch=True)
        table_scroll = self.ttk.Scrollbar(
            sessions, orient="vertical", command=self.rows.yview)
        self.rows.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side="right", fill="y")
        self.rows.pack(side="left", fill="both", expand=True,
                       padx=(6, 0), pady=6)
        self.rows.bind("<<TreeviewSelect>>", self.select)
        self.canvas = self.tk.Canvas(
            chart, height=220, background=self.chart_background,
            highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self._chart_sessions = ()
        self.canvas.bind("<Configure>", self.draw_chart)
        self.details_panel = self.ttk.LabelFrame(
            self.tab, text="Détails de la session sélectionnée")
        self.detail = self.tk.Text(
            self.details_panel, height=7, state="disabled", wrap="word")
        details_scroll = self.ttk.Scrollbar(
            self.details_panel, orient="vertical", command=self.detail.yview)
        self.detail.configure(yscrollcommand=details_scroll.set)
        details_scroll.pack(side="right", fill="y")
        self.detail.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.empty_state = self.ttk.Frame(self.tab, padding=24)
        self.empty_state.pack(fill="both", expand=True)
        self.ttk.Label(
            self.empty_state, text="Aucune session de playtest importée",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(pady=(20, 8))
        self.ttk.Label(
            self.empty_state,
            text="Lancez une partie avec la télémétrie volontaire activée, "
                 "exportez le rapport JSON, puis importez-le ici pour "
                 "comparer les sessions et inspecter les décisions.",
            wraplength=580, justify="center",
        ).pack(pady=(0, 14))
        self.ttk.Button(
            self.empty_state, text="Importer un premier rapport…",
            command=self.load,
        ).pack()
        self.status = self.ttk.Label(
            self.tab, text="Import manuel uniquement · aucun envoi.")
        self.status.pack(anchor="w")

    def load(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.tab, title="Importer les données playtest",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                report = validate_report(json.load(fh))
            self.set_report(report)
        except (OSError, ValueError, TypeError, KeyError, RuleError) as exc:
            self.owner.dialogs.showerror("Playtest Lab", str(exc))

    def load_ai(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.tab, title="Rapport de référence IA",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("kind") != "battle_lab" or data.get("schema") != 1:
                raise RuleError("Référence Battle Lab 3.8 invalide")
            self.ai_report = data
            self.render()
        except (OSError, ValueError, TypeError, KeyError, RuleError) as exc:
            self.owner.dialogs.showerror("Playtest Lab", str(exc))

    def set_report(self, report):
        self.report = validate_report(report)
        if self.empty_state.winfo_manager():
            self.empty_state.pack_forget()
            self.report_panels.pack(fill="both", expand=True,
                                    pady=(6, 4), before=self.status)
            self.details_panel.pack(fill="both", expand=True,
                                    pady=(0, 6), before=self.status)
        self.annotations = []
        missions = sorted({row["mission"] for row in report["sessions"]})
        self.mission_box["values"] = ["Toutes missions", *missions]
        if self.mission.get() not in self.mission_box["values"]:
            self.mission.set("Toutes missions")
        self.render()

    def render(self):
        if self.report is None:
            return
        mission = None if self.mission.get() == "Toutes missions" else self.mission.get()
        # The reference is only compared for matching authored mission IDs.
        ai = self.ai_report if (
            self.ai_report is not None and mission is not None and
            self.ai_report.get("mission") == mission) else None
        summary = analyze_playtests(self.report, mission=mission,
                                    ai_report=ai)
        label = ("Mission : {} · observations : {} · complètes : {} · abandons : {} · "
                 "durée humaine p50/p95 : {} / {} min").format(
            mission or "Toutes missions",
            summary["sessions"], summary["complete_observations"],
            ("{:.1%}".format(summary["abandonment_rate"])
             if summary["abandonment_rate"] is not None else "n.d."),
            summary["human_duration_minutes_p50"],
            summary["human_duration_minutes_p95"])
        if ai:
            label += ("\nIA séparée : victoire {:.1%}, CT p95 {}, "
                      "commandes p95 {}. Aucune conversion CT→minutes.").format(
                ai["victory_rate"], ai["ticks_p95"], ai["commands_p95"])
        if ai and summary["ai_reference"]["matching_content"] is False:
            label += "\nAttention : la référence IA a un contenu authored différent."
        label += ("\nActions joueur : {} · actions IA : {}").format(
            summary["player_commands"], summary["enemy_commands"])
        if mission is not None:
            analysis = human_variant_breakdown(
                self.report, self.annotations, min_complete=5)
            for row in analysis["groups"]:
                if row["mission"] != mission:
                    continue
                measured = row["duration_target_15_30_minutes"]
                evidence = ("non vérifiée" if measured is None else
                            "dans la cible" if measured else "hors cible")
                label += ("\nR6.11 · {} : {} parties complètes, {} défaites ; "
                          "incompréhensions {} ; durée 15–30 min : {}").format(
                    row["variant"], row["summary"]["complete_observations"],
                    row["failures"], row["confusion"], evidence)
        self.summary.configure(text=label)
        self.rows.delete(*self.rows.get_children())
        chosen = [(i, row) for i, row in enumerate(self.report["sessions"])
                  if mission is None or row["mission"] == mission]
        for i, row in chosen:
            self.rows.insert("", "end", iid=str(i), values=(
                row["mission"], row["outcome"],
                "{:.2f}".format(row["duration_seconds"] / 60),
                sum(row["command_kinds"].values()), row["ct_end"],
                str(row["objective_hold_ticks"]) +
                (" · goal" if row["goal_occupied"] else "")))
        self._chart_sessions = chosen
        self.draw_chart()
        self.status.configure(
            text="{} sessions · collecte volontaire et export local · "
                 "données non modifiées".format(len(chosen)))

    def set_appearance(self, palette):
        """Update chart tokens without changing telemetry data or selection."""
        self.chart_background = palette.elevated
        self.chart_foreground = palette.text
        self.chart_success = palette.success
        self.chart_failure = palette.danger
        self.chart_other = palette.warning
        self.canvas.configure(background=self.chart_background)
        self.draw_chart()

    def draw_chart(self, _event=None):
        """Only redraw the chart on resize; preserve the Treeview selection."""
        if self.report is None:
            return
        self.canvas.delete("all")
        self.canvas.create_text(14, 16, anchor="w", fill=self.chart_foreground,
                                text="Durée réelle par session (minutes, y compris l'inactivité)")
        maximum = max((row["duration_seconds"] for _, row in self._chart_sessions), default=0)
        span = max(1, maximum)
        width = max(250, self.canvas.winfo_width())
        for n, (_, row) in enumerate(self._chart_sessions[:8]):
            y = 36 + n * 17
            length = max(0, width - 185) * row["duration_seconds"] / span
            color = (self.chart_success if row["outcome"] == "victory" else
                     self.chart_failure if row["outcome"] == "defeat"
                     else self.chart_other)
            self.canvas.create_rectangle(130, y, 130 + length, y + 11,
                                         fill=color, outline="")
            self.canvas.create_text(
                12, y + 6, anchor="w", fill=self.chart_foreground,
                text=row["mission"][:15] + " · " + row["outcome"][:8])
            self.canvas.create_text(
                139 + length, y + 6, anchor="w", fill=self.chart_foreground,
                text="{:.1f}m".format(row["duration_seconds"] / 60))

    def annotate(self):
        if self.report is None or not self.rows.selection():
            self.owner.dialogs.showerror(
                "Playtest Lab", "Sélectionner une session à annoter.")
            return
        index = int(self.rows.selection()[0])
        item = {
            "index": index, "variant": self.variant_name.get().strip(),
            "confusion": ([] if self.confusion_tag.get() == "aucune"
                          else [self.confusion_tag.get()]),
            "exit_reason": self.exit_reason.get(),
        }
        updated = [a for a in self.annotations if a["index"] != index] + [item]
        try:
            human_variant_breakdown(self.report, updated)
        except (RuleError, ValueError, TypeError) as exc:
            self.owner.dialogs.showerror("Playtest Lab", str(exc))
            return
        self.annotations = sorted(updated, key=lambda a: a["index"])
        self.render()

    def export_annotations(self):
        from tkinter import filedialog
        if self.report is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.tab, defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if path:
            try:
                payload = {
                    "kind": "r6_playtest_annotations", "schema": 1,
                    "session_count": len(self.report["sessions"]),
                    "content_sha256": self.report.get("content_sha256"),
                    "annotations": self.annotations}
                with open(path, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, indent=2, ensure_ascii=False,
                              sort_keys=True)
            except OSError as exc:
                self.owner.dialogs.showerror("Playtest Lab", str(exc))

    def import_annotations(self):
        from tkinter import filedialog
        if self.report is None:
            return
        path = filedialog.askopenfilename(
            parent=self.tab, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
            if (type(data) is not dict or
                    data.get("kind") != "r6_playtest_annotations" or
                    data.get("schema") != 1 or
                    data.get("session_count") != len(self.report["sessions"]) or
                    data.get("content_sha256") != self.report.get("content_sha256")):
                raise RuleError("Annotations incompatibles avec ces sessions.")
            human_variant_breakdown(self.report, data["annotations"])
            self.annotations = data["annotations"]
            self.render()
        except (OSError, ValueError, TypeError, KeyError, RuleError) as exc:
            self.owner.dialogs.showerror("Playtest Lab", str(exc))

    def select(self, _event=None):
        selected = self.rows.selection()
        if not selected or self.report is None:
            return
        row = self.report["sessions"][int(selected[0])]
        lines = [
            "{} · {} · {:.1f} min".format(
                row["mission"], row["outcome"], row["duration_seconds"] / 60),
            "Commandes : " + json.dumps(row["command_kinds"],
                                       sort_keys=True, ensure_ascii=False),
            "Dégâts observés : {} · soins observés : {}".format(
                row["damage_observed"], row["healing_observed"]),
            "Objectif : {} · maintien {} CT · atteint ? {}".format(
                row["objective"], row["objective_hold_ticks"],
                row["goal_occupied"]),
            "Capture partielle : {} · événements tronqués : {}".format(
                row["partial_capture"], row["truncated_events"]),
            "Événements acceptés :",
        ]
        lines.extend("  {:.1f}s · {} · {} · {} CT".format(
            evt["seconds"], evt["event"],
            evt["command"].get("kind", ""), evt["tick"]) for evt in row["events"])
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("end", "\n".join(lines))
        self.detail.configure(state="disabled")
