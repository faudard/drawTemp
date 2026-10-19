"""R28.E — native Qt gallery for three independently created R15 minigames.

Projects are created only on an explicit click. No project currently open in
the Studio is modified; opening a generated project uses the shell's normal
unsaved-changes policy.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from drawtemp.studio.r28e_minigames import (
    MINIGAMES, MiniGameError, audit_minigame, certification_matrix,
    create_minigame, create_portfolio, preview_minigame,
)
from sporebound.model import RuleError


class MiniGameGallery(QWidget):
    """UI creator with honest executable coverage and explicit release blockers."""

    openRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("r28e-minigames-gallery")
        self._created = {}
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("R28.E — Mini-jeux de référence et certification 6.4"))
        notice = QLabel(
            "Trois projets distincts (2 tactiques, 1 narratif). "
            "La certification trois genres et le Player Action R26 restent bloqués.")
        notice.setWordWrap(True)
        outer.addWidget(notice)
        form = QFormLayout()
        self.game = QComboBox()
        self.game.setAccessibleName("Mini-jeu à créer")
        for spec in MINIGAMES:
            self.game.addItem(spec.label + " — " + spec.genre, spec.key)
        form.addRow("Mini-jeu", self.game)
        self.parent_path = QLineEdit()
        self.parent_path.setPlaceholderText("Dossier parent existant (jamais écrasé)")
        self.parent_path.setAccessibleName("Dossier parent de création")
        choose = QPushButton("Choisir…")
        choose.clicked.connect(self.browse_parent)
        parent_row = QHBoxLayout()
        parent_row.addWidget(self.parent_path, 1)
        parent_row.addWidget(choose)
        form.addRow("Dossier parent", parent_row)
        outer.addLayout(form)
        self.description = QLabel("")
        self.description.setWordWrap(True)
        outer.addWidget(self.description)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Aperçu sans écriture")
        self.preview_button.clicked.connect(self.preview)
        buttons.addWidget(self.preview_button)
        self.create_button = QPushButton("Créer le mini-jeu sélectionné")
        self.create_button.setObjectName("r28e-create-one")
        self.create_button.clicked.connect(self.create_selected)
        buttons.addWidget(self.create_button)
        self.all_button = QPushButton("Créer les 3 mini-jeux")
        self.all_button.setObjectName("r28e-create-three")
        self.all_button.clicked.connect(self.create_three)
        buttons.addWidget(self.all_button)
        outer.addLayout(buttons)

        follow = QHBoxLayout()
        self.open_button = QPushButton("Ouvrir le projet créé dans le Studio")
        self.open_button.setObjectName("r28e-open-created")
        self.open_button.clicked.connect(self.open_selected)
        follow.addWidget(self.open_button)
        self.audit_button = QPushButton("Vérifier le mini-jeu")
        self.audit_button.clicked.connect(self.audit_selected)
        follow.addWidget(self.audit_button)
        self.matrix_button = QPushButton("Matrice de certification")
        self.matrix_button.clicked.connect(self.certify)
        follow.addWidget(self.matrix_button)
        outer.addLayout(follow)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Rapport de création, tests et certification")
        outer.addWidget(self.report, 1)
        self.game.currentIndexChanged.connect(self._selected)
        self.parent_path.textChanged.connect(self._selected)
        self._selected()

    def _selected(self, *_):
        spec = next(row for row in MINIGAMES if row.key == self.game.currentData())
        self.description.setText(spec.description)
        target = self._created.get(spec.key)
        enabled = bool(target and target.joinpath("game.json").is_file())
        self.open_button.setEnabled(enabled)
        self.audit_button.setEnabled(enabled)

    def browse_parent(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier parent pour les projets", self.parent_path.text())
        if folder:
            self.parent_path.setText(folder)

    def _directory(self):
        value = self.parent_path.text().strip()
        if not value:
            raise MiniGameError("Choisissez d'abord un dossier parent existant.")
        root = Path(value).expanduser().absolute()
        if not root.is_dir():
            raise MiniGameError("Le dossier parent n'existe pas.")
        return root

    def _print(self, result):
        self.report.setPlainText(json.dumps(
            result, indent=2, ensure_ascii=False, default=str))

    def _error(self, error):
        self.report.setPlainText("Opération refusée : " + str(error))

    def preview(self):
        try:
            destination = self._directory() / self.game.currentData()
            self._print(preview_minigame(self.game.currentData(), destination))
        except (MiniGameError, RuleError, ValueError, OSError) as exc:
            self._error(exc)

    def create_selected(self):
        try:
            key = self.game.currentData()
            destination = self._directory() / key
            preview_minigame(key, destination)
            result = create_minigame(key, destination)
            self._created[key] = result
            report = audit_minigame(result / "game.json", key)
            self._print({"created": str(result), "audit": report})
        except (MiniGameError, RuleError, OSError, ValueError) as exc:
            self._error(exc)
        self._selected()

    def create_three(self):
        try:
            target = self._directory() / "DrawTemp_R28_MiniGames"
            portfolio = create_portfolio(target)
            for spec in MINIGAMES:
                self._created[spec.key] = portfolio / spec.key
            self._print({"created_portfolio": str(portfolio),
                         "certification": certification_matrix(portfolio)})
        except (MiniGameError, RuleError, ValueError, OSError) as exc:
            self._error(exc)
        self._selected()

    def audit_selected(self):
        try:
            key = self.game.currentData()
            target = self._created.get(key)
            if target is None:
                raise MiniGameError("Créer d'abord ce mini-jeu.")
            self._print(audit_minigame(target / "game.json", key))
        except (MiniGameError, RuleError, ValueError, OSError) as exc:
            self._error(exc)

    def certify(self):
        try:
            root = self._directory() / "DrawTemp_R28_MiniGames"
            self._print(certification_matrix(root))
        except (MiniGameError, RuleError, ValueError, OSError) as exc:
            self._error(exc)

    def open_selected(self):
        key = self.game.currentData()
        path = self._created.get(key)
        if path is not None and (path / "game.json").is_file():
            self.openRequested.emit(str(path / "game.json"))
        else:
            self._error(MiniGameError("Mini-jeu inexistant ou non créé."))
