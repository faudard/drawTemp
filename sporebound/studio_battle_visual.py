"""3.8.3 Visual Battle Lab — interactive Tk Canvas on canonical telemetry.

Charts are projections of versioned 3.8 JSON. Command-by-command replay is
only generated on demand via 3.8.1 trace_seed; no second engine or fake turns.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from .battle_visual import (METRICS, chart_model, notable_seeds,
                            timeline_model)
from .model import RuleError


OUTCOME_COLORS = {
    "victory": "#38a18a", "defeat": "#c56f74",
    "draw": "#cfac68", "limit": "#8c8fa3",
}
GRAPH_BG = "#272c34"
TEXT = "#e7e9eb"
GRID = "#626a75"
BLUE = "#74b4eb"
ORANGE = "#e0b06b"


class VisualBattleLabStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.notebook = notebook
        self.ttk, self.tk = owner.ttk, owner.tk
        self.report = None
        self.reference = None
        self.snapshot = None
        self.spec = None
        self.matrix = None
        self.view = None
        self.trace = None
        self.trace_view = None
        self.busy = False
        self.mailbox = Queue()
        self.frame = self.ttk.Frame(notebook, padding=8)
        self.tab = self.frame
        notebook.add(self.frame, text="Visual Battle Lab")
        self.ttk.Label(self.frame, text="Visual Battle Lab · 3.8.3",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.ttk.Label(
            self.frame, text="Graphiques réels · seeds appariées · survie par classe · "
            "chronologie CT · replay vérifié. CT ≠ durée humaine.",
            wraplength=980).pack(anchor="w", pady=(1, 5))
        toolbar = self.ttk.Frame(self.frame)
        toolbar.pack(fill="x", pady=4)
        self.ttk.Button(toolbar, text="Charger rapport JSON",
                        command=self.load_json).pack(side="left", padx=3)
        self.ttk.Label(toolbar, text="Scénario :").pack(side="left", padx=(12, 2))
        self.case = self.tk.StringVar()
        self.case_box = self.ttk.Combobox(
            toolbar, textvariable=self.case, state="readonly", width=26)
        self.case_box.pack(side="left", padx=3)
        self.case_box.bind("<<ComboboxSelected>>", self._choose_case)
        self.metric = self.tk.StringVar(value=METRICS[0])
        self.ttk.Label(toolbar, text="Mesure :").pack(side="left", padx=(12, 3))
        metric_box = self.ttk.Combobox(toolbar, textvariable=self.metric,
                                       values=METRICS, state="readonly", width=19)
        metric_box.pack(side="left", padx=3)
        metric_box.bind("<<ComboboxSelected>>", lambda _e: self._draw_metrics())
        self.trace_button = self.ttk.Button(
            toolbar, text="Tracer seed sélectionnée", command=self.trace_selected)
        self.trace_button.pack(side="right", padx=3)
        self.replay_button = self.ttk.Button(
            toolbar, text="Replay détaillé", command=self.open_replay,
            state="disabled")
        self.replay_button.pack(side="right", padx=3)

        overview = self.ttk.Frame(self.frame)
        overview.pack(fill="both", expand=False, pady=4)
        self.outcomes_canvas = self.tk.Canvas(
            overview, height=130, background=GRAPH_BG,
            highlightthickness=0)
        self.outcomes_canvas.pack(fill="x", expand=True, pady=2)
        self.duration_canvas = self.tk.Canvas(
            overview, height=160, background=GRAPH_BG,
            highlightthickness=0)
        self.duration_canvas.pack(fill="x", expand=True, pady=2)
        self.metrics_canvas = self.tk.Canvas(
            overview, height=170, background=GRAPH_BG,
            highlightthickness=0)
        self.metrics_canvas.pack(fill="x", expand=True, pady=2)

        lower = self.ttk.Frame(self.frame)
        lower.pack(fill="both", expand=True, pady=4)
        self.ttk.Label(lower, text="Seeds à examiner (sélection cliquable)").pack(
            anchor="w")
        columns = ("seed", "outcome", "ct", "commands", "delta", "alert")
        self.rows = self.ttk.Treeview(lower, columns=columns,
                                      show="headings", height=5)
        for key, title, width in zip(columns,
                                     ("Seed", "Issue", "CT", "Commandes",
                                      "Δ commandes", "Pourquoi l'examiner"),
                                     (65, 100, 80, 90, 100, 390)):
            self.rows.heading(key, text=title)
            self.rows.column(key, width=width)
        self.rows.pack(fill="x", pady=3)
        self.rows.bind("<<TreeviewSelect>>", self._seed_selected)
        self.ttk.Label(lower, text="Chronologie CT — événements réels (sur demande)").pack(
            anchor="w", pady=(4, 2))
        self.timeline_canvas = self.tk.Canvas(
            lower, height=135, background=GRAPH_BG,
            highlightthickness=0)
        self.timeline_canvas.pack(fill="x")
        self.details = self.ttk.Label(lower, text="Charger un rapport ou passer "
                                             "par Battle Lab / Balance Matrix.",
                                      wraplength=1000)
        self.details.pack(anchor="w", pady=3)
        self.status = self.ttk.Label(
            lower, text="Prêt · aucune simulation modifiée.")
        self.status.pack(anchor="w", pady=2)

    def show_report(self, report, *, reference=None, snapshot=None,
                    spec=None):
        """Open an existing real sweep; optional snapshot enables exact trace.

        snapshot is (Content, RuleSet), captured when the sweep ran. Never
        derive it from the current editor document after later modifications.
        """
        view = chart_model(report, reference=reference)
        self.report, self.reference, self.snapshot, self.spec = (
            report, reference, snapshot, spec)
        self.matrix = None
        self.case_box["values"] = ()
        self.case.set("")
        self.view = view
        self._render()
        self.notebook.select(self.tab)

    def show_matrix(self, matrix, case_id, *, snapshot=None):
        """Show an authored case and its same-mission baseline only."""
        if matrix.get("kind") != "balance_matrix":
            raise RuleError("Ce document n'est pas une Balance Matrix.")
        rows = {row["id"]: row for row in matrix["cases"]}
        if case_id not in rows:
            raise RuleError("Scénario de matrice absent.")
        target = rows[case_id]
        baseline = rows[target["reference"]]
        spec = target["spec"] if target["id"] != target["reference"] else None
        self.report = target["report"]
        self.reference = baseline["report"] if spec is not None else None
        self.snapshot, self.spec = snapshot, spec
        self.view = chart_model(self.report, reference=self.reference)
        self.matrix = matrix
        self.case_box["values"] = [row["id"] for row in matrix["cases"]]
        self.case.set(case_id)
        self._render()
        self.notebook.select(self.tab)

    def _choose_case(self, _event=None):
        if self.matrix is not None:
            self.show_matrix(self.matrix, self.case.get(), snapshot=self.snapshot)

    def load_json(self):
        from tkinter import filedialog
        import json
        filename = filedialog.askopenfilename(
            parent=self.tab, title="Rapport Battle Lab / Matrix",
            filetypes=[("JSON", "*.json")])
        if not filename:
            return
        try:
            with open(filename, encoding="utf-8") as fh:
                report = json.load(fh)
            if report.get("kind") == "balance_matrix":
                if not report.get("cases"):
                    raise RuleError("Matrice vide.")
                self.show_matrix(report, report["cases"][0]["id"])
            else:
                self.show_report(report)
            self.status.configure(text="Rapport JSON chargé · graphiques disponibles. "
                                       "Replay désactivé sans snapshot identique.")
        except (OSError, ValueError, TypeError, KeyError, RuleError) as exc:
            self.owner.dialogs.showerror("Visual Battle Lab", str(exc))

    def _size(self, canvas):
        return max(560, canvas.winfo_width())

    def _text(self, canvas, x, y, text, *, anchor="w", color=TEXT, font=None):
        kw = {"anchor": anchor, "fill": color}
        if font is not None:
            kw["font"] = font
        return canvas.create_text(x, y, text=text, **kw)

    def _render(self):
        self.trace = self.trace_view = None
        self.replay_button.configure(state="disabled")
        view = self.view
        if view is None:
            return
        self.rows.delete(*self.rows.get_children())
        candidates = {row["seed"]: ", ".join(row["issues"])
                      for row in notable_seeds(self.report,
                                               reference=self.reference)}
        for row in view["samples"]:
            self.rows.insert("", "end", iid=str(row["seed"]), values=(
                row["seed"], row["outcome"], row["ct"], row["commands"],
                "{:+d}".format(row["commands_delta"])
                if row["commands_delta"] is not None else "—",
                candidates.get(row["seed"], "")))
        interesting = notable_seeds(self.report, reference=self.reference)
        seed = interesting[0]["seed"] if interesting else view["seeds"][0]
        self.rows.selection_set(str(seed))
        self.rows.see(str(seed))
        self._draw_outcomes()
        self._draw_durations()
        self._draw_metrics()
        self.timeline_canvas.delete("all")
        self._text(self.timeline_canvas, 12, 48,
                   "Sélectionner une seed puis « Tracer » pour afficher la "
                   "chronologie CT vérifiée.")
        self.status.configure(text="Mission {} · {} seeds · source canonique".format(
            view["mission"], view["runs"]))
        self._seed_selected()

    def _draw_outcomes(self):
        c, view = self.outcomes_canvas, self.view
        c.delete("all")
        width = self._size(c)
        self._text(c, 12, 16, "ISSUES / VICTOIRES — {} ({})".format(
            view["mission"], view["runs"]))
        count = max(1, view["runs"])
        for y, is_ref in ((40, False), (85, True)):
            if is_ref and not view["paired"]:
                continue
            self._text(c, 12, y + 10, "Référence" if is_ref else "Courant")
            start = 102
            for row in view["outcomes"]:
                value = row["reference_count"] if is_ref else row["count"]
                length = (width - 240) * value / count
                if length > 0:
                    c.create_rectangle(start, y, start + length,
                                       y + 22, fill=OUTCOME_COLORS[row["name"]],
                                       outline="")
                    if length > 30:
                        self._text(c, start + length / 2, y + 11, str(value),
                                   anchor="center")
                start += length
            win = (view["reference_win_rate"] if is_ref else view["win_rate"])
            self._text(c, width - 10, y + 11, "{:.1%} vict.".format(win),
                       anchor="e")
        self._text(c, 12, 122,
                   "Vert=victoire  Rouge=défaite  Orange=nul  Gris=limite",
                   color="#c0c5cb")

    def _select_seed(self, seed):
        if str(seed) not in self.rows.get_children():
            return
        self.rows.selection_set(str(seed))
        self.rows.see(str(seed))
        self._seed_selected()

    def _draw_durations(self):
        c, view = self.duration_canvas, self.view
        c.delete("all")
        width = self._size(c)
        self._text(c, 12, 16, "DURÉES PAR SEED — CT (points) / commandes (barres)")
        samples = view["samples"]
        top, bottom = 38, 127
        highest = max(1, max(max(row["ct"], row["commands"]) for row in samples))
        c.create_line(40, bottom, width - 28, bottom, fill=GRID)
        c.create_line(40, top, 40, bottom, fill=GRID)
        self._text(c, 40, 30, str(highest))
        count = len(samples)
        bandwidth = (width - 82) / max(1, count)
        for i, row in enumerate(samples):
            x = 43 + (i + .5) * bandwidth
            y_ct = bottom - row["ct"] / highest * (bottom - top)
            y_commands = bottom - row["commands"] / highest * (bottom - top)
            barw = min(13, max(2, bandwidth * .35))
            item = c.create_rectangle(x - barw / 2, y_commands,
                                      x + barw / 2, bottom,
                                      fill=ORANGE, outline="")
            circle = c.create_oval(x - 4, y_ct - 4, x + 4, y_ct + 4,
                                   fill=BLUE, outline="")
            for cid in (item, circle):
                c.tag_bind(cid, "<Button-1>",
                           lambda _event, seed=row["seed"]:
                           self._select_seed(seed))
            if count <= 20:
                self._text(c, x, 143, str(row["seed"]),
                           anchor="center", color="#b6bec9")
        self._text(c, width - 10, 143, "Seeds →", anchor="e")

    def _draw_metrics(self):
        if self.view is None:
            return
        c = self.metrics_canvas
        c.delete("all")
        width = self._size(c)
        key = self.metric.get()
        data = sorted(self.view["metrics"][key],
                      key=lambda row: (-row["value"], row["name"]))[:6]
        self._text(c, 12, 16,
                   "{} — {} catégories {}".format(key.upper(), len(data),
                      "(taux)" if key == "class_survival" else "(total sur seeds)"))
        if not data:
            self._text(c, 12, 74, "Aucune donnée mesurée pour cette catégorie.")
            return
        highest = max(1, max(max(row["value"],
                                 row["reference"] or 0) for row in data))
        bar_start, maxwidth = 220, max(80, width - 370)
        for i, row in enumerate(data):
            y = 38 + 21 * i
            self._text(c, 12, y + 5, row["name"][:28])
            reference = row["reference"]
            if reference is not None:
                c.create_rectangle(bar_start, y, bar_start + maxwidth *
                                   reference / highest, y + 12,
                                   outline=ORANGE, width=1)
            c.create_rectangle(bar_start, y + 3,
                               bar_start + maxwidth * row["value"] / highest,
                               y + 9, fill=BLUE, outline="")
            fmt = "{:.1%}" if key == "class_survival" else "{}"
            self._text(c, bar_start + maxwidth + 7, y + 6,
                       fmt.format(row["value"]))
        if self.view["paired"]:
            self._text(c, width - 10, 16, "Bleu: actuel · contour: référence",
                       anchor="e", color=ORANGE)

    def _seed_selected(self, _event=None):
        selection = self.rows.selection()
        if not selection or self.view is None:
            return
        seed = int(selection[0])
        row = next(row for row in self.view["samples"] if row["seed"] == seed)
        text = "Seed {} · {} · {} ticks CT · {} commandes".format(
            seed, row["outcome"], row["ct"], row["commands"])
        if row["commands_delta"] is not None:
            text += " · Δ commandes {:+d}".format(row["commands_delta"])
        if row["possible_stall"]:
            text += " · stagnation possible (heuristique)"
        self.details.configure(text=text)
        if self.trace is not None and self.trace["seed"] != seed:
            self.trace = self.trace_view = None
            self.replay_button.configure(state="disabled")
            self.timeline_canvas.delete("all")

    def trace_selected(self):
        if self.busy or self.report is None:
            return
        selection = self.rows.selection()
        if not selection:
            return
        if self.snapshot is None:
            self.owner.dialogs.showerror(
                "Visual Battle Lab",
                "Rapport chargé sans snapshot d'exécution. "
                "Rejouer depuis Battle Lab ou Balance Matrix pour garantir "
                "le même contenu et les mêmes règles.")
            return
        seed = int(selection[0])
        if self.report["max_commands"] > 5000:
            self.owner.dialogs.showerror(
                "Visual Battle Lab", "La trace détaillée est limitée à 5000 commandes.")
            return
        report = self.report
        content, rules = self.snapshot
        spec = self.spec
        self.busy = True
        self.trace_button.configure(state="disabled")
        self.status.configure(text="Rejoue et vérifie la seed {}…".format(seed))

        def worker():
            try:
                from .battle_diagnostics import trace_seed
                from .balance_matrix import scenario_content
                from .battle_lab import _fingerprint
                source = (scenario_content(content, spec, rules=rules)
                          if spec is not None else content)
                if _fingerprint(source.to_dict()) != report["content_sha256"]:
                    raise RuleError("Snapshot de mission différent de la simulation.")
                trace = trace_seed(source, report["mission"], seed=seed,
                                   max_commands=report["max_commands"], rules=rules)
                sample = next(row for row in report["samples"]
                              if row["seed"] == seed)
                if (trace["digest"] != sample["digest"]
                        or trace["commands"] != sample["commands"]
                        or trace["result"] != sample["result"]):
                    raise RuleError("Replay visuel différent de la seed mesurée.")
                self.mailbox.put(("ok", trace))
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
        self.trace_button.configure(state="normal")
        if kind == "error":
            self.status.configure(text="Échec de traçage de la seed")
            self.owner.dialogs.showerror("Visual Battle Lab", value)
            return
        self.trace = value
        self.trace_view = timeline_model(value)
        self._draw_timeline()
        self.replay_button.configure(state="normal")
        self.status.configure(text="Seed {} · replay vérifié · {} événements visuels".format(
            value["seed"], len(self.trace_view["points"])))

    def _draw_timeline(self):
        canvas = self.timeline_canvas
        canvas.delete("all")
        timeline = self.trace_view
        if timeline is None:
            return
        width = self._size(canvas)
        left, right, top, bottom = 36, width - 22, 30, 101
        self._text(canvas, 12, 14, "SEED {} · {} COMMANDES · CT {}".format(
            timeline["seed"], timeline["commands"], timeline["final_tick"]))
        canvas.create_line(left, bottom, right, bottom, fill=GRID)
        points = timeline["points"]
        if not points:
            self._text(canvas, 12, 69, "Aucune commande : combat déjà terminé.")
            return
        peak = max(1, max(p["tick"] for p in points))
        span = max(1, timeline["commands"] - 1)
        for point in points:
            x = left + (point["step"] - 1) / span * (right - left)
            y = bottom - point["tick"] / peak * (bottom - top)
            tone = (OUTCOME_COLORS["defeat"] if point["damage"] else
                    OUTCOME_COLORS["victory"] if point["healing"] else BLUE)
            shape = canvas.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5,
                                      fill=tone, outline="")
            canvas.tag_bind(shape, "<Button-1>",
                            lambda _event, step=point["step"]:
                            self.open_replay(step))
        for finding in timeline["findings"]:
            x = left + (finding["step"] - 1) / span * (right - left)
            canvas.create_line(x, top - 1, x, bottom,
                               fill=ORANGE, dash=(2, 4))
        self._text(canvas, left, 120, "Début CT")
        self._text(canvas, right, 120, "Fin CT", anchor="e")
        self._text(canvas, width - 12, 14, "Rouge: dégâts · Vert: soins · "
                   "Orange: anomalies", anchor="e", color=ORANGE)

    def open_replay(self, step=None):
        if self.trace is None:
            return
        from .studio_battle_replay import show_trace
        viewer = show_trace(self, self.trace)
        if step is not None:
            viewer.show(step)

    def open_map(self):
        if self.report is None:
            return
        self.owner.select_mission(self.report["mission"])
        self.owner.workspace._show_tab("Carte et combat")
