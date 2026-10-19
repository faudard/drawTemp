"""R32.C Qt collider authoring panel, embedded in the existing Gameplay workspace.

QGraphicsView is only an authoring/debug overlay: never the Player renderer.
All edits use the shared R1 AuthoringSession (preview/apply/undo/redo).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from drawtemp.studio.platform_collider_authoring import (
    ColliderAuthoringError, PlatformColliderStudio,
)
from drawtemp.sdk.authoring import AuthoringError
from sporebound.model import RuleError


def _spin(value, *, minimum=0, maximum=128000):
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setSingleStep(100)
    widget.setValue(value)
    return widget


class ColliderEditorPanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setObjectName("r32-collider-editor")
        self.studio = PlatformColliderStudio(session)
        self._pending = None
        self._loading = False
        layout = QVBoxLayout(self)
        label = QLabel("R32.C • Colliders de plateforme (AABB, couches, capteurs)")
        layout.addWidget(label)
        note = QLabel(
            "Édition transactionnelle GameProject. Aperçu 2D de diagnostic ; "
            "pas de rendu Player certifié ni de raccordement R31/CT.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.target = QComboBox()
        self.target.setObjectName("r32-scene-target")
        self.target.setAccessibleName("Scène canonique à éditer")
        form.addRow("Scène", self.target)
        self.collider = QComboBox()
        self.collider.setObjectName("r32-collider-choice")
        self.collider.setAccessibleName("Collider existant")
        form.addRow("Collider", self.collider)
        self.identifier = QLineEdit()
        self.identifier.setObjectName("r32-collider-id")
        self.identifier.setPlaceholderText("id de forme (ex. jump_wall)")
        form.addRow("Identifiant", self.identifier)
        self.x = _spin(2500)
        self.y = _spin(3000)
        self.w = _spin(1000, minimum=1)
        self.h = _spin(500, minimum=1)
        for title, field in (("X", self.x), ("Y", self.y),
                             ("Largeur", self.w), ("Hauteur", self.h)):
            form.addRow(title + " (1/1000 case)", field)
        self.layer = _spin(1, minimum=1, maximum=65535)
        self.mask = _spin(1, maximum=65535)
        form.addRow("Layer", self.layer)
        form.addRow("Mask", self.mask)
        self.trigger = QCheckBox("Déclencheur (sans collision)")
        self.one_way = QCheckBox("Plateforme sens unique")
        form.addRow("", self.trigger)
        form.addRow("", self.one_way)
        self.velocity = _spin(0, maximum=500)
        self.travel_min = _spin(0)
        self.travel_max = _spin(0)
        form.addRow("Vitesse mobile (0 = statique)", self.velocity)
        form.addRow("Parcours X minimum", self.travel_min)
        form.addRow("Parcours X maximum", self.travel_max)
        layout.addLayout(form)
        self.canvas = QGraphicsView()
        self.canvas.setObjectName("r32-collider-overlay")
        self.canvas.setAccessibleName("Aperçu des zones de collision")
        self.canvas.setMinimumHeight(155)
        layout.addWidget(self.canvas, 1)
        tools = QHBoxLayout()
        self.create_button = QPushButton("Créer scène physique")
        self.create_button.setObjectName("r32-create-scene")
        self.create_button.clicked.connect(self.create_scene)
        tools.addWidget(self.create_button)
        self.preview_button = QPushButton("Prévisualiser collider")
        self.preview_button.setObjectName("r32-preview-collider")
        self.preview_button.clicked.connect(self.preview_collider)
        tools.addWidget(self.preview_button)
        self.apply_button = QPushButton("Appliquer (Undo)")
        self.apply_button.setObjectName("r32-apply-collider")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        tools.addWidget(self.apply_button)
        self.remove_button = QPushButton("Supprimer sélection")
        self.remove_button.setObjectName("r32-remove-collider")
        self.remove_button.clicked.connect(self.remove_collider)
        tools.addWidget(self.remove_button)
        layout.addLayout(tools)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r32-collider-diagnostics")
        self.diagnostics.setAccessibleName("Diagnostics de validation du collider")
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(110)
        layout.addWidget(self.diagnostics)
        self.target.currentIndexChanged.connect(self._load_scene)
        self.collider.currentIndexChanged.connect(self._load_collider)
        for spin in (self.x, self.y, self.w, self.h, self.layer,
                     self.mask, self.velocity, self.travel_min, self.travel_max):
            spin.valueChanged.connect(self._dirty)
        for checkbox in (self.trigger, self.one_way):
            checkbox.toggled.connect(self._dirty)
        self.identifier.textChanged.connect(self._dirty)
        self.refresh()

    def _dirty(self, *_):
        if not self._loading:
            self._pending = None
            self.apply_button.setEnabled(False)

    def refresh(self):
        old = self.target.currentData()
        self._loading = True
        self.target.clear()
        for scene_id in self.studio.targets():
            self.target.addItem(scene_id, scene_id)
        at = self.target.findData(old)
        self.target.setCurrentIndex(at if at >= 0 else 0)
        self._loading = False
        self._load_scene()

    def _load_scene(self, *_):
        if self._loading:
            return
        self._dirty()
        selected = self.target.currentData()
        existing = self.collider.currentData()
        self._loading = True
        self.collider.clear()
        if selected in self.studio.catalog()["scenes"]:
            for row in self.studio.scene(selected)["colliders"]:
                self.collider.addItem(row["id"], row["id"])
        at = self.collider.findData(existing)
        self.collider.setCurrentIndex(at if at >= 0 else -1)
        self._loading = False
        self._load_collider()
        self.create_button.setEnabled(selected not in self.studio.catalog()["scenes"])
        self.remove_button.setEnabled(self.collider.currentData() is not None)
        self._draw()

    def _load_collider(self, *_):
        if self._loading:
            return
        sid, cid = self.target.currentData(), self.collider.currentData()
        self._loading = True
        if sid in self.studio.catalog()["scenes"] and cid:
            row = next(c for c in self.studio.scene(sid)["colliders"] if c["id"] == cid)
            self.identifier.setText(row["id"])
            for control, value in zip((self.x, self.y, self.w, self.h), row["rect"]):
                control.setValue(value)
            self.layer.setValue(row["layer"])
            self.mask.setValue(row["mask"])
            self.trigger.setChecked(row["trigger"])
            self.one_way.setChecked(row["one_way"])
            self.velocity.setValue(row.get("velocity", 0))
            travel = row.get("travel", [0, 0])
            self.travel_min.setValue(travel[0])
            self.travel_max.setValue(travel[1])
        self._loading = False
        self._dirty()
        self._draw()

    def _draw(self):
        scene = QGraphicsScene(self)
        selected = self.target.currentData()
        try:
            authored = self.studio.scene(selected)
        except ColliderAuthoringError:
            scene.addText("Créer d'abord une scène physique")
            self.canvas.setScene(scene)
            return
        scale = 0.001
        scene.addRect(0, 0, authored["width"] * scale, authored["height"] * scale)
        for row in authored["colliders"]:
            rect = row["rect"]
            color = "#c18cff" if row["trigger"] else (
                "#52c9ab" if row["one_way"] else "#8496ae")
            scene.addRect(*(v * scale for v in rect),
                          brush=QBrush(QColor(color)))
        hero = authored["hero"]
        scene.addRect(hero["pos"][0] * scale, hero["pos"][1] * scale,
                      hero["size"][0] * scale, hero["size"][1] * scale,
                      brush=QBrush(QColor("#e5b755")))
        self.canvas.setScene(scene)
        self.canvas.fitInView(scene.itemsBoundingRect())

    def _preview(self, factory):
        try:
            self._pending = factory()
            self.apply_button.setEnabled(True)
            self.diagnostics.setPlainText("Aperçu valide à révision "
                                          + str(self._pending.source_revision)
                                          + " — aucun changement appliqué.")
        except (ColliderAuthoringError, AuthoringError, RuleError,
                ValueError, TypeError, KeyError) as exc:
            self._pending = None
            self.apply_button.setEnabled(False)
            self.diagnostics.setPlainText("Modification refusée : " + str(exc))

    def create_scene(self):
        sid = self.target.currentData()
        self._preview(lambda: self.studio.preview_create(
            sid, revision=self.studio.session.revision))

    def preview_collider(self):
        sid = self.target.currentData()
        collider = {
            "id": self.identifier.text().strip(),
            "rect": [self.x.value(), self.y.value(), self.w.value(), self.h.value()],
            "layer": self.layer.value(), "mask": self.mask.value(),
            "trigger": self.trigger.isChecked(),
            "one_way": self.one_way.isChecked(),
        }
        if self.velocity.value():
            collider["velocity"] = self.velocity.value()
            collider["travel"] = [self.travel_min.value(), self.travel_max.value()]
        self._preview(lambda: self.studio.preview_put(
            sid, collider, revision=self.studio.session.revision))

    def remove_collider(self):
        sid, cid = self.target.currentData(), self.collider.currentData()
        if cid is None:
            return
        self._preview(lambda: self.studio.preview_remove(
            sid, cid, revision=self.studio.session.revision))

    def apply_changes(self):
        if self._pending is None:
            return
        try:
            self.studio.apply(self._pending)
        except Exception as exc:
            self.diagnostics.setPlainText("Application refusée : " + str(exc))
            self._pending = None
            self.apply_button.setEnabled(False)
            return
        self._pending = None
        self.refresh()
        self.diagnostics.setPlainText("Transaction appliquée : Undo/Redo du Studio.")
        self.updated.emit()


__all__ = ["ColliderEditorPanel"]
