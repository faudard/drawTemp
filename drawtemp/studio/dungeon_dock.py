"""R27.A Qt dungeon controls over the existing R3 viewport and R1 history.

This dock is contextual to R5 MapWindow: no second QML scene or document owner.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
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
        journey = QPushButton("Créer un parcours village → temple → boss → retour")
        journey.setObjectName("r27_build_journey")
        journey.clicked.connect(self.create_journey)
        layout.addWidget(journey)

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
        self.kind.addItem("Clé", "key")
        self.kind.addItem("Plaque de pression", "plate")
        self.kind.addItem("Bloc à pousser", "block")
        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("Identifiant unique (vide = automatique)")
        self.object_x, self.object_y = _spin(7), _spin(2)
        self.link = QComboBox()
        self.amount = QSpinBox()
        self.amount.setRange(0, 10000)
        self.amount.setValue(25)
        self.locked = QCheckBox("Porte verrouillée")
        self.locked.setChecked(True)
        self.latch = QCheckBox("Plaque mémorisée après activation")
        self.latch.setChecked(True)
        objects.addRow("Interaction", self.kind)
        objects.addRow("Identifiant", self.identifier)
        objects.addRow("Position (X/Y)", self._pair(self.object_x, self.object_y))
        objects.addRow("Porte liée au levier", self.link)
        objects.addRow("Gain du coffre", self.amount)
        objects.addRow("", self.locked)
        objects.addRow("", self.latch)
        layout.addLayout(objects)
        place = QPushButton("Placer l'interaction")
        place.setObjectName("r27_place_object")
        place.clicked.connect(self.place_object)
        layout.addWidget(place)
        layout.addWidget(QLabel("Séquence de leviers (ex. levier_a, levier_b)"))
        self.sequence = QLineEdit()
        self.sequence.setPlaceholderText("IDs séparés par des virgules, dans l'ordre")
        layout.addWidget(self.sequence)
        self.reset_sequence = QCheckBox("Réinitialiser après erreur")
        self.reset_sequence.setChecked(True)
        layout.addWidget(self.reset_sequence)
        set_order = QPushButton("Configurer la séquence de la porte sélectionnée")
        set_order.setObjectName("r27_configure_sequence")
        set_order.clicked.connect(self.configure_sequence)
        layout.addWidget(set_order)

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
        layout.addWidget(QLabel("Graphe de puzzles (sélectionner pour localiser)"))
        self.graph = QTreeWidget()
        self.graph.setObjectName("r27_puzzle_graph")
        self.graph.setHeaderLabels(["Nœud", "Type", "Lien / ordre"])
        self.graph.setMinimumHeight(125)
        self.graph.itemClicked.connect(self.select_graph_node)
        layout.addWidget(self.graph)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setObjectName("r27_puzzle_diagnostics")
        self.report.setPlainText(
            "Recherche bornée : cases, clés, leviers, séquences, plaques "
            "et blocs. Combat, sauvegardes inter-scènes et transitions "
            "ne sont pas certifiés.")
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
        selected = self.graph.currentItem()
        selected_id = selected.text(0) if selected is not None else None
        self.graph.blockSignals(True)
        self.graph.clear()
        graph = self._studio().puzzle_graph()
        outgoing = {}
        for edge in graph["edges"]:
            outgoing.setdefault(edge["from"], []).append(
                "{} → {}{}".format(
                    edge["type"], edge["to"],
                    " #" + str(edge["order"]) if "order" in edge else ""))
        for node in graph["nodes"]:
            item = QTreeWidgetItem([
                node["id"], node["kind"],
                "; ".join(outgoing.get(node["id"], ()))])
            self.graph.addTopLevelItem(item)
            if node["id"] == selected_id:
                self.graph.setCurrentItem(item)
        self.graph.blockSignals(False)

    def select_graph_node(self, item, _column):
        identifier = item.text(0)
        target = next((o for o in self.window.studio.mission()["objects"]
                       if o["id"] == identifier), None)
        if target is not None:
            self.set_position(*target["pos"])

    def configure_sequence(self):
        door_id = self.link.currentData()
        if not door_id:
            return
        order = self.sequence.text().replace(",", " ").split()
        self.window._safe(lambda: self._studio().set_sequence(
            door_id, order, reset_on_error=self.reset_sequence.isChecked()))
        self.refresh()

    def create_journey(self):
        prefix, ok = QInputDialog.getText(
            self, "Parcours R27.D",
            "Préfixe des missions et de la campagne (unique)",
            text="r27")
        if not ok or not prefix.strip():
            return
        confirmed = QMessageBox.question(
            self, "Ajouter le parcours au projet",
            "Cette création ajoute 4 missions et modifie le manifeste de "
            "campagne. Les sauvegardes existantes du projet peuvent devenir "
            "incompatibles avec les nouvelles empreintes Content/Project. "
            "Travaillez sur une copie ou un projet non publié. Continuer ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirmed != QMessageBox.Yes:
            return
        from .dungeon_journey import build_dungeon_journey
        self.window._safe(lambda: build_dungeon_journey(
            self.window.studio, prefix=prefix.strip()))
        self.window.refresh_maps()

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
        stem = {"door": "door", "switch": "lever", "chest": "chest",
                "key": "key", "plate": "plate", "block": "block"}[kind]
        identifier = self.identifier.text().strip()
        if not identifier:
            identifier = stem
            index = 2
            while identifier in existing:
                identifier = f"{stem}_{index}"
                index += 1
        if kind in ("key", "plate", "block"):
            self.window._safe(lambda: self._studio().place_puzzle(
                identifier, kind,
                (self.object_x.value(), self.object_y.value()),
                door_id=self.link.currentData() or "",
                latch=self.latch.isChecked()))
        else:
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
        if result.get("witness"):
            lines.append("Trajet témoin (recherche headless) :")
            lines.extend("  " + action for action in result["witness"][:80])
            if len(result["witness"]) > 80:
                lines.append("  … parcours tronqué à 80 actions affichées")
        lines += ["Analyse symbolique ≠ validation du Player, des ennemis ou des sauvegardes."]
        self.report.setPlainText("\n".join(lines))
