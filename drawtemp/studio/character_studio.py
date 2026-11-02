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
from drawtemp.assets.character_library import (
    discover_character_library, search_characters,
)
from drawtemp.assets.character_looks import available_looks, apply_look
from drawtemp.assets.character_parts import (
    PART_CATEGORIES, PROFILE_PRESETS, PROFILE_LABELS,
    active_part, available_parts, ensure_profile, part_paths,
    set_part, set_part_style, split_legacy_hair_front, upgrade_legacy_hair,
)


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="DrawTemp 5 Character Studio")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--open", type=Path, help="Open an R7 character recipe JSON")
    parser.add_argument("--template", default="modular_hero",
                        help="Starter template ID (e.g. modular_hero)")
    parser.add_argument("--smoke", action="store_true", help="Build native Qt workbench and exit")
    args = parser.parse_args(argv)

    try:
        from PySide6.QtCore import Qt, QTimer, QSize
        from PySide6.QtGui import QAction, QKeySequence, QPixmap, QIcon, QColor
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QColorDialog, QDockWidget, QFileDialog, QFormLayout,
            QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
            QMainWindow, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
            QTabBar, QToolButton,
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
    if not args.open and args.template not in templates:
        parser.error("Unknown character template: " + args.template)
    if args.open:
        recipe = json.loads(args.open.read_text(encoding="utf-8"))
    else:
        recipe = templates[args.template]

    class Workbench(QMainWindow):
        def __init__(self):
            super().__init__()
            self.session = CharacterSession(recipe)
            self.path = args.open
            self.art_root = (args.open.parent if args.open and
                             (args.open.parent / "sources/jeanne_atlas.png").is_file()
                             else root)
            self.frame_index = 0
            self.playing = False
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.advance)
            self.setWindowTitle("DrawTemp — Character Studio")
            self.setStyleSheet("""
                QMainWindow, QDockWidget { background-color: #eaf0f6; }
                QWidget { color: #25374b; font-size: 12px; }
                QLabel { color: #25374b; }
                QListWidget, QLineEdit, QComboBox, QSpinBox {
                    background: #ffffff; color: #22374a;
                    border: 1px solid #bdcbd9; border-radius: 5px;
                    padding: 4px;
                }
                QListWidget::item:selected { background: #cce2ff; color: #173854; }
                QListWidget::item:hover { background: #eef5ff; }
                QPushButton, QToolButton {
                    border: 1px solid #b3c4d4; border-radius: 5px;
                    background: #f7faff; padding: 5px 9px;
                }
                QPushButton:hover, QToolButton:hover {
                    background: #dcecff; border-color: #7399c6;
                }
                QPushButton:pressed, QToolButton:pressed { background: #bcd9ff; }
                QDockWidget::title {
                    background: #d9e6f3; color: #213a55;
                    padding: 7px; font-weight: 600;
                }
                QTabBar::tab {
                    padding: 9px 18px; margin-right: 3px;
                    border: 1px solid #b6c9db;
                    background: #e0eaf4; color: #34536a;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background: #ffffff; color: #154f83;
                    border-bottom: 2px solid #3b86cd;
                }
            """)
            self.resize(1580, 930)
            self.library_entries = discover_character_library(root, templates)
            self.saved_revision = self.session.revision
            self._gallery_cache = {}
            self.build_ui()
            self.refresh()

        def build_ui(self):
            self.library_search = QLineEdit()
            self.library_search.setPlaceholderText("Search characters and templates…")
            self.library_search.setClearButtonEnabled(True)
            self.library_search.textChanged.connect(self.refresh_library)
            self.library_search.returnPressed.connect(self.open_selected_library)
            self.library_grid = QListWidget()
            self.library_grid.setViewMode(QListView.IconMode)
            self.library_grid.setIconSize(QSize(76, 76))
            self.library_grid.setGridSize(QSize(112, 122))
            self.library_grid.setResizeMode(QListView.Adjust)
            self.library_grid.setMovement(QListView.Static)
            self.library_grid.setWrapping(True)
            self.library_grid.setToolTip(
                "Double-click a character to open it. Searching does not "
                "replace the current character.")
            self.library_grid.itemDoubleClicked.connect(self.open_library_item)
            self.library_open = QPushButton("Open selected character")
            self.library_open.clicked.connect(self.open_selected_library)
            self.library_count = QLabel()
            self.library_count.setWordWrap(True)
            self.library_reload = QPushButton("Refresh library")
            self.library_reload.clicked.connect(self.reload_library)
            self.variants = QListWidget()
            self.variants.currentTextChanged.connect(self.variant_changed)
            self.profile_tabs = QTabBar()
            self.profile_tabs.setExpanding(True)
            self.profile_tabs.setToolTip(
                "Editable starting appearances. All parts remain available "
                "to Male, Female and Kid; profiles are independent.")
            for profile in PROFILE_PRESETS:
                index = self.profile_tabs.addTab(PROFILE_LABELS[profile])
                self.profile_tabs.setTabData(index, profile)
            self.profile_tabs.currentChanged.connect(self.profile_changed)
            self.add_variant = QPushButton("Duplicate Outfit")
            self.add_variant.clicked.connect(self.duplicate_variant)

            self.expression = QComboBox()
            self.expression.currentIndexChanged.connect(self.refresh_preview)
            self.add_expression = QPushButton("Ajouter un portrait / une expression…")
            self.add_expression.clicked.connect(self.import_expression)

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
            self.browse_source = QPushButton("Choisir PNG…")
            self.browse_source.clicked.connect(self.select_source)
            self.region = QLineEdit()
            self.region.setPlaceholderText("x,y,largeur,hauteur ou vide")
            self.region.editingFinished.connect(self.change_region)
            self.add_layer = QPushButton("Configurer calque…")
            self.add_layer.clicked.connect(self.configure_layer)
            self.diagnostics_box = QLabel()
            self.diagnostics_box.setWordWrap(True)

            # RPG Maker-style visual part selection, with canonical R7 layers.
            self.part_category = QListWidget()
            for slot, label in PART_CATEGORIES:
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, slot)
                self.part_category.addItem(item)
            self.part_category.currentRowChanged.connect(self.refresh_parts)
            self.part_grid = QListWidget()
            self.part_grid.setViewMode(QListView.IconMode)
            self.part_grid.setIconSize(QSize(58, 58))
            self.part_grid.setGridSize(QSize(94, 88))
            self.part_grid.setResizeMode(QListView.Adjust)
            self.part_grid.setMovement(QListView.Static)
            self.part_grid.setWrapping(True)
            self.part_grid.currentItemChanged.connect(self.choose_part)
            self.part_status = QLabel()
            self.part_status.setWordWrap(True)
            self.look_grid = QListWidget()
            self.look_grid.setViewMode(QListView.IconMode)
            self.look_grid.setIconSize(QSize(72, 72))
            self.look_grid.setGridSize(QSize(108, 104))
            self.look_grid.setResizeMode(QListView.Adjust)
            self.look_grid.setMovement(QListView.Static)
            self.look_grid.setWrapping(True)
            self.look_grid.itemClicked.connect(self.choose_look)
            self.look_hint = QLabel("Ready-made looks (editable). Select to apply.")
            self.look_hint.setWordWrap(True)
            self.face_canvas = QLabel("Face / portrait")
            self.face_canvas.setAlignment(Qt.AlignCenter)
            self.face_canvas.setMinimumSize(145, 145)
            self.face_canvas.setStyleSheet(
                "background: #243142; border-radius: 5px; color: white;")
            self.direction_canvases = {}
            self.overview_title = QLabel("CHARACTER OVERVIEW")
            self.overview_title.setStyleSheet("font-weight: bold; font-size: 15px;")
            self.character_name = QLabel()
            self.character_name.setStyleSheet("font-size: 13px;")

            self.split_hair = QPushButton("Split legacy Hair into Front + Rear")
            self.split_hair.setToolTip(
                "Undoable conversion of the old Hair layer. Original artwork "
                "is preserved; separate edits become possible.")
            self.split_hair.clicked.connect(self.split_selected_legacy_hair)
            self.part_color = QPushButton("Choose color…")
            self.part_color.clicked.connect(self.choose_color)
            self.part_opacity = QSpinBox()
            self.part_opacity.setRange(0, 255)
            self.part_opacity.editingFinished.connect(self.apply_part_style)
            self.part_x = QSpinBox()
            self.part_y = QSpinBox()
            for spin in (self.part_x, self.part_y):
                spin.setRange(-4096, 4096)
                spin.editingFinished.connect(self.apply_part_style)
            self.pose_grid = QListWidget()
            self.pose_grid.setViewMode(QListView.IconMode)
            self.pose_grid.setIconSize(QSize(58, 58))
            self.pose_grid.setGridSize(QSize(90, 96))
            self.pose_grid.setResizeMode(QListView.Adjust)
            self.pose_grid.setMovement(QListView.Static)
            self.pose_grid.setWrapping(True)
            self.pose_grid.itemClicked.connect(self.choose_pose)

            # Three permanent editor regions, similar to the reference
            # character generator. The preview NEVER gets hidden by tools.
            category_box = QWidget()
            category_layout = QVBoxLayout(category_box)
            category_layout.setContentsMargins(8, 8, 8, 8)
            category_layout.addWidget(QLabel("Appearance"))
            category_layout.addWidget(self.part_category, 7)
            category_layout.addWidget(QLabel("Outfits / Variants"))
            category_layout.addWidget(self.variants, 2)
            category_layout.addWidget(self.add_variant)
            category_layout.addWidget(QLabel("Expressions"))
            category_layout.addWidget(self.expression)
            category_layout.addWidget(self.add_expression)
            category_layout.addWidget(self.diagnostics_box, 1)

            variation_box = QWidget()
            variation_layout = QVBoxLayout(variation_box)
            variation_layout.setContentsMargins(8, 8, 8, 8)
            variation_layout.addWidget(QLabel("Variation"))
            variation_layout.addWidget(self.part_grid, 5)
            variation_layout.addWidget(self.part_status)
            variation_layout.addWidget(self.split_hair)
            color_controls = QHBoxLayout()
            color_controls.addWidget(QLabel("Color"))
            color_controls.addWidget(self.part_color)
            color_controls.addWidget(QLabel("Alpha"))
            color_controls.addWidget(self.part_opacity)
            variation_layout.addLayout(color_controls)
            palette = QHBoxLayout()
            for color in ("#ffffff", "#f8ce9d", "#b87652", "#412a24",
                          "#ffd359", "#71b7e3", "#d875b7", "#8e5ecb",
                          "#44885a", "#2e2e36"):
                swatch = QToolButton()
                swatch.setToolTip(color)
                swatch.setFixedSize(22, 22)
                swatch.setStyleSheet(
                    "QToolButton { background-color: " + color +
                    "; border: 1px solid #73808e; }")
                swatch.clicked.connect(
                    lambda checked=False, value=color: self.apply_part_style(tint=value))
                palette.addWidget(swatch)
            variation_layout.addLayout(palette)
            offsets = QHBoxLayout()
            offsets.addWidget(QLabel("Offset X"))
            offsets.addWidget(self.part_x)
            offsets.addWidget(QLabel("Y"))
            offsets.addWidget(self.part_y)
            for label, dx, dy in (("←", -1, 0), ("↑", 0, -1),
                                  ("↓", 0, 1), ("→", 1, 0)):
                move = QToolButton()
                move.setText(label)
                move.setToolTip("Move selected element 1 px (Ctrl+Z to undo)")
                move.clicked.connect(
                    lambda checked=False, x=dx, y=dy: self.move_part(x, y))
                offsets.addWidget(move)
            variation_layout.addLayout(offsets)
            variation_layout.addWidget(QLabel("Ready-made looks"))
            variation_layout.addWidget(self.look_grid, 4)
            variation_layout.addWidget(self.look_hint)

            overview_box = QWidget()
            overview = QVBoxLayout(overview_box)
            overview.setContentsMargins(10, 8, 10, 8)
            overview.addWidget(self.overview_title)
            overview.addWidget(self.character_name)
            overview.addWidget(self.profile_tabs)
            scene = QHBoxLayout()
            scene.addWidget(self.canvas, 3)
            face_col = QVBoxLayout()
            face_col.addWidget(QLabel("Face / Portrait"))
            face_col.addWidget(self.face_canvas, 1)
            face_col.addWidget(QLabel("View / Action"))
            face_col.addWidget(self.direction)
            face_col.addWidget(self.action)
            face_col.addWidget(self.play)
            face_col.addWidget(self.onion)
            face_col.addStretch()
            scene.addLayout(face_col, 1)
            overview.addLayout(scene, 4)

            overview.addWidget(QLabel("FOUR DIRECTIONS · live overview"))
            directions_row = QHBoxLayout()
            for direction, label in (("south", "Front"), ("north", "Back"),
                                     ("east", "Right"), ("west", "Left")):
                direction_box = QVBoxLayout()
                thumb = QLabel()
                thumb.setAlignment(Qt.AlignCenter)
                thumb.setMinimumHeight(96)
                thumb.setStyleSheet(
                    "background: #293648; border-radius: 5px; color: white;")
                direction_box.addWidget(thumb, 1)
                text_label = QLabel(label)
                text_label.setAlignment(Qt.AlignCenter)
                direction_box.addWidget(text_label)
                directions_row.addLayout(direction_box, 1)
                self.direction_canvases[direction] = thumb
            overview.addLayout(directions_row, 2)
            overview.addWidget(QLabel("Existing poses / animations"))
            overview.addWidget(self.pose_grid, 2)
            overview.addWidget(self.status)

            center = QSplitter(Qt.Horizontal)
            center.addWidget(category_box)
            center.addWidget(variation_box)
            center.addWidget(overview_box)
            center.setStretchFactor(0, 1)
            center.setStretchFactor(1, 2)
            center.setStretchFactor(2, 3)
            center.setSizes([220, 385, 650])
            center.setChildrenCollapsible(False)
            self.setCentralWidget(center)

            # Searchable scalable library (replaces the original combobox).
            library_panel = QWidget()
            library_layout = QVBoxLayout(library_panel)
            library_layout.addWidget(self.library_search)
            library_layout.addWidget(self.library_grid, 1)
            library_layout.addWidget(self.library_count)
            library_layout.addWidget(self.library_open)
            library_layout.addWidget(self.library_reload)
            self.library_dock = QDockWidget("Character Library", self)
            self.library_dock.setObjectName("CharacterLibraryDock")
            self.library_dock.setWidget(library_panel)
            self.library_dock.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.addDockWidget(Qt.LeftDockWidgetArea, self.library_dock)

            # Timeline and source-PNG tools exist for advanced authoring only.
            # They must never replace or obscure the character overview.
            tools_panel = QWidget()
            tools_layout = QVBoxLayout(tools_panel)
            tools_layout.addWidget(QLabel("Timeline — select a keyframe"))
            tools_layout.addWidget(self.timeline, 1)
            tools_layout.addWidget(self.make_clip)
            key_buttons = QHBoxLayout()
            key_buttons.addWidget(self.add_key)
            key_buttons.addWidget(self.remove_key)
            tools_layout.addLayout(key_buttons)
            form = QFormLayout()
            form.addRow("Duration", self.duration)
            form.addRow("Frame Offset X", self.offset_x)
            form.addRow("Frame Offset Y", self.offset_y)
            source_row = QWidget()
            source_layout = QHBoxLayout(source_row)
            source_layout.setContentsMargins(0, 0, 0, 0)
            source_layout.addWidget(self.source)
            source_layout.addWidget(self.browse_source)
            form.addRow("PNG source", source_row)
            form.addRow("Atlas region", self.region)
            tools_layout.addLayout(form)
            tools_layout.addWidget(self.add_layer)
            self.timeline_dock = QDockWidget("Animation Tools", self)
            self.timeline_dock.setObjectName("CharacterAnimationDock")
            self.timeline_dock.setWidget(tools_panel)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.timeline_dock)
            self.timeline_dock.hide()

            file_menu = self.menuBar().addMenu("&File")
            def command(text, shortcut, handler, menu=file_menu):
                action = QAction(text, self)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(handler)
                menu.addAction(action)
                return action
            command("&New Character…", "Ctrl+N", self.new_character)
            command("&Open Character…", "Ctrl+O", self.open_recipe)
            command("&Save", "Ctrl+S", self.save_recipe)
            command("&Export Atlas…", "Ctrl+E", self.export)
            edit_menu = self.menuBar().addMenu("&Edit")
            command("&Undo", "Ctrl+Z", self.undo, edit_menu)
            command("&Redo", "Ctrl+Shift+Z", self.redo, edit_menu)
            view_menu = self.menuBar().addMenu("&View")
            view_menu.addAction(self.library_dock.toggleViewAction())
            view_menu.addAction(self.timeline_dock.toggleViewAction())
            command("Search Character Library", "Ctrl+L",
                    lambda: self.library_search.setFocus(), view_menu)
            self.part_category.setCurrentRow(0)
            self.refresh_library()
            self.statusBar().showMessage(
                "Character Studio | Select parts, edit colors and offsets. "
                "Preview and four directions remain visible.")

        def _character_icon(self, document, variant=None, action="idle"):
            """Only genuine rendered sprites are used for gallery thumbnails."""
            try:
                variant = variant or next(iter(document["variants"]))
                clips = document["variants"][variant]["clips"]
                if action not in clips:
                    action = next(iter(clips))
                directions = clips[action]["directions"]
                direction = next((key for key in ("south", "east", "north", "west")
                                  if directions.get(key)), None)
                if direction is None:
                    return QIcon()
                source = render_frame(document, variant, action, direction, 0, root)
                memory = io.BytesIO()
                source.save(memory, format="PNG")
                image = QPixmap()
                image.loadFromData(memory.getvalue(), "PNG")
                return QIcon(image)
            except (ValueError, OSError, KeyError, StopIteration):
                return QIcon()

        def refresh_library(self, *_):
            """Filter by name/ID without changing what the user is editing."""
            previous = self.library_grid.currentItem()
            key_before = previous.data(Qt.UserRole) if previous else None
            results = search_characters(
                self.library_entries, self.library_search.text())
            self.library_grid.blockSignals(True)
            self.library_grid.clear()
            for key, label in results:
                cache_key = ("library", key)
                if cache_key not in self._gallery_cache:
                    self._gallery_cache[cache_key] = self._character_icon(
                        self.library_entries[key][1])
                icon = self._gallery_cache[cache_key]
                item = QListWidgetItem(icon, label)
                item.setData(Qt.UserRole, key)
                item.setToolTip(
                    label + "\n" + key + "\nDouble-click to open")
                self.library_grid.addItem(item)
                if key == key_before:
                    self.library_grid.setCurrentItem(item)
            if self.library_grid.currentRow() < 0 and self.library_grid.count():
                self.library_grid.setCurrentRow(0)
            self.library_grid.blockSignals(False)
            self.library_count.setText(
                f"{len(results)} of {len(self.library_entries)} characters"
                " | Double-click to open")
            self.library_open.setEnabled(bool(results))

        def reload_library(self):
            self.library_entries = discover_character_library(root, templates)
            self._gallery_cache.clear()
            self.refresh_library()

        def _confirm_replace(self):
            if self.session.revision == self.saved_revision:
                return True
            return QMessageBox.question(
                self, "Unsaved changes",
                "Open another character and discard your unsaved changes?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            ) == QMessageBox.Yes

        def open_selected_library(self):
            item = self.library_grid.currentItem()
            if item is not None:
                self.open_library_item(item)

        def open_library_item(self, item):
            key = item.data(Qt.UserRole)
            record = self.library_entries.get(key)
            if record is None or not self._confirm_replace():
                return
            try:
                self.stop()
                self.session = CharacterSession(record[1])
                self.path = (root / key[len("file:"):]
                             if key.startswith("file:") else None)
                self.art_root = root
                self.saved_revision = self.session.revision
                self.refresh()
                self.statusBar().showMessage("Opened " + record[0])
            except (KeyError, CharacterError, ValueError) as exc:
                QMessageBox.warning(self, "Character library", str(exc))

        def new_character(self):
            from PySide6.QtWidgets import QInputDialog
            import re
            if not self._confirm_replace():
                return
            name, ok = QInputDialog.getText(
                self, "New Character", "Character name", text="New Hero")
            if not ok or not name.strip():
                return
            identifier = re.sub(r"[^a-z0-9]+", "_", name.strip().casefold())
            identifier = identifier.strip("_")[:60]
            if not identifier or not identifier[0].isalpha():
                QMessageBox.warning(
                    self, "Character name", "Name needs at least one Latin letter.")
                return
            doc = templates["modular_hero"].copy()
            doc["id"] = identifier
            doc["name"] = name.strip()
            self.stop()
            self.session = CharacterSession(doc)
            self.path = None
            self.art_root = root
            self.saved_revision = 0
            self.refresh()

        def _look_icon(self, look):
            key = ("look", look["id"])
            if key not in self._gallery_cache:
                from copy import deepcopy
                doc = deepcopy(templates["modular_hero"])
                try:
                    apply_look(doc, look["profile"], look["id"], root)
                    self._gallery_cache[key] = self._character_icon(
                        doc, look["profile"])
                except (CharacterError, ValueError, OSError):
                    self._gallery_cache[key] = QIcon()
            return self._gallery_cache[key]

        def refresh_looks(self):
            self.look_grid.blockSignals(True)
            self.look_grid.clear()
            doc = self.session.document
            enabled = doc["size"] == [192, 192] and self.art_root == root
            self.look_grid.setEnabled(enabled)
            profile = self.active_variant()
            if enabled:
                looks = available_looks(
                    profile if profile in PROFILE_PRESETS else None)
                for look in looks:
                    icon = self._look_icon(look)
                    item = QListWidgetItem(icon, look["name"])
                    item.setData(Qt.UserRole, look["id"])
                    item.setToolTip(
                        look["profile"].title() + " / " + look["name"] +
                        "\nUses existing sprites with editable defaults")
                    self.look_grid.addItem(item)
                self.look_hint.setText(
                    f"{len(looks)} curated looks using existing parts. "
                    "Select to apply; Ctrl+Z undoes the change.")
            else:
                self.look_hint.setText(
                    "Looks require a 192×192 Modular Hero. "
                    "Other character formats remain editable in Animation Tools.")
            self.look_grid.blockSignals(False)

        def choose_look(self, item):
            look_id = item.data(Qt.UserRole)
            if not look_id or not self.look_grid.isEnabled():
                return
            variant = self.active_variant()
            try:
                self.session.edit(
                    lambda document: apply_look(document, variant, look_id, root))
                self.refresh()
                self.statusBar().showMessage(
                    "Applied " + item.text() + " to " + variant +
                    "; adjust parts and offsets freely.")
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))

        def _to_pixmap(self, image, size):
            memory = io.BytesIO()
            image.save(memory, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(memory.getvalue(), "PNG"):
                return QPixmap()
            return pixmap.scaled(size, size, Qt.KeepAspectRatio,
                                 Qt.FastTransformation)

        def refresh_overview(self):
            """Always show four authored facings plus a face crop/portrait."""
            doc = self.session.document
            variant = self.active_variant()
            action = self.action.currentData()
            self.character_name.setText(
                doc["name"] + "  ·  " +
                doc["variants"][variant]["name"] + "  ·  " +
                str(doc["size"][0]) + "×" + str(doc["size"][1]))
            for direction, thumb in self.direction_canvases.items():
                thumb.clear()
                frames = doc["variants"][variant]["clips"].get(
                    action, {}).get("directions", {}).get(direction, ())
                if not frames:
                    thumb.setText("Not authored")
                    continue
                try:
                    frame_no = min(self.frame_index, len(frames) - 1)
                    image = render_frame(
                        doc, variant, action, direction, frame_no, self.art_root)
                    thumb.setPixmap(self._to_pixmap(image, 126))
                except (ValueError, OSError, KeyError) as exc:
                    thumb.setText("Missing asset")
            # Face panel: existing authored expression takes precedence.
            self.face_canvas.clear()
            expr = self.expression.currentData()
            portrait = doc["variants"][variant]["expressions"].get(expr, "")
            if portrait:
                pixmap = QPixmap(str(self.art_root / portrait))
                if not pixmap.isNull():
                    self.face_canvas.setPixmap(
                        pixmap.scaled(158, 158, Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation))
                    return
            for action_name in ("idle", action):
                frames = doc["variants"][variant]["clips"].get(
                    action_name, {}).get("directions", {}).get("south", ())
                if not frames:
                    continue
                try:
                    image = render_frame(
                        doc, variant, action_name, "south", 0, self.art_root)
                    width, height = image.size
                    head = image.crop((0, 0, width, max(1, round(height * 0.68))))
                    self.face_canvas.setPixmap(self._to_pixmap(head, 154))
                    self.face_canvas.setToolTip(
                        "Crop of the actual sprite (not a separate authored portrait)")
                    return
                except (OSError, ValueError, KeyError):
                    continue
            self.face_canvas.setText("No face art")

        def sync_profile_tabs(self):
            """Tabs are only for Modular Hero, not arbitrary RPG actors."""
            doc = self.session.document
            visible = (doc["size"] == [192, 192]
                       and bool(set(PROFILE_PRESETS) & set(doc["variants"])))
            self.profile_tabs.setVisible(visible)
            self.profile_tabs.blockSignals(True)
            active = self.active_variant() if visible else None
            index = (PROFILE_PRESETS.index(active)
                     if active in PROFILE_PRESETS else -1)
            self.profile_tabs.setCurrentIndex(index)
            self.profile_tabs.blockSignals(False)

        def profile_changed(self, index):
            if index < 0:
                return
            doc = self.session.document
            if doc["size"] != [192, 192]:
                return
            profile = self.profile_tabs.tabData(index)
            if profile not in PROFILE_PRESETS:
                return
            try:
                if profile not in doc["variants"]:
                    # Non-destructive migration of old 'default' characters.
                    self.session.edit(lambda candidate: ensure_profile(
                        candidate, profile))
                    self.refresh()
                ids = list(self.session.document["variants"])
                if profile in ids:
                    self.variants.setCurrentRow(ids.index(profile))
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))
                self.sync_profile_tabs()

        def split_selected_legacy_hair(self):
            variant = self.active_variant()
            try:
                self.session.edit(
                    lambda doc: upgrade_legacy_hair(doc, variant, root))
                for index in range(self.part_category.count()):
                    if self.part_category.item(index).data(Qt.UserRole) == "front_hair":
                        self.part_category.setCurrentRow(index)
                        break
                self.refresh()
                self.statusBar().showMessage(
                    "Legacy Hair split. Front/Rear have separate offsets "
                    "and colors. Ctrl+Z to undo.")
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))

        def selected_part_slot(self):
            item = self.part_category.currentItem()
            return item.data(Qt.UserRole) if item else None

        def refresh_parts(self, *_):
            """Show actual four-direction variations, never fabricated art."""
            slot = self.selected_part_slot()
            self.part_grid.blockSignals(True)
            self.part_grid.clear()
            if slot is None:
                self.part_grid.blockSignals(False)
                return
            doc = self.session.document
            variant = self.active_variant()
            layer = active_part(doc, variant, slot)
            enabled = doc["size"] == [192, 192] and self.art_root == root
            self.part_grid.setEnabled(enabled)
            if enabled:
                none = QListWidgetItem("None")
                none.setData(Qt.UserRole, None)
                self.part_grid.addItem(none)
                try:
                    variants = available_parts(root, slot)
                except CharacterError:
                    variants = ()
                for name in variants:
                    icon_path = root / part_paths(slot, name, root)["south"]
                    icon = QIcon(str(icon_path))
                    # Preview exactly the same legacy fringe mask used in
                    # render_frame/export_pack, never the unsplit source art.
                    if slot == "front_hair" and icon_path.parent.name == "hair":
                        try:
                            with Image.open(icon_path) as source_image:
                                split = split_legacy_hair_front(
                                    source_image.convert("RGBA"))
                            memory = io.BytesIO()
                            split.save(memory, format="PNG")
                            thumbnail = QPixmap()
                            if thumbnail.loadFromData(memory.getvalue(), "PNG"):
                                icon = QIcon(thumbnail)
                        except (OSError, ValueError):
                            pass
                    item = QListWidgetItem(icon,
                                           name.replace("_", " ").title())
                    item.setData(Qt.UserRole, name)
                    self.part_grid.addItem(item)
                selected_name = None
                if layer is not None:
                    path = layer["paths"].get("south", "")
                    if path.endswith("_front.png"):
                        candidate = Path(path).stem[:-len("_front")]
                        if candidate in variants and path == part_paths(
                                slot, candidate, root)["south"]:
                            selected_name = candidate
                for i in range(self.part_grid.count()):
                    item = self.part_grid.item(i)
                    if item.data(Qt.UserRole) == selected_name:
                        self.part_grid.setCurrentRow(i)
                        break
                prefix = ""
                if slot == "front_hair":
                    prefix = ("Legacy source: upper-fringe approximation. "
                              "Independently painted PNGs are preferred. ")
                elif slot == "rear_hair":
                    prefix = ("Legacy source: full hair behind the head. "
                              "Independently painted PNGs are preferred. ")
                self.part_status.setText(
                    prefix + f"{len(variants)} variants | 4 directions | "
                    "Independent color and offset for selected piece")
            else:
                self.part_status.setText(
                    "Visual modular parts use a 192 x 192 canvas and repository "
                    "assets. Choose the Modular Hero template to enable them.")
            self.part_grid.blockSignals(False)
            active = enabled and layer is not None
            for control in (self.part_color, self.part_opacity, self.part_x, self.part_y):
                control.setEnabled(active)
            for spin, value in (
                (self.part_x, layer["offset"][0] if layer else 0),
                (self.part_y, layer["offset"][1] if layer else 0),
                (self.part_opacity, layer["opacity"] if layer else 255),
            ):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
            tint = layer["tint"] if layer else "#ffffff"
            self.part_color.setStyleSheet("background-color: " + tint + ";")
            self.split_hair.setVisible(
                enabled and active_part(doc, variant, "hair") is not None)

        def choose_part(self, item, previous):
            if item is None or not self.part_grid.isEnabled():
                return
            slot = self.selected_part_slot()
            name = item.data(Qt.UserRole)
            current = active_part(self.session.document, self.active_variant(), slot)
            expected = part_paths(slot, name, root) if name is not None else None
            if (current is None and name is None) or (
                    current is not None and current["paths"] == expected):
                return
            try:
                vid = self.active_variant()
                self.session.edit(
                    lambda doc: set_part(doc, vid, slot, name, root))
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))
            self.refresh_parts()
            self.refresh_pose_grid()
            self.refresh_preview()

        def choose_color(self):
            layer = active_part(self.session.document, self.active_variant(),
                                self.selected_part_slot())
            if layer is None:
                return
            color = QColorDialog.getColor(
                QColor(layer["tint"]), self, "Selected element color")
            if color.isValid():
                self.apply_part_style(tint=color.name())

        def apply_part_style(self, *, tint=None):
            slot = self.selected_part_slot()
            if slot is None or not self.part_grid.isEnabled():
                return
            old = active_part(self.session.document, self.active_variant(), slot)
            if old is None:
                return
            vid = self.active_variant()
            offset = [self.part_x.value(), self.part_y.value()]
            opacity = self.part_opacity.value()
            color = tint if tint is not None else old["tint"]
            if (old["offset"] == offset and old["opacity"] == opacity
                    and old["tint"] == color):
                return
            try:
                self.session.edit(lambda doc: set_part_style(
                    doc, vid, slot, offset=offset, opacity=opacity, tint=color))
            except CharacterError as exc:
                self.statusBar().showMessage(str(exc))
            self.refresh_parts()
            self.refresh_pose_grid()
            self.refresh_preview()

        def move_part(self, dx, dy):
            if not self.part_grid.isEnabled():
                return
            slot = self.selected_part_slot()
            if slot is None or active_part(
                    self.session.document, self.active_variant(), slot) is None:
                return
            self.part_x.setValue(max(-4096, min(4096, self.part_x.value() + dx)))
            self.part_y.setValue(max(-4096, min(4096, self.part_y.value() + dy)))
            self.apply_part_style()

        def refresh_pose_grid(self):
            """All existing posture/direction combinations; no animation copies."""
            self.pose_grid.clear()
            doc = self.session.document
            variant = self.active_variant()
            for action in ACTIONS:
                directions = doc["variants"][variant]["clips"].get(
                    action, {}).get("directions", {})
                for direction in DIRECTIONS:
                    if not directions.get(direction):
                        continue
                    try:
                        image = render_frame(
                            doc, variant, action, direction, 0, self.art_root)
                        data = io.BytesIO()
                        image.save(data, format="PNG")
                        pixmap = QPixmap()
                        pixmap.loadFromData(data.getvalue(), "PNG")
                    except (CharacterError, OSError, KeyError, ValueError):
                        continue
                    item = QListWidgetItem(
                        QIcon(pixmap), action.capitalize() + " / " + direction)
                    item.setData(Qt.UserRole, (action, direction))
                    self.pose_grid.addItem(item)
            if not self.pose_grid.count():
                self.pose_grid.addItem("No authored postures for this outfit")

        def choose_pose(self, item):
            choice = item.data(Qt.UserRole)
            if not choice:
                return
            action, direction = choice
            self.stop()
            self.action.setCurrentIndex(self.action.findData(action))
            self.direction.setCurrentIndex(self.direction.findData(direction))
            self.frame_index = 0
            self.refresh_timeline()

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
            self.sync_profile_tabs()
            # Clear stale portrait choice before drawing a different outfit.
            self.refresh_expressions()
            self.refresh_timeline()
            self.refresh_parts()
            self.refresh_looks()
            self.refresh_pose_grid()
            problems = diagnostics(document, require_outfits=document["id"] == "jeanne")
            errors = sum(p["severity"] == "error" for p in problems)
            self.diagnostics_box.setText(
                f"{errors} erreur(s), {len(problems)-errors} avertissement(s)\n" +
                "\n".join(f"• {p['code']} {p.get('variant','')} {p.get('action','')}"
                          for p in problems[:7]))
            self.setWindowTitle(
                "DrawTemp — Character Studio — " + document["name"] +
                ("" if self.path is None else " — " + self.path.name))

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
            self.sync_profile_tabs()
            self.stop()
            self.frame_index = 0
            # Clear stale portrait choice before drawing a different outfit.
            self.refresh_expressions()
            self.refresh_timeline()
            self.refresh_parts()
            self.refresh_looks()
            self.refresh_pose_grid()

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
                            self.offset_x, self.offset_y, self.source, self.region,
                            self.browse_source):
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
            # Overview persists even when a single pose or portrait is absent.
            self.refresh_overview()
            self.canvas.clear()
            expression = self.expression.currentData()
            if expression:
                path = self.session.document["variants"][self.active_variant()]\
                       ["expressions"][expression]
                picture = QPixmap(str(self.art_root / path))
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
                    self.frame_index, self.art_root)
                if self.onion.isChecked() and self.frame_index > 0:
                    ghost = render_frame(
                        self.session.document, self.active_variant(),
                        self.action.currentData(), self.direction.currentData(),
                        self.frame_index - 1, self.art_root)
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
            self.refresh_pose_grid()

        def change_duration(self):
            self.change_frame("duration_ms", self.duration.value())

        def change_offset(self):
            self.change_frame("offset", [self.offset_x.value(), self.offset_y.value()])

        def change_source(self):
            self.change_frame("path", self.source.text().strip())

        def choose_asset(self, caption):
            source, _ = QFileDialog.getOpenFileName(
                self, caption, str(root), "Images PNG (*.png)")
            if not source:
                return None
            try:
                return Path(source).resolve().relative_to(root).as_posix()
            except ValueError:
                QMessageBox.warning(self, "Image externe",
                                    "Importez d’abord les PNG dans le projet.")
                return None

        def select_source(self):
            source = self.choose_asset("Choisir une pose PNG")
            if source is not None:
                self.change_frame("path", source)

        def import_expression(self):
            from PySide6.QtWidgets import QInputDialog
            source = self.choose_asset("Importer un portrait PNG")
            if source is None:
                return
            name, ok = QInputDialog.getText(
                self, "Expression", "ID de l'expression (ex. determined)")
            if not ok or not name.strip():
                return
            vid = self.active_variant()
            try:
                def transform(doc):
                    doc["variants"][vid]["expressions"][name.strip()] = source
                self.session.edit(transform)
                self.refresh()
                self.expression.setCurrentIndex(self.expression.findData(name.strip()))
            except CharacterError as exc:
                QMessageBox.warning(self, "Portrait", str(exc))

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
            opacity, ok = QInputDialog.getInt(
                self, "Opacité", "Alpha de 0 (transparent) à 255 (opaque)",
                255, 0, 255)
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
                        existing["opacity"] = opacity
                self.session.edit(transform)
                self.refresh()
            except CharacterError as exc:
                QMessageBox.warning(self, "Calque", str(exc))

        def open_recipe(self):
            if not self._confirm_replace():
                return
            path, _ = QFileDialog.getOpenFileName(
                self, "Ouvrir un personnage R7", str(root), "JSON (*.json)")
            if path:
                try:
                    self.session = CharacterSession(
                        json.loads(Path(path).read_text(encoding="utf-8")))
                    self.path = Path(path)
                    self.art_root = (
                        self.path.parent if
                        (self.path.parent / "sources/jeanne_atlas.png").is_file()
                        else root)
                    self.saved_revision = self.session.revision
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
                self.saved_revision = self.session.revision
                self.statusBar().showMessage("Character saved.")
                self.refresh()
            except OSError as exc:
                QMessageBox.critical(self, "Enregistrement", str(exc))

        def export(self):
            path = QFileDialog.getExistingDirectory(
                self, "Dossier de sortie du pack R7", str(root.parent))
            if not path:
                return
            try:
                registry = export_pack(self.session.document, self.art_root, Path(path))
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
    smoke_errors = []
    if args.smoke:
        def verify_smoke():
            try:
                if window.session.document["id"] == "modular_hero":
                    # Exercise actual Qt tab selection, not only construction.
                    assert window.profile_tabs.count() == len(PROFILE_PRESETS)
                    for index, name in enumerate(PROFILE_PRESETS):
                        window.profile_tabs.setCurrentIndex(index)
                        assert window.active_variant() == name, (
                            "Profile tab did not select " + name)
                    assert window.pose_grid.count() == 4, (
                        "Static four-direction poses were not shown")
                    assert window.library_grid.count() >= 7, (
                        "Character library not populated")
                    assert len(window.direction_canvases) == 4, (
                        "All four permanent facing previews must exist")
                    assert window.canvas.isVisible(), (
                        "Main overview should always be visible")
                    assert not hasattr(window, "generate_outfits"), (
                        "Jeanne-specific outfit UI must not return")
            except Exception as exc:
                smoke_errors.append(str(exc))
            finally:
                app.quit()
        QTimer.singleShot(120, verify_smoke)
    result = app.exec()
    if smoke_errors:
        print("Character Studio smoke failed: " + "; ".join(smoke_errors),
              file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
