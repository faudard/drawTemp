"""Help menu UI: documentation, tutorial catalog and About.

The catalog is a UI-only placeholder for future tutorial content. It must not
mutate the project, start a player, or claim that tutorials are implemented.
"""
from __future__ import annotations

from importlib import metadata

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)


DOCS_URL = "https://github.com/faudard/drawTemp/tree/master/docs"

# Keep IDs stable when lessons are authored in a later PR.
TUTORIAL_CATALOG = (
    ("first_steps", "Premiers pas dans DrawTemp"),
    ("map_basics", "Créer une carte"),
    ("tiles_layers", "Terrains, tuiles et calques"),
    ("camera", "Naviguer, déplacer la caméra et zoomer"),
    ("actors", "Placer un personnage"),
    ("dialogue", "Créer un dialogue"),
    ("events", "Créer un événement"),
    ("switches", "Interrupteurs et conditions"),
    ("branching", "Événements et embranchements conditionnels"),
    ("treasure", "Coffres et récompenses"),
    ("doors", "Portes, leviers et interactions"),
    ("transitions", "Passer d'une carte à une autre"),
    ("quests", "Créer une quête"),
    ("database", "Personnages et base de données"),
    ("abilities", "Compétences et classes"),
    ("combat", "Créer un combat tactique"),
    ("objectives", "Objectifs et conditions de victoire"),
    ("boss", "Créer un boss à plusieurs phases"),
    ("playtest", "Tester et sauvegarder son jeu"),
)


class TutorialSelectorDialog(QDialog):
    """Screenshot-inspired tutorial picker; lessons are intentionally unavailable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tutorial-selector-dialog")
        self.setWindowTitle("Tutorial Selector")
        self.resize(600, 430)

        root = QHBoxLayout(self)
        self.tutorial_list = QListWidget(self)
        self.tutorial_list.setObjectName("tutorial-selector-list")
        self.tutorial_list.setAccessibleName("Liste des exemples de tutoriels")
        self.tutorial_list.setAlternatingRowColors(True)
        for number, (tutorial_id, title) in enumerate(TUTORIAL_CATALOG, 1):
            item = QListWidgetItem(f"Étape {number} : {title}")
            item.setData(Qt.ItemDataRole.UserRole, tutorial_id)
            self.tutorial_list.addItem(item)
        self.tutorial_list.setCurrentRow(0)
        root.addWidget(self.tutorial_list, 3)

        sidebar = QVBoxLayout()
        self.start_button = QPushButton("Démarrer le tutoriel…")
        self.start_button.setObjectName("tutorial-selector-start")
        self.start_button.setAccessibleName("Démarrer le tutoriel sélectionné")
        self.start_button.setEnabled(False)
        self.start_button.setToolTip(
            "Les tutoriels seront créés dans une prochaine version.")
        sidebar.addWidget(self.start_button)

        notice = QLabel("Tutoriels à venir.\nLa liste présente les sujets prévus.")
        notice.setObjectName("tutorial-selector-notice")
        notice.setWordWrap(True)
        sidebar.addWidget(notice)
        sidebar.addStretch(1)

        close_button = QPushButton("Fermer")
        close_button.setObjectName("tutorial-selector-close")
        close_button.clicked.connect(self.reject)
        sidebar.addWidget(close_button)
        root.addLayout(sidebar, 2)


def open_docs(parent=None) -> bool:
    """Open the repository's published documentation directory."""
    opened = QDesktopServices.openUrl(QUrl(DOCS_URL))
    if not opened:
        QMessageBox.warning(
            parent, "Documentation",
            "Impossible d'ouvrir la documentation dans le navigateur.\n"
            + DOCS_URL,
        )
    return opened


def show_about(parent=None) -> None:
    """Present the installed distribution's version, when available."""
    try:
        version = metadata.version("drawtemp-tactics")
    except metadata.PackageNotFoundError:
        version = "version de développement"
    QMessageBox.about(
        parent,
        "À propos de DrawTemp",
        "DrawTemp Studio\n"
        f"Version : {version}\n\n"
        "Éditeur de jeux 2D / 2.5D en Python et PySide6.\n"
        "Le Studio et le Player utilisent le même format de projet.\n\n"
        "Documentation : " + DOCS_URL,
    )
