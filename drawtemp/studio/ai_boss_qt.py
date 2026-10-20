"""R37.E2 Qt Boss Director: author only real R6 phases, visual read-only cues."""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from drawtemp.studio.ai_boss_authoring import BossDirectorDesigner


class BossDirectorDialog(QDialog):
    updated = Signal()

    def __init__(self, session, *, game_session=None, parent=None):
        super().__init__(parent)
        self.designer = BossDirectorDesigner(session)
        self.game_session = game_session
        self.revision = session.revision
        self.pending = None
        self.setObjectName("r37-boss-dialog")
        self.setWindowTitle("DrawTemp · Boss & AI Director R37.E")
        self.resize(820, 615)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Boss Director R37.E — phases et avertissements de présentation. "
            "Les transformations et renforts réels restent dans les triggers R8."))
        form = QFormLayout()
        self.candidate = QComboBox()
        self.candidate.setObjectName("r37-boss-candidate")
        for item in self.designer.choices():
            title = item["mission"] + " / " + item["boss"]
            self.candidate.addItem(title, (item["mission"], item["boss"]))
        form.addRow("Boss de mission", self.candidate)
        self.director = QComboBox()
        self.director.setObjectName("r37-boss-director")
        form.addRow("Director", self.director)
        self.phase = QComboBox()
        self.phase.setObjectName("r37-boss-phase")
        form.addRow("Phase R8 existante", self.phase)
        self.label = QLineEdit()
        self.label.setObjectName("r37-boss-label")
        form.addRow("Nom affiché", self.label)
        self.cue = QLineEdit()
        self.cue.setMaxLength(160)
        self.cue.setObjectName("r37-boss-cue")
        form.addRow("Indication visuelle / texte", self.cue)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.buttons = {}
        for key, title, callback in (
            ("new", "Créer depuis les triggers R8", self.add),
            ("validate", "Valider phase", self.validate),
            ("apply", "Appliquer (1 Undo)", self.apply),
            ("remove", "Supprimer", self.remove),
            ("preview", "Inspecter", self.inspect),
            ("undo", "Annuler", self.undo),
            ("redo", "Rétablir", self.redo),
        ):
            widget = QPushButton(title)
            widget.setObjectName("r37-boss-" + key)
            widget.clicked.connect(callback)
            buttons.addWidget(widget)
            self.buttons[key] = widget
        root.addLayout(buttons)
        self.buttons["apply"].setEnabled(False)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setObjectName("r37-boss-diagnostics")
        root.addWidget(self.diagnostics, 1)
        self.director.currentIndexChanged.connect(self.select_director)
        self.phase.currentIndexChanged.connect(self.select_phase)
        self.label.textChanged.connect(self.invalidate)
        self.cue.textChanged.connect(self.invalidate)
        self.refresh()

    def invalidate(self, *_):
        self.pending = None
        self.buttons["apply"].setEnabled(False)

    def refresh(self):
        old = self.director.currentData()
        self.director.blockSignals(True)
        self.director.clear()
        for row in self.designer.catalog():
            self.director.addItem(
                row["mission"] + " / " + row["boss"], row["id"])
        index = self.director.findData(old)
        if index >= 0:
            self.director.setCurrentIndex(index)
        self.director.blockSignals(False)
        self.revision = self.designer.session.revision
        self.select_director()

    def _selected(self):
        return next((row for row in self.designer.catalog()
                     if row["id"] == self.director.currentData()), None)

    def select_director(self, *_):
        self.invalidate()
        chosen = self._selected()
        self.phase.blockSignals(True)
        self.phase.clear()
        if chosen is not None:
            for row in chosen["phases"]:
                self.phase.addItem(
                    str(row["phase"]) + " — " + row["label"],
                    row["phase"])
        self.phase.blockSignals(False)
        self.select_phase()

    def select_phase(self, *_):
        self.invalidate()
        director = self._selected()
        phase = self.phase.currentData()
        row = next((row for row in director["phases"]
                    if row["phase"] == phase), None) if director else None
        self.label.blockSignals(True)
        self.cue.blockSignals(True)
        self.label.setText(row["label"] if row else "")
        self.cue.setText(row["cue"] if row else "")
        self.label.blockSignals(False)
        self.cue.blockSignals(False)

    def _stage(self, plan):
        self.pending = plan
        self.buttons["apply"].setEnabled(True)
        self.diagnostics.setPlainText(
            "Projet validé ; Appliquer pour commettre une transaction R1.")

    def add(self):
        pair = self.candidate.currentData()
        if pair is None:
            return
        try:
            self._stage(self.designer.preview_add(
                *pair, expected_revision=self.revision))
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            self.diagnostics.setPlainText("Création refusée : " + str(exc))

    def validate(self):
        director_id = self.director.currentData()
        if director_id is None:
            return
        try:
            self._stage(self.designer.preview_phase(
                director_id, self.phase.currentData(),
                label=self.label.text(), cue=self.cue.text(),
                expected_revision=self.revision))
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            self.diagnostics.setPlainText("Validation refusée : " + str(exc))

    def apply(self):
        if self.pending is None:
            return
        try:
            self.designer.apply(self.pending)
            self.updated.emit()
            self.refresh()
            self.diagnostics.setPlainText("Boss Director sauvegardé dans le projet.")
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            self.diagnostics.setPlainText("Application refusée : " + str(exc))

    def remove(self):
        director_id = self.director.currentData()
        if director_id is None:
            return
        try:
            self.designer.apply(self.designer.preview_remove(
                director_id, expected_revision=self.revision))
            self.updated.emit()
            self.refresh()
        except (ValueError, KeyError, TypeError) as exc:
            self.diagnostics.setPlainText("Suppression refusée : " + str(exc))

    def inspect(self):
        chosen = self._selected()
        if chosen is None:
            return
        if self.game_session is not None:
            try:
                report = self.game_session.ai_boss_preview(chosen["id"])
            except (ValueError, KeyError, TypeError) as exc:
                self.diagnostics.setPlainText("Playtest indisponible : " + str(exc))
                return
        else:
            report = {
                "preview_only": True,
                "origin": "authored_mission_triggers",
                "note": "Aucune instance Battle active ; les prévisions CT ne sont pas inventées.",
                "director": chosen,
            }
        self.diagnostics.setPlainText(json.dumps(
            report, ensure_ascii=False, indent=2))

    def undo(self):
        try:
            self.designer.session.undo()
            self.updated.emit()
            self.refresh()
        except ValueError as exc:
            self.diagnostics.setPlainText(str(exc))

    def redo(self):
        try:
            self.designer.session.redo()
            self.updated.emit()
            self.refresh()
        except ValueError as exc:
            self.diagnostics.setPlainText(str(exc))
