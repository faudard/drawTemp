"""DrawTemp 5.0 R5 Map Studio preview.

Qt Widgets authoring chrome embeds the canonical R3 Qt Quick scenegraph.
All editing goes through MapStudio / R1; no private QML Canvas renderer.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from drawtemp.core import Content, RuleError
from drawtemp.render.iso_scene import scene_from_mission
from drawtemp.render.qt_viewport import make_controller
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.construction import ConstructionWorkspace
from .map_authoring import MapStudio, SURFACE_PALETTE

try:
    from PySide6.QtCore import QObject, Property, Signal, Slot, Qt, QUrl
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDockWidget, QFileDialog,
        QFormLayout, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMainWindow,
        QMessageBox, QPushButton, QSpinBox, QTextEdit, QToolBar, QVBoxLayout,
        QWidget,
    )
except ImportError:
    # Allow headless command/type discovery without importing PySide6.
    QObject = object
    def Signal(*args):
        return None
    def Slot(*args):
        return lambda fn: fn
    def Property(*args, **kwargs):
        return lambda fn: fn



class MapWindow(QMainWindow):
    def __init__(self, studio=None):
        super().__init__()
        self.studio = studio or MapStudio.reference()
        self.setWindowTitle("DrawTemp 5.0 — Éditeur de cartes R5")
        self.resize(1400, 820)
        self.stroke = []
        self.selected = None
        self.selection = []

        toolbar = QToolBar("Carte", self)
        self.addToolBar(toolbar)
        for name, func in (
            ("Nouvelle carte", self.create_map),
            ("Dupliquer", self.duplicate_map),
            ("Renommer", self.rename_map),
            ("Ouvrir", self.open_map),
            ("Enregistrer", self.save_map),
            ("Annuler", self.undo),
            ("Rétablir", self.redo),
            ("Copier", self.copy_selection),
            ("Coller", self.paste_selection),
            ("Test IA", self.playtest),
        ):
            action = toolbar.addAction(name)
            action.triggered.connect(func)

        self.tools = QComboBox()
        self.tools.addItems([
            "Pinceau", "Rectangle", "Ligne", "Remplissage", "Pipette", "Sélection",
            "Gomme", "Objectif", "Mur", "Couvert", "Danger",
            "Hauteur +", "Hauteur -", "Maison", "Pont", "Tour",
        ])
        toolbar.addSeparator()
        self.mode = QComboBox()
        self.mode.addItems(["Édition carte", "Construction 2.5D"])
        toolbar.addWidget(QLabel(" Espace "))
        toolbar.addWidget(self.mode)
        toolbar.addWidget(QLabel(" Outil "))
        toolbar.addWidget(self.tools)

        self.material = QComboBox()
        self.material.addItems(list(SURFACE_PALETTE))
        toolbar.addWidget(QLabel(" Surface "))
        toolbar.addWidget(self.material)

        # R3 controller is the only source of camera, hit-testing and render
        # delegates. Its scene is reconstructed from the validated R1 Content.
        self.renderer = make_controller(self._render_scene())
        viewport = QQuickWidget(self)
        viewport.setResizeMode(QQuickWidget.SizeRootObjectToView)
        viewport.rootContext().setContextProperty("renderer", self.renderer)
        source = Path(__file__).resolve().parents[1] / "render" / "IsoViewport.qml"
        viewport.setSource(QUrl.fromLocalFile(str(source)))
        if viewport.status() == QQuickWidget.Error:
            raise RuntimeError("\n".join(error.toString() for error in viewport.errors()))
        root = viewport.rootObject()
        root.setProperty("interactionMode", "edit")
        root.setProperty("showLegend", False)
        root.strokeStarted.connect(self.begin_stroke)
        root.strokeMoved.connect(self.extend_stroke)
        root.strokeFinished.connect(self.finish_stroke)
        root.strokeCancelled.connect(self.cancel_stroke)
        root.buildingPicked.connect(self._on_building_pick)
        self.viewport = viewport
        self.setCentralWidget(viewport)

        self.maps = QListWidget()
        self.maps.currentRowChanged.connect(self.change_map)
        self._dock("Cartes / Missions", self.maps, Qt.LeftDockWidgetArea)

        right = QWidget()
        layout = QVBoxLayout(right)
        layout.addWidget(QLabel("Affichage tactique"))
        self.show_grid = QCheckBox("Grille")
        self.show_grid.setChecked(True)
        self.show_grid.toggled.connect(self.refresh)
        self.show_blocked = QCheckBox("Collisions")
        self.show_blocked.toggled.connect(self.refresh)
        self.show_height = QCheckBox("Hauteurs")
        self.show_height.toggled.connect(self.refresh)
        self.show_actors = QCheckBox("Personnages")
        self.show_actors.setChecked(True)
        self.show_actors.toggled.connect(self.refresh)
        for widget in (self.show_grid, self.show_blocked, self.show_height, self.show_actors):
            layout.addWidget(widget)
        layout.addWidget(QLabel("Objectif de mission"))
        self.objective = QComboBox()
        self.objective.addItems(["eliminate", "reach", "survive", "protect"])
        layout.addWidget(self.objective)
        apply_objective = QPushButton("Appliquer l'objectif")
        apply_objective.clicked.connect(self.change_objective)
        layout.addWidget(apply_objective)
        layout.addWidget(QLabel("Diagnostics et sélection"))
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics, 1)
        layout.addWidget(QLabel("Glisser pour peindre en un seul geste.\n"
                                "Molette : zoom • bouton droit : déplacement.\n"
                                "Les changements sont validés avant application."))
        self._dock("Inspecteur", right, Qt.RightDockWidgetArea)

        from .construction_dock import ConstructionDock
        # R6 runs on the EXACT MapStudio authoring session and viewport.
        # Its dock is contextual, not a second map editor or renderer.
        self.construction = ConstructionDock(
            ConstructionWorkspace(self.studio.authoring, self.studio.mission_id), self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.construction)
        self.construction.hide()
        self.mode.currentIndexChanged.connect(self._construction_mode)
        self.construction.committed.connect(lambda _change: self.refresh())
        self.construction.level_changed.connect(self._construction_view)
        self.construction.cutaway_changed.connect(self._construction_view)
        self.statusBar().showMessage("Viewport Qt Quick partagé R3 · édition R5")
        self.refresh_maps()

    def _construction_mode(self, *_):
        active = self.mode.currentIndex() == 1
        root = self.viewport.rootObject()
        root.setProperty("interactionMode", "construction" if active else "edit")
        self.construction.setVisible(active)
        self.tools.setEnabled(not active)
        self.material.setEnabled(not active)
        self._construction_view()
        self.statusBar().showMessage(
            "R6 : sélectionner directement toiture, murs, fenêtres, porte et étages"
            if active else "R5 : édition de carte et terrain")

    def _construction_view(self, *_):
        active = self.mode.currentIndex() == 1
        workspace = self.construction.workspace
        self.renderer.setConstructionView(
            workspace.active_level if active else 0,
            workspace.cutaway if active else False)

    def _on_building_pick(self, hit):
        if self.mode.currentIndex() != 1:
            return
        hit = dict(hit or {})
        self.construction.on_renderer_hit(
            hit.get("structure_id"), hit.get("anchor", ()),
            hit.get("cell", ()), hit.get("part", "building"), hit.get("level", 0))
        self._construction_view()

    def _dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)

    def _safe(self, operation):
        try:
            result = operation()
            self.refresh()
            return result
        except (RuleError, AuthoringError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Modification refusée", str(exc))
            return None

    def refresh_maps(self):
        self.maps.blockSignals(True)
        self.maps.clear()
        for mission in self.studio.snapshot()["content"]["missions"]:
            self.maps.addItem(f'{mission["name"]}  [{mission["id"]}]')
        self.maps.setCurrentRow(self.studio.map_ids().index(self.studio.mission_id))
        self.maps.blockSignals(False)
        self.refresh()

    def change_map(self, row):
        if row < 0:
            return
        self._safe(lambda: self.studio.select_map(self.studio.map_ids()[row]))

    def _name_id(self, title, initial):
        name, ok = QInputDialog.getText(self, title, "Nom de la carte", text=initial)
        if not ok or not name.strip():
            return None
        identifier, ok = QInputDialog.getText(
            self, title, "Identifiant stable (lettres, chiffres, _)", text=initial.lower())
        if not ok or not identifier.strip():
            return None
        return identifier.strip(), name.strip()

    def create_map(self):
        value = self._name_id("Nouvelle carte", "village")
        if value is None:
            return
        self._safe(lambda: self.studio.create(value[0], value[1], 12, 12))
        self.refresh_maps()

    def duplicate_map(self):
        value = self._name_id("Dupliquer la carte", self.studio.mission_id + "_copy")
        if value is None:
            return
        self._safe(lambda: self.studio.duplicate(*value))
        self.refresh_maps()

    def rename_map(self):
        name, ok = QInputDialog.getText(
            self, "Renommer", "Nouveau nom", text=self.studio.mission()["name"])
        if ok and name.strip():
            self._safe(lambda: self.studio.rename(name))
            self.refresh_maps()

    def open_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un contenu avec manifeste .game.json", "", "Content JSON (*.json)")
        if not path:
            return
        if self.studio.authoring.snapshot().dirty:
            QMessageBox.information(self, "Carte modifiée",
                                    "Enregistrez avant d'ouvrir un autre projet.")
            return
        def open_document():
            self.studio = MapStudio.open(path)
            self.refresh_maps()
        self._safe(open_document)

    def save_map(self):
        def action():
            try:
                return self.studio.save()
            except AuthoringError as exc:
                if exc.code != "no_destination":
                    raise
                path, _ = QFileDialog.getSaveFileName(
                    self, "Enregistrer contenu + projet", "jeanne-village.json",
                    "Content JSON (*.json)")
                if path:
                    return self.studio.save_as(path)
        self._safe(action)

    def undo(self):
        self._safe(self.studio.undo)
        self.refresh_maps()

    def redo(self):
        self._safe(self.studio.redo)
        self.refresh_maps()

    def playtest(self):
        result = self._safe(lambda: self.studio.playtest(max_steps=100))
        if result:
            QMessageBox.information(
                self, "Playtest headless R5",
                ("Mission : {}\nSeed : {}\nPhase : {} → {}\nIssue : {}\n\n"
                 "Simulation déterministe. Pour jouer dans le Player Qt R12, "
                 "lancez drawtemp-player5 ; le viewport R3 est commun.").format(
                    result["mission"], result["seed"], result["initial_mode"],
                    result["final_mode"], result["result"] or "En cours"))

    def copy_selection(self):
        if not self.selection:
            QMessageBox.information(self, "Copie", "Choisissez Sélection et tracez une zone.")
            return
        self._safe(lambda: self.studio.copy(self.selection))

    def paste_selection(self):
        if self.selected is not None:
            self._safe(lambda: self.studio.paste(self.selected))

    def change_objective(self):
        self._safe(lambda: self.studio.set_objective(self.objective.currentText()))

    def _tool(self):
        return self.tools.currentText()

    def _brush(self):
        return {
            "Gomme": "erase", "Objectif": "goal", "Mur": "wall",
            "Couvert": "cover", "Danger": "hazard",
            "Hauteur +": "height+", "Hauteur -": "height-",
        }.get(self._tool(), "surface:" + self.material.currentText())

    def _render_scene(self):
        """Render exactly the Content mission edited by R5, with R3 projection."""
        content = Content.from_dict(self.studio.snapshot()["content"])
        return scene_from_mission(content.missions[self.studio.mission_id])

    def cancel_stroke(self):
        self.stroke = []

    def begin_stroke(self, x, y):
        self.stroke = [(x, y)]
        self.selected = (x, y)

    def extend_stroke(self, x, y):
        if self.stroke and (x, y) != self.stroke[-1]:
            self.stroke.append((x, y))
            self.selected = (x, y)

    def finish_stroke(self, x, y):
        if not self.stroke:
            return
        self.extend_stroke(x, y)
        cells = self.stroke
        self.stroke = []
        tool = self._tool()
        first, last = cells[0], cells[-1]
        def apply():
            if tool == "Sélection":
                self.selection = list(self.studio.rectangle_cells(first, last))
                self.statusBar().showMessage(
                    "{} cases sélectionnées — Copier puis Coller".format(len(self.selection)))
                return None
            if tool in ("Maison", "Pont", "Tour"):
                return self.studio.structure(tool, last)
            if tool == "Pipette":
                sampled = self.studio.sample(last)
                index = self.material.findText(sampled)
                if index >= 0:
                    self.material.setCurrentIndex(index)
                return None
            brush = self._brush()
            if tool == "Rectangle":
                return self.studio.rectangle(first, last, brush)
            if tool == "Ligne":
                return self.studio.line(first, last, brush)
            if tool == "Remplissage":
                return self.studio.flood(last, brush)
            return self.studio.paint(cells, brush)
        self._safe(apply)

    def refresh(self, *_):
        if hasattr(self, "construction"):
            workspace = self.construction.workspace
            if (workspace.authoring is not self.studio.authoring or
                    workspace.mission_id != self.studio.mission_id):
                # Opening/selecting a different map invalidates *all* prior
                # selections; a house ID may occur on multiple missions.
                self.construction.workspace = ConstructionWorkspace(
                    self.studio.authoring, self.studio.mission_id)
                workspace = self.construction.workspace
            elif (workspace.pick is not None and
                  workspace._selection_revision != self.studio.authoring.revision):
                workspace.clear_selection()
            self.construction.refresh()
        mission = self.studio.mission()
        board = mission["board"]
        self.renderer.replace_scene(self._render_scene())
        if hasattr(self, "construction"):
            self._construction_view()
        root = self.viewport.rootObject()
        root.setProperty("showGrid", self.show_grid.isChecked())
        root.setProperty("showBlocked", self.show_blocked.isChecked())
        root.setProperty("showHeights", self.show_height.isChecked())
        root.setProperty("showActors", self.show_actors.isChecked())
        current = self.studio.snapshot()
        warnings = self.studio.diagnostics()
        self.diagnostics.setPlainText(
            f'{mission["name"]}\n{board["width"]} × {board["height"]} • '
            f'révision {current["revision"]}\n'
            f'{"Modifications non enregistrées" if current["dirty"] else "Enregistré / nouveau"}\n\n'
            + ("\n".join(warnings) if warnings else "Aucun problème de navigation détecté."))
        index = self.objective.findText(mission["objective"])
        if index >= 0:
            self.objective.setCurrentIndex(index)

    def closeEvent(self, event):
        if self.studio.authoring.snapshot().dirty:
            response = QMessageBox.question(self, "Quitter",
                "Des modifications ne sont pas enregistrées. Quitter sans enregistrer ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if response != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, help="Existing canonical Content JSON (paired .game.json)")
    parser.add_argument("--smoke", action="store_true", help="Create window in Qt offscreen CI, then exit")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QTimer
    except ImportError:
        parser.error('Qt 6 required: pip install ".[qt6]"')
    app = QApplication([sys.argv[0]])
    studio = MapStudio.open(args.content) if args.content else MapStudio.reference()
    window = MapWindow(studio)
    window.show()
    if args.smoke:
        QTimer.singleShot(100, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
