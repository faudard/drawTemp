"""R11 drag handles for Qt timeline.

One gesture produces one immutable, validated document edit at mouse release.
Scene items are intentionally disposable: a rebuild happens after commit.
"""
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsPolygonItem,
    QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsView,
)

from drawtemp.cinematics.timeline import TimelineScale


class TimelineView(QGraphicsView):
    cursorRequested = Signal(int)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.scale = None
        self.setRenderHint(QPainter.Antialiasing, True)

    def mousePressEvent(self, event):
        point = self.mapToScene(event.pos())
        item = self.scene().itemAt(point, self.transform())
        # Descendants of a movable block are still part of that block.
        while item is not None and not isinstance(item, TimelineBlock):
            item = item.parentItem()
        if (event.button() == Qt.LeftButton and item is None
                and self.scale is not None and point.x() >= self.scale.origin_x):
            self.cursorRequested.emit(self.scale.seek(point.x()))
        super().mousePressEvent(event)


class TimelineBlock(QGraphicsRectItem):
    def __init__(self, event, scale, lane_y, revision, move_callback, color):
        super().__init__(0, 0, max(5, scale.width_for(event["duration_ms"])), 21)
        self.event_id = event["id"]
        self.original_ms = event["start_ms"]
        self.event_duration = event["duration_ms"]
        self.scale = scale
        self.base_revision = revision
        self.move_callback = move_callback
        self.lane_y = lane_y
        self.setPos(scale.time_to_x(self.original_ms), lane_y)
        self.setPen(QPen(QColor("#253246")))
        self.setBrush(QBrush(QColor(color)))
        self.setData(0, self.event_id)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setToolTip("Glisser horizontalement pour déplacer · 100 ms par pas")
        caption = QGraphicsSimpleTextItem(self.event_id, self)
        caption.setBrush(QBrush(QColor("#f5f1e9")))
        caption.setPos(4, 1)
        caption.setAcceptedMouseButtons(Qt.NoButton)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
            max_start = self.scale.duration_ms - self.event_duration
            x = min(self.scale.time_to_x(max_start),
                    max(self.scale.origin_x, value.x()))
            return QPointF(x, self.lane_y)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._pressed_x = self.pos().x()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if abs(self.pos().x() - getattr(self, "_pressed_x", self.pos().x())) < 2:
            return  # Selection never snaps an existing unsnapped event.
        target = self.scale.absolute(self.pos().x(), self.event_duration)
        if target == self.original_ms:
            self.setPos(self.scale.time_to_x(self.original_ms), self.lane_y)
        else:
            # Never mutate the scene while QGraphicsScene is dispatching release.
            QTimer.singleShot(0, lambda: self.move_callback(
                self.event_id, target, self.base_revision))


class TimelineKeyframe(QGraphicsPolygonItem):
    def __init__(self, event, key, scale, parent, revision, move_callback):
        shape = QPolygonF([QPointF(-6, 0), QPointF(0, -6),
                           QPointF(6, 0), QPointF(0, 6)])
        super().__init__(shape, parent)
        self.event_id = event["id"]
        self.old_local = key["at_ms"]
        self.start_ms = event["start_ms"]
        self.event_duration = event["duration_ms"]
        self.scale = scale
        self.base_revision = revision
        self.move_callback = move_callback
        self.track_width = scale.width_for(event["duration_ms"])
        self.setPos(scale.width_for(key["at_ms"]), 10)
        self.setPen(QPen(QColor("#f6e8ca")))
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setZValue(3)
        self.setData(0, self.event_id)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setToolTip("Glisser le losange pour déplacer l'image-clé")

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
            return QPointF(min(self.track_width - 0.1,
                               max(0.1, value.x())), 10)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        # Selection belongs to this handle; moving a key never moves its track.
        self._pressed_x = self.pos().x()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if abs(self.pos().x() - getattr(self, "_pressed_x", self.pos().x())) < 2:
            return
        absolute_x = self.parentItem().pos().x() + self.pos().x()
        target = self.scale.local_key(absolute_x, self.start_ms,
                                      self.event_duration)
        if target == self.old_local:
            self.setPos(self.scale.width_for(self.old_local), 10)
        else:
            QTimer.singleShot(0, lambda: self.move_callback(
                self.event_id, self.old_local, target, self.base_revision))
