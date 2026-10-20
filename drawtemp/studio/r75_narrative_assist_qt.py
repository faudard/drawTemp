"""R75.B opt-in Qt review surface; canonical project mutations remain headless."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout)

from drawtemp.studio.r75_narrative_assist import (
    NarrativeAssistController, three_endings_template)


class R75NarrativeAssistDialog(QDialog):
    """Human-read diff, path witnesses, explicit approval, single-step Undo."""

    def __init__(self, session, *, parent=None):
        super().__init__(parent)
        self.setObjectName("r75-assisted-narrative-dialog")
        self.setWindowTitle("R75 — Assistant de quête / dialogue (hors ligne)")
        self.resize(900, 650)
        self.controller = NarrativeAssistController(session)
        self._review = None
        root = QVBoxLayout(self)
        introduction = QLabel(
            "Assistant local, sans service externe. Les scènes proposées ne "
            "modifient PAS le projet avant validation humaine. Les chemins "
            "sont analysés depuis une campagne vierge, pas toutes les sauvegardes. "
            "Enregistrer reste une action distincte du Studio.")
        introduction.setWordWrap(True)
        root.addWidget(introduction)
        row = QHBoxLayout()
        row.addWidget(QLabel("Attacher après la mission"))
        self.mission_box = QComboBox()
        self.mission_box.setObjectName("r75-mission")
        self.mission_box.setAccessibleName("Mission de la quête")
        snapshot = session.snapshot().to_dict()
        for mission in snapshot["content"]["missions"]:
            self.mission_box.addItem(mission.get("name", mission["id"]), mission["id"])
        row.addWidget(self.mission_box, 1)
        row.addWidget(QLabel("Préfixe"))
        self.prefix = QLineEdit("r75")
        self.prefix.setObjectName("r75-prefix")
        self.prefix.setMaxLength(24)
        self.prefix.setAccessibleName("Préfixe des identifiants des scènes")
        row.addWidget(self.prefix)
        root.addLayout(row)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setObjectName("r75-review-diff")
        self.preview_text.setAccessibleName("Diff de la quête, conditions et chemins")
        root.addWidget(self.preview_text, 1)
        self.status = QLabel("Cliquez sur Prévisualiser pour inspecter la proposition.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Statut de l'analyse narrative")
        root.addWidget(self.status)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser et vérifier")
        self.preview_button.setObjectName("r75-preview")
        self.preview_button.clicked.connect(self.preview_proposal)
        actions.addWidget(self.preview_button)
        self.apply_button = QPushButton("Approuver et appliquer…")
        self.apply_button.setObjectName("r75-apply")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.confirm_apply)
        actions.addWidget(self.apply_button)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        root.addLayout(actions)
        self.mission_box.currentIndexChanged.connect(self.invalidate)
        self.prefix.textChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.controller.invalidate()
        self._review = None
        self.apply_button.setEnabled(False)
        self.preview_text.clear()
        self.status.setText("Paramètres modifiés : nouvelle revue requise.")

    def preview_proposal(self):
        self.invalidate()
        try:
            proposal = three_endings_template(
                self.mission_box.currentData(), prefix=self.prefix.text().strip())
            review = self.controller.preview(proposal)
        except (ValueError, OSError) as exc:
            self.status.setText("Refus de prévisualisation : " + str(exc))
            return None
        self._review = review
        lines = [
            "DIFF : scènes ajoutées uniquement (aucun écrasement)",
            "Proposition : " + review.proposal_id,
            "SHA-256 : " + review.proposal_sha256,
            "Origine : " + review.source["kind"],
            "Attribution : " + review.source["attribution"],
            "Licence déclarée : " + review.source["license"],
            "Droits déclarés : " + review.source["rights"],
            "Export : déclaration non certifiée par le Studio",
            "Hook : " + review.hook["kind"] + "/" + review.hook["id"],
            "",
        ]
        for scene in proposal["scenes"]:
            lines.append("+ SCÈNE " + scene["id"] + " — " + scene["title"])
            lines.append("  " + scene["text"])
            for choice in scene["choices"]:
                lines.append("  + CHOIX " + choice["id"] + " : " + choice["label"])
                if choice.get("when"):
                    lines.append("    SI " + json.dumps(
                        choice["when"], ensure_ascii=False, sort_keys=True))
                if choice.get("effects"):
                    lines.append("    EFFETS " + json.dumps(
                        choice["effects"], ensure_ascii=False, sort_keys=True))
                if choice.get("next_scene"):
                    lines.append("    → " + choice["next_scene"])
        lines.extend(["", "CHEMINS TÉMOINS (depuis état vierge)"])
        for ending, path in review.ending_paths:
            lines.append("  " + ending + " : " + " → ".join(
                scene + "/" + choice for scene, choice in path))
        lines.extend(["", "L'approbation modifie la session active avec Undo.",
                      "L'enregistrement sur disque reste manuel."])
        self.preview_text.setPlainText("\n".join(lines))
        self.apply_button.setEnabled(True)
        self.status.setText(
            str(len(review.added_scenes)) + " scènes, " +
            str(len(review.ending_paths)) + " fins vérifiées. "
            "Aucune modification enregistrée.")
        return review

    def confirm_apply(self):
        if self._review is None or not self.apply_button.isEnabled():
            return None
        response = QMessageBox.question(
            self, "Approuver la quête R75",
            "Avez-vous relu le diff, les textes, les chemins et les droits "
            "déclarés ? Appliquer dans la session (Undo disponible), sans "
            "enregistrer sur disque ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if response != QMessageBox.Yes:
            return None
        return self.apply_review(approved=True)

    def apply_review(self, *, approved=False):
        if not approved or self._review is None or not self.apply_button.isEnabled():
            return None
        review = self._review
        self._review = None
        self.apply_button.setEnabled(False)
        try:
            change = self.controller.apply(review, approved=True)
        except (OSError, ValueError) as exc:
            self.status.setText("Application refusée : " + str(exc))
            return None
        self.status.setText(
            "R75 appliqué en révision " + str(change.snapshot.revision) +
            ". Utiliser Édition → Annuler si besoin; enregistrer séparément.")
        return change
