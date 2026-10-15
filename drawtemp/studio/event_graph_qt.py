"""R9.C editable Qt graph surface backed by canonical Mission.triggers.

Dragging a card changes only view-local layout. Clicking two cards in Connect
mode issues one validated authoring link; lines do NOT become serialized nodes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsTextItem, QGraphicsView)


class EventGraphView(QGraphicsView):
    eventSelected = Signal(str)
    connectRequested = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(self.renderHints() | __import__(
            "PySide6.QtGui", fromlist=["QPainter"]).QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._positions = {}
        self._cards = {}
        self._lines = []
        self._mission = ""
        self._connect_mode = False
        self._any_of = False
        self._pending = ""
        self._pressed = None

    def set_connect_mode(self, enabled, *, any_of=False):
        self._connect_mode = bool(enabled)
        self._any_of = bool(any_of)
        self._pending = ""

    def render_events(self, events, mission_id, *, selected_id=""):
        self._mission = mission_id
        scene = self.scene()
        scene.clear()
        self._cards.clear()
        self._lines.clear()
        self._pending = ""
        for index, event in enumerate(events):
            eid = event["id"]
            key = (mission_id, eid)
            x, y = self._positions.get(key, (40 + (index % 3)*348,
                                              40 + (index // 3)*188))
            rect = QGraphicsRectItem(0, 0, 302, 128)
            rect.setData(0, eid)
            rect.setPos(x, y)
            rect.setFlag(QGraphicsItem.ItemIsMovable, True)
            rect.setFlag(QGraphicsItem.ItemIsSelectable, True)
            rect.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
            focused = eid == selected_id
            rect.setPen(QPen(QColor("#efc970" if focused else "#668aaf"), 2))
            rect.setBrush(QBrush(QColor("#29425d" if focused else "#1d3041")))
            scene.addItem(rect)
            self._cards[eid] = rect
            titles = [a.get("kind", "?") for a in event.get("actions", ())]
            description = (eid + "\n" + event["condition"] + " · " +
                           str(len(titles)) + " action(s)\n" +
                           ", ".join(titles[:4]))
            label = QGraphicsTextItem(rect)
            label.setPlainText(description)
            label.setTextWidth(282)
            label.setDefaultTextColor(QColor("#ffffff"))
            label.setPos(10, 8)
            label.setAcceptedMouseButtons(Qt.NoButton)

        for event in events:
            for field, any_of in (("after", False), ("after_any", True)):
                for predecessor in event.get(field, ()):
                    if predecessor not in self._cards:
                        continue
                    pen = QPen(QColor("#deb96e" if any_of else "#8fc0e9"), 2)
                    line = scene.addLine(0, 0, 1, 1, pen)
                    line.setZValue(-1)
                    self._lines.append((line, predecessor, event["id"]))
        self._update_edges()
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 80, 80))

    def _update_edges(self):
        for line, predecessor, target in self._lines:
            source = self._cards[predecessor]
            destination = self._cards[target]
            a, b = source.scenePos(), destination.scenePos()
            line.setLine(a.x() + 302, a.y() + 64, b.x(), b.y() + 64)

    def _event_id_at(self, pos):
        item = self.itemAt(pos)
        while item is not None:
            eid = item.data(0)
            if isinstance(eid, str) and eid:
                return eid
            item = item.parentItem()
        return ""

    def mousePressEvent(self, event):
        self._pressed = (self._event_id_at(event.pos()), event.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        for eid, card in self._cards.items():
            p = card.scenePos()
            self._positions[(self._mission, eid)] = (p.x(), p.y())
        self._update_edges()
        if event.button() != Qt.LeftButton or self._pressed is None:
            return
        source_id, start = self._pressed
        self._pressed = None
        moved = abs(event.pos().x()-start.x()) + abs(event.pos().y()-start.y())
        if moved > 7 or not source_id or source_id != self._event_id_at(event.pos()):
            return
        if not self._connect_mode:
            self.eventSelected.emit(source_id)
        elif not self._pending:
            self._pending = source_id
            self.eventSelected.emit(source_id)
        else:
            source, target = self._pending, source_id
            self._pending = ""
            if source != target:
                self.connectRequested.emit(source, target, self._any_of)
