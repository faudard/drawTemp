"""Interactive, presentation-only QGraphics canvas for R55 typed system graphs.

Only the headless system_design_graph adapter may mutate recipe links. Node
coordinates live in the editor's local draft history, never in GameProject.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView,
)

from drawtemp.studio.system_design_graph import links

NODE_W = 210
NODE_H = 58
GAP_Y = 82


class GraphPort(QGraphicsEllipseItem):
    """Left=input or right=output; clicked directly with the mouse."""
    def __init__(self, node, direction, canvas):
        x = -10 if direction == "input" else NODE_W - 10
        super().__init__(x, NODE_H / 2 - 10, 20, 20, node)
        self.node = node
        self.direction = direction
        self.canvas = canvas
        self.setBrush(QBrush(QColor("#16a34a" if direction == "output" else "#0284c7")))
        self.setPen(QPen(QColor("#f8fafc"), 1.5))
        self.setZValue(4)
        self.setToolTip(
            ("Sortie" if direction == "output" else "Entrée") +
            " — " + node.identifier + " ; clic pour relier")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Defer until after Qt has dispatched mousePress/Release: applying
            # a link rebuilds the scene and destroys the clicked port item.
            canvas = self.canvas
            key = (self.node.category, self.node.identifier)
            direction = self.direction
            QTimer.singleShot(0, lambda: canvas.port_clicked(key, direction))
            event.accept()
        else:
            super().mousePressEvent(event)


class GraphNode(QGraphicsRectItem):
    """Draggable/selectable node; never writes GameProject or runtime."""
    def __init__(self, category, identifier, canvas):
        super().__init__(0, 0, NODE_W, NODE_H)
        self.category, self.identifier, self.canvas = category, identifier, canvas
        self._drag_origin = QPointF()
        self.setFlags(QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemIsFocusable |
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.setBrush(QBrush(QColor({
            "resources": "#164e63", "producers": "#374151",
            "merchants": "#78350f", "quests": "#4c1d95"}[category])))
        self.setPen(QPen(QColor("#e2e8f0"), 1.5))
        text = QGraphicsTextItem(identifier + "\n" + category, self)
        text.setDefaultTextColor(QColor("#ffffff"))
        text.setTextWidth(NODE_W - 28)
        text.setPos(15, 6)
        text.setAcceptedMouseButtons(Qt.NoButton)
        self.input = GraphPort(self, "input", canvas)
        self.output = (GraphPort(self, "output", canvas)
                       if category in ("resources", "producers") else None)
        self.setToolTip("Sélectionner, déplacer ou utiliser un port pour relier")

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.canvas.redraw_links()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._drag_origin = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.pos() != self._drag_origin:
            self.canvas.node_dragged(
                (self.category, self.identifier), self._drag_origin, self.pos())


class GraphLink(QGraphicsLineItem):
    def __init__(self, source, target, amount):
        super().__init__()
        self.source, self.target, self.amount = source, target, amount
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(-1)
        self.setPen(QPen(QColor("#38bdf8" if source[0] == "resources"
                                else "#4ade80"), 2))
        self.setToolTip(
            source[1] + " → " + target[1] +
            (f" · {amount} unités" if amount is not None else ""))


class InteractiveSystemGraph(QGraphicsView):
    """Selection, draggable nodes and two-click typed port connection."""

    def __init__(self, *, on_select=None, on_connect=None,
                 on_move=None, on_status=None, parent=None):
        super().__init__(parent)
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.canvas.selectionChanged.connect(self._selection_changed)
        self.setAccessibleName("Graphe R55, nœuds déplaçables et ports à relier")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.on_select = on_select
        self.on_connect = on_connect
        self.on_move = on_move
        self.on_status = on_status
        self._building = False
        self.pending = None
        self.nodes = {}
        self.connections = []
        self._document = None

    def rebuild(self, document, positions=None, selected=None):
        self._building = True
        self._document = document
        self.pending = None
        self.canvas.clear()
        self.nodes = {}
        positions = positions or {}
        columns = {"resources": 30, "producers": 360,
                   "merchants": 690, "quests": 690}
        for category in columns:
            rows = document[category]
            for index, row in enumerate(rows):
                key = (category, row["id"])
                item = GraphNode(*key, self)
                self.canvas.addItem(item)
                y = (20 + index * GAP_Y +
                     (len(document["merchants"]) * GAP_Y
                      if category == "quests" else 0))
                x, y = positions.get(key, (columns[category], y))
                item.setPos(float(x), float(y))
                self.nodes[key] = item
        self.connections = []
        for source, target, amount in links(document):
            edge = GraphLink(source, target, amount)
            self.canvas.addItem(edge)
            self.connections.append(edge)
        self._building = False
        self.redraw_links()
        if selected in self.nodes:
            self.nodes[selected].setSelected(True)
        self.canvas.setSceneRect(self.canvas.itemsBoundingRect().adjusted(
            -30, -30, 30, 30))

    def redraw_links(self):
        if self._building:
            return
        for edge in self.connections:
            a, b = self.nodes[edge.source], self.nodes[edge.target]
            start = a.mapToScene(NODE_W if edge.source[0] in ("resources", "producers")
                                 else 0, NODE_H / 2)
            stop = b.mapToScene(0, NODE_H / 2)
            edge.setLine(start.x(), start.y(), stop.x(), stop.y())

    def port_clicked(self, key, direction):
        if direction == "output":
            if key[0] not in ("resources", "producers"):
                return
            self.pending = key
            self._status("Sortie " + key[1] + " sélectionnée ; choisir une entrée.")
        elif direction == "input":
            if self.pending is None:
                self._status("Sélectionner d'abord une sortie (port vert).")
                return
            source = self.pending
            self.pending = None
            if self.on_connect is not None:
                self.on_connect(source, key)
        else:
            self.pending = None

    def node_dragged(self, key, old, new):
        if self.on_move is not None:
            self.on_move(key, (old.x(), old.y()), (new.x(), new.y()))

    def _selection_changed(self):
        if self._building or self.on_select is None:
            return
        selected = self.canvas.selectedItems()
        for item in selected:
            if isinstance(item, GraphNode):
                self.on_select(("node", (item.category, item.identifier)))
                return
            if isinstance(item, GraphLink):
                self.on_select(("link", (item.source, item.target)))
                return
        self.on_select(None)

    def _status(self, message):
        if self.on_status is not None:
            self.on_status(message)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.pending is not None:
            self.pending = None
            self._status("Connexion annulée.")
            event.accept()
            return
        selected = self.canvas.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], GraphNode):
            item = selected[0]
            steps = {Qt.Key_Left: (-12, 0), Qt.Key_Right: (12, 0),
                     Qt.Key_Up: (0, -12), Qt.Key_Down: (0, 12)}
            if event.key() in steps:
                old = QPointF(item.pos())
                dx, dy = steps[event.key()]
                item.moveBy(dx, dy)
                self.node_dragged((item.category, item.identifier), old, item.pos())
                event.accept()
                return
        super().keyPressEvent(event)
