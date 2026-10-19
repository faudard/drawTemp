"""R37.D Qt sensor configuration and authored-reference LOS debug overlay."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from drawtemp.studio.ai_sensor_authoring import AISensorDesigner


class AISensorDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.designer = AISensorDesigner(session)
        self.source_revision = session.revision
        self.pending = None
        self.setObjectName("r37-sensor-dialog")
        self.setWindowTitle("DrawTemp · Perception & Navigation R37.D")
        self.resize(680, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Configuration des capteurs IA — scénario de référence simulé, "
            "aucune commande Player exécutée"))
        form = QFormLayout()
        self.actor = QComboBox()
        self.actor.setObjectName("r37-sensor-actor")
        for agent in self.designer.agents():
            if agent["mode"] == "realtime":
                self.actor.addItem(agent["id"], agent["id"])
        form.addRow("PNJ R35", self.actor)
        self.facing = QComboBox()
        self.facing.setObjectName("r37-sensor-facing")
        for direction in ("north", "south", "west", "east", "omni"):
            self.facing.addItem(direction, direction)
        form.addRow("Regard", self.facing)
        self.vision = QSpinBox()
        self.vision.setObjectName("r37-sensor-vision")
        self.vision.setRange(1, 16)
        form.addRow("Vision (cases Manhattan)", self.vision)
        self.hearing = QSpinBox()
        self.hearing.setObjectName("r37-sensor-hearing")
        self.hearing.setRange(0, 16)
        form.addRow("Audition (distance de chemin)", self.hearing)
        self.movement = QCheckBox("Simuler un déplacement sonore du héros")
        self.movement.setObjectName("r37-sensor-movement")
        form.addRow("Scénario", self.movement)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.commands = {}
        for key, title, action in (
            ("preview", "Prévisualiser les capteurs", self.preview),
            ("validate", "Valider pour application", self.validate),
            ("apply", "Appliquer (1 Undo)", self.apply),
            ("remove", "Supprimer le capteur", self.remove),
            ("undo", "Annuler", self.undo),
            ("redo", "Rétablir", self.redo),
        ):
            button = QPushButton(title)
            button.setObjectName("r37-sensor-" + key)
            button.clicked.connect(action)
            buttons.addWidget(button)
            self.commands[key] = button
        self.commands["apply"].setEnabled(False)
        layout.addLayout(buttons)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r37-sensor-diagnostics")
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics, 1)
        self.actor.currentIndexChanged.connect(self.load_actor)
        for control in (self.facing, self.vision, self.hearing):
            (control.currentIndexChanged if isinstance(control, QComboBox)
             else control.valueChanged).connect(self.invalidate)
        self.load_actor()

    def _sensor(self):
        return {"version": 1, "facing": self.facing.currentData(),
                "vision_range": self.vision.value(),
                "hearing_range": self.hearing.value()}

    def invalidate(self, *_):
        self.pending = None
        self.commands["apply"].setEnabled(False)

    def load_actor(self, *_):
        self.invalidate()
        actor_id = self.actor.currentData()
        row = next((a for a in self.designer.agents()
                    if a["id"] == actor_id), None)
        if row is None:
            return
        sensor = row["sensor"] or {
            "facing": "omni", "vision_range": 5, "hearing_range": 4}
        self.facing.blockSignals(True)
        self.vision.blockSignals(True)
        self.hearing.blockSignals(True)
        self.facing.setCurrentIndex(self.facing.findData(sensor["facing"]))
        self.vision.setValue(sensor["vision_range"])
        self.hearing.setValue(sensor["hearing_range"])
        self.facing.blockSignals(False)
        self.vision.blockSignals(False)
        self.hearing.blockSignals(False)
        self.source_revision = self.designer.session.revision

    def preview(self):
        actor_id = self.actor.currentData()
        if actor_id is None:
            return
        try:
            report = self.designer.simulate(
                actor_id, sensor=self._sensor(),
                movement=self.movement.isChecked())
            self.diagnostics.setPlainText(json.dumps(
                report, ensure_ascii=False, indent=2))
        except (ValueError, KeyError, TypeError) as exc:
            self.diagnostics.setPlainText("Diagnostic refusé : " + str(exc))

    def validate(self):
        actor_id = self.actor.currentData()
        if actor_id is None:
            return
        try:
            self.pending = self.designer.preview(
                actor_id, self._sensor(),
                expected_revision=self.source_revision)
            self.commands["apply"].setEnabled(True)
            self.diagnostics.setPlainText(
                "Capteur validé par GameProject. Appliquer pour enregistrer.")
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            self.diagnostics.setPlainText("Validation refusée : " + str(exc))

    def apply(self):
        if self.pending is None:
            return
        try:
            self.designer.apply(self.pending)
            self.updated.emit()
            self.invalidate()
            self.source_revision = self.designer.session.revision
            self.diagnostics.setPlainText("Capteur appliqué au projet.")
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            self.diagnostics.setPlainText("Application refusée : " + str(exc))

    def remove(self):
        actor_id = self.actor.currentData()
        if actor_id is None:
            return
        try:
            plan = self.designer.preview(
                actor_id, None, expected_revision=self.source_revision)
            self.designer.apply(plan)
            self.updated.emit()
            self.load_actor()
        except (ValueError, KeyError, TypeError) as exc:
            self.diagnostics.setPlainText("Suppression refusée : " + str(exc))

    def undo(self):
        try:
            self.designer.session.undo()
            self.updated.emit()
            self.load_actor()
        except ValueError as exc:
            self.diagnostics.setPlainText("Annulation impossible : " + str(exc))

    def redo(self):
        try:
            self.designer.session.redo()
            self.updated.emit()
            self.load_actor()
        except ValueError as exc:
            self.diagnostics.setPlainText("Rétablissement impossible : " + str(exc))
