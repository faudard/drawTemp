"""Compact, single-purpose new-project dialog for the Studio.

Advanced template, genre and export flows remain separate. Creation delegates
to the canonical headless project wizard; no files are written on preview.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from drawtemp.export.r15 import ExportError
from drawtemp.studio.project_wizard import ProjectSpec, create_project, project_preview


_INVALID_FOLDER = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


def folder_error(name: str) -> str:
    """Conservative, portable folder-name checks, including Windows rules."""
    if not name or name != name.strip() or name in (".", ".."):
        return "Indiquez un nom de dossier valide."
    if len(name) > 120 or _INVALID_FOLDER.search(name) or name.endswith("."):
        return "Le nom du dossier contient des caractères interdits."
    if name.split(".", 1)[0].upper() in _RESERVED_WINDOWS:
        return "Ce nom de dossier est réservé par Windows."
    return ""


class SimpleProjectDialog(QDialog):
    """Three visible fields: folder name, game title and final location."""

    def __init__(self, parent=None, *, parent_directory=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet")
        self.setMinimumWidth(480)
        self.created_content_path: Path | None = None
        self.settings = settings or QSettings("DrawTemp", "Studio5")
        if parent_directory is None:
            remembered = self.settings.value("projects/parent_directory", "")
            documents = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation)
            parent_directory = remembered or documents or str(Path.home())
        self._parent_directory = Path(parent_directory).expanduser().absolute()
        self._title_auto = True

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.addWidget(QLabel("Nom du dossier :"), 0, 0)
        grid.addWidget(QLabel("Titre du jeu :"), 0, 1)
        self.folder_name = QLineEdit()
        self.folder_name.setAccessibleName("Nom du dossier du projet")
        self.game_title = QLineEdit()
        self.game_title.setAccessibleName("Titre du jeu")
        grid.addWidget(self.folder_name, 1, 0)
        grid.addWidget(self.game_title, 1, 1)
        grid.addWidget(QLabel("Emplacement :"), 2, 0, 1, 2)

        location_row = QHBoxLayout()
        self.location = QLineEdit()
        self.location.setAccessibleName("Emplacement complet du projet")
        self.browse_button = QPushButton("...")
        self.browse_button.setAccessibleName("Choisir le dossier parent")
        self.browse_button.setFixedWidth(34)
        self.browse_button.clicked.connect(self.browse_directory)
        location_row.addWidget(self.location, 1)
        location_row.addWidget(self.browse_button)
        grid.addLayout(location_row, 3, 0, 1, 2)
        layout.addLayout(grid)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setAccessibleName("Erreur de création du projet")
        layout.addWidget(self.error_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Annuler")
        self.buttons.accepted.connect(self.create)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.folder_name.textChanged.connect(self._folder_changed)
        self.game_title.textEdited.connect(self._title_edited)
        self.game_title.textChanged.connect(self._update_validation)
        self.location.textChanged.connect(self._update_validation)
        self.location.editingFinished.connect(self._location_edited)

        initial_name = "Project1"
        index = 1
        while (self._parent_directory / initial_name).exists() or (
                self._parent_directory / initial_name).is_symlink():
            index += 1
            initial_name = f"Project{index}"
        self.folder_name.setText(initial_name)
        self._update_validation()
        self.folder_name.setFocus()
        self.folder_name.selectAll()

    def _folder_changed(self, name: str):
        if self._title_auto:
            self.game_title.setText(name)
        self.location.setText(str(self._parent_directory / name))
        self._update_validation()

    def _title_edited(self, _value: str):
        self._title_auto = False

    def _location_edited(self):
        """A manually entered full path also updates the folder-name field."""
        raw = self.location.text().strip()
        if not raw:
            self._update_validation()
            return
        destination = Path(raw).expanduser().absolute()
        self._parent_directory = destination.parent
        if destination.name != self.folder_name.text():
            self.folder_name.setText(destination.name)
        self.location.setText(str(destination))
        self._update_validation()

    def browse_directory(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier parent du projet",
            str(self._parent_directory))
        if selected:
            self._parent_directory = Path(selected).absolute()
            self.location.setText(
                str(self._parent_directory / self.folder_name.text()))

    def project_spec(self) -> ProjectSpec:
        return ProjectSpec(
            "blank", self.location.text().strip(),
            title=self.game_title.text().strip(),
        )

    def _validation_error(self) -> str:
        error = folder_error(self.folder_name.text())
        if error:
            return error
        if not self.game_title.text().strip():
            return "Indiquez le titre du jeu."
        if self.location.text().strip() != str(
                self._parent_directory / self.folder_name.text()):
            return "L'emplacement et le nom du dossier ne correspondent pas."
        report = project_preview(self.project_spec())
        return "; ".join(report["errors"])

    def _update_validation(self, *_):
        error = self._validation_error()
        self.error_label.setText(error)
        self.error_label.setVisible(bool(error))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            not error)

    def create(self):
        self._location_edited()
        error = self._validation_error()
        if error:
            self._update_validation()
            return
        try:
            self.created_content_path = create_project(self.project_spec())
        except (ExportError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Création impossible", str(exc))
            return
        self.settings.setValue(
            "projects/parent_directory", str(self._parent_directory))
        self.accept()
