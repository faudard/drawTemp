"""R41.B1 — accessible Qt Party Studio over the ONE AuthoringSession.

Configuration is an explicit preview/apply with transactional Undo/Redo in the
host Studio. Loading a panel does not enable RPG mode or mutate project data.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from drawtemp.studio.party_authoring import (
    apply_party_edit, inspect_party, party_campaigns, preview_party_edit,
)


class PartyStudioDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._draft = None
        self.setObjectName("r41-party-studio")
        self.setWindowTitle("R41.B — Éditeur de groupe RPG")
        self.resize(700, 610)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("RPG classique — groupe, recrutement et réserve"))
        note = QLabel(
            "Les personnages, classes, équipements et objets restent dans Content/"
            "Campaign. La configuration est une transaction dans GameProject. "
            "Activez un profil RPG classique dans l'atelier Profils avant d'appliquer.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.campaign = QComboBox()
        self.campaign.setObjectName("r41-party-campaign")
        self.campaign.setAccessibleName("Campagne RPG")
        for cid, label in party_campaigns(session.snapshot()):
            self.campaign.addItem(label, cid)
        form.addRow("Campagne", self.campaign)
        self.capacity = QSpinBox()
        self.capacity.setObjectName("r41-party-capacity")
        self.capacity.setAccessibleName("Capacité du groupe actif")
        self.capacity.setRange(1, 8)
        form.addRow("Capacité active", self.capacity)
        layout.addLayout(form)

        self.members = QTableWidget()
        self.members.setObjectName("r41-party-members")
        self.members.setAccessibleName("Personnages recrutables et groupe initial")
        self.members.setColumnCount(4)
        self.members.setHorizontalHeaderLabels(
            ["Personnage", "Recrutable", "Initial", "Actif au départ"])
        layout.addWidget(self.members, 1)

        self.report = QPlainTextEdit()
        self.report.setObjectName("r41-party-preview")
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(170)
        self.report.setAccessibleName("Prévisualisation de la transaction du groupe")
        layout.addWidget(self.report)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser")
        self.preview_button.setObjectName("r41-party-preview-button")
        self.apply_button = QPushButton("Appliquer au projet")
        self.apply_button.setObjectName("r41-party-apply")
        refresh_button = QPushButton("Actualiser")
        refresh_button.setObjectName("r41-party-refresh")
        close_button = QPushButton("Fermer")
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(refresh_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.campaign.currentIndexChanged.connect(self.refresh)
        self.capacity.valueChanged.connect(self._invalidate)
        self.members.itemChanged.connect(self._invalidate)
        self.preview_button.clicked.connect(self.preview)
        self.apply_button.clicked.connect(self.apply)
        refresh_button.clicked.connect(self.refresh)
        close_button.clicked.connect(self.close)
        self.refresh()

    def _invalidate(self, *_):
        self._draft = None
        self.apply_button.setEnabled(False)

    def refresh(self, *_):
        self._draft = None
        self.apply_button.setEnabled(False)
        cid = self.campaign.currentData()
        if cid is None:
            self.members.setRowCount(0)
            return
        view = inspect_party(self.session.snapshot(), cid)
        selection = view["selection"] or {}
        candidates = view["eligible"]
        self.capacity.blockSignals(True)
        self.capacity.setValue(selection.get("max_active", 3))
        self.capacity.blockSignals(False)
        self.members.blockSignals(True)
        self.members.setRowCount(len(candidates))
        for row, (uid, title) in enumerate(candidates):
            title_item = QTableWidgetItem(title + " (" + uid + ")")
            title_item.setData(Qt.UserRole, uid)
            title_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.members.setItem(row, 0, title_item)
            for col, key in ((1, "recruitable"), (2, "initial"), (3, "active")):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable |
                              Qt.ItemIsSelectable)
                default = (row == 0)
                item.setCheckState(
                    Qt.Checked if (uid in selection.get(key, []) if selection
                                   else default) else Qt.Unchecked)
                self.members.setItem(row, col, item)
        self.members.blockSignals(False)
        self.report.setPlainText(
            "Projet : " + ("profil RPG_TURN disponible" if (
                view["rpg_default"] or view["rpg_scenes"]) else
                "Aucun profil RPG_TURN — sélectionnez RPG classique dans Profils") +
            "\nGroupes actifs initiaux : aucun changement tant que non appliqué.")

    def _selection(self):
        result = {"recruitable": [], "initial": [], "active": []}
        for row in range(self.members.rowCount()):
            uid = self.members.item(row, 0).data(Qt.UserRole)
            for column, key in ((1, "recruitable"), (2, "initial"), (3, "active")):
                if self.members.item(row, column).checkState() == Qt.Checked:
                    result[key].append(uid)
        result["max_active"] = self.capacity.value()
        return result

    def preview(self):
        try:
            self._draft = preview_party_edit(
                self.session, self.campaign.currentData(),
                expected_revision=self.session.revision, **self._selection())
            report = {"campaign": self._draft.campaign,
                      "before": self._draft.before, "after": self._draft.after,
                      "revision": self._draft.revision}
            self.report.setPlainText(json.dumps(
                report, ensure_ascii=False, indent=2))
            self.apply_button.setEnabled(True)
            return self._draft
        except Exception as exc:
            self._invalidate()
            self.report.setPlainText("Configuration refusée : " + str(exc))
            return None

    def apply(self):
        if self._draft is None:
            return
        try:
            result = apply_party_edit(self.session, self._draft)
        except Exception as exc:
            self._invalidate()
            QMessageBox.warning(self, "R41 — groupe", str(exc))
            return
        self.updated.emit()
        self.refresh()
        self.report.setPlainText(
            "Groupe appliqué dans AuthoringSession. Enregistrez le projet "
            "depuis le Studio. Annuler/Rétablir reste disponible.")
        return result


__all__ = ["PartyStudioDialog"]
