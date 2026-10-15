"""Optional Qt Widgets asset browser shared by future Studio and Player tooling.

The browser consumes GameProject.asset_registry() IDs, never writes gameplay
content, and exports a stable MIME ID for map/character drag-and-drop.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .catalog import AssetIndex, BrowserPreferences, FAMILIES

MIME_ASSET_ID = "application/x-drawtemp-asset-id"


class DraggableAssetList(QListWidget):
    def mimeData(self, items):
        mime = QMimeData()
        if items:
            asset_id = items[0].data(Qt.ItemDataRole.UserRole)
            if asset_id:
                mime.setData(MIME_ASSET_ID, QByteArray(asset_id.encode("utf-8")))
                mime.setText(asset_id)
        return mime


class AssetBrowser(QWidget):
    """Searchable, grouped icon palette with looping animated preview."""

    def __init__(self, registry, project_root, *, preferences_path=None, parent=None):
        super().__init__(parent)
        self.index = AssetIndex(registry)
        self.root = Path(project_root)
        self.preferences = BrowserPreferences.load(
            preferences_path or self.root / ".drawtemp" / "asset-browser.json")
        self._frame = 0
        self._current = None
        self._frames = ()
        self._thumb_cache = {}
        self.setWindowTitle("DrawTemp 5.0 — Assets")
        self.resize(780, 590)

        layout = QVBoxLayout(self)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un personnage, matériau, effet…")
        self.search.setAccessibleName("Recherche d'assets")
        self.filter = QComboBox()
        self.filter.addItems([*FAMILIES, "favorites", "recents"])
        self.filter.setAccessibleName("Collection d'assets")
        self.favorite = QPushButton("☆ Favori")
        self.favorite.setAccessibleName("Ajouter ou retirer l'asset des favoris")
        tools.addWidget(self.search, stretch=1)
        tools.addWidget(self.filter)
        tools.addWidget(self.favorite)
        layout.addLayout(tools)

        self.items = DraggableAssetList()
        self.items.setViewMode(QListWidget.ViewMode.IconMode)
        self.items.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.items.setIconSize(QSize(90, 90))
        self.items.setGridSize(QSize(150, 136))
        self.items.setMovement(QListWidget.Movement.Static)
        self.items.setDragEnabled(True)
        self.items.setAccessibleName("Vignettes des ressources")
        layout.addWidget(self.items, stretch=1)

        bottom = QHBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(132, 132)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setAccessibleName("Aperçu animé de la ressource sélectionnée")
        self.details = QLabel("Aucune ressource")
        self.details.setWordWrap(True)
        bottom.addWidget(self.preview)
        bottom.addWidget(self.details, stretch=1)
        layout.addLayout(bottom)

        self.clock = QTimer(self)
        self.clock.setSingleShot(True)
        self.clock.timeout.connect(self._next_frame)
        self.search.textChanged.connect(self.refresh)
        self.filter.currentTextChanged.connect(self.refresh)
        self.items.currentItemChanged.connect(self._select)
        self.favorite.clicked.connect(self._favorite)
        self.refresh()

    def _preview(self, asset):
        asset_id = asset["id"]
        if asset_id in self._thumb_cache:
            return self._thumb_cache[asset_id]
        try:
            path = self.index.registry.resolve(asset_id, self.root)
            image = QPixmap(str(path))
            if image.isNull():
                raise ValueError("PNG decoder rejected file")
            region = asset.get("region")
            if region:
                x, y, w, h = region
                if x + w > image.width() or y + h > image.height():
                    raise ValueError("Region exceeds decoded PNG")
                image = image.copy(x, y, w, h)
            image = image.scaled(112, 112,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        except (OSError, ValueError, RuntimeError, Exception) as exc:
            image = QPixmap(112, 112)
            image.fill(QColor("#334155"))
            painter = QPainter(image)
            painter.setPen(QColor("#ffcead"))
            painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Asset\nindisponible")
            painter.end()
            self.details.setToolTip(str(exc))
        self._thumb_cache[asset_id] = image
        return image

    def refresh(self, *_):
        selected = self._current
        self.items.blockSignals(True)
        self.items.clear()
        cards = self.index.find(
            self.search.text(), self.filter.currentText(),
            favorites=self.preferences.favorites, recents=self.preferences.recents)
        for card in cards:
            row = QListWidgetItem(QIcon(self._preview(self.index.registry.require_reference(
                card.preview_id))), card.label)
            row.setData(Qt.ItemDataRole.UserRole, card.id)
            row.setToolTip(f"{card.kind} • {card.family} • {card.frame_count} frame(s)")
            self.items.addItem(row)
        self.items.blockSignals(False)
        for position in range(self.items.count()):
            if self.items.item(position).data(Qt.ItemDataRole.UserRole) == selected:
                self.items.setCurrentRow(position)
                break
        else:
            if self.items.count():
                self.items.setCurrentRow(0)
            else:
                self._current = None
                self._frames = ()
                self.clock.stop()
                self.details.setText("Aucune ressource")
                self.preview.clear()

    def _select(self, item, previous=None):
        self.clock.stop()
        self._frame = 0
        if item is None:
            return
        self._current = item.data(Qt.ItemDataRole.UserRole)
        self._frames = self.index.frames(self._current)
        self.preferences.visit(self._current)
        entry = self.index.registry.require_reference(self._current)
        self.details.setText(f"ID : {self._current}\nType : {entry['kind']}\n"
                             f"Images : {len(self._frames)}")
        self.favorite.setText("★ Favori" if self._current in self.preferences.favorites
                              else "☆ Favori")
        self._next_frame()

    def _next_frame(self):
        if not self._frames:
            self.preview.clear()
            return
        sprite, duration = self._frames[self._frame]
        self.preview.setPixmap(self._preview(sprite))
        if len(self._frames) > 1:
            self._frame = (self._frame + 1) % len(self._frames)
            self.clock.start(duration)

    def _favorite(self):
        if self._current is not None:
            self.preferences.favorite(self._current)
            self.favorite.setText("★ Favori" if self._current in self.preferences.favorites
                                  else "☆ Favori")
            if self.filter.currentText() == "favorites":
                self.refresh()


def main(argv=None):
    import argparse
    from sporebound.model import Content
    from sporebound.game_project import GameProject
    from sporebound.__main__ import DEFAULT_CONTENT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    args = parser.parse_args(argv)
    content = Content.load(args.content)
    project = GameProject.load(args.project, content)
    app = QApplication.instance() or QApplication([])
    widget = AssetBrowser(project.asset_registry(), args.project.parent)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
