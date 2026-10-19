"""R34.B Qt Widgets preview of *proposed* procedural rooms.

Read-only with respect to AuthoringSession. Prefab IDs may point to canonical
Content missions / GameProject sprite assets, but room placement and physical
map instantiation belong to a later, transactional authoring lot.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QSplitter,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from drawtemp.sdk.procgen import ProcGenError, ProcGenRecipe
from drawtemp.sdk.procgen_prefabs import (
    demo_library, generate_with_prefabs, preview_seeds, validate_library,
)


class ProcGenPreviewDialog(QDialog):
    """Standalone, opt-in procedural preview; no writes except explicit export."""

    def __init__(self, parent=None, *, content=None, project=None, library=None):
        super().__init__(parent)
        self.setObjectName("r34-procgen-dialog")
        self.setWindowTitle("R34 — Donjons procéduraux (aperçu uniquement)")
        self.resize(950, 650)
        self._content, self._project = content, project
        self._library = validate_library(library or demo_library(),
                                         content=content, project=project)
        self._last_layout = None
        self._last_recipe = None
        self._last_biome = None
        host = QVBoxLayout(self)
        notice = QLabel("Aperçu déterministe, sans appliquer de changements à Content/GameProject.")
        notice.setWordWrap(True)
        host.addWidget(notice)
        splitter = QSplitter(Qt.Horizontal)
        form_host = QWidget()
        form_panel = QVBoxLayout(form_host)
        form = QFormLayout()
        self.seed = QSpinBox()
        self.seed.setObjectName("r34-seed")
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(42)
        form.addRow("Seed", self.seed)
        self.rooms = QSpinBox()
        self.rooms.setRange(3, 64)
        self.rooms.setValue(8)
        form.addRow("Salles", self.rooms)
        self.branches = QSpinBox()
        self.branches.setRange(0, 5)
        self.branches.setValue(2)
        form.addRow("Branches", self.branches)
        self.rooms.valueChanged.connect(self._sync_branches)
        self.locked = QCheckBox("Porte de l'objectif verrouillée")
        self.locked.setChecked(True)
        form.addRow("", self.locked)
        self.encounters = QSpinBox()
        self.encounters.setRange(0, 256)
        self.encounters.setValue(4)
        form.addRow("Budget rencontres", self.encounters)
        self.loot = QSpinBox()
        self.loot.setRange(0, 256)
        self.loot.setValue(3)
        form.addRow("Budget loot", self.loot)
        self.biome = QComboBox()
        self.biome.setObjectName("r34-biome")
        self.biome.addItems(sorted({b for p in self._library["prefabs"]
                                   for b in p["biomes"]}))
        form.addRow("Biome", self.biome)
        form_panel.addLayout(form)
        self.library_label = QLabel("Prefabs : démonstration (aucun asset instancié)")
        self.library_label.setWordWrap(True)
        form_panel.addWidget(self.library_label)
        load = QPushButton("Charger une bibliothèque JSON…")
        load.clicked.connect(self.load_library)
        form_panel.addWidget(load)
        preview = QPushButton("Générer la seed")
        preview.setObjectName("r34-generate")
        preview.clicked.connect(self.preview)
        form_panel.addWidget(preview)
        batch = QPushButton("Vérifier 25 seeds")
        batch.setObjectName("r34-batch")
        batch.clicked.connect(self.batch)
        form_panel.addWidget(batch)
        export = QPushButton("Exporter la reproduction JSON…")
        export.setObjectName("r34-export")
        export.clicked.connect(self.export_repro)
        form_panel.addWidget(export)
        form_panel.addStretch()
        splitter.addWidget(form_host)
        right = QWidget()
        right_panel = QVBoxLayout(right)
        self.graph = QGraphicsView()
        self.graph.setObjectName("r34-graph")
        self.graph.setScene(QGraphicsScene(self))
        right_panel.addWidget(self.graph, 3)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setObjectName("r34-report")
        right_panel.addWidget(self.report, 2)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 3)
        host.addWidget(splitter)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        host.addWidget(close, alignment=Qt.AlignRight)
        self.preview()

    def _sync_branches(self, rooms: int) -> None:
        self.branches.setMaximum(rooms - 3)
        if self.branches.value() == 0:
            self.locked.setChecked(False)

    def _recipe(self) -> ProcGenRecipe:
        return ProcGenRecipe.from_dict({
            "seed": self.seed.value(), "rooms": self.rooms.value(),
            "branches": self.branches.value(),
            "locked_goal": self.locked.isChecked(),
            "encounter_budget": self.encounters.value(),
            "loot_budget": self.loot.value(),
        })

    def load_library(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Bibliothèque de salles", "", "Room prefabs (*.json)")
        if not source:
            return
        try:
            path = Path(source)
            if path.stat().st_size > 262144:
                raise ProcGenError("invalid_library", "Bibliothèque trop volumineuse")
            candidate = json.loads(path.read_text(encoding="utf-8"))
            validated = validate_library(candidate, content=self._content,
                                         project=self._project)
            previous_biome = self.biome.currentText()
            self._library = validated
            self.biome.clear()
            self.biome.addItems(sorted({b for p in validated["prefabs"]
                                       for b in p["biomes"]}))
            if previous_biome in [self.biome.itemText(i)
                                  for i in range(self.biome.count())]:
                self.biome.setCurrentText(previous_biome)
            self.library_label.setText(f"Bibliothèque : {path.name} — "
                                       f"{len(validated['prefabs'])} prefabs")
            self.preview()
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, "Bibliothèque refusée", str(exc))

    def _render_graph(self, result) -> None:
        scene = self.graph.scene()
        scene.clear()
        rooms = result["rooms"]
        by_id = {room["id"]: room for room in rooms}
        seen = {0: 0}
        queue = [0]
        while queue:
            node = queue.pop(0)
            for neighbor in by_id[node]["neighbors"]:
                if neighbor not in seen:
                    seen[neighbor] = seen[node] + 1
                    queue.append(neighbor)
        layers = {}
        for room in rooms:
            layers.setdefault(seen[room["id"]], []).append(room["id"])
        coords = {}
        for depth, layer in sorted(layers.items()):
            for row, room_id in enumerate(sorted(layer)):
                coords[room_id] = (85 + depth * 160, 45 + row * 110)
        for room in rooms:
            x1, y1 = coords[room["id"]]
            for neighbor in room["neighbors"]:
                if neighbor > room["id"]:
                    x2, y2 = coords[neighbor]
                    scene.addLine(x1, y1, x2, y2)
        for room in rooms:
            x, y = coords[room["id"]]
            color = {"entry": "#8dd6a6", "goal": "#e49c9c",
                     "exit": "#90b8f4", "key": "#f3da84"}.get(
                         room["role"], "#d2d9e4")
            node = scene.addEllipse(x - 23, y - 23, 46, 46)
            node.setBrush(QColor(color))
            label = scene.addText(str(room["id"]))
            label.setDefaultTextColor(QColor("#222222"))
            label.setPos(x - 7, y - 12)
            prefab = scene.addText(room["prefab_id"])
            prefab.setDefaultTextColor(QColor("#bbbbbb"))
            prefab.setPos(x - 33, y + 25)
        self.graph.fitInView(scene.itemsBoundingRect().adjusted(-25, -25, 25, 25),
                             Qt.KeepAspectRatio)

    def preview(self) -> dict | None:
        self._last_layout = None
        self._last_recipe = None
        self._last_biome = None
        self.graph.scene().clear()
        try:
            recipe = self._recipe()
            result = generate_with_prefabs(recipe, self._library, biome=self.biome.currentText(),
                                           content=self._content, project=self._project)
            self._last_layout, self._last_recipe = result, recipe
            self._last_biome = self.biome.currentText()
            self._render_graph(result)
            self.report.setPlainText(json.dumps({
                "status": "preview only", "seed": recipe.seed,
                "digest": result["digest"], "library_digest": result["library_digest"],
                "route": result["route"],
                "rooms": [{"id": r["id"], "role": r["role"],
                           "prefab": r["prefab_id"], "doors": r["doors"]}
                          for r in result["rooms"]],
            }, ensure_ascii=False, indent=2))
            return result
        except (ProcGenError, ValueError) as exc:
            self.report.setPlainText("Génération refusée : " + str(exc))
            return None

    def batch(self) -> list | None:
        try:
            recipe = self._recipe()
            seeds = list(range(recipe.seed, min(recipe.seed + 25, (1 << 63) - 1)))
            report = preview_seeds(recipe, self._library, seeds, biome=self.biome.currentText(),
                                   content=self._content, project=self._project)
            self.report.setPlainText(json.dumps({
                "tested": len(report),
                "passed": sum(item["passed"] for item in report),
                "failures": [item for item in report if not item["passed"]],
                "samples": report[:5],
            }, ensure_ascii=False, indent=2))
            return report
        except (ProcGenError, ValueError) as exc:
            self.report.setPlainText("Validation refusée : " + str(exc))
            return None

    def export_repro(self) -> None:
        # Invalid or superseded previews must never be exported as successful.
        if (self._last_layout is None or self._last_recipe != self._recipe()
                or self._last_biome != self.biome.currentText()):
            if self.preview() is None:
                QMessageBox.warning(self, "Export refusé", "Génération invalide")
                return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter seed, recette et graphe", "", "JSON (*.json)")
        if not path:
            return
        dest = Path(path)
        if dest.exists():
            QMessageBox.warning(self, "Export refusé",
                                "Destination existante, aucun écrasement implicite.")
            return
        try:
            payload = {"kind": "r34_preview_not_game_session",
                       "recipe": self._last_recipe.to_dict(),
                       "library": self._library, "layout": self._last_layout}
            with dest.open("x", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Export impossible", str(exc))


def open_procgen_preview(parent, session):
    """Use canonical detached snapshot for reference validation only."""
    from drawtemp.sdk.simulation import thaw
    from sporebound.model import Content
    from sporebound.game_project import GameProject

    snapshot = session.snapshot()
    content = Content.from_dict(thaw(snapshot.content))
    project = GameProject.from_dict(thaw(snapshot.project), content)
    dialog = ProcGenPreviewDialog(parent, content=content, project=project)
    return dialog.exec()
