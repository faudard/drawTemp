"""Tk 3.8.1 trace inspector; consumes verified headless diagnostic snapshots."""
from __future__ import annotations

import json


class BattleTraceWindow:
    def __init__(self, owner, report):
        self.owner = owner
        self.report = report
        self.tk = owner.tk
        self.ttk = owner.ttk
        self.index = 0
        self.window = self.tk.Toplevel(owner.tab)
        self.window.title("Battle Lab · replay seed {} · {}".format(
            report["seed"], report["mission"]))
        self.window.geometry("1050x710")
        frame = self.ttk.Frame(self.window, padding=9)
        frame.pack(fill="both", expand=True)
        self.ttk.Label(
            frame, text="Replay vérifié · Seed {} · {} · {}".format(
                report["seed"], report["mission"], report["result"]),
            font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.ttk.Label(
            frame, text="États réels après chaque commande Battle.execute. "
            "Vue schématique des positions : le rendu Player reste indépendant.",
            wraplength=970).pack(anchor="w", pady=(2, 8))

        navigation = self.ttk.Frame(frame)
        navigation.pack(fill="x")
        self.ttk.Button(navigation, text="|◀", command=lambda: self.show(0)).pack(side="left")
        self.ttk.Button(navigation, text="◀", command=lambda: self.show(self.index - 1)).pack(side="left")
        self.ttk.Button(navigation, text="▶", command=lambda: self.show(self.index + 1)).pack(side="left")
        self.ttk.Button(
            navigation, text="▶|",
            command=lambda: self.show(len(self.report["steps"]))).pack(side="left")
        self.position = self.ttk.Label(navigation, text="")
        self.position.pack(side="left", padx=12)
        self.ttk.Button(
            navigation, text="Ouvrir la mission dans la carte",
            command=self.owner.open_map).pack(side="right")

        body = self.ttk.Panedwindow(frame, orient="horizontal")
        body.pack(fill="both", expand=True, pady=8)
        left = self.ttk.Frame(body)
        right = self.ttk.Frame(body)
        body.add(left, weight=2)
        body.add(right, weight=3)

        self.ttk.Label(left, text="Décisions exécutées").pack(anchor="w")
        cols = ("index", "tick", "actor", "kind")
        self.steps = self.ttk.Treeview(left, columns=cols, show="headings", height=14)
        for col, text, width in zip(cols, ("#", "CT", "Unité", "Action"),
                                    (40, 55, 108, 105)):
            self.steps.heading(col, text=text)
            self.steps.column(col, width=width, anchor="center")
        self.steps.pack(fill="both", expand=True)
        self.steps.insert("", "end", iid="0", values=(0, 0, "-", "État initial"))
        for step in report["steps"]:
            self.steps.insert(
                "", "end", iid=str(step["index"]),
                values=(step["index"], step["tick_before"],
                        step["actor"] or "déploiement",
                        step["command"]["kind"]))
        self.steps.bind("<<TreeviewSelect>>", self._on_step)

        self.ttk.Label(left, text="Constats et événements suspects").pack(
            anchor="w", pady=(8, 1))
        self.findings = self.ttk.Treeview(
            left, columns=("severity", "index", "code"), show="headings",
            height=6)
        for col, title, width in zip(("severity", "index", "code"),
                                     ("Niveau", "#", "Signal"), (75, 40, 210)):
            self.findings.heading(col, text=title)
            self.findings.column(col, width=width, anchor="w")
        self.findings.pack(fill="x")
        for n, finding in enumerate(report["diagnostics"]["findings"]):
            self.findings.insert("", "end", iid=str(n),
                                 values=(finding["severity"], finding["step"],
                                         finding["code"]))
        self.findings.bind("<<TreeviewSelect>>", self._on_finding)

        self.ttk.Label(right, text="Position des unités et état de l'objectif").pack(
            anchor="w")
        self.canvas = self.tk.Canvas(
            right, width=580, height=355, highlightthickness=1,
            background="#24272d", highlightbackground="#656970")
        self.canvas.pack(fill="x", pady=4)
        self.details = self.tk.Text(right, height=13, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True, pady=(7, 0))
        self.window.bind("<Left>", lambda _: self.show(self.index - 1))
        self.window.bind("<Right>", lambda _: self.show(self.index + 1))
        self.show(0)

    def _on_step(self, _event=None):
        selection = self.steps.selection()
        if selection and int(selection[0]) != self.index:
            self.show(int(selection[0]))

    def _on_finding(self, _event=None):
        selection = self.findings.selection()
        if selection:
            row = self.report["diagnostics"]["findings"][int(selection[0])]
            self.show(row["step"])

    def show(self, index):
        self.index = min(max(0, index), len(self.report["steps"]))
        self.steps.selection_set(str(self.index))
        self.steps.see(str(self.index))
        item = self.report["steps"][self.index - 1] if self.index else None
        state = item["after"] if item else self.report["initial"]
        self.position.configure(
            text="Étape {} / {} · Tick CT {} · {}".format(
                self.index, len(self.report["steps"]), state["tick"],
                state["result"] or "en cours"))
        self._draw(state, item)
        lines = []
        if item:
            lines.append("Unité : {} ({})".format(
                item["actor"] or "déploiement", item["team"]))
            lines.append("Commande : " + json.dumps(item["command"], ensure_ascii=False))
            lines.append("Progression observable : " +
                         ("oui" if item["progress"] else "non"))
            lines.extend("Événement : " + json.dumps(e, ensure_ascii=False)
                         for e in item["events"])
        else:
            lines.append("Avant la première commande · état initial canonique.")
        lines.append("PV / CT des unités :")
        lines.extend("  {} [{} · N{}] : {}/{} PV, {} CT @ {}".format(
            u["id"], u["team"], u["level"], u["hp"], u["max_hp"],
            u["ct"], u["pos"]) for u in state["units"])
        flags = [x for x in self.report["diagnostics"]["findings"]
                 if x["step"] == self.index]
        lines.extend("Diagnostic {} : {} ({})".format(
            x["code"], x["message"], x["evidence"]) for x in flags)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", "\n".join(lines))
        self.details.configure(state="disabled")

    def _draw(self, state, item):
        canvas = self.canvas
        canvas.delete("all")
        board = self.report["board"]
        width, height = board["width"], board["height"]
        size = min(36, 550 / max(1, width), 325 / max(1, height))
        left, top = 16, 18
        right, bottom = left + width * size, top + height * size
        canvas.create_rectangle(left, top, right, bottom,
                                outline="#737883", fill="#31363d")
        for col in range(1, width):
            x = left + col * size
            canvas.create_line(x, top, x, bottom, fill="#474c55")
        for row in range(1, height):
            y = top + row * size
            canvas.create_line(left, y, right, y, fill="#474c55")
        for cell in board["goals"]:
            x, y = cell
            canvas.create_rectangle(left + x * size + 1, top + y * size + 1,
                                    left + (x + 1) * size - 1,
                                    top + (y + 1) * size - 1,
                                    outline="#f0b754", width=2)
        for obj in state["objects"]:
            if len(obj["pos"]) < 2:
                continue
            x, y = obj["pos"][:2]
            color = "#60bca3" if obj["open"] else "#d2a36e"
            canvas.create_rectangle(left + x * size + size * .25,
                                    top + y * size + size * .25,
                                    left + (x + .75) * size,
                                    top + (y + .75) * size, fill=color)
        active = item["actor"] if item else state["active"]
        for unit in sorted(state["units"], key=lambda u: (u["level"], u["id"])):
            if not unit["alive"]:
                continue
            x, y = unit["pos"]
            center_x = left + (x + .5) * size
            center_y = top + (y + .5) * size
            radius = max(1.5, min(size * .38, 12))
            canvas.create_oval(center_x - radius, center_y - radius,
                               center_x + radius, center_y + radius,
                               fill="#61a7ff" if unit["team"] == "player"
                               else "#ef7b77",
                               outline="#ffe28b" if unit["id"] == active
                               else "#151820", width=2)
            if size >= 22:
                canvas.create_text(center_x, center_y,
                                   text=unit["id"][:3] + (
                                       "↑" + str(unit["level"]) if unit["level"] else ""),
                                   font=("TkDefaultFont", 7, "bold"),
                                   fill="#151820")


def show_trace(owner, report):
    return BattleTraceWindow(owner, report)
