"""R63.B native Survival Designer — typed forms, map placement and Studio history.

Every control edits a detached draft. Apply is one canonical AuthoringSession
transaction; no JSON editor, script execution or second inventory database.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QPlainTextEdit, QSpinBox, QSplitter,
    QTabWidget, QVBoxLayout, QWidget,
)

from drawtemp.studio.survival_authoring import (
    apply_survival_design, preview_survival_design)
from sporebound.survival import EXTENSION, SurvivalRuntime, validate_survival


def starter_survival(scene):
    """Detached, valid two-recipe starting point; never auto-applied."""
    return {
        "version": 1,
        "needs": {"energy": 85, "hunger": 80, "temperature": 80,
                  "energy_drain": 1, "hunger_drain": 1, "cold_drain": 1},
        "items": ["axe", "wood", "stone", "berries", "camp", "ration"],
        "tools": [{"id": "axe", "durability": 12}],
        "nodes": [
            {"id": "forest", "scene": scene, "item": "wood", "stock": 20,
             "yield": 1, "tool": "axe", "wear": 1, "energy_cost": 4, "cold": 8},
            {"id": "quarry", "scene": scene, "item": "stone", "stock": 20,
             "yield": 1, "tool": None, "wear": 0, "energy_cost": 5, "cold": 0},
            {"id": "bush", "scene": scene, "item": "berries", "stock": 20,
             "yield": 2, "tool": None, "wear": 0, "energy_cost": 2, "cold": 0},
        ],
        "recipes": [
            {"id": "build_camp", "inputs": {"wood": 1, "stone": 1},
             "outputs": {"camp": 1}, "energy_cost": 5},
            {"id": "cook_ration", "inputs": {"berries": 2},
             "outputs": {"ration": 1}, "energy_cost": 3},
        ],
        "shelters": [
            {"id": "refuge", "scene": scene, "fuel": {"camp": 1},
             "energy_restore": 35, "warmth": 30}],
        "foods": [{"item": "ration", "nutrition": 20}],
    }


def parse_materials(raw, allowed):
    """No expressions, coercions, repeated identifiers or inferred items."""
    if type(raw) is not str:
        raise ValueError("Les matériaux doivent être du texte id:quantité.")
    parts = raw.split(",")
    if not 1 <= len(parts) <= 8:
        raise ValueError("Une liste contient 1 à 8 matériaux.")
    result = {}
    for part in parts:
        pair = part.strip().split(":")
        if len(pair) != 2:
            raise ValueError("Format attendu : bois:2, pierre:1")
        key, number = (x.strip() for x in pair)
        if key not in allowed or key in result:
            raise ValueError("Objet inconnu ou doublon : " + key)
        if not number.isascii() or not number.isdecimal():
            raise ValueError("Quantité entière requise : " + key)
        amount = int(number)
        if not 1 <= amount <= 99:
            raise ValueError("Quantité hors limites (1 à 99) : " + key)
        result[key] = amount
    return result


def _material_text(rows):
    return ", ".join(f"{k}:{v}" for k, v in sorted(rows.items()))


def typed_form(parent, title, definitions):
    """Small accessible modal input dialog returning typed, detached values."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    form = QFormLayout(dialog)
    controls = {}
    for key, label, kind, initial, bounds in definitions:
        if kind == "number":
            control = QSpinBox(dialog)
            control.setRange(*bounds)
            control.setValue(initial)
        elif kind == "choice":
            control = QComboBox(dialog)
            control.addItems(bounds)
            control.setCurrentText(initial if initial is not None else "(aucun)")
        else:
            control = QLineEdit(initial, dialog)
        control.setObjectName("r63Field_" + key)
        control.setAccessibleName(label)
        form.addRow(label, control)
        controls[key] = control
    actions = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    actions.accepted.connect(dialog.accept)
    actions.rejected.connect(dialog.reject)
    form.addRow(actions)
    if dialog.exec() != QDialog.Accepted:
        return None
    return {key: (control.value() if isinstance(control, QSpinBox) else
                  control.currentText() if isinstance(control, QComboBox) else
                  control.text().strip())
            for key, control in controls.items()}


