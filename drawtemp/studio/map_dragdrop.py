"""R5.5 native Qt drop target for the shared R3 Quick viewport.

Only canonical brush MIME payloads are accepted. No file URLs, arbitrary
project paths or untrusted asset references can be introduced by drag/drop.
"""
from PySide6.QtCore import Signal
from PySide6.QtQuickWidgets import QQuickWidget

from .map_palette import MIME_BRUSH, require_brush


class MapDropViewport(QQuickWidget):
    brushHovered = Signal(str, int, int)
    brushDropped = Signal(str, int, int)
    dragEnded = Signal()

    def __init__(self, renderer, parent=None):
        super().__init__(parent)
        self.renderer = renderer
        self.setAcceptDrops(True)

    @staticmethod
    def _brush(event):
        mime = event.mimeData()
        if not mime.hasFormat(MIME_BRUSH):
            return None
        try:
            raw = bytes(mime.data(MIME_BRUSH)).decode("utf-8", errors="strict")
            if len(raw) > 128:
                return None
            return require_brush(raw)
        except (UnicodeError, ValueError):
            return None

    def _cell(self, event):
        pos = event.position()
        cell = self.renderer.cellAt(pos.x(), pos.y())
        if isinstance(cell, dict) and "x" in cell and "y" in cell:
            return cell["x"], cell["y"]
        return None

    def dragEnterEvent(self, event):
        if self._brush(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        brush = self._brush(event)
        cell = self._cell(event)
        if brush is not None and cell is not None:
            self.brushHovered.emit(brush, *cell)
            event.acceptProposedAction()
        else:
            event.ignore()
            self.dragEnded.emit()

    def dragLeaveEvent(self, event):
        self.dragEnded.emit()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        brush = self._brush(event)
        cell = self._cell(event)
        if brush is None or cell is None:
            event.ignore()
        else:
            self.brushDropped.emit(brush, *cell)
            event.acceptProposedAction()
        self.dragEnded.emit()
