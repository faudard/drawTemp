"""R50.B Qt catalog for existing Studio: only connected workflows are enabled.

The widget is a client of R50.B headless authoring, never a replacement for
the project's canonical Studio/Player or a GPU/hardware certification.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QComboBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from drawtemp.studio.r50b_catalog import (
    CatalogError, catalog, create_starter, preview_starter,
)


class R50CatalogWidget(QWidget):
    openRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r50b-catalog")
        self._created = {}
        outer = QVBoxLayout(self)
        heading = QLabel("R50.B — Catalogue Creator 9.0 (démonstrateur, NO-GO)")
        heading.setWordWrap(True)
        outer.addWidget(heading)
        self.genre = QComboBox()
        self.genre.setAccessibleName("Genre du projet R50")
        for entry in catalog()["entries"]:
            suffix = "création headless" if entry["can_create"] else "non disponible"
            self.genre.addItem(entry["title"] + " — " + suffix, entry["id"])
        form = QFormLayout()
        form.addRow("Genre", self.genre)
        self.parent_folder = QLineEdit()
        self.parent_folder.setObjectName("r50b-parent-folder")
        self.parent_folder.setPlaceholderText("Dossier parent existant")
        self.parent_folder.setAccessibleName("Dossier parent du nouveau projet")
        browse = QPushButton("Choisir…")
        browse.clicked.connect(self.browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.parent_folder)
        folder_row.addWidget(browse)
        form.addRow("Dossier parent", folder_row)
        outer.addLayout(form)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        outer.addWidget(self.warning)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Vérifier la disponibilité")
        self.preview_button.clicked.connect(self.preview)
        actions.addWidget(self.preview_button)
        self.create_button = QPushButton("Créer et tester (headless)")
        self.create_button.setObjectName("r50b-create")
        self.create_button.clicked.connect(self.create)
        actions.addWidget(self.create_button)
        self.open_button = QPushButton("Ouvrir dans Studio")
        self.open_button.setObjectName("r50b-open")
        self.open_button.clicked.connect(self.open_created)
        actions.addWidget(self.open_button)
        outer.addLayout(actions)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Diagnostic R50.B; ne certifie pas le Player")
        outer.addWidget(self.report)
        self.genre.currentIndexChanged.connect(self.refresh)
        self.parent_folder.textChanged.connect(self.refresh)
        self.refresh()

    def browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier pour les nouveaux projets", self.parent_folder.text())
        if folder:
            self.parent_folder.setText(folder)

    def _entry(self):
        return next(x for x in catalog()["entries"]
                    if x["id"] == self.genre.currentData())

    def _target(self):
        parent = self.parent_folder.text().strip()
        if not parent:
            raise CatalogError("Choisissez un dossier parent.")
        root = Path(parent).expanduser().absolute()
        if not root.is_dir():
            raise CatalogError("Le dossier parent n'existe pas.")
        return root / self.genre.currentData()

    def refresh(self, *_):
        entry = self._entry()
        self.warning.setText(entry["limitation"])
        self.create_button.setEnabled(entry["can_create"])
        self.open_button.setEnabled(
            bool(self._created.get(entry["id"]) and
                 self._created[entry["id"]].is_file()))

    def _output(self, result):
        self.report.setPlainText(json.dumps(
            result, ensure_ascii=False, indent=2, sort_keys=True))

    def preview(self):
        try:
            self._output(preview_starter(self.genre.currentData(), self._target()))
        except (CatalogError, OSError, ValueError) as exc:
            self.report.setPlainText("Prévisualisation refusée : " + str(exc))

    def create(self):
        try:
            key = self.genre.currentData()
            result = create_starter(key, self._target())
            self._created[key] = Path(result["content_path"])
            self._output(result)
        except (CatalogError, OSError, ValueError) as exc:
            self.report.setPlainText("Création refusée : " + str(exc))
        self.refresh()

    def open_created(self):
        path = self._created.get(self.genre.currentData())
        if path is not None and path.is_file():
            self.openRequested.emit(str(path))
        else:
            self.report.setPlainText("Aucun projet créé pour cette entrée.")
