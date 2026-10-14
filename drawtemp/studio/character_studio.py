"""Qt 6 character and animation workbench (R7), using the shared R7 recipe.

Opt-in native Widgets editor. PySide6 and Pillow are imported lazily so the
headless game and installed non-Qt builds remain unaffected.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from drawtemp.assets.characters import (
    ACTIONS, DIRECTIONS, SLOTS, CharacterError, CharacterSession, diagnostics,
    export_pack, frame, render_frame, starter_library,
)


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="DrawTemp 5 Character Studio")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--open", type=Path, help="Open an R7 character recipe JSON")
    parser.add_argument("--smoke", action="store_true", help="Build native Qt workbench and exit")
    args = parser.parse_args(argv)

    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QAction, QKeySequence, QPixmap
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDockWidget, QFileDialog, QFormLayout,
            QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
            QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter,
            QVBoxLayout, QWidget,
        )
    except ImportError as exc:
        parser.error("PySide6 is required: python -m pip install '.[qt6,art]' (" +
                     str(exc) + ")")
    try:
        from PIL import Image
    except ImportError as exc:
        parser.error("Pillow is required: python -m pip install '.[qt6,art]' (" +
                     str(exc) + ")")

    root = args.root.resolve()
    templates = starter_library()
    if args.open:
        recipe = json.loads(args.open.read_text(encoding="utf-8"))
    else:
        recipe = templates["jeanne"]

    class Workbench(QMainWindow):
        def __init__(self):
            super().__init__()
            self.session = CharacterSession(recipe)
            self.path = args.open
            self.frame_index = 0
            self.playing = False
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.advance)
            self.setWindowTitle("DrawTemp 5.0 — Character & Animation Studio")
            self.resize(1240, 820)
            self.build_ui()
            self.refresh()

        def build_ui(self):
            self.templates = QComboBox()
            for key, doc in templates.items():
                self.templates.addItem(doc["name"], key)
            self.templates.currentIndexChanged.connect(self.use_template)
            self.variants = QListWidget()
            self.variants.currentTextChanged.connect(self.variant_changed)
            self.add_variant = QPushButton("Dupliquer la tenue")
            self.add_variant.clicked.connect(self.duplicate_variant)
            self.expression = QComboBox()
            self.expression.currentIndexChanged.connect(self.refresh_preview)

            self.direction = QComboBox()
            for key in DIRECTIONS:
                self.direction.addItem({"south": "Sud", "north": "Nord",
                                        "east": "Est", "west": "Ouest"}[key], key)
            self.direction.currentIndexChanged.connect(self.reset_frame)
            self.action = QComboBox()
            for key in ACTIONS:
                self.action.addItem(key.capitalize(), key)
            self.action.currentIndexChanged.connect(self.reset_frame)
            self.canvas = QLabel()
            self.canvas.setMinimumSize(390, 390)
            self.canvas.setAlignment(Qt.AlignCenter)
            self.canvas.setStyleSheet(
                "background-color: #263242; color: #f7e8cc; border-radius: 8px;"
            )
            self.status = QLabel()
            self.status.setWordWrap(True)
            self.timeline = QListWidget()
            self.timeline.currentRowChanged.connect(self.select_frame)
            self.play = QPushButton("▶ Lecture")
            self.play.clicked.connect(self.toggle_play)
            self.add_key = QPushButton("+ Dupliquer image-clé")
            self.add_key.clicked.connect(self.add_frame)
            self.remove_key = QPushButton("− Supprimer image-clé")
            self.remove_key.clicked.connect(self.remove_frame)
            self.make_clip = QPushButton("Créer cette animation / direction")
            self.make_clip.clicked.connect(self.create_clip)
            self.onion = QCheckBox("Pelure d’oignon (image précédente)")
            self.onion.toggled.connect(self.refresh_preview)
            self.duration = QSpinBox()
            self.duration.setRange(16, 60000)
            self.duration.setSuffix(" ms")
            self.duration.editingFinished.connect(self.change_duration)
            self.offset_x = QSpinBox()
            self.offset_x.setRange(-2048, 2048)
            self.offset_x.editingFinished.connect(self.change_offset)
            self.offset_y = QSpinBox()
            self.offset_y.setRange(-2048, 2048)
            self.offset_y.editingFinished.connect(self.change_offset)
            self.source = QLineEdit()
            self.source.editingFinished.connect(self.change_source)
            self.region = QLineEdit()
            self.region.setPlaceholderText("x,y,largeur,hauteur ou vide")
            self.region.editingFinished.connect(self.change_region)
            self.add_layer = QPushButton("Configurer calque…")
            self.add_layer.clicked.connect(self.configure_layer)
            self.diagnostics_box = QLabel()
            self.diagnostics_box.setWordWrap(True)

            library_box = QWidget()
            left = QVBoxLayout(library_box)
            left.addWidget(QLabel("Modèles existants"))
            left.addWidget(self.templates)
            left.addWidget(QLabel("Tenues / variantes"))
            left.addWidget(self.variants, 1)
            left.addWidget(self.add_variant)
            left.addWidget(QLabel("Portraits / expressions"))
            left.addWidget(self.expression)
            left.addWidget(QLabel("Contrôle artistique"))
            left.addWidget(self.diagnostics_box)

            editor_box = QWidget()
            middle = QVBoxLayout(editor_box)
            toolbar = QHBoxLayout()
            toolbar.addWidget(QLabel("Orientation"))
            toolbar.addWidget(self.direction)
            toolbar.addWidget(QLabel("Action"))
            toolbar.addWidget(self.action)
            middle.addLayout(toolbar)
            middle.addWidget(self.canvas, 1)
            middle.addWidget(self.status)
            middle.addWidget(self.onion)
            middle.addWidget(self.play)

            edit_box = QWidget()
            right = QVBoxLayout(edit_box)
            right.addWidget(QLabel("Timeline — sélectionnez une image"))
            right.addWidget(self.timeline, 1)
            right.addWidget(self.make_clip)
            buttons = QHBoxLayout()
            buttons.addWidget(self.add_key)
            buttons.addWidget(self.remove_key)
            right.addLayout(buttons)
            form = QFormLayout()
            form.addRow("Durée", self.duration)
            form.addRow("Offset X", self.offset_x)
            form.addRow("Offset Y", self.offset_y)
            form.addRow("Fichier source", self.source)
            form.addRow("Région atlas", self.region)
            right.addLayout(form)
            right.addWidget(self.add_layer)
            right.addStretch()

            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(library_box)
            splitter.addWidget(editor_box)
            splitter.addWidget(edit_box)
            splitter.setSizes([270, 570, 330])
            self.setCentralWidget(splitter)

            file_menu = self.menuBar().addMenu("&Fichier")
            def command(text, shortcut, handler):
                action = QAction(text, self)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(handler)
                file_menu.addAction(action)
                return action
            command("Ouvrir une fiche…", "Ctrl+O", self.open_recipe)
            command("Enregistrer", "Ctrl+S", self.save_recipe)
            command("Exporter un atlas…", "Ctrl+E", self.export)
            edit_menu = self.menuBar().addMenu("&Édition")
            for label, shortcut, handler in (
                ("Annuler", "Ctrl+Z", self.undo), ("Rétablir", "Ctrl+Shift+Z", self.redo)):
                action = QAction(label, self)
                action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(handler)
                edit_menu.addAction(action)
            self.statusBar().showMessage("R7 | Le rendu Player Qt sera raccordé par R3/R12.")

        def active_variant(self):
            vid = self.variants.currentItem()
            return vid.text() if vid else next(iter(self.session.document["variants"]))

        def active_clip(self):
            data = self.session.document
            outfit = data["variants"][self.active_variant()]
            action, direction = self.action.currentData(), self.direction.currentData()
            return outfit["clips"].get(action, {}).get("directions", {}).get(direction, [])

        def refresh(self):
            document = self.session.document
            selected = self.variants.currentItem()
            selected = selected.text() if selected else None
            self.variants.blockSignals(True)
            self.variants.clear()
            self.variants.addItems(list(document["variants"]))
            keys = list(document["variants"])
            self.variants.setCurrentRow(keys.index(selected) if selected in keys else 0)
            self.variants.blockSignals(False)
            self.refresh_timeline()
            self.refresh_expressions()
            problems = diagnostics(document, require_outfits=document["id"] == "jeanne")
            errors = sum(p["severity"] == "error" for p in problems)
            self.diagnostics_box.setText(
                f"{errors} erreur(s), {len(problems)-errors} avertissement(s)\n" +
                "\n".join(f"• {p['code']} {p.get('variant','')} {p.get('action','')}"
                          for p in problems[:7]))
            self.setWindowTitle(
                "DrawTemp 5.0 — " + document["name"] +
                ("  ●" if self.path is None else " — " + self.path.name))

        def refresh_expressions(self):
            active = self.expression.currentData()
            self.expression.blockSignals(True)
            self.expression.clear()
            self.expression.addItem("Sprite", "")
            outfit = self.session.document["variants"][self.active_variant()]
            for name in outfit["expressions"]:
                self.expression.addItem(name.capitalize(), name)
            index = self.expression.findData(active)
            self.expression.setCurrentIndex(index if index >= 0 else 0)
            self.expression.blockSignals(False)

        def variant_changed(self, _):
            self.stop()
            self.frame_index = 0
            self.refresh_timeline()
            self.refresh_expressions()

        def reset_frame(self, *_):
            self.stop()
            self.frame_index = 0
            self.refresh_timeline()

        def refresh_timeline(self):
            frames = self.active_clip()
            self.timeline.blockSignals(True)
            self.timeline.clear()
            for index, item in enumerate(frames):
                self.timeline.addItem(f"{index+1:02d}   {item['duration_ms']} ms"
                                      f"    {Path(item['path']).name}")
            self.frame_index = min(self.frame_index, max(0, len(frames)-1))
            self.timeline.setCurrentRow(self.frame_index if frames else -1)
            self.timeline.blockSignals(False)
            enabled = bool(frames)
            self.make_clip.setEnabled(not enabled)
            for control in (self.play, self.add_key, self.remove_key, self.duration,
                            self.offset_x, self.offset_y, self.source, self.region):
                control.setEnabled(enabled)
            if enabled:
                current = frames[self.frame_index]
                for widget, value in ((self.duration, current["duration_ms"]),
                                      (self.offset_x, current["offset"][0]),
                                      (self.offset_y, current["offset"][1])):
                    widget.blockSignals(True)
                    widget.setValue(value)
                    widget.blockSignals(False)
                self.source.setText(current["path"])
                self.region.setText(
                    ",".join(map(str, current["region"]))
                    if current["region"] is not None else "")
            else:
                self.source.clear()
                self.region.clear()
            self.refresh_preview()

        def refresh_preview(self, *_):
            self.canvas.clear()
            expression = self.expression.currentData()
            if expression:
                path = self.session.document["variants"][self.active_variant()]\
                       ["expressions"][expression]
                picture = QPixmap(str(root / path))
                if not picture.isNull():
                    self.canvas.setPixmap(picture.scaled(
                        360, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.status.setText("Portrait : " + expression)
                else:
                    self.status.setText("Portrait introuvable : " + path)
                return
            if not self.active_clip():
                self.canvas.setText("Action non dessinée\nAjoutez des poses à la fiche.")
                self.status.setText("R7 : pose manquante")
                return
            try:
                image = render_frame(
                    self.session.document, self.active_variant(),
                    self.action.currentData(), self.direction.currentData(),
                    self.frame_index, root)
                if self.onion.isChecked() and self.frame_index > 0:
                    ghost = render_frame(
                        self.session.document, self.active_variant(),
                        self.action.currentData(), self.direction.currentData(),
                        self.frame_index - 1, root)
                    ghost.putalpha(ghost.getchannel("A").point(lambda a: a // 4))
                    ghost.alpha_composite(image)
                    image = ghost
                memory = io.BytesIO()
                image.save(memory, format="PNG")
                pixmap = QPixmap()
                pixmap.loadFromData(memory.getvalue(), "PNG")
                self.canvas.setPixmap(pixmap.scaled(
                    300, 300, Qt.KeepAspectRatio, Qt.FastTransformation))
                self.status.setText(
                    f"{self.active_variant()} / {self.action.currentData()}"
                    f" / {self.direction.currentData()} / image {self.frame_index+1}")
            except (ValueError, OSError, KeyError) as exc:
                self.canvas.setText("Asset indisponible")
                self.status.setText(str(exc))

        def select_frame(self, index):
            if index >= 0 and index != self.frame_index:
                self.frame_index = index
                self.refresh_timeline()

        def stop(self):
            self.timer.stop()
            self.playing = False
            self.play.setText("▶ Lecture")

        def toggle_play(self):
            if self.playing:
                self.stop()
            elif self.active_clip():
                self.playing = True
                self.play.setText("■ Arrêt")
                self.timer.start(self.active_clip()[self.frame_index]["duration_ms"])

        def advance(self):
            if not self.playing:
                return
            frames = self.active_clip()
            if not frames:
                self.stop()
                return
            next_frame = self.frame_index + 1
            clip = self.session.document["variants"][self.active_variant()]\
                   ["clips"][self.action.currentData()]
            if next_frame >= len(frames) and not clip["loop"]:
                self.stop()
                return
            self.frame_index = next_frame % len(frames)
            self.refresh_timeline()
            self.timer.start(frames[self.frame_index]["duration_ms"])

        def change_frame(self, name, value):
            if not self.active_clip():
                return
            vid, action, direction, index = (
                self.active_variant(), self.action.currentData(),
                self.direction.currentData(), self.frame_index)
            try:
                def transform(doc):
                    doc["variants"][vid]["clips"][action]["directions"][direction]\
                       [index][name] = value
                self.session.edit(transform)
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))
            self.refresh_timeline()

        def change_duration(self):
            self.change_frame("duration_ms", self.duration.value())

        def change_offset(self):
            self.change_frame("offset", [self.offset_x.value(), self.offset_y.value()])

        def change_source(self):
            self.change_frame("path", self.source.text().strip())

        def change_region(self):
            try:
                value = ([int(part.strip()) for part in self.region.text().split(",")]
                         if self.region.text().strip() else None)
            except ValueError:
                self.statusBar().showMessage("Région : 4 entiers attendus")
                return
            self.change_frame("region", value)

        def create_clip(self):
            vid, action, direction = (self.active_variant(),
                                      self.action.currentData(),
                                      self.direction.currentData())
            outfit = self.session.document["variants"][vid]
            donor = outfit["clips"].get("idle", {}).get("directions", {}).get(direction)
            if not donor:
                donor = next((frames for clip in outfit["clips"].values()
                              for frames in clip["directions"].values() if frames), None)
            if not donor:
                self.statusBar().showMessage("Aucune pose source disponible pour créer le clip")
                return
            from copy import deepcopy
            try:
                def transform(doc):
                    clips = doc["variants"][vid]["clips"]
                    if action not in clips:
                        clips[action] = {"loop": action in ("idle", "walk", "run"),
                                         "directions": {}}
                    clips[action]["directions"][direction] = [deepcopy(donor[0])]
                self.session.edit(transform)
                self.refresh()
                self.statusBar().showMessage(
                    "Pose provisoire créée : remplacez sa source pour éviter le recyclage d’art.")
            except CharacterError as exc:
                QMessageBox.warning(self, "Animation", str(exc))

        def add_frame(self):
            vid, action, direction, index = (
                self.active_variant(), self.action.currentData(),
                self.direction.currentData(), self.frame_index)
            self.session.edit(lambda doc: doc["variants"][vid]["clips"][action]
                              ["directions"][direction].insert(
                                  index + 1, dict(self.active_clip()[index])))
            self.frame_index += 1
            self.refresh()

        def remove_frame(self):
            frames = self.active_clip()
            if len(frames) <= 1:
                self.statusBar().showMessage("Une direction doit conserver une image.")
                return
            vid, action, direction, index = (
                self.active_variant(), self.action.currentData(),
                self.direction.currentData(), self.frame_index)
            self.session.edit(lambda doc: doc["variants"][vid]["clips"][action]
                              ["directions"][direction].pop(index))
            self.frame_index = max(0, index - 1)
            self.refresh()

        def duplicate_variant(self):
            from PySide6.QtWidgets import QInputDialog
            from copy import deepcopy
            name, ok = QInputDialog.getText(
                self, "Nouvelle tenue", "Identifiant (ex. peasant ou armor)")
            name = name.strip()
            if not ok or not name:
                return
            try:
                def transform(doc):
                    if name in doc["variants"]:
                        raise CharacterError("Cette tenue existe déjà")
                    doc["variants"][name] = deepcopy(doc["variants"][self.active_variant()])
                    doc["variants"][name]["name"] = name.capitalize()
                self.session.edit(transform)
                self.refresh()
                self.variants.setCurrentRow(list(self.session.document["variants"]).index(name))
                self.statusBar().showMessage(
                    "Tenue clonée : remplacez ses sprites/calques pour créer un art distinct.")
            except CharacterError as exc:
                QMessageBox.warning(self, "Variante", str(exc))

        def configure_layer(self):
            from PySide6.QtWidgets import QInputDialog
            vid = self.active_variant()
            slot, ok = QInputDialog.getItem(
                self, "Calque directionnel", "Pièce à personnaliser", list(SLOTS), 0, False)
            if not ok:
                return
            path, ok = QInputDialog.getText(
                self, "Fichier du calque", "PNG relatif au dépôt (vide = retirer)")
            if not ok:
                return
            tint, ok = QInputDialog.getText(
                self, "Teinte", "Hex RGB #RRGGBB", text="#ffffff")
            if not ok:
                return
            try:
                def transform(doc):
                    layers = doc["variants"][vid]["layers"]
                    existing = next((x for x in layers if x["slot"] == slot), None)
                    if not path.strip():
                        if existing:
                            layers.remove(existing)
                    else:
                        if existing is None:
                            existing = {"slot": slot, "paths": {}, "offset": [0, 0],
                                        "tint": "#ffffff", "opacity": 255}
                            layers.append(existing)
                        existing["paths"][self.direction.currentData()] = path.strip()
                        existing["tint"] = tint
                self.session.edit(transform)
                self.refresh()
            except CharacterError as exc:
                QMessageBox.warning(self, "Calque", str(exc))

        def use_template(self, *_):
            key = self.templates.currentData()
            if key in templates:
                self.stop()
                self.session = CharacterSession(templates[key])
                self.path = None
                self.refresh()

        def open_recipe(self):
            path, _ = QFileDialog.getOpenFileName(
                self, "Ouvrir un personnage R7", str(root), "JSON (*.json)")
            if path:
                try:
                    self.session = CharacterSession(
                        json.loads(Path(path).read_text(encoding="utf-8")))
                    self.path = Path(path)
                    self.refresh()
                except (OSError, ValueError, KeyError) as exc:
                    QMessageBox.critical(self, "Fichier invalide", str(exc))

        def save_recipe(self):
            if self.path is None:
                path, _ = QFileDialog.getSaveFileName(
                    self, "Enregistrer la fiche", str(root / "jeanne.character.json"),
                    "JSON (*.json)")
                if not path:
                    return
                self.path = Path(path)
            try:
                self.path.write_text(json.dumps(
                    self.session.document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                self.statusBar().showMessage("Fiche enregistrée.")
                self.refresh()
            except OSError as exc:
                QMessageBox.critical(self, "Enregistrement", str(exc))

        def export(self):
            path = QFileDialog.getExistingDirectory(
                self, "Dossier de sortie du pack R7", str(root.parent))
            if not path:
                return
            try:
                registry = export_pack(self.session.document, root, Path(path))
                self.statusBar().showMessage(
                    f"Atlas exporté : {len(registry['entries'])} ressources")
            except (OSError, ValueError) as exc:
                QMessageBox.critical(self, "Export", str(exc))

        def undo(self):
            if self.session.undo():
                self.stop()
                self.refresh()

        def redo(self):
            if self.session.redo():
                self.stop()
                self.refresh()

    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = Workbench()
    window.show()
    if args.smoke:
        QTimer.singleShot(120, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