class SurvivalMapView(QGraphicsView):
    def __init__(self, clicked, parent=None):
        super().__init__(parent)
        self.clicked = clicked
        self.cell_size = 30
        self.width_cells = 0
        self.height_cells = 0
        self.setAccessibleName("Carte de placement des ressources et refuges R63")
        self.setObjectName("r63SurvivalMap")
        self.setMinimumHeight(235)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width_cells and self.height_cells:
            point = self.mapToScene(event.position().toPoint())
            x, y = int(point.x() // self.cell_size), int(point.y() // self.cell_size)
            if 0 <= x < self.width_cells and 0 <= y < self.height_cells:
                self.clicked(x, y)
                return
        super().mousePressEvent(event)


class SurvivalDesignerDialog(QDialog):
    ORDER = (
        ("items", "Objets"), ("tools", "Outils"),
        ("nodes", "Ressources et dangers"), ("recipes", "Recettes"),
        ("shelters", "Refuges"), ("foods", "Nourriture"),
    )
    NEEDS = (
        ("energy", "Énergie initiale", 0, 100),
        ("hunger", "Satiété initiale", 0, 100),
        ("temperature", "Chaleur initiale", 0, 100),
        ("energy_drain", "Perte énergie/tick", 0, 10),
        ("hunger_drain", "Perte satiété/tick", 0, 10),
        ("cold_drain", "Perte chaleur/tick", 0, 10),
    )

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        snapshot = session.snapshot().to_dict()
        self.source_revision = snapshot["revision"]
        self.exploration = deepcopy(snapshot["project"].get("exploration", {}))
        self.scenes = sorted(self.exploration)
        authored = snapshot["project"].get("extensions", {}).get(EXTENSION)
        self.document = (deepcopy(authored["data"]) if authored else
                         starter_survival(self.scenes[0]) if self.scenes else None)
        self.history = [deepcopy(self.document)]
        self.history_index = 0

        self.setWindowTitle("Survival Designer R63 — recettes, besoins et cartes")
        self.setObjectName("r63SurvivalDesigner")
        self.resize(1040, 820)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Modifications locales jusqu'à Appliquer. "
                              "Clic sur la carte : placer la ressource ou le refuge sélectionné."))
        if self.document is None:
            root.addWidget(QLabel("Créez une scène d'exploration avant la survie."))
            self.accept_button = QPushButton("Appliquer (indisponible)")
            self.accept_button.setEnabled(False)
            root.addWidget(self.accept_button)
            return

        need_group = QGroupBox("Besoins et dangers environnementaux")
        need_layout = QHBoxLayout(need_group)
        self.need_fields = {}
        for key, title, low, high in self.NEEDS:
            column = QVBoxLayout()
            label = QLabel(title)
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(self.document["needs"][key])
            widget.setObjectName("r63Needs_" + key)
            widget.setAccessibleName(title)
            column.addWidget(label)
            column.addWidget(widget)
            need_layout.addLayout(column)
            self.need_fields[key] = widget
        self.need_commit = QPushButton("Modifier les besoins")
        self.need_commit.clicked.connect(self.commit_needs)
        need_layout.addWidget(self.need_commit)
        root.addWidget(need_group)

        body = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tabs = QTabWidget()
        self.lists = {}
        for category, title in self.ORDER:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            view = QListWidget()
            view.setObjectName("r63List_" + category)
            view.setAccessibleName(title + " R63")
            page_layout.addWidget(view)
            actions = QHBoxLayout()
            for label, handler in (("Ajouter", self.add_item),
                                   ("Modifier", self.edit_item),
                                   ("Supprimer", self.remove_item)):
                button = QPushButton(label)
                button.clicked.connect(
                    lambda checked=False, c=category, h=handler: h(c))
                actions.addWidget(button)
            page_layout.addLayout(actions)
            self.tabs.addTab(page, title)
            self.lists[category] = view
        self.tabs.currentChanged.connect(lambda _: self.refresh_map())
        left_layout.addWidget(self.tabs)
        body.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        row = QHBoxLayout()
        row.addWidget(QLabel("Scène de placement :"))
        self.scene_choice = QComboBox()
        self.scene_choice.setAccessibleName("Choisir la carte de placement")
        self.scene_choice.addItems(self.scenes)
        self.scene_choice.currentTextChanged.connect(lambda _: self.refresh_map())
        row.addWidget(self.scene_choice)
        right_layout.addLayout(row)
        self.map_scene = QGraphicsScene()
        self.map_view = SurvivalMapView(self.place_selected)
        self.map_view.setScene(self.map_scene)
        right_layout.addWidget(self.map_view)
        right_layout.addWidget(QLabel(
            "Les cellules grisées sont bloquées. Sélectionnez une ligne "
            "dans Ressources ou Refuges, puis une case libre."))
        body.addWidget(right)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 4)
        root.addWidget(body, 1)

        tools = QHBoxLayout()
        self.undo_button = QPushButton("Annuler le brouillon")
        self.undo_button.clicked.connect(self.undo_draft)
        tools.addWidget(self.undo_button)
        self.redo_button = QPushButton("Rétablir le brouillon")
        self.redo_button.clicked.connect(self.redo_draft)
        tools.addWidget(self.redo_button)
        preview = QPushButton("Prévisualiser la survie")
        preview.clicked.connect(self.preview)
        tools.addWidget(preview)
        root.addLayout(tools)

        self.report = QPlainTextEdit()
        self.report.setObjectName("r63Preview")
        self.report.setAccessibleName("Rapport de besoins, recettes et risques")
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(120)
        root.addWidget(self.report)
        self.status = QLabel("Brouillon non appliqué au projet.")
        self.status.setAccessibleName("Résultat de validation Survival Designer")
        root.addWidget(self.status)
        bottom = QHBoxLayout()
        self.accept_button = QPushButton("Appliquer au projet (Undo/Redo)")
        self.accept_button.setObjectName("r63Apply")
        self.accept_button.clicked.connect(self.apply)
        bottom.addWidget(self.accept_button)
        cancel = QPushButton("Fermer sans appliquer")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        root.addLayout(bottom)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_draft)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.redo_shortcut.activated.connect(self.redo_draft)
        self.refresh()

    def _category(self):
        return self.ORDER[self.tabs.currentIndex()][0]

    def _draft(self, candidate):
        validate_survival(candidate, self.scenes, exploration=self.exploration)
        if candidate == self.document:
            return False
        self.history = self.history[:self.history_index + 1]
        self.history.append(deepcopy(candidate))
        if len(self.history) > 51:
            self.history.pop(0)
        self.history_index = len(self.history) - 1
        self.document = deepcopy(candidate)
        self.refresh()
        self.status.setText("Brouillon valide ; projet inchangé.")
        return True

    def commit_needs(self):
        candidate = deepcopy(self.document)
        candidate["needs"] = {
            key: widget.value() for key, widget in self.need_fields.items()}
        try:
            return self._draft(candidate)
        except (ValueError, TypeError) as exc:
            self.status.setText("Besoins rejetés : " + str(exc))
            return False

    def _definitions(self, category, row=None):
        row = row or {}
        items = self.document["items"]
        tools = [r["id"] for r in self.document["tools"]]
        scenes = self.scenes
        text = lambda key, label, value="": (key, label, "text", value, None)
        num = lambda key, label, value, limits: (key, label, "number", value, limits)
        choice = lambda key, label, value, options: (
            key, label, "choice", value, options)
        if category == "items":
            return [text("id", "Identifiant objet", row if type(row) is str else "")]
        if category == "tools":
            return [
                choice("id", "Objet outil", row.get("id", items[0]), items),
                num("durability", "Durabilité", row.get("durability", 10), (1, 1000))]
        if category == "nodes":
            return [
                text("id", "Identifiant du gisement", row.get("id", "")),
                choice("scene", "Scène", row.get("scene", scenes[0]), scenes),
                choice("item", "Ressource obtenue", row.get("item", items[0]), items),
                num("stock", "Stock fini", row.get("stock", 10), (1, 1000000)),
                num("yield", "Quantité par collecte", row.get("yield", 1), (1, 99)),
                choice("tool", "Outil requis", row.get("tool") or "(aucun)",
                       ["(aucun)"] + tools),
                num("wear", "Usure/collecte", row.get("wear", 0), (0, 100)),
                num("energy_cost", "Coût énergie", row.get("energy_cost", 3), (1, 100)),
                num("cold", "Exposition au froid", row.get("cold", 0), (0, 100))]
        if category == "recipes":
            default = items[0] + ":1"
            return [
                text("id", "Identifiant de recette", row.get("id", "")),
                text("inputs", "Entrées (id:quantité)",
                     _material_text(row["inputs"]) if row else default),
                text("outputs", "Produits (id:quantité)",
                     _material_text(row["outputs"]) if row else default),
                num("energy_cost", "Coût énergie", row.get("energy_cost", 3), (1, 100))]
        if category == "shelters":
            return [
                text("id", "Identifiant refuge", row.get("id", "")),
                choice("scene", "Scène", row.get("scene", scenes[0]), scenes),
                text("fuel", "Consommables (id:quantité)",
                     _material_text(row["fuel"]) if row else items[0] + ":1"),
                num("energy_restore", "Énergie récupérée",
                    row.get("energy_restore", 25), (1, 100)),
                num("warmth", "Chaleur récupérée",
                    row.get("warmth", 25), (0, 100))]
        return [
            choice("item", "Objet consommable", row.get("item", items[0]), items),
            num("nutrition", "Satiété récupérée", row.get("nutrition", 15), (1, 100))]

    def commit_row(self, category, values, index=None):
        """Typed insert/edit callable by keyboard, mouse and GUI regression tests."""
        if category not in dict(self.ORDER):
            raise ValueError("Unknown survival category")
        candidate = deepcopy(self.document)
        if category == "items":
            row = values["id"].strip()
        else:
            row = dict(values)
            if category in ("recipes", "shelters"):
                keys = ("inputs", "outputs") if category == "recipes" else ("fuel",)
                for key in keys:
                    if type(row[key]) is str:
                        row[key] = parse_materials(row[key], set(candidate["items"]))
            if category == "nodes":
                row["tool"] = None if row["tool"] == "(aucun)" else row["tool"]
                if index is not None and "pos" in candidate[category][index]:
                    row["pos"] = deepcopy(candidate[category][index]["pos"])
            if category == "shelters" and index is not None:
                if "pos" in candidate[category][index]:
                    row["pos"] = deepcopy(candidate[category][index]["pos"])
        if index is None:
            candidate[category].append(row)
        else:
            if not 0 <= index < len(candidate[category]):
                raise IndexError("Unknown survival row")
            candidate[category][index] = row
        return self._draft(candidate)

    def add_item(self, category):
        values = typed_form(self, "Ajouter : " + category,
                            self._definitions(category))
        if values is None:
            return
        try:
            self.commit_row(category, values)
        except (ValueError, TypeError, IndexError) as exc:
            QMessageBox.warning(self, "R63 : élément invalide", str(exc))

    def edit_item(self, category):
        index = self.lists[category].currentRow()
        if index < 0:
            self.status.setText("Sélectionnez d'abord une ligne.")
            return
        values = typed_form(self, "Modifier : " + category,
                            self._definitions(category, self.document[category][index]))
        if values is None:
            return
        try:
            self.commit_row(category, values, index)
        except (ValueError, TypeError, IndexError) as exc:
            QMessageBox.warning(self, "R63 : modification invalide", str(exc))

    def remove_item(self, category):
        index = self.lists[category].currentRow()
        if index < 0:
            return False
        candidate = deepcopy(self.document)
        del candidate[category][index]
        try:
            return self._draft(candidate)
        except (ValueError, TypeError) as exc:
            self.status.setText("Suppression refusée : " + str(exc))
            return False

    def place_selected(self, x, y):
        """Placement is a validated document edit, not a mutable map overlay."""
        category = self._category()
        if category not in ("nodes", "shelters"):
            self.status.setText("Sélectionnez Ressources ou Refuges pour placer.")
            return False
        index = self.lists[category].currentRow()
        if index < 0:
            self.status.setText("Sélectionnez une ressource ou un refuge.")
            return False
        scene = self.scene_choice.currentText()
        if scene != self.document[category][index]["scene"]:
            self.status.setText("Choisissez la scène associée à cet élément.")
            return False
        candidate = deepcopy(self.document)
        candidate[category][index]["pos"] = [x, y]
        try:
            return self._draft(candidate)
        except (ValueError, TypeError) as exc:
            self.status.setText("Placement refusé : " + str(exc))
            return False

    def undo_draft(self):
        if self.history_index == 0:
            return False
        self.history_index -= 1
        self.document = deepcopy(self.history[self.history_index])
        self.refresh()
        return True

    def redo_draft(self):
        if self.history_index >= len(self.history) - 1:
            return False
        self.history_index += 1
        self.document = deepcopy(self.history[self.history_index])
        self.refresh()
        return True

    def refresh(self):
        if self.document is None:
            return
        for key, control in self.need_fields.items():
            control.setValue(self.document["needs"][key])
        for category, view in self.lists.items():
            previous = view.currentRow()
            view.clear()
            for row in self.document[category]:
                if category == "items":
                    label = row
                elif category == "recipes":
                    label = (row["id"] + " : " + _material_text(row["inputs"])
                             + " → " + _material_text(row["outputs"]))
                else:
                    label = row.get("id", row.get("item", ""))
                    if "scene" in row:
                        label += " @ " + row["scene"]
                    if "pos" in row:
                        label += " (" + ", ".join(str(v) for v in row["pos"]) + ")"
                view.addItem(label)
            if view.count():
                view.setCurrentRow(min(max(previous, 0), view.count() - 1))
        self.undo_button.setEnabled(self.history_index > 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)
        self.refresh_map()

    def refresh_map(self):
        if self.document is None:
            return
        scene_name = self.scene_choice.currentText()
        scene = self.exploration.get(scene_name, {})
        self.map_scene.clear()
        width, height = scene.get("width", 0), scene.get("height", 0)
        if not 0 < width <= 64 or not 0 < height <= 64:
            self.map_view.width_cells = self.map_view.height_cells = 0
            self.status.setText("Carte trop grande ou absente pour le placement visuel (max. 64×64).")
            return
        cell = self.map_view.cell_size
        self.map_view.width_cells, self.map_view.height_cells = width, height
        blocked = {tuple(p) for p in scene.get("blocked", [])}
        for y in range(height):
            for x in range(width):
                brush = QBrush(QColor("#454a52" if (x, y) in blocked else "#243c46"))
                self.map_scene.addRect(x * cell, y * cell, cell, cell,
                                       QPen(QColor("#60747a")), brush)
        for category, symbol, color in (
                ("nodes", "R", "#e7c78b"), ("shelters", "A", "#9fe4b1")):
            for row in self.document[category]:
                if row["scene"] != scene_name or "pos" not in row:
                    continue
                x, y = row["pos"]
                mark = self.map_scene.addEllipse(
                    x * cell + 5, y * cell + 5, cell - 10, cell - 10,
                    QPen(QColor(color)), QBrush(QColor("#19242c")))
                mark.setToolTip(row["id"])
                label = self.map_scene.addText(symbol)
                label.setDefaultTextColor(QColor(color))
                label.setPos(x * cell + 8, y * cell + 3)
        self.map_scene.setSceneRect(0, 0, width * cell, height * cell)

    def preview(self):
        try:
            # Full shared authoring validator, including revision freshness.
            plan = preview_survival_design(
                self.session, self.document, expected_revision=self.source_revision)
            runtime = SurvivalRuntime(
                self.document, self.scenes, exploration=self.exploration)
            before = dict(runtime.needs)
            runtime.advance(8)
            after = runtime.needs
            rows = [
                "R63 — projet non modifié",
                f"Recettes : {plan.report['recipes']} ; gisements : {plan.report['nodes']}",
                f"Refuges : {plan.report['shelters']} ; dangers : {plan.report['hazards']}",
                "Simulation sans déplacement, 8 ticks:",
                *[f"{key} : {before[key]} → {after[key]}"
                  for key in ("energy", "hunger", "temperature")],
            ]
            self.report.setPlainText("\n".join(rows))
            self.status.setText("Prévisualisation valide ; aucun commit.")
            return True
        except (ValueError, TypeError) as exc:
            self.report.setPlainText("R63 : prévisualisation refusée : " + str(exc))
            return False

    def apply(self):
        try:
            plan = preview_survival_design(
                self.session, self.document, expected_revision=self.source_revision)
            apply_survival_design(self.session, plan)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "R63 : validation / révision", str(exc))
            return False
        self.accept()
        return True


__all__ = ["SurvivalDesignerDialog", "starter_survival", "parse_materials"]
