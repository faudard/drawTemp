"""R5.5 illustrated Qt map-paint palette with validated MIME drag/drop."""
from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QDrag, QIcon, QPainter, QPen, QPixmap, QPolygon,
)
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from .map_palette import CATALOG, MIME_BRUSH, find_cards, require_brush
from sporebound.terrain_watercolor import TILE_WIDTH, TILE_HEIGHT, watercolor_atlas_png
from sporebound.environment_atlas import environment_strip_png, FRAME_SIZE


class BrushList(QListWidget):
    def startDrag(self, supportedActions):
        row = self.currentItem()
        if row is None:
            return
        brush = require_brush(row.data(Qt.UserRole))
        mime = QMimeData()
        mime.setData(MIME_BRUSH, QByteArray(brush.encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(row.icon().pixmap(self.iconSize()))
        drag.exec(Qt.CopyAction)


class MapPaletteDock(QWidget):
    brushSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = "surface:grass"
        self._icon_cache = {}
        source = files("sporebound").joinpath("content/art/iso/terrain.png")
        atlas = QPixmap(str(source)) if source.is_file() else QPixmap()
        if atlas.isNull() or atlas.width() != 16*TILE_WIDTH or atlas.height() != TILE_HEIGHT:
            atlas.loadFromData(watercolor_atlas_png(), "PNG")
        self._atlas = atlas
        self._decor_atlas = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        heading = QLabel("Palette de matériaux et de décors")
        root.addWidget(heading)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("r5_palette_search")
        self.search.setPlaceholderText("Rechercher herbe, arbre, roche…")
        self.search.setAccessibleName("Rechercher dans les carreaux")
        self.family = QComboBox()
        self.family.setObjectName("r5_palette_family")
        self.family.addItems(("Tous", "Terrain", "Décors"))
        filters.addWidget(self.search, 1)
        filters.addWidget(self.family)
        root.addLayout(filters)
        self.items = BrushList()
        self.items.setObjectName("r5_palette_tiles")
        self.items.setViewMode(QListWidget.IconMode)
        self.items.setResizeMode(QListWidget.Adjust)
        self.items.setMovement(QListWidget.Static)
        self.items.setDragEnabled(True)
        self.items.setIconSize(QSize(100, 72))
        self.items.setGridSize(QSize(130, 114))
        self.items.setSpacing(3)
        self.items.setAccessibleName("Palette graphique de terrain et décors")
        root.addWidget(self.items, 1)
        self.selected_label = QLabel("")
        self.selected_label.setWordWrap(True)
        root.addWidget(self.selected_label)
        self.search.textChanged.connect(self.refresh)
        self.family.currentTextChanged.connect(self.refresh)
        self.items.currentItemChanged.connect(self._select)
        self.refresh()

    @property
    def current_brush(self):
        return self._current

    def select_brush(self, brush):
        require_brush(brush)
        self._current = brush
        self.refresh()

    def refresh(self, *_):
        self.items.blockSignals(True)
        self.items.clear()
        current_row = None
        for card in find_cards(self.search.text(), self.family.currentText()):
            item = QListWidgetItem(QIcon(self._thumbnail(card)), card.label)
            item.setData(Qt.UserRole, card.id)
            item.setToolTip(card.id + " • " + card.family + "\nGlisser sur la carte pour peindre")
            self.items.addItem(item)
            if card.id == self._current:
                current_row = item
        if current_row is not None:
            self.items.setCurrentItem(current_row)
        self.items.blockSignals(False)
        self.selected_label.setText("Pinceau : " + self._current
                                    + " — cliquer ou glisser une vignette sur la carte")

    def _select(self, item, previous=None):
        if item is None:
            return
        selected = require_brush(item.data(Qt.UserRole))
        if selected != self._current:
            self._current = selected
            self.selected_label.setText("Pinceau : " + selected)
            self.brushSelected.emit(selected)

    def _thumbnail(self, card):
        if card.id in self._icon_cache:
            return self._icon_cache[card.id]
        pixmap = QPixmap(100, 72)
        pixmap.fill(QColor("#1c2b35"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(3, 3, 94, 66, QColor("#324453"))
        if card.atlas_index is not None:
            source = self._atlas.copy(card.atlas_index*TILE_WIDTH, 0,
                                      TILE_WIDTH, TILE_HEIGHT)
            painter.drawPixmap(2, 12, 96, 48, source)
        else:
            # The ground is the same watercolour atlas; vegetation uses the
            # real procedurally generated R4 illustration, not emoji.
            ground = self._atlas.copy(0, 0, TILE_WIDTH, TILE_HEIGHT)
            painter.drawPixmap(2, 18, 96, 48, ground)
            kind = "reeds" if card.token == "reeds" else (
                "leaves" if card.token in ("tree", "bush") else None)
            if kind:
                if kind not in self._decor_atlas:
                    sprite = QPixmap()
                    sprite.loadFromData(environment_strip_png(kind), "PNG")
                    self._decor_atlas[kind] = sprite
                sprite = self._decor_atlas[kind].copy(0, 0, FRAME_SIZE, FRAME_SIZE)
                if card.token == "tree":
                    painter.setPen(QPen(QColor("#614c38"), 9))
                    painter.drawLine(50, 50, 50, 29)
                painter.drawPixmap(24, 3, 52, 52, sprite)
            else:
                painter.setPen(QPen(QColor("#f3e2bd"), 3))
                painter.setBrush(QColor("#b5a18b"))
                if card.token in ("boulder", "ruin", "stone_wall", "pillar"):
                    points = QPolygon()
                    from PySide6.QtCore import QPoint
                    for x, y in ((25, 47), (32, 20), (58, 15),
                                 (76, 43), (60, 54), (34, 53)):
                        points.append(QPoint(x, y))
                    painter.drawPolygon(points)
                elif card.token == "fence":
                    for x in (30, 48, 66):
                        painter.drawLine(x, 18, x, 52)
                    painter.drawLine(25, 32, 71, 32)
                elif card.token == "arch":
                    painter.drawArc(30, 12, 40, 48, 0, 180*16)
                    painter.drawLine(30, 34, 30, 60)
                    painter.drawLine(70, 34, 70, 60)
                else:
                    painter.drawRoundedRect(30, 19, 40, 36, 4, 4)
                painter.setPen(QColor("#fff3d5"))
                painter.drawText(10, 68, card.token[:14])
        painter.end()
        self._icon_cache[card.id] = pixmap
        return pixmap
