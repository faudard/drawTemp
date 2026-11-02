"""Qt Widgets authoring controls for actual 2D project visual layers.

Distinct from the legacy R5 functional map-layer visibility/lock dock.
All mutations go through one AuthoringSession transaction and Undo/Redo.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QSlider, QSpinBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from sporebound.visual_layers import PLANES


class VisualLayersDock(QWidget):
    MODES = ("Terrain", "Layer Paint", "Mask Paint", "Layer Erase")

    def __init__(self, editor, on_change, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.on_change = on_change
        self._building = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.addWidget(QLabel("2D graphical layers · bottom to top"))
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("r5-graphic-layers")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Layer", "Eye", "Lock"])
        self.tree.setRootIsDecorated(False)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.itemSelectionChanged.connect(self._selected_changed)
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        for title, callback, name in (
            ("+", self.add_layer, "r5-layer-add"),
            ("−", self.delete_layer, "r5-layer-remove"),
            ("↑", lambda: self.reorder(1), "r5-layer-up"),
            ("↓", lambda: self.reorder(-1), "r5-layer-down"),
        ):
            button = QPushButton(title)
            button.setObjectName(name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)

        settings = QFormLayout()
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setObjectName("r5-graphic-opacity")
        self.opacity.setRange(0, 100)
        # Commit on release instead of flooding the shared Undo history with
        # one authoritative project transaction per mouse-move pixel.
        self.opacity.valueChanged.connect(self._opacity_changed)
        self.opacity.sliderReleased.connect(
            lambda: self._opacity_changed(self.opacity.value()))
        settings.addRow("Opacity", self.opacity)
        self.plane = QComboBox()
        self.plane.setObjectName("r5-graphic-plane")
        self.plane.addItem("Below actors", "below")
        self.plane.addItem("Above actors", "above")
        self.plane.currentIndexChanged.connect(self._plane_changed)
        settings.addRow("Depth", self.plane)
        layout.addLayout(settings)

        layout.addWidget(QLabel("Paint target"))
        self.mode = QComboBox()
        self.mode.setObjectName("r5-graphic-brush-mode")
        self.mode.addItems(self.MODES)
        layout.addWidget(self.mode)
        layout.addWidget(QLabel("Quadrant alpha mask (0 transparent → 255 opaque)"))
        self.quarters = {}
        masks = QFormLayout()
        for quadrant in ("NW", "NE", "SW", "SE"):
            input_ = QSpinBox()
            input_.setObjectName("r5-mask-" + quadrant.lower())
            input_.setRange(0, 255)
            input_.setValue(255)
            self.quarters[quadrant] = input_
            masks.addRow(quadrant, input_)
        layout.addLayout(masks)
        message = QLabel(
            "Painting and mask edits apply to the selected unlocked layer. "
            "Each stroke is one Undo step. Gameplay terrain and collisions "
            "are unaffected. Masks edit the four quarters of a graphic cell.")
        message.setWordWrap(True)
        layout.addWidget(message)
        self.refresh()

    def set_editor(self, editor):
        self.editor = editor
        self.refresh()

    def selected_id(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def mask_values(self):
        return [self.quarters[key].value() for key in ("NW", "NE", "SW", "SE")]

    def editing(self):
        return self.mode.currentText() != "Terrain"

    def _apply(self, fn):
        try:
            result = fn()
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Visual layer edit rejected", str(exc))
            self.refresh()
            return False
        self.refresh()
        self.on_change()
        return result

    def refresh(self):
        selected = self.selected_id()
        layers = self.editor.layers()
        self._building = True
        self.tree.blockSignals(True)
        self.tree.clear()
        # Show the highest layer first, while preserving bottom-to-top model.
        for layer in reversed(layers):
            item = QTreeWidgetItem(self.tree)
            item.setText(0, layer["name"])
            item.setData(0, Qt.UserRole, layer["id"])
            item.setCheckState(1, Qt.Checked if layer["visible"] else Qt.Unchecked)
            item.setCheckState(2, Qt.Checked if layer["locked"] else Qt.Unchecked)
            if layer["id"] == selected:
                self.tree.setCurrentItem(item)
        if selected is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.tree.blockSignals(False)
        self._building = False
        self._selected_changed()

    def _selected_changed(self):
        selected = self.selected_id()
        layer = next((l for l in self.editor.layers() if l["id"] == selected), None)
        self._building = True
        self.opacity.setEnabled(layer is not None)
        self.plane.setEnabled(layer is not None)
        self.opacity.setValue(layer["opacity"] if layer else 100)
        self.plane.setCurrentIndex(
            self.plane.findData(layer["plane"]) if layer else 0)
        self._building = False

    def add_layer(self):
        name, accepted = QInputDialog.getText(self, "New visual layer", "Name",
                                               text="Decoration")
        if not accepted or not name.strip():
            return
        current = self.editor.layers()
        ids = {l["id"] for l in current}
        stem = "".join(c.lower() if c.isascii() and c.isalnum() else "_"
                       for c in name.strip()).strip("_")[:40]
        stem = stem if stem and stem[0].isalpha() else "layer"
        identifier = stem
        suffix = 2
        while identifier in ids:
            identifier = f"{stem[:38]}_{suffix}"
            suffix += 1
        if self._apply(lambda: self.editor.create(identifier, name.strip())) is not False:
            self.refresh()
            self.tree.setCurrentItem(next(
                self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                if self.tree.topLevelItem(i).data(0, Qt.UserRole) == identifier))

    def delete_layer(self):
        ident = self.selected_id()
        if not ident:
            return
        if QMessageBox.question(
                self, "Remove visual layer", f"Delete layer {ident} and its sprites?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self._apply(lambda: self.editor.remove(ident))

    def reorder(self, direction):
        ident = self.selected_id()
        if ident:
            self._apply(lambda: self.editor.reorder(ident, direction))

    def _item_changed(self, item, column):
        if self._building or column not in (1, 2):
            return
        ident = item.data(0, Qt.UserRole)
        value = item.checkState(column) == Qt.Checked
        if column == 1:
            self._apply(lambda: self.editor.configure(ident, visible=value))
        else:
            self._apply(lambda: self.editor.configure(ident, locked=value))

    def _opacity_changed(self, value):
        if self.opacity.isSliderDown():
            return
        if not self._building and self.selected_id():
            self._apply(lambda: self.editor.configure(
                self.selected_id(), opacity=value))

    def _plane_changed(self, _index):
        if not self._building and self.selected_id():
            ident = self.selected_id()
            plane = self.plane.currentData()
            self._apply(lambda: self.editor.configure(ident, plane=plane))
