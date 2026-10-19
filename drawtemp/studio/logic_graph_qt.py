"""R31.B — Qt visual editor for the canonical R9-backed logic graph subset.

No QML, gameplay runtime or parallel project state. A dialog uses the owner's
AuthoringSession; incomplete node/edge drafts are private until Apply.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPainterPath, QPen, QPainter
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGraphicsView, QGraphicsScene, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QSpinBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from drawtemp.studio.logic_debugger import LogicGraphDebugger


class LogicCanvas(QGraphicsView):
    selected = Signal(str)
    activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r31-canvas")
        self.setAccessibleName("Graphe visuel des événements R31")
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self._cards = {}
        self._selected = ""
        self._query = ""
        self._debug_states = {}
        self._paused_node = ""
        self._breakpoint_nodes = set()

    def render_graph(self, graph):
        scene = self.scene()
        scene.clear()
        self._cards = {}
        nodes = graph["nodes"]
        # Compact, deterministic card layout; no presentation positions
        # are added to the canonical graph schema.
        for index, node in enumerate(nodes):
            col, row = divmod(index, 4)
            x, y = 30 + col * 225, 35 + row * 106
            color = QColor("#225785" if node["kind"] == "event" else
                           "#775325" if node["kind"] == "branch" else
                           "#295943" if node["kind"] == "wait" else
                           "#59466e" if node["kind"] == "flag" else "#35465f")
            box = scene.addRect(x, y, 186, 76, QPen(QColor("#8ca9d0"), 2),
                                QBrush(color))
            box.setData(0, node["id"])
            box.setZValue(2)
            text = scene.addText(node["id"] + "\n" +
                                 node["params"].get("kind", "unknown"))
            text.setDefaultTextColor(QColor("#f3f6fa"))
            text.setParentItem(box)
            text.setPos(10, 10)
            self._cards[node["id"]] = box
        for edge in graph["edges"]:
            start = self._cards.get(edge["from"])
            end = self._cards.get(edge["to"])
            if start is None or end is None:
                continue
            start_point = start.sceneBoundingRect().center()
            end_point = end.sceneBoundingRect().center()
            path = QPainterPath(start_point)
            halfway = (start_point.x() + end_point.x()) / 2
            path.cubicTo(halfway, start_point.y(),
                         halfway, end_point.y(), end_point.x(), end_point.y())
            stroke = "#68c2a1" if edge["out"] == "true" else (
                "#efa46e" if edge["out"] == "false" else "#66b9de")
            line = scene.addPath(path, QPen(QColor(stroke), 3))
            line.setZValue(1)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-20, -25, 30, 30))
        self.highlight(self._selected)
        self.search(self._query)

    def _hit_id(self, viewport_position):
        item = self.itemAt(viewport_position)
        while item is not None:
            value = item.data(0)
            if isinstance(value, str):
                return value
            item = item.parentItem()
        return ""

    def mousePressEvent(self, event):
        identifier = self._hit_id(event.pos())
        if identifier and event.button() == Qt.LeftButton:
            self.selected.emit(identifier)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        identifier = self._hit_id(event.pos())
        if identifier:
            self.activated.emit(identifier)
        super().mouseDoubleClickEvent(event)

    def highlight(self, node_id):
        self._selected = node_id
        for identifier, item in self._cards.items():
            selected = identifier == node_id
            state = self._debug_states.get(identifier, "")
            color = ("#ffcc73" if selected else
                     "#ff765c" if identifier == self._paused_node else
                     "#ae8cf0" if identifier in self._breakpoint_nodes else
                     "#54c49a" if state in ("executed", "fired") else
                     "#78818e" if state == "cancelled" else "#8ca9d0")
            item.setPen(QPen(QColor(color), 4 if selected or
                             identifier == self._paused_node else 2))

    def set_debug_state(self, states=None, *, paused=None, breakpoints=()):
        self._debug_states = dict(states or {})
        self._paused_node = paused or ""
        self._breakpoint_nodes = set(breakpoints)
        self.highlight(self._selected)

    def search(self, query):
        self._query = query.casefold()
        for identifier, item in self._cards.items():
            item.setOpacity(1.0 if not self._query or
                            self._query in identifier.casefold() else 0.24)


class LogicGraphDialog(QDialog):
    updated = Signal()

    def __init__(self, session: AuthoringSession, parent=None):
        super().__init__(parent)
        if not isinstance(session, AuthoringSession):
            raise TypeError("A shared AuthoringSession is required")
        self.session = session
        self.draft = None
        self._baseline = None
        self.selected_node = ""
        self.link_start = ""
        self.debug_session = None
        self._debug_nodes = set()
        self.setObjectName("r31-logic-dialog")
        self.setWindowTitle("DrawTemp · Game Logic Studio R31.B")
        self.resize(1040, 700)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission du graphe")
        for row in self.session.snapshot().to_dict()["content"]["missions"]:
            self.mission.addItem(row["name"], row["id"])
        header.addWidget(QLabel("Mission"))
        header.addWidget(self.mission)
        self.graphs = QComboBox()
        self.graphs.setAccessibleName("Graphes enregistrés")
        self.graphs.currentIndexChanged.connect(self.load_selected_graph)
        header.addWidget(QLabel("Graphe"))
        header.addWidget(self.graphs)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        self.buttons = {}
        for key, label, callback in (
                ("new", "Nouveau", self.new_graph),
                ("add", "+ Action", self.add_action),
                ("branch", "+ Si / Sinon", self.add_branch),
                ("wait", "+ Attendre", self.add_wait),
                ("flag", "+ Drapeau", self.add_flag),
                ("copy", "Dupliquer", self.copy_action),
                ("edit", "Propriétés…", self.edit_node),
                ("remove", "Supprimer", self.remove_action),
                ("connect", "Relier", lambda: self.start_connect()),
                ("true", "Relier SI", lambda: self.start_connect("true")),
                ("false", "Relier SINON", lambda: self.start_connect("false")),
                ("disconnect", "Délier", self.start_disconnect),
                ("preview", "Vérifier", self.preview),
                ("apply", "Appliquer", self.apply_changes),
                ("undo", "Annuler", self.undo),
                ("redo", "Rétablir", self.redo),
        ):
            button = QPushButton(label)
            button.setObjectName("r31-" + key)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
            self.buttons[key] = button
        root.addLayout(toolbar)
        debugger_bar = QHBoxLayout()
        debugger_bar.addWidget(QLabel("Scénario test"))
        self.debug_scenario = QComboBox()
        self.debug_scenario.setObjectName("r31-debug-scenario")
        self.debug_scenario.setAccessibleName("État initial du diagnostic R9")
        for caption, value in (("Initial", "initial"),
                               ("Condition satisfaite", "satisfied"),
                               ("Condition non satisfaite", "unsatisfied")):
            self.debug_scenario.addItem(caption, value)
        debugger_bar.addWidget(self.debug_scenario)
        debugger_bar.addWidget(QLabel("Tick"))
        self.debug_tick = QSpinBox()
        self.debug_tick.setObjectName("r31-debug-tick")
        self.debug_tick.setRange(0, 100000)
        debugger_bar.addWidget(self.debug_tick)
        for key, label, callback in (
                ("debug_start", "Démarrer debug", self.start_debug),
                ("debug_bp", "Point d'arrêt", self.toggle_breakpoint),
                ("debug_step", "Pas événement", self.debug_step),
                ("debug_resume", "Continuer", self.debug_resume),
                ("debug_inspect", "Inspecter", self.debug_inspect),
        ):
            button = QPushButton(label)
            button.setObjectName("r31-" + key.replace("_", "-"))
            button.clicked.connect(callback)
            debugger_bar.addWidget(button)
            self.buttons[key] = button
        root.addLayout(debugger_bar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)
        self.canvas = LogicCanvas(self)
        splitter.addWidget(self.canvas)
        panel = QWidget()
        side = QVBoxLayout(panel)
        side.addWidget(QLabel("Chercher un nœud"))
        self.search_input = QLineEdit()
        self.search_input.setAccessibleName("Chercher dans le graphe")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.canvas.search)
        side.addWidget(self.search_input)
        self.node_info = QLabel("Sélectionnez un nœud")
        self.node_info.setWordWrap(True)
        side.addWidget(self.node_info)
        side.addWidget(QLabel("Diagnostic / aperçu natif R9"))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r31-diagnostics")
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setAccessibleName("Diagnostic du graphe")
        side.addWidget(self.diagnostics, 1)
        side.addWidget(QLabel("Relier : choisir source puis destination.\n"
                              "Les brouillons incomplets ne sont jamais sauvegardés."))
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        self.canvas.selected.connect(self.choose_node)
        self.canvas.activated.connect(lambda _id: self.edit_node())
        self.reload_graph_choices()
        self._render()

    def reload_graph_choices(self, desired=None):
        current = desired if desired is not None else self.graphs.currentData()
        self.graphs.blockSignals(True)
        self.graphs.clear()
        self.graphs.addItem("Nouveau / non enregistré", "")
        for graph in graphs_from_project(self.session.snapshot().to_dict()["project"]):
            self.graphs.addItem(graph["id"] + " (" + graph["mission_id"] + ")",
                                graph["id"])
        index = self.graphs.findData(current)
        self.graphs.setCurrentIndex(max(index, 0))
        self.graphs.blockSignals(False)

    def _has_unsaved_draft(self):
        return self.draft is not None and (
            self._baseline is None or self.draft.document() != self._baseline)

    def _can_discard_draft(self):
        if not self._has_unsaved_draft():
            return True
        response = QMessageBox.question(
            self, "Brouillon R31", "Abandonner les modifications non appliquées ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return response == QMessageBox.Yes

    def load_selected_graph(self, *_):
        if not self._can_discard_draft():
            previous = self.draft.graph["id"]
            index = self.graphs.findData(previous)
            self.graphs.blockSignals(True)
            self.graphs.setCurrentIndex(max(0, index))
            self.graphs.blockSignals(False)
            return
        identifier = self.graphs.currentData()
        if identifier:
            self.draft = LogicGraphDraft.load(self.session, identifier)
            self._baseline = self.draft.document()
            target = self.mission.findData(self.draft.graph["mission_id"])
            if target >= 0:
                self.mission.setCurrentIndex(target)
        else:
            self.draft = None
            self._baseline = None
        self.link_start = ""
        self.selected_node = ""
        self._reset_debug()
        self._render()

    def new_graph(self):
        if not self._can_discard_draft():
            return
        mission_id = self.mission.currentData()
        identifier, accepted = QInputDialog.getText(
            self, "Nouveau graphe", "Identifiant stable (minuscules, lettres/chiffres)",
            text="nouveau_graphe")
        if not accepted:
            return
        identifier = identifier.strip()
        if any(row["id"] == identifier for row in graphs_from_project(
                self.session.snapshot().to_dict()["project"])):
            self._problem(LogicGraphError(
                "duplicate_graph", "Un graphe enregistré porte déjà cet identifiant."))
            return
        self.graphs.blockSignals(True)
        self.graphs.setCurrentIndex(0)
        self.graphs.blockSignals(False)
        self.draft = LogicGraphDraft.new(
            mission_id, identifier, source_revision=self.session.revision)
        self._baseline = None
        self.selected_node = "start"
        self.link_start = ""
        self._reset_debug()
        self._render()

    def _reset_debug(self):
        self.debug_session = None
        self._debug_nodes.clear()
        self.canvas.set_debug_state()

    def _render(self):
        if self.draft is None:
            self.canvas.scene().clear()
            self.node_info.setText("Sélectionnez un graphe ou créez-en un.")
        else:
            self.canvas.render_graph(self.draft.graph)
            self.canvas.highlight(self.selected_node)
            self._inspect()
        self.mission.setEnabled(self.draft is None)
        if self.debug_session is not None and (
                self.draft is None or self.draft.graph["id"] != self.debug_session.graph_id
                or self._has_unsaved_draft()
                or self.session.revision != self.debug_session.source_revision):
            self._reset_debug()
        self.buttons["apply"].setEnabled(self.draft is not None)
        for key in ("debug_bp", "debug_step", "debug_resume", "debug_inspect"):
            self.buttons[key].setEnabled(self.debug_session is not None)
        self.buttons["debug_start"].setEnabled(
            self.draft is not None and not self._has_unsaved_draft())
        for key in ("add", "branch", "wait", "flag", "copy", "edit", "remove", "connect", "true", "false", "disconnect", "preview"):
            self.buttons[key].setEnabled(self.draft is not None)

    def _inspect(self):
        if self.draft is None or not self.selected_node:
            self.node_info.setText("Sélectionnez un nœud")
            return
        node = self.draft.node(self.selected_node)
        self.node_info.setText(
            node["id"] + " · " + node["kind"] + "\n"
            + ", ".join(str(k) + ": " + str(v)
                        for k, v in node["params"].items()))

    def _debug_result(self, state):
        report = state["report"]
        details = [
            "R31.D — DEBUG DANS UN BATTLE ISOLÉ",
            "Pas = un déclencheur R9 (PAS une action)",
            "Replay : NON ATTESTÉ",
            "Nœuds : " + ", ".join(node + "=" + value
                                  for node, value in report["node_states"].items()),
        ]
        for event in report["timeline"]:
            details.append("Événement " + event["event_id"] + " → " +
                           ", ".join(event["node_ids"]))
        self.diagnostics.setPlainText("\n".join(details + state["lines"]))
        self.canvas.set_debug_state(
            report["node_states"], paused=report["paused_node"],
            breakpoints=self._debug_nodes)
        return state

    def _debug_action(self, callback):
        if self.debug_session is None:
            return False
        try:
            self._debug_result(callback())
            return True
        except AuthoringError as exc:
            self._reset_debug()
            self._problem(exc)
            return False
        except (LogicGraphError, ValueError) as exc:
            self._problem(exc)
            return False

    def start_debug(self):
        if self.draft is None or self._has_unsaved_draft():
            self._problem(LogicGraphError(
                "unsaved_graph", "Appliquer le graphe avant un diagnostic Battle isolé."))
            return False
        try:
            self._reset_debug()
            self.debug_session = LogicGraphDebugger(
                self.session, self.draft.graph["id"],
                scenario=self.debug_scenario.currentData(),
                tick=self.debug_tick.value())
            self._debug_result(self.debug_session.report())
            self._render()
            return True
        except (LogicGraphError, AuthoringError, ValueError) as exc:
            self._problem(exc)
            return False

    def toggle_breakpoint(self):
        if self.debug_session is None or not self.selected_node:
            return False
        node_id = self.selected_node
        new_state = node_id not in self._debug_nodes
        if self._debug_action(lambda: self.debug_session.breakpoint(node_id, new_state)):
            if new_state:
                self._debug_nodes.add(node_id)
            else:
                self._debug_nodes.discard(node_id)
            self.canvas.set_debug_state(
                self.debug_session.report()["report"]["node_states"],
                paused=self.debug_session.report()["report"]["paused_node"],
                breakpoints=self._debug_nodes)
            return True
        return False

    def debug_step(self):
        return self._debug_action(self.debug_session.step) if self.debug_session else False

    def debug_resume(self):
        return self._debug_action(self.debug_session.resume) if self.debug_session else False

    def debug_inspect(self):
        if self.debug_session is None or not self.selected_node:
            return False
        try:
            state = self.debug_session.inspect(self.selected_node)
            parts = [f"NŒUD : {state['node_id']} ({state['kind']})",
                     "PAS R9 : déclencheur entier, jamais action individuelle",
                     "Replay : NON ATTESTÉ"]
            for event in state["native_events"]:
                parts.append(event["event_id"] + " · " +
                             event["temporal"]["state"] + " · condition : " +
                             str(event["condition_passed"]))
                parts.extend("  " + row["label"] + ": " + str(row["passed"])
                             for row in event["conditions"])
            if state["action"] is not None:
                parts.append("Action native : " + str(state["action"]))
            self.diagnostics.setPlainText("\n".join(parts))
            return True
        except (LogicGraphError, AuthoringError, ValueError) as exc:
            self._problem(exc)
            return False

    def _problem(self, error):
        code = getattr(error, "code", type(error).__name__)
        self.diagnostics.setPlainText(str(code) + ": " + str(error))

    def choose_node(self, node_id):
        if self.draft is None:
            return
        if self.link_start and self.link_start.split(":", 1)[0] in (
                "connect", "connect_true", "connect_false", "disconnect"):
            mode, source = self.link_start.split(":", 1)
            self.link_start = ""
            try:
                if mode.startswith("connect"):
                    port = {"connect_true": "true", "connect_false": "false"}.get(mode, "next")
                    self.draft.connect(source, node_id, port=port)
                else:
                    self.draft.disconnect(source, node_id)
                self.diagnostics.setPlainText("Connexion modifiée en brouillon.")
            except (LogicGraphError, ValueError) as exc:
                self._problem(exc)
            self._render()
        self.selected_node = node_id
        self.canvas.highlight(node_id)
        self._inspect()

    def start_connect(self, port="next"):
        if self.selected_node and self.draft is not None:
            node = self.draft.node(self.selected_node)
            if node["kind"] == "branch" and port == "next":
                port = "true"
            if node["kind"] != "branch" and port in ("true", "false"):
                self.diagnostics.setPlainText("Relier SI/SINON requiert un nœud condition.")
                return
            code = {"true": "connect_true", "false": "connect_false"}.get(port, "connect")
            self.link_start = code + ":" + self.selected_node
            self.diagnostics.setPlainText("Cliquez la destination du port " +
                                          port + " de " + self.selected_node)

    def start_disconnect(self):
        if self.selected_node:
            self.link_start = "disconnect:" + self.selected_node
            self.diagnostics.setPlainText("Cliquez la destination à déconnecter.")

    def add_action(self):
        if self.draft is None:
            return
        kind, accepted = QInputDialog.getItem(
            self, "Ajouter une action", "Action R9",
            ["message", "hazard", "despawn"], 0, False)
        if not accepted:
            return
        try:
            self.selected_node = self.draft.add_action(kind)
            self._render()
            self.diagnostics.setPlainText("Nœud ajouté. Reliez ses ports avant Appliquer.")
        except LogicGraphError as exc:
            self._problem(exc)

    def add_branch(self):
        if self.draft is None:
            return
        try:
            self.selected_node = self.draft.add_branch()
            self._render()
            self.diagnostics.setPlainText("SI/SINON inséré. Condition typée modifiable.")
        except (LogicGraphError, ValueError) as exc:
            self._problem(exc)

    def add_wait(self):
        if self.draft is None or not self.selected_node:
            self._problem(LogicGraphError("invalid_sequence",
                                         "Sélectionnez une action avant une attente."))
            return
        ticks, ok = QInputDialog.getInt(
            self, "Attente logique", "Ticks de jeu", 5, 1, 10000)
        if not ok:
            return
        try:
            self.selected_node = self.draft.add_wait_after(self.selected_node, ticks)
            self._render()
            self.diagnostics.setPlainText(
                "Attente insérée. Chaque phase est un déclencheur R9 journalisé.")
        except (LogicGraphError, ValueError) as exc:
            self._problem(exc)

    def add_flag(self):
        if self.draft is None or not self.selected_node:
            self._problem(LogicGraphError("invalid_sequence",
                                         "Sélectionnez une action avant le drapeau."))
            return
        source, ok = QInputDialog.getText(
            self, "Variable booléenne", "ID du déclencheur R9 déjà exécuté",
            text="r31_example")
        if not ok:
            return
        try:
            self.selected_node = self.draft.add_flag_after(
                self.selected_node, source.strip())
            self._render()
            self.diagnostics.setPlainText(
                "Drapeau lecture seule : événement R9 déjà déclenché.")
        except (LogicGraphError, ValueError) as exc:
            self._problem(exc)

    def copy_action(self):
        if self.draft is None or not self.selected_node:
            return
        try:
            self.selected_node = self.draft.copy_action(self.selected_node)
            self._render()
            self.diagnostics.setPlainText("Copie en brouillon, non connectée.")
        except LogicGraphError as exc:
            self._problem(exc)

    def remove_action(self):
        if self.draft is None or not self.selected_node:
            return
        try:
            self.draft.remove_action(self.selected_node)
            self.selected_node = ""
            self._render()
        except LogicGraphError as exc:
            self._problem(exc)

    def _prompt_expression(self, previous):
        """Strict boolean AST via typed dialogs; no JSON or interpreter."""
        operator, ok = QInputDialog.getItem(
            self, "Expression booléenne", "Opération",
            ["Remplacer", "ET", "OU", "NON"], 0, False)
        if not ok:
            return None
        if operator == "NON":
            value = {"not": deepcopy(previous)}
        else:
            kind, ok = QInputDialog.getItem(
                self, "Prédicat typé", "Condition",
                ["hp_below", "wave_capacity", "defeated", "tick"], 0, False)
            if not ok:
                return None
            if kind in ("hp_below", "defeated"):
                unit, ok = QInputDialog.getText(
                    self, "Acteur", "ID existant (validé par R9)", text="hero")
                if not ok:
                    return None
                leaf = {"condition": kind, "unit": unit}
                if kind == "hp_below":
                    percent, ok = QInputDialog.getInt(
                        self, "PV", "Seuil %", 50, 1, 99)
                    if not ok:
                        return None
                    leaf["percent"] = percent
            elif kind == "wave_capacity":
                team, ok = QInputDialog.getItem(
                    self, "Équipe", "Équipe", ["enemy", "player", "neutral"], 0, False)
                if not ok:
                    return None
                quantity, ok = QInputDialog.getInt(
                    self, "Effectifs", "Nombre maximum", 0, 0, 100000)
                if not ok:
                    return None
                leaf = {"condition": kind, "team": team,
                        "max_alive": quantity}
            else:
                tick, ok = QInputDialog.getInt(
                    self, "Temps logique", "Tick minimum", 0, 0, 100000)
                if not ok:
                    return None
                leaf = {"condition": kind, "value": tick}
            value = (leaf if operator == "Remplacer"
                     else {{"ET": "all", "OU": "any"}[operator]:
                           [deepcopy(previous), leaf]})
        from drawtemp.sdk.logic_branches import validate_expression
        validate_expression(value)
        return value

    def edit_node(self):
        if self.draft is None or not self.selected_node:
            return
        node = self.draft.node(self.selected_node)
        params = deepcopy(node["params"])
        kind = params["kind"]
        try:
            if node["kind"] == "wait":
                ticks, ok = QInputDialog.getInt(
                    self, "Attente", "Ticks logiques", params["ticks"], 1, 10000)
                if not ok:
                    return
                self.draft.edit_node(self.selected_node,
                                     {"kind": "ticks", "ticks": ticks})
                self._render()
                return
            if node["kind"] == "flag":
                value, ok = QInputDialog.getText(
                    self, "Drapeau journal", "ID d'événement R9", text=params["event_id"])
                if not ok:
                    return
                self.draft.edit_node(self.selected_node, {
                    "kind": "event_fired", "event_id": value.strip()})
                self._render()
                return
            if node["kind"] == "branch":
                expression = self._prompt_expression(params["predicate"])
                if expression is None:
                    return
                self.draft.edit_node(self.selected_node, {
                    "kind": "if", "predicate": expression})
                self._render()
                self.diagnostics.setPlainText("Condition booléenne modifiée en brouillon.")
                return
            if node["kind"] == "event":
                selected, ok = QInputDialog.getItem(
                    self, "Type de déclencheur", "Événement R9",
                    ["tick", "interact"], 0 if kind == "tick" else 1, False)
                if not ok:
                    return
                if selected != kind:
                    params = ({"kind": "tick", "tick": 0} if selected == "tick"
                              else {"kind": "interact", "object_id": "lever"})
                    kind = selected
            if kind == "tick":
                value, ok = QInputDialog.getInt(
                    self, "Déclencheur", "Tick logique", params["tick"], 0, 1000000)
                if not ok:
                    return
                params["tick"] = value
            elif kind == "interact":
                value, ok = QInputDialog.getText(
                    self, "Interaction", "ID de l'objet", text=params["object_id"])
                if not ok:
                    return
                params["object_id"] = value
            elif kind == "message":
                value, ok = QInputDialog.getMultiLineText(
                    self, "Message", "Texte", params["text"])
                if not ok:
                    return
                params["text"] = value
            elif kind == "despawn":
                value, ok = QInputDialog.getText(
                    self, "Retirer un acteur", "ID de l'acteur", text=params["unit"])
                if not ok:
                    return
                params["unit"] = value
            elif kind == "hazard":
                old = params["pos"] + [params["amount"]]
                value, ok = QInputDialog.getText(
                    self, "Danger", "x,y,puissance",
                    text=",".join(str(i) for i in old))
                if not ok:
                    return
                values = [int(x.strip()) for x in value.split(",")]
                if len(values) != 3:
                    raise ValueError("Attendu : x,y,puissance")
                params.update(pos=values[:2], amount=values[2])
            self.draft.edit_node(self.selected_node, params)
            self._render()
            self.diagnostics.setPlainText("Propriété modifiée localement.")
        except (LogicGraphError, ValueError) as exc:
            self._problem(exc)

    def preview(self):
        if self.draft is None:
            return False
        try:
            _plan, compiled = self.draft.prepare(self.session)
            triggers = compiled if isinstance(compiled, list) else [compiled]
            self.diagnostics.setPlainText(
                "VALIDÉ (non enregistré)\n" +
                "\n".join(t["id"] + " [" + t["condition"] + "]: " +
                          " → ".join(a["kind"] for a in t["actions"])
                          for t in triggers) +
                ("\nSI/SINON exclusifs via cancel_after R9"
                 if self.draft.graph["schema_version"] == 2 else
                 ("\nÉvénements R9 enchaînés via after/delay_ticks"
                  if self.draft.graph["schema_version"] == 3 else "")))
            return True
        except (AuthoringError, LogicGraphError, ValueError) as exc:
            self._problem(exc)
            return False

    def apply_changes(self):
        if self.draft is None:
            return False
        try:
            graph_id = self.draft.graph["id"]
            self.draft.apply(self.session)
            self.reload_graph_choices(graph_id)
            self.draft = LogicGraphDraft.load(self.session, graph_id)
            self._baseline = self.draft.document()
            self.link_start = ""
            self.diagnostics.setPlainText("APPLIQUÉ : Content + GameProject (une transaction).")
            self._render()
            self.updated.emit()
            return True
        except (AuthoringError, LogicGraphError, ValueError) as exc:
            self._problem(exc)
            return False

    def _history(self, direction):
        if not self._can_discard_draft():
            return
        try:
            getattr(self.session, direction)()
            self.reload_graph_choices()
            self.load_selected_graph()
            self.updated.emit()
        except (AuthoringError, LogicGraphError, ValueError) as exc:
            self._problem(exc)

    def undo(self):
        self._history("undo")

    def redo(self):
        self._history("redo")
