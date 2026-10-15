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
    def __init__(self, studio=None, *, character_pack=None, character_variant=None):
        super().__init__()
        self.studio = studio or MapStudio.reference()
        self.setWindowTitle("DrawTemp 5.0 — Éditeur de cartes R5")
        self.resize(1400, 820)
        self.stroke = []
        self.selected = None
        self.selection = []
        self.pending_operation = None
        self.pending_transform = None
        self.preview_anchor = None

        toolbar = QToolBar("Carte", self)
        self.addToolBar(toolbar)
        self.toolbar_actions = {}
        for name, func in (
            ("Nouveau / Export", self.creator),
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
            self.toolbar_actions[name] = action
        self.toolbar_actions["Copier"].setShortcut("Ctrl+C")
        self.toolbar_actions["Coller"].setShortcut("Ctrl+V")
        transform_actions = (
            ("Déplacer sélection", lambda: self.start_transform("move"), "Ctrl+M"),
            ("Dupliquer sélection", lambda: self.start_transform("duplicate"), "Ctrl+D"),
            ("Rotation ↻", lambda: self.start_transform("rotate_cw"), "Ctrl+R"),
            ("Rotation ↺", lambda: self.start_transform("rotate_ccw"), "Ctrl+Shift+R"),
            ("Miroir horizontal", lambda: self.start_transform("mirror_x"), "Ctrl+H"),
            ("Miroir vertical", lambda: self.start_transform("mirror_y"), "Ctrl+J"),
            ("Appliquer aperçu", self.apply_transform, "Return"),
            ("Annuler aperçu", self.cancel_transform, "Escape"),
        )
        toolbar.addSeparator()
        for label, handler, shortcut in transform_actions:
            action = toolbar.addAction(label)
            action.setShortcut(shortcut)
            action.triggered.connect(handler)
            self.toolbar_actions[label] = action

        self.tools = QComboBox()
        self.tools.addItems([
            "Pinceau", "Rectangle", "Ligne", "Remplissage", "Pipette", "Sélection",
            "Lasso", "Placement sélection",
            "Gomme", "Objectif", "Mur", "Couvert", "Danger",
            "Hauteur +", "Hauteur -", "Maison", "Pont", "Tour",
        ])
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Outil "))
        toolbar.addWidget(self.tools)

        self.material = QComboBox()
        self.material.addItems(list(SURFACE_PALETTE))
        toolbar.addWidget(QLabel(" Surface "))
        toolbar.addWidget(self.material)
        self.additive_selection = QCheckBox("Ajouter à la sélection")
        self.additive_selection.setObjectName("r5_selection_additive")
        self.additive_selection.setToolTip("Conserver les cellules déjà sélectionnées, même disjointes")
        toolbar.addWidget(self.additive_selection)

        # R3 controller is the only source of camera, hit-testing and render
        # delegates. Its scene is reconstructed from the validated R1 Content.
        self.renderer = make_controller(self._render_scene(),
                                        character_pack=character_pack,
                                        character_variant=character_variant)
        viewport = QQuickWidget(self)
        self.renderer.attach_engine(viewport.engine())
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
        root.editHover.connect(self._hover_transform)
        root.editHoverLeft.connect(self._hover_left)
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
        # Editor-only layers share the canonical mission, not the Player save.
        from .map_layers_dock import MapLayersDock
        self.layers_panel = MapLayersDock(self.studio.layers, self.refresh)
        self._dock("Calques", self.layers_panel, Qt.RightDockWidgetArea)
        self.statusBar().showMessage("Viewport Qt Quick partagé R3 · édition R5")
        self.refresh_maps()

    def creator(self):
        # Import lazily: headless MapStudio and Player do not depend on Qt UI.
        from .r15_creator import open_creator
        open_creator(self)

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
        def action():
            self.studio.select_map(self.studio.map_ids()[row])
            self.selection = []
            self.cancel_transform()
        self._safe(action)

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
        if self.studio.authoring.snapshot().dirty or self.studio.layers.dirty:
            QMessageBox.information(self, "Carte modifiée",
                                    "Enregistrez avant d'ouvrir un autre projet.")
            return
        def open_document():
            self.studio = MapStudio.open(path)
            self.layers_panel.set_workspace(self.studio.layers)
            self.selection = []
            self.cancel_transform()
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
        self.cancel_transform()
        self._safe(self.studio.undo)
        self.refresh_maps()

    def redo(self):
        self.cancel_transform()
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
            QMessageBox.information(self, "Copier", "Sélectionnez des cases au rectangle ou au lasso.")
            return
        result = self._safe(lambda: self.studio.copy_region(self.selection))
        if result is not None:
            self.statusBar().showMessage(
                "Copie terrain + objectifs prête. Identités d'unités/objets non dupliquées.")

    def paste_selection(self):
        if self.studio.region_clipboard is None:
            QMessageBox.information(self, "Coller", "Copiez une sélection avant le collage.")
            return
        self.start_transform("paste")

    def _selection_origin(self):
        if not self.selection:
            raise RuleError("Sélectionnez une zone au rectangle ou au lasso")
        return min(x for x, _ in self.selection), min(y for _, y in self.selection)

    def _project_cells(self, cells, *, invalid=False):
        from drawtemp.render.iso_scene import MATERIALS, COLORS
        heights = {(tile["x"], tile["y"]): tile.get("height", 0)
                   for tile in self.renderer.scene["tiles"]}
        result = []
        for x, y, surface in cells:
            sx, sy = self.renderer.projection.project(
                x, y, heights.get((x, y), 0))
            tint = COLORS[MATERIALS.index(surface)] if surface in MATERIALS else "#87ad9b"
            result.append({"x": x, "y": y, "sx": sx, "sy": sy,
                           "tint": tint, "invalid": invalid})
        return result

    def _render_selection(self):
        if not hasattr(self, "viewport"):
            return
        tiles = {(tile["x"], tile["y"]): tile for tile in self.renderer.scene["tiles"]}
        cells = [(x, y, tiles.get((x, y), {}).get("surface", "grass"))
                 for x, y in self.selection
                 if 0 <= x < self.renderer.scene["width"]
                 and 0 <= y < self.renderer.scene["height"]]
        self.viewport.rootObject().setProperty(
            "selectionCells", self._project_cells(cells))

    def cancel_transform(self, *_):
        self.pending_operation = None
        self.pending_transform = None
        self.preview_anchor = None
        if hasattr(self, "viewport") and self.viewport.rootObject():
            self.viewport.rootObject().setProperty("transformCells", [])

    def start_transform(self, operation):
        if operation != "paste" and not self.selection:
            QMessageBox.information(self, "Sélection", "Choisissez d'abord une région.")
            return
        if operation == "paste" and self.studio.region_clipboard is None:
            QMessageBox.information(self, "Coller", "Aucun presse-papiers de carte.")
            return
        self.pending_operation = operation
        self.pending_transform = None
        self.preview_anchor = None
        self.tools.setCurrentText("Placement sélection")
        if operation in ("rotate_cw", "rotate_ccw", "mirror_x", "mirror_y"):
            self._preview_transform_at(self._selection_origin())
        else:
            self.viewport.rootObject().setProperty("transformCells", [])
            self.statusBar().showMessage(
                "Survolez la carte pour placer la transformation, puis Appliquer aperçu.")

    def _hover_transform(self, x, y):
        self.selected = (x, y)
        if self.pending_operation:
            if self.preview_anchor != (x, y):
                self._preview_transform_at((x, y))

    def _hover_left(self):
        # Keep the last valid preview so a toolbar click can commit it.
        pass

    def _preview_transform_at(self, anchor):
        if self.pending_operation is None:
            return
        operation = self.pending_operation
        self.preview_anchor = anchor
        try:
            preview = self.studio.preview_region(
                self.selection if operation != "paste" else (),
                operation=operation, anchor=anchor)
            self.pending_transform = preview
            tinted = [(x, y, tile.get("surface", "grass"))
                      for x, y, tile, _ in preview.preview_cells]
            self.viewport.rootObject().setProperty(
                "transformCells", self._project_cells(tinted))
            self.statusBar().showMessage(
                f"{operation} : {len(tinted)} cases · aperçu validé · Appliquer pour confirmer")
        except (AuthoringError, RuleError, ValueError) as exc:
            self.pending_transform = None
            self.statusBar().showMessage("Placement refusé : " + str(exc))
            self._show_invalid_transform(anchor)

    def _show_invalid_transform(self, anchor):
        from sporebound.map_authoring import copy_terrain
        from sporebound.map_transform import transform_terrain
        try:
            op = self.pending_operation
            if op == "paste":
                clip = self.studio.region_clipboard.clip
            else:
                clip = copy_terrain(self.studio.snapshot()["content"],
                                    self.studio.mission_id, self.selection)
            if op in ("rotate_cw", "rotate_ccw", "mirror_x", "mirror_y"):
                clip = transform_terrain(clip, op)
            stamped = [(anchor[0] + dx, anchor[1] + dy,
                        tile.get("surface", "grass"))
                       for (dx, dy), tile in zip(clip.offsets, clip.terrain)]
            self.viewport.rootObject().setProperty(
                "transformCells", self._project_cells(stamped, invalid=True))
        except (RuleError, ValueError, AttributeError):
            self.viewport.rootObject().setProperty("transformCells", [])

    def apply_transform(self, *_):
        if self.pending_transform is None:
            QMessageBox.information(
                self, "Placement", "Choisissez une destination valide (aperçu non rouge).")
            return
        preview = self.pending_transform
        def action():
            result = self.studio.commit_region(preview)
            self.selection = list(preview.target_cells)
            return result
        result = self._safe(action)
        if result is not None:
            self.cancel_transform()
            self._render_selection()
            self.statusBar().showMessage(
                "Transformation validée en une transaction. Ctrl+Z pour annuler.")

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
            if tool in ("Sélection", "Lasso"):
                selected = (self.studio.select_lasso(
                    cells, existing=self.selection,
                    additive=self.additive_selection.isChecked())
                    if tool == "Lasso" else self.studio.select_rectangle(
                        first, last, existing=self.selection,
                        additive=self.additive_selection.isChecked()))
                self.selection = list(selected)
                self.cancel_transform()
                self._render_selection()
                self.statusBar().showMessage(
                    "{} cases sélectionnées — Copier, déplacer, dupliquer, pivoter ou miroir"
                    .format(len(self.selection)))
                return None
            if tool == "Placement sélection":
                if self.pending_operation is not None:
                    self._preview_transform_at(last)
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
        self.layers_panel.set_mission(self.studio.mission_id)
        mission = self.studio.mission()
        board = mission["board"]
        self.renderer.replace_scene(self._render_scene())
        root = self.viewport.rootObject()
        self._render_selection()
        root.setProperty("showGrid", self.show_grid.isChecked())
        root.setProperty("showBlocked", self.show_blocked.isChecked())
        root.setProperty("showHeights", self.show_height.isChecked())
        root.setProperty("showActors", self.show_actors.isChecked())
        view = self.studio.layers.view(self.studio.mission_id)
        root.setProperty("layerVisibility", view["visible"])
        root.setProperty("layerOpacity", view["opacity"])
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
        if self.studio.authoring.snapshot().dirty or self.studio.layers.dirty:
            response = QMessageBox.question(self, "Quitter",
                "La carte ou ses réglages de calques ne sont pas enregistrés. "
                "Quitter sans enregistrer ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if response != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, help="Existing canonical Content JSON (paired .game.json)")
    parser.add_argument("--smoke", action="store_true", help="Create window in Qt offscreen CI, then exit")
    parser.add_argument("--character-pack", type=Path, help="R7 published character atlas")
    parser.add_argument("--character-variant", help="R7 character outfit ID")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QTimer
    except ImportError:
        parser.error('Qt 6 required: pip install ".[qt6]"')
    app = QApplication([sys.argv[0]])
    studio = MapStudio.open(args.content) if args.content else MapStudio.reference()
    window = MapWindow(studio, character_pack=args.character_pack,
                       character_variant=args.character_variant)
    window.show()
    if args.smoke:
        QTimer.singleShot(100, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
