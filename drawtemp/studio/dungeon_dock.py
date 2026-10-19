"""R27.A Qt dungeon controls over the existing R3 viewport and R1 history.

This dock is contextual to R5 MapWindow: no second QML scene or document owner.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

from .dungeon_authoring import DungeonStudio


def _spin(value=0):
    widget = QSpinBox()
    widget.setRange(0, 127)
    widget.setValue(value)
    return widget


class DungeonDock(QDockWidget):
    def __init__(self, window):
        super().__init__("R27 • Donjons et énigmes", window)
        self.setObjectName("r27_dungeon_dock")
        self.window = window
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(QLabel(
            "Les salles utilisent les cases R5, et les portes/leviers/coffres "
            "les interactions du Player existant. Un clic dans le viewport "
            "règle la position de l'objet."))
        new_map = QPushButton("Créer une carte de donjon liée")
        new_map.setObjectName("r27_create_dungeon")
        new_map.clicked.connect(self.create_dungeon)
        layout.addWidget(new_map)

        room = QFormLayout()
        self.x0, self.y0 = _spin(3), _spin(3)
        self.x1, self.y1 = _spin(10), _spin(10)
        self.entry_x, self.entry_y = _spin(7), _spin(3)
        room.addRow("Salle coin haut-gauche (X/Y)", self._pair(self.x0, self.y0))
        room.addRow("Salle coin bas-droite (X/Y)", self._pair(self.x1, self.y1))
        room.addRow("Entrée sur le mur (X/Y)", self._pair(self.entry_x, self.entry_y))
        layout.addLayout(room)
        room_button = QPushButton("Construire salle + porte verrouillée")
        room_button.setObjectName("r27_build_room")
        room_button.clicked.connect(self.build_room)
        layout.addWidget(room_button)

        objects = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItem("Porte", "door")
        self.kind.addItem("Levier", "switch")
        self.kind.addItem("Coffre", "chest")
        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("Identifiant unique (vide = automatique)")
        self.object_x, self.object_y = _spin(7), _spin(2)
        self.link = QComboBox()
        self.amount = QSpinBox()
        self.amount.setRange(0, 10000)
        self.amount.setValue(25)
        self.locked = QCheckBox("Porte verrouillée")
        self.locked.setChecked(True)
        objects.addRow("Interaction", self.kind)
        objects.addRow("Identifiant", self.identifier)
        objects.addRow("Position (X/Y)", self._pair(self.object_x, self.object_y))
        objects.addRow("Porte liée au levier", self.link)
        objects.addRow("Gain du coffre", self.amount)
        objects.addRow("", self.locked)
        layout.addLayout(objects)
        place = QPushButton("Placer l'interaction")
        place.setObjectName("r27_place_object")
        place.clicked.connect(self.place_object)
        layout.addWidget(place)

        self.destination = QComboBox()
        layout.addWidget(QLabel("Carte de destination (graphe de progression)"))
        layout.addWidget(self.destination)
        link_button = QPushButton("Relier la carte actuelle à cette destination")
        link_button.setObjectName("r27_link_maps")
        link_button.clicked.connect(self.link_maps)
        layout.addWidget(link_button)

        inspect = QPushButton("Analyser leviers, coffres et issues")
        inspect.setObjectName("r27_puzzle_report")
        inspect.clicked.connect(self.show_report)
        layout.addWidget(inspect)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setObjectName("r27_puzzle_diagnostics")
        self.report.setPlainText(
            "Analyse statique limitée aux déplacements orthogonaux, "
            "portes/leviers et objectifs. Combat, clés, sauvegardes et "
            "conditions narratives non certifiés.")
        layout.addWidget(self.report, 1)
        self.setWidget(body)

    @staticmethod
    def _pair(left, right):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(left)
        row.addWidget(right)
        return container

    def _studio(self):
        return DungeonStudio(self.window.studio)

    def set_position(self, x, y):
        self.object_x.setValue(x)
        self.object_y.setValue(y)

    def refresh(self):
        mission = self.window.studio.mission()
        previous = self.link.currentData()
        self.link.blockSignals(True)
        self.link.clear()
        for row in mission["objects"]:
            if row["kind"] == "door":
                self.link.addItem(row["id"], row["id"])
        index = self.link.findData(previous)
        if index >= 0:
            self.link.setCurrentIndex(index)
        self.link.blockSignals(False)
        old = self.destination.currentData()
        self.destination.blockSignals(True)
        self.destination.clear()
        for candidate in self.window.studio.snapshot()["content"]["missions"]:
            if candidate["id"] != self.window.studio.mission_id:
                self.destination.addItem(candidate["name"], candidate["id"])
        index = self.destination.findData(old)
        if index >= 0:
            self.destination.setCurrentIndex(index)
        self.destination.blockSignals(False)

    def create_dungeon(self):
        mid, ok = QInputDialog.getText(
            self, "Nouveau donjon", "Identifiant stable du donjon")
        if not ok or not mid.strip():
            return
        name, ok = QInputDialog.getText(
            self, "Nouveau donjon", "Nom du donjon", text=mid.strip())
        if not ok or not name.strip():
            return
        parent = self.window.studio.mission_id
        self.window._safe(lambda: self._studio().create_dungeon(
            mid.strip(), name.strip(), width=16, height=16, from_map=parent))
        self.window.refresh_maps()

    def build_room(self):
        self.window._safe(lambda: self._studio().build_room(
            (self.x0.value(), self.y0.value()),
            (self.x1.value(), self.y1.value()),
            entrance=(self.entry_x.value(), self.entry_y.value())))
        self.refresh()

    def place_object(self):
        kind = self.kind.currentData()
        mission = self.window.studio.mission()
        existing = {o["id"] for o in mission["objects"]}
        stem = {"door": "door", "switch": "lever", "chest": "chest"}[kind]
        identifier = self.identifier.text().strip()
        if not identifier:
            identifier = stem
            index = 2
            while identifier in existing:
                identifier = f"{stem}_{index}"
                index += 1
        self.window._safe(lambda: self._studio().place_object(
            identifier, kind,
            (self.object_x.value(), self.object_y.value()),
            link=self.link.currentData() or "",
            amount=self.amount.value(), locked=self.locked.isChecked()))
        self.refresh()

    def link_maps(self):
        target = self.destination.currentData()
        if target is not None:
            self.window._safe(lambda: self._studio().link_maps(target))

    def show_report(self):
        try:
            result = self._studio().puzzle_report()
        except (ValueError, TypeError) as exc:
            self.report.setPlainText(str(exc))
            return
        lines = [
            "Analyse terminée" if result["complete"] else "Analyse incomplète",
            f'États explorés : {result["states"]}',
            f'Objectifs accessibles : {len(result["reachable_goals"])}',
            f'Objectifs inaccessibles : {len(result["unreachable_goals"])}',
        ]
        lines += result["warnings"] or ["Aucune impasse détectée dans le modèle statique."]
        lines += ["Ce diagnostic ne remplace pas un playtest dans le Player."]
        self.report.setPlainText("\n".join(lines))
