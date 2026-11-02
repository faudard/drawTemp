"""R5 visual 2D material palette; no independent map or file format."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QLabel, QWidget

from drawtemp.assets.topdown_tileset import atlas_rect, starter_tileset_png
from drawtemp.render.autotile2d import MATERIALS


class TopDownTilesetDock(QWidget):
    """Show real RGBA atlas swatches and select a canonical terrain brush."""

    materialSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Tileset 2D — Ground")
        label.setAccessibleName("2D Tileset palette")
        layout.addWidget(label)
        self.items = QListWidget(self)
        self.items.setObjectName("r5-topdown-tileset")
        self.items.setViewMode(QListWidget.IconMode)
        self.items.setFlow(QListWidget.LeftToRight)
        self.items.setResizeMode(QListWidget.Adjust)
        self.items.setWrapping(True)
        self.items.setIconSize(QSize(56, 56))
        self.items.setSpacing(6)
        self.items.setMovement(QListWidget.Static)
        self.items.setSelectionMode(QListWidget.SingleSelection)
        self.items.setAccessibleName("2D terrain textures")
        sheet = QImage()
        if not sheet.loadFromData(starter_tileset_png(), "PNG"):
            raise RuntimeError("Unable to load the default 2D tileset")
        for material in MATERIALS:
            x, y, w, h = atlas_rect(material, 0)
            item = QListWidgetItem(QIcon(QPixmap.fromImage(sheet.copy(x, y, w, h))),
                                   material.title(), self.items)
            item.setData(Qt.UserRole, material)
            item.setToolTip("Paint " + material)
        self.items.currentItemChanged.connect(self._selected)
        layout.addWidget(self.items, 1)
        hint = QLabel("AutoTile: neighboring terrain edges and corners blend automatically.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _selected(self, item, _previous):
        if item is not None:
            self.materialSelected.emit(item.data(Qt.UserRole))

    def set_material(self, material):
        for i in range(self.items.count()):
            item = self.items.item(i)
            if item.data(Qt.UserRole) == material:
                self.items.blockSignals(True)
                self.items.setCurrentItem(item)
                self.items.blockSignals(False)
                return
