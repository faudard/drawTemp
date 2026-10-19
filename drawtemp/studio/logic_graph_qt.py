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
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft


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
            color = QColor("#225785" if node["kind"] == "event" else "#35465f")
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
            line = scene.addPath(path, QPen(QColor("#66b9de"), 3))
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
            item.setPen(QPen(QColor("#ffcc73" if selected else "#8ca9d0"),
                             4 if selected else 2))

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
        self.selected_node = ""
        self.link_start = ""
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
                ("copy", "Dupliquer", self.copy_action),
                ("edit", "Propriétés…", self.edit_node),
                ("remove", "Supprimer", self.remove_action),
                ("connect", "Relier", self.start_connect),
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

    def load_selected_graph(self, *_):
        identifier = self.graphs.currentData()
        if identifier:
            self.draft = LogicGraphDraft.load(self.session, identifier)
            target = self.mission.findData(self.draft.graph["mission_id"])
            if target >= 0:
                self.mission.setCurrentIndex(target)
        else:
            self.draft = None
        self.link_start = ""
        self.selected_node = ""
        self._render()

    def new_graph(self):
        mission_id = self.mission.currentData()
        identifier, accepted = QInputDialog.getText(
            self, "Nouveau graphe", "Identifiant stable (minuscules, lettres/chiffres)",
            text="nouveau_graphe")
        if not accepted:
            return
        self.graphs.blockSignals(True)
        self.graphs.setCurrentIndex(0)
        self.graphs.blockSignals(False)
        self.draft = LogicGraphDraft.new(
            mission_id, identifier.strip(), source_revision=self.session.revision)
        self.selected_node = "start"
        self.link_start = ""
        self._render()

    def _render(self):
        if self.draft is None:
            self.canvas.scene().clear()
            self.node_info.setText("Sélectionnez un graphe ou créez-en un.")
        else:
            self.canvas.render_graph(self.draft.graph)
            self.canvas.highlight(self.selected_node)
            self._inspect()
        self.buttons["apply"].setEnabled(self.draft is not None)
        for key in ("add", "copy", "edit", "remove", "connect", "disconnect", "preview"):
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

    def _problem(self, error):
        code = getattr(error, "code", type(error).__name__)
        self.diagnostics.setPlainText(str(code) + ": " + str(error))

    def choose_node(self, node_id):
        if self.draft is None:
            return
        if self.link_start.startswith("connect:") or self.link_start.startswith("disconnect:"):
            mode, source = self.link_start.split(":", 1)
            self.link_start = ""
            try:
                if mode == "connect":
                    self.draft.connect(source, node_id)
                else:
                    self.draft.disconnect(source, node_id)
                self.diagnostics.setPlainText("Connexion modifiée en brouillon.")
            except (LogicGraphError, ValueError) as exc:
                self._problem(exc)
            self._render()
        self.selected_node = node_id
        self.canvas.highlight(node_id)
        self._inspect()

    def start_connect(self):
        if self.selected_node:
            self.link_start = "connect:" + self.selected_node
            self.diagnostics.setPlainText("Cliquez la destination du nœud " +
                                          self.selected_node)

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

    def edit_node(self):
        if self.draft is None or not self.selected_node:
            return
        node = self.draft.node(self.selected_node)
        params = deepcopy(node["params"])
        kind = params["kind"]
        try:
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
            self.diagnostics.setPlainText(
                "VALIDÉ (non enregistré)\n" +
                "R9: " + compiled["id"] + "\n" +
                "Déclencheur: " + compiled["condition"] + "\n" +
                "Actions: " + " → ".join(row["kind"] for row in compiled["actions"]))
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
            self.link_start = ""
            self.diagnostics.setPlainText("APPLIQUÉ : Content + GameProject (une transaction).")
            self._render()
            self.updated.emit()
            return True
        except (AuthoringError, LogicGraphError, ValueError) as exc:
            self._problem(exc)
            return False

    def _history(self, direction):
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
