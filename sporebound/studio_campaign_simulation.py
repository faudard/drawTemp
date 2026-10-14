"""R5.14 campaign route sandbox: compact Tk explorer and diff inspector.

This presentation owns only transient CampaignSimulation state. Changing tabs,
exploring alternatives and comparing branches cannot publish any game save.
"""
from __future__ import annotations

import json
from copy import deepcopy
from queue import Empty, Queue
from threading import Thread

from .campaign_path_certification import certify_path

from .campaign_flow_simulation import CampaignSimulation
from .model import RuleError, require


class CampaignSimulationStudio:
    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.notebook = notebook
        self.sandbox = None
        self._identity = None
        self._loading = False
        self.compare_a = 0
        self.compare_b = 0
        self._certificate_queue = Queue()
        self._certifying = False
        self._generation = 0
        self._build(notebook)

    def _button(self, parent, label, operation):
        button = self.ttk.Button(parent, text=label,
                                 command=lambda: self.owner._run(operation))
        button.pack(side="left", padx=3, pady=3)
        return button

    def _build(self, notebook):
        tk, ttk = self.tk, self.ttk
        root = ttk.Frame(notebook)
        self.tab = root
        notebook.add(root, text="Campaign Simulation")
        title = ttk.Frame(root)
        title.pack(fill="x", padx=10, pady=(9, 3))
        ttk.Label(title, text="Campaign Simulation Studio",
                  font=("TkDefaultFont", 13, "bold")).pack(side="left")
        ttk.Label(title, text="Simulation hypothétique · aucune sauvegarde réelle",
                  ).pack(side="right")

        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=10, pady=(0, 7))
        self._button(controls, "Nouvelle simulation", self.start)
        self._button(controls, "Depuis partie chargée (copie)", self.start_from_loaded)
        self._button(controls, "Revenir au parent", self.parent)
        self._button(controls, "Créer une bifurcation", self.fork)
        self.ttk.Label(controls, text="Seed").pack(side="left", padx=(12, 3))
        self.cert_seed = tk.StringVar(value="7")
        self.ttk.Entry(controls, textvariable=self.cert_seed, width=7).pack(
            side="left", padx=3)
        self._button(controls, "Certifier ce parcours R5.15", self.certify_selected)

        panels = ttk.Panedwindow(root, orient="horizontal")
        panels.pack(fill="both", expand=True, padx=10, pady=5)

        left = ttk.Frame(panels)
        panels.add(left, weight=2)
        ttk.Label(left, text="Parcours et points de décision",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse",
                                 yscrollcommand=scrollbar.set, height=12)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self._select_node)
        ttk.Label(left, text="Actions possibles à ce point (choix ou résultat supposé)"
                  ).pack(anchor="w", pady=(9, 3))
        self.action_list = tk.Listbox(left, height=7, exportselection=False)
        self.action_list.pack(fill="x")
        self.action_list.bind("<Double-Button-1>",
                              lambda _event: self._apply_safe(self.apply_action))
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=4)
        self._button(actions, "Exécuter l'action", self.apply_action)
        self._button(actions, "Comparer A", lambda: self.mark_compare("a"))
        self._button(actions, "Comparer B", lambda: self.mark_compare("b"))

        right = ttk.Frame(panels)
        panels.add(right, weight=3)
        self.details = ttk.Notebook(right)
        self.details.pack(fill="both", expand=True)
        state_frame = ttk.Frame(self.details)
        self.details.add(state_frame, text="État persistant")
        self.state_text = self._readonly_text(state_frame)
        compare_frame = ttk.Frame(self.details)
        self.details.add(compare_frame, text="Différences A / B")
        self.compare_text = self._readonly_text(compare_frame)
        coverage_frame = ttk.Frame(self.details)
        self.details.add(coverage_frame, text="Couverture explorée")
        self.coverage_text = self._readonly_text(coverage_frame)
        certificate_frame = ttk.Frame(self.details)
        self.details.add(certificate_frame, text="Certification R5.15")
        self.certificate_text = self._readonly_text(certificate_frame)
        self.status = tk.StringVar(value="Créer une simulation pour explorer la campagne.")
        ttk.Label(root, textvariable=self.status, wraplength=1100
                  ).pack(fill="x", padx=10, pady=(3, 8))

    def _readonly_text(self, frame):
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        view = self.tk.Text(frame, wrap="none", state="disabled",
                            yscrollcommand=scrollbar.set, height=17)
        view.pack(fill="both", expand=True)
        scrollbar.configure(command=view.yview)
        return view

    @staticmethod
    def _value(item):
        if isinstance(item, str):
            return item
        return json.dumps(item, ensure_ascii=False, sort_keys=True)

    def _state_report(self, row):
        def summary(items):
            return ", ".join(items) if items else "—"
        missions = row["missions"]
        lines = [
            "ÉTAT DE CAMPAGNE · POINT " + str(row["node"]),
            "Simulation uniquement — pas de combat certifié",
            "",
            "MISSIONS",
            "  Disponibles : " + summary(missions["available"]),
            "  Terminées : " + summary(missions["completed"]),
            "  Bloquées : " + summary(missions["blocked"]),
            "",
            "NARRATION",
            "  Scène active : " + (row["story_pending"] or "aucune"),
            "  Choix : " + summary(row["choices"]),
            "  Fins satisfaites : " + summary(row["endings"]),
            "",
            "RESSOURCES",
            "  Or : " + str(row["resources"]["gold"]),
        ]
        for key, value in sorted(row["resources"]["inventory"].items()):
            lines.append("  Inventaire · " + key + " : " + str(value))
        lines += ["", "VARIABLES PERSISTANTES"]
        for key, value in sorted(row["variables"].items()):
            lines.append("  " + key + " = " + self._value(value))
        if not row["variables"]:
            lines.append("  —")
        lines += ["", "COMPAGNONS"]
        for uid, hero in sorted(row["companions"].items()):
            lines.append("  " + uid + " · " + hero["job"]
                         + " · moral " + hero["morale"]
                         + " · blessures : " + summary(hero["wounds"]))
        if not row["companions"]:
            lines.append("  —")
        lines += ["", "CONSÉQUENCES APPLIQUÉES"]
        lines += ["  " + entry for entry in row["consequences"]] or ["  —"]
        return "\n".join(lines)

    def _comparison_report(self, row):
        lines = [
            f"COMPARAISON A = {row['left']}   /   B = {row['right']}",
            f"Plus proche ancêtre commun : {row['common_ancestor']}",
            "",
            "PARCOURS A",
            *["  " + event for event in row["left_path"]],
            "",
            "PARCOURS B",
            *["  " + event for event in row["right_path"]],
            "",
            "FINS SATISFAITES",
            "  A : " + (", ".join(row["left_endings"]) or "—"),
            "  B : " + (", ".join(row["right_endings"]) or "—"),
            "",
            "DIFFÉRENCES",
        ]
        if row["changed"]:
            for change in row["changed"]:
                lines.append("  " + change["path"])
                lines.append("      A : " + self._value(change["before"]))
                lines.append("      B : " + self._value(change["after"]))
        else:
            lines.append("  Aucun écart de progression")
        lines += ["", "Résultats de mission fictifs — aucune preuve de combat."]
        return "\n".join(lines)

    @staticmethod
    def _coverage_report(row):
        return "\n".join([
            "COUVERTURE OBSERVÉE (NON EXHAUSTIVE)",
            "",
            "Nombre de points : " + str(row["nodes"]),
            "Missions terminées dans les simulations :",
            "  " + (", ".join(row["missions_completed_in_preview"]) or "—"),
            "Scènes choisies :",
            "  " + (", ".join(row["scenes_chosen_in_preview"]) or "—"),
            "Fins rencontrées :",
            "  " + (", ".join(row["endings_witnessed"]) or "—"),
            "Fins encore non observées :",
            "  " + (", ".join(row["endings_not_witnessed"]) or "—"),
            "",
            "Un parcours non observé n'est pas nécessairement impossible.",
            "Pour certifier une victoire : exécuter un vrai GameSession/Battle.",
        ])

    def _set_text(self, view, text):
        view.configure(state="normal")
        view.delete("1.0", "end")
        view.insert("end", text)
        view.configure(state="disabled")

    def _source_identity(self):
        # Detect authoring edits and any campaign switch, but never try to
        # transparently migrate speculative branches to a new project revision.
        return json.dumps({"content": self.owner.doc().data,
                           "project": self.owner.project.to_dict(),
                           "campaign": self.owner.campaign_id.get()},
                          sort_keys=True, ensure_ascii=False)

    def _ensure_current(self):
        require(self.sandbox is not None, "Créer une simulation d'abord")
        require(self._identity == self._source_identity(),
                "La campagne a changé : réinitialiser la simulation")

    def start(self):
        self._new(from_loaded=False)

    def start_from_loaded(self):
        self._new(from_loaded=True)

    def _new(self, *, from_loaded):
        content = self.owner._content()
        project = self.owner.project
        campaign_id = self.owner.campaign_id.get()
        progress = None
        if from_loaded:
            if (self.owner.session is None or
                    self.owner.session_campaign != campaign_id):
                raise RuleError("Aucune partie chargée pour cette campagne")
            progress = self.owner.session
        candidate = CampaignSimulation(content, project, campaign_id,
                                       progress=progress)
        # Swap sandbox only after successful construction/compatibility checks.
        self.sandbox = candidate
        self._generation += 1
        self._identity = self._source_identity()
        self._set_text(self.certificate_text,
                       "Aucun résultat. Sélectionner un parcours et demander un replay réel.")
        self.compare_a = self.compare_b = 0
        self.draw()
        self.status.set("Copie d'une partie chargée : aucune modification de sauvegarde."
                        if from_loaded else
                        "Nouvelle simulation. Toutes les victoires/défaites sont fictives.")

    def refresh(self):
        if self.sandbox is not None and self._identity != self._source_identity():
            self.sandbox = None
            self._generation += 1
            self._identity = None
            self.compare_a = self.compare_b = 0
            self._clear()
            self.status.set("Projet ou campagne modifié : simulation invalidée. Recommencer.")

    def _clear(self):
        self._loading = True
        self.tree.delete(*self.tree.get_children())
        self.action_list.delete(0, "end")
        for text in (self.state_text, self.compare_text, self.coverage_text,
                     self.certificate_text):
            self._set_text(text, "")
        self._loading = False

    def draw(self):
        self._ensure_current()
        self._loading = True
        self.tree.delete(*self.tree.get_children())
        for item in self.sandbox.tree():
            parent = ("n" + str(item["parent"])) if item["parent"] is not None else ""
            ident = "n" + str(item["id"])
            self.tree.insert(parent, "end", iid=ident,
                             text=f'{item["id"]} · {item["action"]}', open=True)
        self.tree.selection_set("n" + str(self.sandbox.cursor))
        self.tree.see("n" + str(self.sandbox.cursor))
        self._loading = False
        actions = self.sandbox.actions()
        self._offered_actions = actions
        self.action_list.delete(0, "end")
        for action in actions:
            if action["kind"] == "choice":
                label = action["label"]
                self.action_list.insert("end", "Dialogue : " + label
                                        + " [" + action["id"] + "]")
            else:
                title = ("Victoire supposée" if action["outcome"] == "victory"
                         else "Défaite supposée")
                self.action_list.insert("end", title + " : " + action["id"])
        self._set_text(self.state_text, self._state_report(self.sandbox.inspect()))
        self._set_text(self.coverage_text,
                       self._coverage_report(self.sandbox.coverage()))
        self._set_text(self.compare_text,
                       self._comparison_report(
                           self.sandbox.compare(self.compare_a, self.compare_b)))
        self.status.set(
            f"Point {self.sandbox.cursor} · {self.sandbox.size} états · "
            f"comparaison A={self.compare_a}, B={self.compare_b} · "
            "résultats de missions hypothétiques, sans combat/replay ni voyage simulé.")

    def _select_node(self, _event=None):
        if self._loading or self.sandbox is None:
            return
        chosen = self.tree.selection()
        if not chosen:
            return
        try:
            self._ensure_current()
            selected_id = int(chosen[0][1:])
            if selected_id == self.sandbox.cursor:
                return
            self.sandbox.select(selected_id)
            self.draw()
        except RuleError as exc:
            self.status.set(str(exc))

    def _apply_safe(self, method):
        self.owner._run(method)

    def apply_action(self):
        self._ensure_current()
        selected = self.action_list.curselection()
        if not selected:
            raise RuleError("Sélectionner un choix ou une issue de mission")
        action = self._offered_actions[selected[0]]
        if action["kind"] == "choice":
            self.sandbox.choose(action["id"])
        else:
            self.sandbox.resolve(action["id"], action["outcome"])
        self.draw()

    def fork(self):
        self._ensure_current()
        self.sandbox.fork("Alternative")
        self.draw()

    def parent(self):
        self._ensure_current()
        origin = self.sandbox.node().parent
        if origin is None:
            raise RuleError("Déjà au début de ce parcours")
        self.sandbox.select(origin)
        self.draw()

    def mark_compare(self, side):
        self._ensure_current()
        if side == "a":
            self.compare_a = self.sandbox.cursor
        else:
            self.compare_b = self.sandbox.cursor
        self.draw()
        self.details.select(1)

    def certify_selected(self):
        """Run real Battle replay off the Tk thread, with stale-result rejection."""
        self._ensure_current()
        require(not self._certifying, "Une certification est déjà en cours")
        try:
            seed = int(self.cert_seed.get())
        except ValueError as exc:
            raise RuleError("Seed de certification invalide") from exc
        plan = self.sandbox.certification_plan(seed=seed)
        project = deepcopy(self.owner.project)
        content = self.owner._content()
        identity = self._source_identity()
        generation = self._generation
        node_id = self.sandbox.cursor
        self._certifying = True
        self._set_text(self.certificate_text,
                       "CERTIFICATION EN COURS\n\n"
                       "Exécution de vrais combats, replays, et checkpoints "
                       "temporaires vérifiés. Aucun slot joueur modifié.")
        self.details.select(3)
        self.status.set("Certification en cours · progression tactique authentique")

        def work():
            try:
                certificate = certify_path(
                    content, project, plan, max_commands=800,
                    checkpoint_every=7)
                self._certificate_queue.put((identity, generation, node_id, certificate, None))
            except Exception as exc:
                self._certificate_queue.put((identity, generation, node_id, None, str(exc)))

        Thread(target=work, name="CampaignR515", daemon=True).start()
        self.tab.after(100, self._poll_certificate)

    def _poll_certificate(self):
        try:
            identity, generation, node_id, certificate, error = self._certificate_queue.get_nowait()
        except Empty:
            if self._certifying:
                self.tab.after(100, self._poll_certificate)
            return
        self._certifying = False
        if (generation != self._generation or identity != self._source_identity()
                or self.sandbox is None or self.sandbox.cursor != node_id):
            self._set_text(self.certificate_text,
                           "REJETÉ : le projet ou le parcours a changé pendant le calcul.")
            self.status.set("Certification obsolète : refaire la simulation.")
            return
        if error is not None:
            self._set_text(self.certificate_text,
                           "NON CERTIFIÉ\n\n" + error
                           + "\n\nAucun résultat hypothétique ne valide une victoire.")
            self.status.set("Le chemin réel ne valide pas le parcours simulé.")
            return
        evidence = certificate["evidence"]
        observed = certificate["observed"]
        report = [
            "CERTIFIÉ PAR REPLAY GAMESESSION",
            "",
            "Parcours : " + certificate["id"],
            "Seed : " + str(certificate["seed"]),
            "Combats exécutés : " + str(evidence["tactical_battles"]),
            "Commandes tactiques : " + str(evidence["commands"]),
            "Checkpoints relus : " + str(evidence["checkpoints"]),
            "Identité reprise/sans interruption : OUI",
            "Preuve SHA-256 : " + evidence["proof_digest"],
            "",
            "Missions terminées : " + ", ".join(observed["completed"]),
            "Fins prouvées : " + (", ".join(observed["endings"]) or "—"),
            "Conséquences : " + (", ".join(observed["consequences"]) or "—"),
            "",
            "Certification valable UNIQUEMENT pour ce parcours et cette seed.",
            "Les autres parcours et fins ne sont pas automatiquement certifiés.",
        ]
        self._set_text(self.certificate_text, "\n".join(report))
        self.status.set("Parcours certifié : vrais combats et checkpoints concordants.")
