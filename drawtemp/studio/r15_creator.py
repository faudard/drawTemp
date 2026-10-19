"""Qt 6 Creator dialog: templates, preview/backup import and Player export.

This UI reuses the headless R15 validators. It does not silently mutate an
existing project and is independent from the Player process.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
    QWidget,
)

from drawtemp.export.r15 import export_game, preflight
from drawtemp.export.migration import migration_preview, import_project
from drawtemp.export.templates import TEMPLATES
from drawtemp.studio.project_wizard import ProjectSpec, create_project, project_preview


class CreatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DrawTemp 5 — Projets et export")
        self.created_content_path = None
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
        self.game_title = QLineEdit()
        self.game_title.setPlaceholderText("Titre par défaut du modèle")
        self.game_title.setAccessibleName("Titre du nouveau jeu")
        form.addRow("Titre du jeu", self.game_title)
        self.game_subtitle = QLineEdit()
        self.game_subtitle.setPlaceholderText("Sous-titre par défaut")
        self.game_subtitle.setAccessibleName("Sous-titre du nouveau jeu")
        form.addRow("Sous-titre", self.game_subtitle)
        self.language = QComboBox()
        self.language.addItem("Français", "fr")
        self.language.addItem("English", "en")
        form.addRow("Langue", self.language)
        self.save_slots = QSpinBox()
        self.save_slots.setRange(1, 9)
        self.save_slots.setValue(3)
        form.addRow("Emplacements de sauvegarde", self.save_slots)
        self.fullscreen = QCheckBox("Activer au lancement")
        form.addRow("Plein écran", self.fullscreen)
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
        for widget in (self.game_title, self.game_subtitle, self.language,
                       self.save_slots, self.fullscreen):
            widget.setEnabled(is_new)
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

    def project_spec(self):
        return ProjectSpec(
            template=self.template.currentText(),
            destination=self.destination.text(),
            title=self.game_title.text().strip() or None,
            subtitle=self.game_subtitle.text() or None,
            language=self.language.currentData(),
            save_slots=self.save_slots.value(),
            fullscreen=self.fullscreen.isChecked(),
        )

    def preview(self):
        try:
            if self.mode.currentIndex() == 0:
                report = project_preview(self.project_spec())
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
                path = create_project(self.project_spec())
                self.created_content_path = Path(path)
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
        if self.created_content_path is not None:
            self.accept()


def open_creator(parent=None):
    dialog = CreatorDialog(parent)
    return dialog.exec()
