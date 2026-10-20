"""R37.D3 — Qt squad role and direct-radio editor backed by R1 transactions."""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from drawtemp.studio.ai_squad_authoring import AISquadDesigner
from sporebound.ai_squad import ROLES


class AISquadDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.designer = AISquadDesigner(session)
        self.revision = session.revision
        self.pending = None
        self.setObjectName("r37-squad-dialog")
        self.setWindowTitle("DrawTemp · Squad Coordination R37.D3")
        self.resize(680, 450)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Escouades R37 — déclarer un rôle et une portée radio. "
            "Aucun mouvement ni combat n'est exécuté par l'éditeur."))
        form = QFormLayout()
        self.actor = QComboBox()
        self.actor.setObjectName("r37-squad-actor")
        for row in self.designer.members():
            if row["mode"] == "realtime" and row["sensor"]:
                self.actor.addItem(row["id"], row["id"])
        form.addRow("PNJ R35", self.actor)
        self.squad_id = QLineEdit("castle_guard")
        self.squad_id.setObjectName("r37-squad-id")
        form.addRow("Identifiant de l'escouade", self.squad_id)
        self.role = QComboBox()
        self.role.setObjectName("r37-squad-role")
        for name in sorted(ROLES):
            self.role.addItem(name, name)
        form.addRow("Rôle tactique", self.role)
        self.radio_range = QSpinBox()
        self.radio_range.setObjectName("r37-squad-radio")
        self.radio_range.setRange(0, 16)
        self.radio_range.setValue(4)
        form.addRow("Portée radio directe (cases)", self.radio_range)
        root.addLayout(form)
        actions = QHBoxLayout()
        self.buttons = {}
        for key, label, callback in (
            ("preview", "Valider", self.preview),
            ("apply", "Appliquer", self.apply),
            ("remove", "Retirer", self.remove),
            ("undo", "Annuler", self.undo),
            ("redo", "Rétablir", self.redo),
        ):
            button = QPushButton(label)
            button.setObjectName("r37-squad-" + key)
            button.clicked.connect(callback)
            actions.addWidget(button)
            self.buttons[key] = button
        root.addLayout(actions)
        self.buttons["apply"].setEnabled(False)
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setObjectName("r37-squad-diagnostics")
        root.addWidget(self.info, 1)
        self.actor.currentIndexChanged.connect(self.refresh_actor)
        self.squad_id.textChanged.connect(self.invalidate)
        self.role.currentIndexChanged.connect(self.invalidate)
        self.radio_range.valueChanged.connect(self.invalidate)
        self.refresh_actor()

    def invalidate(self, *_):
        self.pending = None
        self.buttons["apply"].setEnabled(False)

    def _binding(self):
        return {"id": self.squad_id.text(), "role": self.role.currentData(),
                "radio_range": self.radio_range.value()}

    def refresh_actor(self, *_):
        self.invalidate()
        actor_id = self.actor.currentData()
        row = next((m for m in self.designer.members()
                    if m["id"] == actor_id), None)
        if row is None:
            return
        binding = row["squad"] or {
            "id": "castle_guard", "role": "scout", "radio_range": 4}
        self.squad_id.blockSignals(True)
        self.role.blockSignals(True)
        self.radio_range.blockSignals(True)
        self.squad_id.setText(binding["id"])
        self.role.setCurrentIndex(self.role.findData(binding["role"]))
        self.radio_range.setValue(binding["radio_range"])
        self.squad_id.blockSignals(False)
        self.role.blockSignals(False)
        self.radio_range.blockSignals(False)
        self.revision = self.designer.session.revision

    def preview(self):
        actor_id = self.actor.currentData()
        if actor_id is None:
            return
        try:
            self.pending = self.designer.preview(
                actor_id, self._binding(),
                expected_revision=self.revision)
            self.buttons["apply"].setEnabled(True)
            self.info.setPlainText(
                "Configuration validée par le projet canonique. "
                "Appliquer enregistre une transaction Undo.")
        except (ValueError, TypeError, KeyError) as exc:
            self.invalidate()
            self.info.setPlainText("Validation refusée : " + str(exc))

    def apply(self):
        if self.pending is None:
            return
        try:
            self.designer.apply(self.pending)
            self.updated.emit()
            self.refresh_actor()
            self.info.setPlainText("Escouade appliquée au projet.")
        except (ValueError, TypeError, KeyError) as exc:
            self.invalidate()
            self.info.setPlainText("Application refusée : " + str(exc))

    def remove(self):
        actor_id = self.actor.currentData()
        if actor_id is None:
            return
        try:
            plan = self.designer.preview(actor_id, None,
                                         expected_revision=self.revision)
            self.designer.apply(plan)
            self.updated.emit()
            self.refresh_actor()
            self.info.setPlainText("Membre retiré de l'escouade.")
        except (ValueError, TypeError, KeyError) as exc:
            self.info.setPlainText("Retrait refusé : " + str(exc))

    def undo(self):
        try:
            self.designer.session.undo()
            self.updated.emit()
            self.refresh_actor()
        except ValueError as exc:
            self.info.setPlainText("Annulation refusée : " + str(exc))

    def redo(self):
        try:
            self.designer.session.redo()
            self.updated.emit()
            self.refresh_actor()
        except ValueError as exc:
            self.info.setPlainText("Rétablissement refusé : " + str(exc))
