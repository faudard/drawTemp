"""R30.G Qt Widgets preview of deterministic terrain/lever-door helpers.

The render grid is only a preview of the selected rectangle, NOT a second map
renderer or tactical truth. R1 validates the real Content/GameProject candidate.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QLineEdit,
)

from drawtemp.studio.r30_assist_generation import AssistController


class R30AssistDialog(QDialog):
    """Preview generates no persistent edits; explicit Apply creates one Undo."""

    def __init__(self, session, *, parent=None):
        super().__init__(parent)
        self.setObjectName("r30g-assist-dialog")
        self.setWindowTitle("DrawTemp R30.G — Génération assistée contrôlée")
        self.resize(920, 710)
        self.session = session
        self.controller = AssistController(session)
        self._preview = None
        root = QVBoxLayout(self)
        note = QLabel(
            "Génération DÉTERMINISTE et locale, sans IA ni script. "
            "Terrain : cases vierges uniquement. Puzzle : amorce levier/porte "
            "accessible, sans garantie que la porte soit incontournable. "
            "Prévisualiser avant d'appliquer ; sauvegarde manuelle, Undo disponible.")
        note.setWordWrap(True)
        root.addWidget(note)
        form = QGridLayout()
        self.mission_box = QComboBox()
        self.mission_box.setAccessibleName("Mission à modifier")
        for mission in session.snapshot().content["missions"]:
            self.mission_box.addItem(mission.get("name", mission["id"]), mission["id"])
        self.mode_box = QComboBox()
        self.mode_box.setAccessibleName("Mode de génération")
        for label, mode in (
            ("Clairière / mosaïque de surfaces", "clearing"),
            ("Sentier quatre-connecté", "trail"),
            ("Puzzle levier / porte (amorce)", "lever-door"),
        ):
            self.mode_box.addItem(label, mode)
        form.addWidget(QLabel("Mission"), 0, 0)
        form.addWidget(self.mission_box, 0, 1, 1, 4)
        form.addWidget(QLabel("Générateur"), 1, 0)
        form.addWidget(self.mode_box, 1, 1, 1, 4)
        self.coords = []
        for index, (title, initial, low, high) in enumerate((
            ("X", 0, 0, 127), ("Y", 0, 0, 127),
            ("Largeur", 4, 1, 16), ("Hauteur", 4, 1, 16),
        )):
            control = QSpinBox()
            control.setAccessibleName("Rectangle : " + title)
            control.setRange(low, high)
            control.setValue(initial)
            self.coords.append(control)
            form.addWidget(QLabel(title), 2, 2 * index % 4)
            form.addWidget(control, 2 + index // 2, 2 * index % 4 + 1)
        self.seed_spin = QSpinBox()
        self.seed_spin.setAccessibleName("Graine déterministe")
        self.seed_spin.setRange(0, 2147483647)
        self.seed_spin.setValue(7)
        self.namespace_input = QLineEdit("demo")
        self.namespace_input.setMaxLength(12)
        self.namespace_input.setAccessibleName("Identifiant du puzzle")
        form.addWidget(QLabel("Seed"), 4, 0)
        form.addWidget(self.seed_spin, 4, 1)
        form.addWidget(QLabel("Namespace"), 4, 2)
        form.addWidget(self.namespace_input, 4, 3)
        root.addLayout(form)
        self.preview_grid = QTableWidget(0, 0)
        self.preview_grid.setAccessibleName("Aperçu du rectangle généré")
        self.preview_grid.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.preview_grid)
        self.status = QLabel("Choisir un rectangle, puis demander une prévisualisation.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Diagnostic de génération et validation")
        root.addWidget(self.status)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser sans modifier")
        self.preview_button.clicked.connect(self.preview_generation)
        actions.addWidget(self.preview_button)
        self.apply_button = QPushButton("Appliquer dans le Studio…")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._confirm_apply)
        actions.addWidget(self.apply_button)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        root.addLayout(actions)
        for widget in (*self.coords, self.seed_spin):
            widget.valueChanged.connect(self.invalidate)
        for widget in (self.mission_box, self.mode_box):
            widget.currentIndexChanged.connect(self.invalidate)
        self.namespace_input.textChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.controller.invalidate()
        self._preview = None
        self.apply_button.setEnabled(False)
        self.preview_grid.setRowCount(0)
        self.preview_grid.setColumnCount(0)
        self.status.setText("Paramètres modifiés : nouvel aperçu requis.")

    def preview_generation(self):
        self.invalidate()
        rectangle = tuple(control.value() for control in self.coords)
        try:
            preview = self.controller.preview(
                self.mission_box.currentData(),
                rectangle=rectangle, mode=self.mode_box.currentData(),
                seed=self.seed_spin.value(),
                namespace=self.namespace_input.text().strip())
        except (OSError, ValueError) as exc:
            self.status.setText("Aperçu refusé : " + str(exc))
            return None
        self._preview = preview
        self._render(preview)
        self.apply_button.setEnabled(True)
        self.status.setText(
            f"{len(preview.tiles)} case(s) modifiée(s), "
            f"{len(preview.object_ids)} objet(s) proposés, "
            f"{preview.protected_count} cellule(s) réservée(s). "
            "Enigme accessible au niveau du levier : " +
            ("oui" if preview.switch_reachable else "sans objet") +
            ". Application : un seul Undo, aucune écriture disque.")
        return preview

    def _render(self, report):
        x, y, width, height = report.rectangle
        changed = {(cell.x, cell.y): cell.after for cell in report.tiles}
        self.preview_grid.setRowCount(height)
        self.preview_grid.setColumnCount(width)
        self.preview_grid.setVerticalHeaderLabels(
            [str(y + row) for row in range(height)])
        self.preview_grid.setHorizontalHeaderLabels(
            [str(x + col) for col in range(width)])
        for row in range(height):
            for col in range(width):
                key = (x + col, y + row)
                surface = changed.get(key)
                cell = QTableWidgetItem(surface or "·")
                cell.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if surface:
                    cell.setBackground(QColor({
                        "grass": "#598e56", "dirt": "#aa825b",
                        "sand": "#dac278", "stone": "#989ea6",
                        "cobble": "#82868a",
                    }.get(surface, "#7b9c6f")))
                    cell.setForeground(QColor("#111111"))
                self.preview_grid.setItem(row, col, cell)
        self.preview_grid.resizeColumnsToContents()

    def _confirm_apply(self):
        if not self.apply_button.isEnabled():
            return
        decision = QMessageBox.question(
            self, "Confirmer la génération R30.G",
            "Ajouter exactement les éléments prévisualisés dans la session "
            "Studio ? Un Undo est possible. Rien n'est enregistré sur disque.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if decision == QMessageBox.Yes:
            self.apply_generation()

    def apply_generation(self):
        if self._preview is None or not self.apply_button.isEnabled():
            return None
        preview = self._preview
        self._preview = None
        self.apply_button.setEnabled(False)
        try:
            transition = self.controller.apply(preview)
        except (OSError, ValueError) as exc:
            self.status.setText("Application refusée : " + str(exc))
            return None
        self.status.setText(
            f"Appliqué à la révision {transition.snapshot.revision}. "
            "Pour annuler, utilisez Édition → Annuler dans le Studio ; "
            "enregistrement disque séparé.")
        return transition
