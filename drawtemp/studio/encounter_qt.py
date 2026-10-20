"""R41.B2 Qt Encounter Studio: typed, explicit preview/apply, no direct JSON editor."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout,
)

from drawtemp.studio.encounter_authoring import (
    apply_encounter_edit, available_rpg_enemies, available_rpg_scenes,
    encounter_definitions, preview_encounter_edit,
)


class EncounterStudioDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._pending = None
        self.setObjectName("r41-encounter-studio")
        self.setWindowTitle("R41.B2 — Encounter Studio")
        self.resize(660, 590)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Rencontres RPG_TURN : scènes et ennemis existants du projet. "
            "Les héros, compétences, objets et récompenses conservent leurs "
            "propriétaires canoniques. Aperçu et Annuler/Rétablir dans le Studio.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.existing = QComboBox()
        self.existing.setObjectName("r41-encounter-existing")
        form.addRow("Rencontre existante", self.existing)
        self.encounter_id = QLineEdit()
        self.encounter_id.setObjectName("r41-encounter-id")
        self.encounter_id.setAccessibleName("Identifiant rencontre RPG")
        form.addRow("Identifiant", self.encounter_id)
        self.scene = QComboBox()
        self.scene.setObjectName("r41-encounter-scene")
        form.addRow("Scène RPG", self.scene)
        self.gold = QSpinBox()
        self.gold.setObjectName("r41-encounter-reward")
        self.gold.setRange(0, 10000)
        form.addRow("Or de victoire", self.gold)
        layout.addLayout(form)
        layout.addWidget(QLabel("Ennemis du Content (sélection multiple)"))
        self.enemies = QListWidget()
        self.enemies.setObjectName("r41-encounter-enemies")
        self.enemies.setAccessibleName("Ennemis de la rencontre")
        self.enemies.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.enemies, 1)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        layout.addWidget(self.preview_text)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser")
        self.preview_button.setObjectName("r41-encounter-preview")
        self.apply_button = QPushButton("Appliquer")
        self.apply_button.setObjectName("r41-encounter-apply")
        refresh_button = QPushButton("Actualiser")
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(refresh_button)
        layout.addLayout(buttons)
        self.preview_button.clicked.connect(self.preview)
        self.apply_button.clicked.connect(self.apply)
        refresh_button.clicked.connect(self.refresh)
        self.existing.currentIndexChanged.connect(self.select_existing)
        self.encounter_id.textChanged.connect(self.invalidate)
        self.scene.currentIndexChanged.connect(self.invalidate)
        self.gold.valueChanged.connect(self.invalidate)
        self.enemies.itemSelectionChanged.connect(self.invalidate)
        self.refresh()

    def invalidate(self, *_):
        self._pending = None
        self.apply_button.setEnabled(False)

    def refresh(self):
        self.invalidate()
        definitions = encounter_definitions(self.session.snapshot())
        self.existing.blockSignals(True)
        self.existing.clear()
        self.existing.addItem("Nouvelle rencontre", "")
        for eid in sorted(definitions):
            self.existing.addItem(eid, eid)
        self.existing.blockSignals(False)
        self.scene.clear()
        for scene in available_rpg_scenes(self.session.snapshot()):
            self.scene.addItem(scene, scene)
        self.enemies.clear()
        for uid, name in available_rpg_enemies(self.session.snapshot()):
            self.enemies.addItem(name + " (" + uid + ")")
            self.enemies.item(self.enemies.count() - 1).setData(Qt.UserRole, uid)
        self.encounter_id.clear()
        self.gold.setValue(0)
        self.preview_text.setPlainText(
            "Aucune donnée changée. Sélectionnez une scène et des ennemis, "
            "puis prévisualisez avant d'appliquer.")

    def select_existing(self, *_):
        eid = self.existing.currentData() or ""
        self.invalidate()
        if not eid:
            self.encounter_id.clear()
            self.gold.setValue(0)
            self.enemies.clearSelection()
            return
        entry = encounter_definitions(self.session.snapshot()).get(eid)
        if entry is None:
            return
        self.encounter_id.setText(eid)
        idx = self.scene.findData(entry["scene"])
        if idx >= 0:
            self.scene.setCurrentIndex(idx)
        self.gold.setValue(entry["reward_gold"])
        self.enemies.clearSelection()
        for row in range(self.enemies.count()):
            item = self.enemies.item(row)
            item.setSelected(item.data(Qt.UserRole) in entry["enemies"])

    def preview(self):
        try:
            self._pending = preview_encounter_edit(
                self.session, self.encounter_id.text().strip(),
                scene=self.scene.currentData(),
                enemies=[self.enemies.item(row).data(Qt.UserRole)
                         for row in range(self.enemies.count())
                         if self.enemies.item(row).isSelected()],
                reward_gold=self.gold.value(),
                expected_revision=self.session.revision)
            self.preview_text.setPlainText(json.dumps({
                "id": self._pending.encounter_id,
                "avant": self._pending.before,
                "après": self._pending.after,
            }, ensure_ascii=False, indent=2))
            self.apply_button.setEnabled(True)
            return self._pending
        except Exception as exc:
            self.invalidate()
            self.preview_text.setPlainText("Erreur : " + str(exc))
            return None

    def apply(self):
        if self._pending is None:
            return
        try:
            result = apply_encounter_edit(self.session, self._pending)
        except Exception as exc:
            self.invalidate()
            QMessageBox.warning(self, "R41 Rencontre", str(exc))
            return
        self.updated.emit()
        self.refresh()
        self.preview_text.setPlainText("Rencontre appliquée. Enregistrez le projet "
                                       "avec la commande habituelle du Studio.")
        return result


__all__ = ["EncounterStudioDialog"]
