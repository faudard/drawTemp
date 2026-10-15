"""Qt 6 Creator dialog: templates, preview/backup import and Player export.

This UI reuses the headless R15 validators. It does not silently mutate an
existing project and is independent from the Player process.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

from drawtemp.export.r15 import export_game, preflight
from drawtemp.export.migration import migration_preview, import_project
from drawtemp.export.templates import TEMPLATES, create_template


class CreatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DrawTemp 5 — Projets et export")
        self.resize(780, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Créer un projet, importer une version compatible ou exporter un Player natif."))
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Nouveau projet", "Importer / migrer", "Exporter le Player"])
        self.mode.currentIndexChanged.connect(self.refresh)
        form.addRow("Opération", self.mode)
        self.template = QComboBox()
        self.template.addItems(list(TEMPLATES))
        form.addRow("Modèle", self.template)
        self.source = QLineEdit()
        source_row = QHBoxLayout()
        source_row.addWidget(self.source)
        choose_source = QPushButton("Parcourir")
        choose_source.clicked.connect(self.browse_source)
        source_row.addWidget(choose_source)
        form.addRow("Contenu JSON", source_row)
        self.runtime = QLineEdit()
        runtime_row = QHBoxLayout()
        runtime_row.addWidget(self.runtime)
        choose_runtime = QPushButton("Parcourir")
        choose_runtime.clicked.connect(self.browse_runtime)
        runtime_row.addWidget(choose_runtime)
        form.addRow("Runtime natif", runtime_row)
        self.destination = QLineEdit()
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination)
        choose_dest = QPushButton("Parcourir")
        choose_dest.clicked.connect(self.browse_destination)
        destination_row.addWidget(choose_dest)
        form.addRow("Destination", destination_row)
        layout.addLayout(form)
        layout.addWidget(QLabel("Rapport de validation (aucun fichier modifié par l'aperçu)"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        buttons = QHBoxLayout()
        preview = QPushButton("Prévisualiser")
        preview.clicked.connect(self.preview)
        buttons.addWidget(preview)
        apply = QPushButton("Créer / importer / exporter")
        apply.clicked.connect(self.execute)
        buttons.addWidget(apply)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self, *_):
        is_new = self.mode.currentIndex() == 0
        is_export = self.mode.currentIndex() == 2
        self.template.setEnabled(is_new)
        self.source.setEnabled(not is_new)
        self.runtime.setEnabled(is_export)
        self.log.clear()
        if is_export:
            self.log.setPlainText(
                "R15 exige un runtime DrawTempPlayer natif, construit pour la "
                "plateforme cible. Une wheel Python seule est insuffisante.")

    def browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir le Content JSON", "", "Content JSON (*.json)")
        if path:
            self.source.setText(path)

    def browse_runtime(self):
        path = QFileDialog.getExistingDirectory(
            self, "Dossier DrawTempPlayer généré par PyInstaller")
        if path:
            self.runtime.setText(path)

    def browse_destination(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier parent de destination")
        if path:
            self.destination.setText(str(Path(path) / "DrawTempProject"))

    def preview(self):
        try:
            if self.mode.currentIndex() == 0:
                report = {"template": self.template.currentText(),
                          "destination": self.destination.text(),
                          "note": "Validation canonique après création; aucun écrasement"}
            elif self.mode.currentIndex() == 1:
                report = migration_preview(self.source.text())
            else:
                report = preflight(self.source.text())
            self.log.setPlainText(json.dumps(
                report, ensure_ascii=False, indent=2))
            return report
        except (OSError, ValueError) as exc:
            self.log.setPlainText(str(exc))
            return None

    def execute(self):
        result = self.preview()
        if result is None or (result.get("supported", True) is False or
                              result.get("passed", True) is False):
            QMessageBox.warning(self, "Validation bloquante",
                                "Corrigez d'abord les erreurs dans le rapport.")
            return
        if not self.destination.text().strip():
            QMessageBox.warning(self, "Destination manquante",
                                "Choisissez un nouveau dossier de sortie.")
            return
        try:
            dest = self.destination.text()
            if self.mode.currentIndex() == 0:
                path = create_template(self.template.currentText(), dest)
            elif self.mode.currentIndex() == 1:
                path = import_project(self.source.text(), dest)
            else:
                path = export_game(
                    self.source.text(), self.runtime.text(), dest)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Opération refusée", str(exc))
            return
        self.log.append("\nCréation réussie : " + str(path))
        QMessageBox.information(self, "Opération terminée", str(path))


def open_creator(parent=None):
    dialog = CreatorDialog(parent)
    return dialog.exec()
