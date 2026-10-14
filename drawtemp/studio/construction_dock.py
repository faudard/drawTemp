"""Opt-in R6 Qt Widgets dock.

Attach to the R2 QMainWindow when available. The R3 viewport should forward
its resolved building-part hits to on_renderer_hit; this dock never draws a
second canvas or translates approximate pixel positions into building IDs.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from drawtemp.sdk.construction import (
    ConstructionPick, ConstructionWorkspace, catalog,
)
from sporebound.building_visuals import FACADES, ROOFS
from sporebound.interior_levels import FLOOR_FEATURES, FLOOR_SURFACES, MAX_INTERIOR_LEVEL


class ConstructionDock(QDockWidget):
    """Working property editor for the shared revisioned construction state."""

    level_changed = Signal(int)
    cutaway_changed = Signal(bool)
    committed = Signal(object)

    def __init__(self, workspace: ConstructionWorkspace, parent=None):
        super().__init__("Construction 2.5D", parent)
        self.workspace = workspace
        self.setObjectName("drawtemp5_construction_dock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root = QWidget()
        layout = QVBoxLayout(root)
        scroll.setWidget(root)
        self.setWidget(scroll)
        self.selected = QLabel("Sélectionner un bâtiment dans la vue isométrique")
        self.selected.setWordWrap(True)
        layout.addWidget(self.selected)

        placement = QGroupBox("Placer une structure")
        form = QFormLayout(placement)
        self.preset = QComboBox()
        for item in catalog():
            self.preset.addItem(item["name"] + "  ·  " +
                                str(item["size"][0]) + "×" + str(item["size"][1]),
                                item["name"])
        form.addRow("Préfabrication", self.preset)
        xy = QWidget()
        xy_layout = QHBoxLayout(xy)
        xy_layout.setContentsMargins(0, 0, 0, 0)
        self.x = QSpinBox()
        self.y = QSpinBox()
        for spin in (self.x, self.y):
            spin.setRange(0, 9999)
        xy_layout.addWidget(self.x)
        xy_layout.addWidget(self.y)
        form.addRow("Case X / Y", xy)
        self.place_button = QPushButton("Placer")
        form.addRow(self.place_button)
        layout.addWidget(placement)

        exterior = QGroupBox("Extérieur")
        ext = QFormLayout(exterior)
        self.facade = QComboBox()
        self.facade.addItems(FACADES)
        self.roof = QComboBox()
        self.roof.addItems(ROOFS)
        self.door = QComboBox()
        ext.addRow("Façade", self.facade)
        ext.addRow("Toiture", self.roof)
        ext.addRow("Porte", self.door)
        self.material_button = QPushButton("Appliquer les matériaux")
        self.door_button = QPushButton("Déplacer la porte")
        self.window_add = QPushButton("Ajouter fenêtre au mur sélectionné")
        self.window_remove = QPushButton("Retirer cette fenêtre")
        ext.addRow(self.material_button)
        ext.addRow(self.door_button)
        ext.addRow(self.window_add)
        ext.addRow(self.window_remove)
        layout.addWidget(exterior)

        interiors = QGroupBox("Intérieurs")
        floor_form = QFormLayout(interiors)
        self.level = QComboBox()
        self.level.addItem("Rez-de-chaussée", 0)
        self.surface = QComboBox()
        self.surface.addItems(sorted(FLOOR_SURFACES))
        self.feature = QComboBox()
        self.feature.addItems(sorted(FLOOR_FEATURES))
        floor_form.addRow("Étage actif", self.level)
        self.add_floor = QPushButton("Ajouter l'étage suivant")
        self.remove_floor = QPushButton("Supprimer cet étage")
        floor_form.addRow(self.add_floor)
        floor_form.addRow(self.remove_floor)
        floor_form.addRow("Sol", self.surface)
        floor_form.addRow("Mobilier", self.feature)
        self.paint_floor = QPushButton("Peindre la case sélectionnée")
        floor_form.addRow(self.paint_floor)
        layout.addWidget(interiors)

        self.cutaway = QPushButton("Afficher la coupe de toiture")
        self.cutaway.setCheckable(True)
        layout.addWidget(self.cutaway)
        line = QHBoxLayout()
        self.undo = QPushButton("Annuler")
        self.redo = QPushButton("Rétablir")
        self.delete = QPushButton("Supprimer la structure")
        for button in (self.undo, self.redo, self.delete):
            line.addWidget(button)
        layout.addLayout(line)
        layout.addStretch(1)

        self.place_button.clicked.connect(self._place)
        self.material_button.clicked.connect(
            lambda: self._apply(lambda: self.workspace.preview_material(
                facade=self.facade.currentText(), roof=self.roof.currentText())))
        self.door_button.clicked.connect(
            lambda: self._apply(lambda: self.workspace.preview_door(
                self.door.currentData())))
        self.window_add.clicked.connect(
            lambda: self._window(True))
        self.window_remove.clicked.connect(
            lambda: self._window(False))
        self.level.currentIndexChanged.connect(self._change_floor)
        self.add_floor.clicked.connect(self._add_floor)
        self.remove_floor.clicked.connect(
            lambda: self._apply(lambda: self.workspace.preview_floor_remove(
                self.workspace.active_level)))
        self.paint_floor.clicked.connect(self._paint_floor)
        self.cutaway.toggled.connect(self._toggle_cutaway)
        self.delete.clicked.connect(
            lambda: self._apply(self.workspace.preview_remove))
        self.undo.clicked.connect(lambda: self._history(self.workspace.undo))
        self.redo.clicked.connect(lambda: self._history(self.workspace.redo))
        self.refresh()

    def on_renderer_hit(self, structure_id, anchor, cell, part):
        """Bind to renderer click handling *after* real R3 geometry picking.

        A null ID clears selection. All other clicks are revalidated against
        the canonical structure footprint and current document revision.
        """
        try:
            if not structure_id:
                self.workspace.select(None)
            else:
                self.workspace.select(ConstructionPick(
                    structure_id, tuple(anchor), tuple(cell), part))
        except (ValueError, TypeError) as exc:
            self.workspace.clear_selection()
            QMessageBox.warning(self, "Sélection invalide", str(exc))
        self.refresh()

    def _apply(self, builder):
        try:
            result = self.workspace.apply(builder())
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Construction refusée", str(exc))
            return
        self.committed.emit(result)
        self.refresh()

    def _history(self, operation):
        try:
            result = operation()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Historique", str(exc))
            return
        self.committed.emit(result)
        self.refresh()

    def _place(self):
        self._apply(lambda: self.workspace.preview_place(
            self.preset.currentData(), (self.x.value(), self.y.value())))

    def _window(self, present):
        if self.workspace.pick is None:
            return
        self._apply(lambda: self.workspace.preview_window(
            self.workspace.pick.cell, present=present))

    def _change_floor(self):
        level = self.level.currentData()
        if level is None:
            return
        try:
            self.workspace.set_level(level)
            self.level_changed.emit(level)
        except ValueError as exc:
            QMessageBox.warning(self, "Étage", str(exc))

    def _add_floor(self):
        if self.workspace.pick is None:
            return
        levels = self.workspace.inspect().levels
        nxt = max(levels, default=0) + 1
        if nxt <= MAX_INTERIOR_LEVEL:
            self._apply(lambda: self.workspace.preview_floor_add(nxt))

    def _paint_floor(self):
        if not self.workspace.pick or self.workspace.active_level == 0:
            return
        self._apply(lambda: self.workspace.preview_floor_tile(
            self.workspace.active_level, self.workspace.pick.cell,
            surface=self.surface.currentText(),
            feature=self.feature.currentText()))

    def _toggle_cutaway(self, enabled):
        self.workspace.set_cutaway(enabled)
        self.cutaway_changed.emit(enabled)

    def refresh(self):
        info = self.workspace.inspect() if self.workspace.pick else None
        if info:
            self.selected.setText(
                info.name + " · " + info.structure_id + " · (" +
                str(info.anchor[0]) + ", " + str(info.anchor[1]) + ") · " +
                info.selected_part)
        else:
            self.selected.setText("Sélectionner un bâtiment dans la vue isométrique")
        supports_exterior = bool(info and info.facade is not None)
        for widget in (self.facade, self.roof, self.material_button,
                       self.door, self.door_button, self.window_add, self.window_remove):
            widget.setEnabled(supports_exterior)
        self.window_add.setEnabled(supports_exterior and bool(info and
                                  info.selected_part in ("facade", "window")))
        self.window_remove.setEnabled(supports_exterior and bool(info and
                                     info.selected_part == "window"))
        self.door.clear()
        if info and supports_exterior:
            from sporebound.iso_structures import door_slots
            for index in range(len(door_slots(info.name))):
                self.door.addItem("Entrée " + str(index + 1), index)
            self.door.setCurrentIndex(info.door_slot)
            self.facade.setCurrentText(info.facade)
            self.roof.setCurrentText(info.roof)
        self.level.blockSignals(True)
        self.level.clear()
        self.level.addItem("Rez-de-chaussée", 0)
        for number in (info.levels if info else ()):
            self.level.addItem("Étage " + str(number), number)
        index = self.level.findData(self.workspace.active_level)
        self.level.setCurrentIndex(max(0, index))
        self.level.blockSignals(False)
        interior = bool(info and info.name in ("Maison", "Tour", "Ruines"))
        self.add_floor.setEnabled(interior and
                                  max(info.levels, default=0) < MAX_INTERIOR_LEVEL
                                  if info else False)
        self.remove_floor.setEnabled(bool(info and info.active_level > 0))
        self.paint_floor.setEnabled(bool(info and info.active_level > 0))
        self.delete.setEnabled(bool(info))
        snapshot = self.workspace.authoring.snapshot()
        self.undo.setEnabled(snapshot.can_undo)
        self.redo.setEnabled(snapshot.can_redo)
