"""R28.A Qt Project Wizard: one entry point, five visible genres.

Unimplemented modes have an explicit disabled create path; no fake action-RPG
documents are emitted. Existing R15/AuthoringSession remain the sole owners.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from drawtemp.studio.genre_workflow import (
    GENRES, create_genre_project, preview_genre_project,
)
from drawtemp.studio.r49_creator_ux import creator_preflight_text


class GenreProjectWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r28-genre-project-wizard")
        self.setWindowTitle("Nouveau projet - DrawTemp Creator")
        self.resize(720, 470)
        self.created_content_path = None
        layout = QVBoxLayout(self)
        heading = QLabel("Creer un jeu dans le Studio multi-genres")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        form = QFormLayout()
        self.genre = QComboBox()
        self.genre.setAccessibleName("Genre du nouveau jeu")
        for preset in GENRES:
            label = preset.label + (" (a venir)" if preset.template is None else "")
            self.genre.addItem(label, preset.key)
        form.addRow("Genre", self.genre)
        self.destination = QLineEdit()
        self.destination.setAccessibleName("Dossier du nouveau projet")
        self.destination.setPlaceholderText("Nouveau dossier, inexistant")
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.destination)
        browse = QPushButton("Parcourir...")
        browse.clicked.connect(self.browse)
        dest_row.addWidget(browse)
        form.addRow("Destination", dest_row)
        layout.addLayout(form)
        layout.addWidget(QLabel("Capacités et conditions de création (aucun fichier modifié)"))
        self.report = QPlainTextEdit()
        self.report.setObjectName("r28-genre-project-diagnostics")
        self.report.setAccessibleName("Diagnostic de creation")
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)
        actions = QHBoxLayout()
        preview = QPushButton("Verifier")
        preview.clicked.connect(self.refresh)
        actions.addWidget(preview)
        self.create_button = QPushButton("Creer et ouvrir")
        self.create_button.setObjectName("r28-create-project")
        self.create_button.clicked.connect(self.create)
        actions.addWidget(self.create_button)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        layout.addLayout(actions)
        self.genre.currentIndexChanged.connect(self.refresh)
        self.destination.textChanged.connect(self.refresh)
        self.refresh()

    def browse(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier parent du nouveau jeu")
        if directory:
            self.destination.setText(str(Path(directory) / "DrawTempGame"))

    def refresh(self, *_):
        result = preview_genre_project(
            self.genre.currentData(), self.destination.text())
        self.report.setPlainText(creator_preflight_text(result))
        self.report.setAccessibleDescription(
            "Préflight accessible : état, genre, dossier, fonctionnalités et blocages")
        self.create_button.setEnabled(result["passed"])
        return result

    def create(self):
        # Recheck at execution time: a destination may have appeared after
        # preview, and selected genre can never override canonical validation.
        try:
            folder = create_genre_project(
                self.genre.currentData(), self.destination.text())
        except (OSError, ValueError) as exc:
            self.refresh()
            QMessageBox.warning(self, "Creation bloquee", str(exc))
            return
        self.created_content_path = Path(folder) / "game.json"
        self.accept()
