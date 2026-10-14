"""3.8.4 Playtest Lab — local opt-in human reports, no game mechanics.

Import-only Studio analysis. Human minutes are measured independently from
headless Battle Lab CT ticks; never convert or fuse their distributions.
"""
from __future__ import annotations

import json

from .playtest_telemetry import analyze_playtests, validate_report
from .model import RuleError


class PlaytestStudio:
    def __init__(self, owner, notebook):
        self.owner, self.notebook = owner, notebook
        self.tk, self.ttk = owner.tk, owner.ttk
        self.report = None
        self.ai_report = None
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

        self.summary = self.ttk.Label(self.tab, text="Aucun rapport chargé.",
                                      wraplength=920, justify="left")
        self.summary.pack(anchor="w", pady=7)
        columns = ("mission", "outcome", "duration", "commands", "ct", "hold")
        self.rows = self.ttk.Treeview(
            self.tab, columns=columns, show="headings", height=9)
        for name, title, width in zip(
                columns,
                ("Mission", "Résultat", "Durée réelle (min)", "Commandes",
                 "CT fin", "Progression objectif"),
                (170, 110, 160, 115, 110, 195)):
            self.rows.heading(name, text=title)
            self.rows.column(name, width=width, anchor="center")
        # Data views start hidden. Empty report state must not consume most
        # of the editor with blank tables and a dark, empty chart.
        self.rows.bind("<<TreeviewSelect>>", self.select)
        self.canvas = self.tk.Canvas(
            self.tab, height=170, background="#252b33",
            highlightthickness=0)
        self.detail = self.tk.Text(self.tab, height=9, state="disabled",
                                    wrap="word")
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
            self.rows.pack(fill="x", pady=(6, 7), before=self.status)
            self.canvas.pack(fill="both", expand=True, before=self.status)
            self.detail.pack(fill="both", expand=True, pady=5,
                             before=self.status)
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
        self.canvas.delete("all")
        self.canvas.create_text(14, 16, anchor="w", fill="#eff2f5",
                                text="Durée réelle par session (minutes, y compris l'inactivité)")
        maximum = max((row["duration_seconds"] for _, row in chosen), default=0)
        span = max(1, maximum)
        width = max(500, self.canvas.winfo_width())
        for n, (_, row) in enumerate(chosen[:8]):
            y = 36 + n * 17
            length = max(0, width - 185) * row["duration_seconds"] / span
            color = ("#56a891" if row["outcome"] == "victory" else
                     "#ce7479" if row["outcome"] == "defeat" else "#d3a967")
            self.canvas.create_rectangle(130, y, 130 + length, y + 11,
                                         fill=color, outline="")
            self.canvas.create_text(
                12, y + 6, anchor="w", fill="#eff2f5",
                text=row["mission"][:15] + " · " + row["outcome"][:8])
            self.canvas.create_text(
                139 + length, y + 6, anchor="w", fill="#eff2f5",
                text="{:.1f}m".format(row["duration_seconds"] / 60))
        self.status.configure(
            text="{} sessions · collecte volontaire et export local · "
                 "données non modifiées".format(len(chosen)))

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
