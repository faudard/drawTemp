"""R5.6 Qt Widgets layer dock; presentation settings never rewrite Content."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QHBoxLayout, QLabel, QSlider, QSpinBox, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .map_layers import LAYERS


class MapLayersDock(QWidget):
    """Visibility, locks, active floor and transient per-layer opacity."""

    def __init__(self, workspace, on_change, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.on_change = on_change
        self.mission_id = ""
        self._building = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        summary = QLabel("Calques métier · indépendants de la profondeur isométrique")
        summary.setWordWrap(True)
        outer.addWidget(summary)
        self.tree = QTreeWidget()
        self.tree.setObjectName("r5_layers_tree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(("Calque", "Visible", "Verrouillé"))
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2):
            self.tree.header().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        outer.addWidget(self.tree, 1)

        fade_row = QHBoxLayout()
        fade_row.addWidget(QLabel("Opacité"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setObjectName("r5_layer_opacity")
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity.setEnabled(False)
        fade_row.addWidget(self.opacity, 1)
        self.opacity_label = QLabel("100 %")
        fade_row.addWidget(self.opacity_label)
        outer.addLayout(fade_row)
        hint = QLabel("L'opacité est temporaire pendant cette session ; visibilité, "
                      "verrouillage et étage actif sont enregistrés avec le projet.")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Étage actif"))
        self.level = QSpinBox()
        self.level.setObjectName("r5_active_level")
        self.level.setRange(0, 3)
        level_row.addWidget(self.level)
        outer.addLayout(level_row)

        self.tree.itemChanged.connect(self._changed_item)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.opacity.valueChanged.connect(self._change_opacity)
        self.level.valueChanged.connect(self._change_level)

    def set_workspace(self, workspace):
        self.workspace = workspace
        self.refresh()

    def set_mission(self, mission_id):
        if self.mission_id != mission_id:
            self.mission_id = mission_id
            self.refresh()

    def refresh(self):
        if not self.mission_id:
            return
        selected = self.selected_layer()
        view = self.workspace.view(self.mission_id)
        self._building = True
        self.tree.blockSignals(True)
        self.tree.clear()
        for name in LAYERS:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, name)
            item.setData(0, Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            item.setCheckState(1, Qt.Checked if view["visible"][name] else Qt.Unchecked)
            item.setCheckState(2, Qt.Checked if view["locked"][name] else Qt.Unchecked)
            if name == selected:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        self.level.blockSignals(True)
        self.level.setValue(view["active_level"])
        self.level.blockSignals(False)
        self._building = False
        self._selection_changed()

    def selected_layer(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _changed_item(self, item, column):
        if self._building or column not in (1, 2):
            return
        layer = item.data(0, Qt.UserRole)
        enabled = item.checkState(column) == Qt.Checked
        if column == 1:
            self.workspace.set_visible(self.mission_id, layer, enabled)
        else:
            self.workspace.set_locked(self.mission_id, layer, enabled)
        self.on_change()

    def _selection_changed(self):
        layer = self.selected_layer()
        self.opacity.setEnabled(layer is not None)
        self.opacity.blockSignals(True)
        value = self.workspace.view(self.mission_id)["opacity"].get(layer, 100) if layer else 100
        self.opacity.setValue(value)
        self.opacity_label.setText(str(value) + " %")
        self.opacity.blockSignals(False)

    def _change_opacity(self, value):
        layer = self.selected_layer()
        if layer is None:
            return
        self.workspace.set_opacity(self.mission_id, layer, value)
        self.opacity_label.setText(str(value) + " %")
        self.on_change()

    def _change_level(self, level):
        if self.mission_id:
            self.workspace.set_level(self.mission_id, level)
            self.on_change()
