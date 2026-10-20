"""R51.B — visually edit versioned HUD layouts in the shared R1 Studio session.

WYSIWYG preview uses the same R51Layout.qml as the Player. Its values are
explicitly labelled samples, not claims about a live combat simulation.
Only a user-confirmed R1 preview/apply updates GameProject.extensions.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.r51_layout_authoring import LayoutAuthoring
from drawtemp.quality.r51_ui import ui_export_audit
from drawtemp.studio.r51_layout_draft import (
    check_layout, edit_breakpoints, edit_layout, edit_gauge_bindings,
    editor_sample, move_focus, new_layout,
)
from sporebound.ui_layout_r51 import FIELDS, INTENTS, KINDS, NAMESPACE, VERSION, UiLayoutError


class R51DesignerDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setObjectName("r51-designer")
        self.setWindowTitle("R51.B — UI & HUD Designer")
        self.resize(1050, 710)
        self.editor = LayoutAuthoring(session)
        self._revision = session.revision
        self._draft = None
        self._layout_id = None
        self._pending = None
        self._populating = False

        outer = QVBoxLayout(self)
        heading = QLabel(
            "Designer UI/HUD · arbre déclaratif partagé avec le Player Qt Quick. "
            "L'aperçu contient des données d'exemple et reste non interactif."
        )
        heading.setWordWrap(True)
        outer.addWidget(heading)
        navigation = QHBoxLayout()
        self.layouts = QComboBox()
        self.layouts.setObjectName("r51-layout-select")
        self.layouts.setAccessibleName("Écran HUD à modifier")
        navigation.addWidget(self.layouts, 1)
        self.new_button = QPushButton("Nouvel écran")
        self.new_button.clicked.connect(self.new_screen)
        navigation.addWidget(self.new_button)
        self.delete_screen = QPushButton("Supprimer écran")
        self.delete_screen.clicked.connect(self.remove_screen)
        navigation.addWidget(self.delete_screen)
        outer.addLayout(navigation)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        self.tree = QTreeWidget()
        self.tree.setObjectName("r51-widget-tree")
        self.tree.setAccessibleName("Arbre de composants du HUD")
        self.tree.setHeaderLabels(["Composant", "Type"])
        editor_layout.addWidget(self.tree, 1)
        buttons = QHBoxLayout()
        for title, slot in (
            ("Ajouter", self.add_widget),
            ("Retirer", self.remove_widget),
            ("Monter", lambda: self.move_widget("up")),
            ("Descendre", lambda: self.move_widget("down")),
        ):
            button = QPushButton(title)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        editor_layout.addLayout(buttons)
        inspector = QFormLayout()
        self.widget_id = QLineEdit()
        self.widget_id.setObjectName("r51-widget-id")
        inspector.addRow("ID", self.widget_id)
        self.widget_text = QLineEdit()
        self.widget_text.setObjectName("r51-widget-label")
        inspector.addRow("Texte", self.widget_text)
        self.binding = QComboBox()
        self.binding.addItem("Texte littéral", "")
        for path in sorted(FIELDS):
            self.binding.addItem(path + " (" + FIELDS[path] + ")", path)
        inspector.addRow("Binding texte", self.binding)
        self.gauge_current = QComboBox()
        self.gauge_current.setObjectName("r51-gauge-current")
        self.gauge_maximum = QComboBox()
        self.gauge_maximum.setObjectName("r51-gauge-maximum")
        for path in sorted(FIELDS):
            if FIELDS[path] == "int":
                self.gauge_current.addItem(path, path)
                self.gauge_maximum.addItem(path, path)
        inspector.addRow("Valeur de jauge", self.gauge_current)
        inspector.addRow("Maximum de jauge", self.gauge_maximum)
        self.action = QComboBox()
        for intent in sorted(INTENTS):
            self.action.addItem(intent, intent)
        inspector.addRow("Action", self.action)
        self.save_widget = QPushButton("Modifier le composant")
        self.save_widget.setObjectName("r51-save-widget")
        self.save_widget.clicked.connect(self.update_widget)
        inspector.addRow(self.save_widget)
        editor_layout.addLayout(inspector)
        focus_row = QHBoxLayout()
        self.focus_up = QPushButton("Focus précédent")
        self.focus_up.setObjectName("r51-focus-up")
        self.focus_up.clicked.connect(lambda: self.move_keyboard_focus("up"))
        self.focus_down = QPushButton("Focus suivant")
        self.focus_down.setObjectName("r51-focus-down")
        self.focus_down.clicked.connect(lambda: self.move_keyboard_focus("down"))
        focus_row.addWidget(self.focus_up)
        focus_row.addWidget(self.focus_down)
        editor_layout.addLayout(focus_row)
        split.addWidget(editor_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.width_choice = QSpinBox()
        self.width_choice.setObjectName("r51-preview-width")
        self.width_choice.setRange(320, 3840)
        self.width_choice.setValue(800)
        self.width_choice.setSuffix(" px logiques")
        right_layout.addWidget(QLabel("Largeur de simulation responsive"))
        right_layout.addWidget(self.width_choice)
        theme_row = QHBoxLayout()
        self.contrast_preview = QCheckBox("Contraste renforcé")
        self.contrast_preview.setObjectName("r51-preview-contrast")
        self.contrast_preview.setAccessibleName("Mode contraste renforcé dans l'aperçu")
        theme_row.addWidget(self.contrast_preview)
        self.scale_preview = QSpinBox()
        self.scale_preview.setObjectName("r51-preview-text-scale")
        self.scale_preview.setRange(85, 135)
        self.scale_preview.setValue(100)
        self.scale_preview.setSingleStep(5)
        self.scale_preview.setSuffix(" % texte")
        self.scale_preview.setAccessibleName("Échelle du texte dans l'aperçu")
        theme_row.addWidget(self.scale_preview)
        right_layout.addLayout(theme_row)
        bp_row = QHBoxLayout()
        add_bp = QPushButton("Ajouter breakpoint")
        add_bp.clicked.connect(self.add_breakpoint)
        bp_row.addWidget(add_bp)
        remove_bp = QPushButton("Retirer dernier breakpoint")
        remove_bp.clicked.connect(self.remove_breakpoint)
        bp_row.addWidget(remove_bp)
        right_layout.addLayout(bp_row)
        self.preview = QQuickWidget()
        self.preview.setObjectName("r51-quick-preview")
        self.preview.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.preview.setSource(QUrl.fromLocalFile(str(
            Path(__file__).resolve().parents[1] / "player" / "R51Layout.qml"
        )))
        self.preview.statusChanged.connect(lambda *_: self._render())
        right_layout.addWidget(self.preview, 1)
        self.report = QLabel("")
        self.report.setObjectName("r51-report")
        self.report.setWordWrap(True)
        right_layout.addWidget(self.report)
        split.addWidget(right_panel)
        split.setSizes([420, 630])

        actions = QHBoxLayout()
        self.stage_button = QPushButton("Préparer la transaction")
        self.stage_button.setObjectName("r51-stage")
        self.stage_button.clicked.connect(self.stage)
        actions.addWidget(self.stage_button)
        self.apply_button = QPushButton("Appliquer au projet")
        self.apply_button.setObjectName("r51-apply")
        self.apply_button.clicked.connect(self.apply_changes)
        self.apply_button.setEnabled(False)
        actions.addWidget(self.apply_button)
        for title, slot in (("Annuler (R1)", self.undo),
                            ("Rétablir (R1)", self.redo),
                            ("Recharger", self.refresh)):
            button = QPushButton(title)
            button.clicked.connect(slot)
            actions.addWidget(button)
        outer.addLayout(actions)

        self.layouts.currentIndexChanged.connect(self._on_screen)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.width_choice.valueChanged.connect(self._render)
        self.contrast_preview.toggled.connect(self._render)
        self.scale_preview.valueChanged.connect(self._render)
        self.refresh()

    def _notice(self, exc):
        self.report.setText("Opération refusée : " + str(exc))
        return False

    def _invalidate(self):
        self._pending = None
        self.apply_button.setEnabled(False)

    def refresh(self):
        self._invalidate()
        info = self.editor.inspect()
        self._revision = info["revision"]
        previous = self._layout_id
        self._populating = True
        self.layouts.clear()
        for key, layout in sorted(info["catalog"]["layouts"].items()):
            self.layouts.addItem(key + " · " + layout["kind"], key)
        index = self.layouts.findData(previous)
        if index >= 0:
            self.layouts.setCurrentIndex(index)
        self._populating = False
        self._on_screen()

    def _on_screen(self, *_):
        if self._populating:
            return
        identifier = self.layouts.currentData()
        info = self.editor.inspect()
        self._layout_id = identifier
        self._draft = (deepcopy(info["catalog"]["layouts"][identifier])
                       if identifier is not None else None)
        self._invalidate()
        self._draw_tree()

    def _draw_tree(self):
        self._populating = True
        selected = self._selected_id()
        self.tree.clear()
        if self._draft is not None:
            def append(node, parent=None):
                item = QTreeWidgetItem([node["id"], node["type"]])
                item.setData(0, Qt.UserRole, node["id"])
                (parent.addChild(item) if parent is not None
                 else self.tree.addTopLevelItem(item))
                for child in node.get("children", []):
                    append(child, item)
                return item
            append(self._draft["root"])
            self.tree.expandAll()
            items = self.tree.findItems(selected, Qt.MatchExactly | Qt.MatchRecursive, 0) if selected else []
            self.tree.setCurrentItem(items[0] if items else self.tree.topLevelItem(0))
        self._populating = False
        self._on_selection()
        self._render()

    def _selected_id(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _selected_node(self):
        if self._draft is None:
            return None
        identifier = self._selected_id()
        def find(node):
            if node["id"] == identifier:
                return node
            for child in node.get("children", []):
                result = find(child)
                if result is not None:
                    return result
            return None
        return find(self._draft["root"])

    def _on_selection(self):
        if self._populating:
            return
        node = self._selected_node()
        self._populating = True
        self.widget_id.setText(node["id"] if node else "")
        self.widget_text.setText(node.get("text", "") if node else "")
        path = node.get("binding", {}).get("path", "") if node else ""
        self.binding.setCurrentIndex(max(0, self.binding.findData(path)))
        action = node.get("action", "") if node else ""
        self.action.setCurrentIndex(max(0, self.action.findData(action)))
        current = node.get("binding", {}).get("path", "") if node else ""
        maximum = node.get("max_binding", {}).get("path", "") if node else ""
        self.gauge_current.setCurrentIndex(max(0, self.gauge_current.findData(current)))
        self.gauge_maximum.setCurrentIndex(max(0, self.gauge_maximum.findData(maximum)))
        kind = node["type"] if node else ""
        self.widget_id.setEnabled(bool(node))
        self.widget_text.setEnabled(kind in ("text", "button"))
        self.binding.setEnabled(kind == "text")
        self.action.setEnabled(kind == "button")
        self.gauge_current.setEnabled(kind == "gauge")
        self.gauge_maximum.setEnabled(kind == "gauge")
        self.save_widget.setEnabled(bool(node))
        self.focus_up.setEnabled(kind == "button")
        self.focus_down.setEnabled(kind == "button")
        self._populating = False

    def _change(self, mutate):
        try:
            self._draft = mutate()
            self._invalidate()
            self._draw_tree()
            self.report.setText("Brouillon valide · préparer puis appliquer pour enregistrer.")
        except (UiLayoutError, ValueError) as exc:
            self._notice(exc)

    def new_screen(self):
        identifier, confirmed = QInputDialog.getText(
            self, "Nouvel écran", "Identifiant (a-z, chiffres et _)")
        if not confirmed:
            return
        kind, confirmed = QInputDialog.getItem(
            self, "Type d'écran", "Type", sorted(KINDS), 0, False)
        if not confirmed:
            return
        try:
            layout = check_layout(new_layout(kind))
            plan = self.editor.preview_replace(
                identifier, layout, expected_revision=self._revision)
            self.editor.apply(plan)
            self.updated.emit()
            self._layout_id = identifier
            self.refresh()
            self.report.setText("Écran créé via une transaction R1.")
        except (AuthoringError, UiLayoutError, ValueError) as exc:
            self._notice(exc)

    def remove_screen(self):
        if self._layout_id is None:
            return
        if QMessageBox.question(self, "Supprimer", "Supprimer cet écran du projet ?") != QMessageBox.Yes:
            return
        try:
            plan = self.editor.preview_remove(
                self._layout_id, expected_revision=self._revision)
            self.editor.apply(plan)
            self._layout_id = None
            self.updated.emit()
            self.refresh()
        except (AuthoringError, UiLayoutError, ValueError) as exc:
            self._notice(exc)

    def add_widget(self):
        if self._draft is None:
            return
        parent = self._selected_node()
        if parent is None or parent["type"] not in ("row", "column"):
            self.report.setText("Sélectionner une ligne ou une colonne.")
            return
        kind, confirmed = QInputDialog.getItem(
            self, "Ajouter un composant", "Type",
            ["text", "button", "gauge", "row", "column"], 0, False)
        if not confirmed:
            return
        identifier, confirmed = QInputDialog.getText(
            self, "Ajouter un composant", "Identifiant unique")
        if not confirmed:
            return
        templates = {
            "text": {"text": "Texte"},
            "button": {"text": "Continuer", "action": "menu.continue"},
            "gauge": {"binding": {"path": "combat.active_hp", "type": "int"},
                      "max_binding": {"path": "combat.active_max_hp", "type": "int"}},
            "row": {"children": [{"id": identifier + "_text", "type": "text", "text": "Texte"}]},
            "column": {"children": [{"id": identifier + "_text", "type": "text", "text": "Texte"}]},
        }
        widget = {"id": identifier, "type": kind, **templates[kind]}
        self._change(lambda: edit_layout(
            self._draft, "add", target=parent["id"], widget=widget))

    def remove_widget(self):
        if self._draft is not None:
            self._change(lambda: edit_layout(
                self._draft, "remove", target=self._selected_id()))

    def move_widget(self, direction):
        if self._draft is not None:
            self._change(lambda: edit_layout(
                self._draft, "move", target=self._selected_id(),
                direction=direction))

    def move_keyboard_focus(self, direction):
        node = self._selected_node()
        if node is not None and self._draft is not None:
            self._change(lambda: move_focus(
                self._draft, node["id"], direction))

    def update_widget(self):
        node = self._selected_node()
        if node is None:
            return
        changes = {"id": self.widget_id.text().strip()}
        if node["type"] == "text":
            path = self.binding.currentData()
            changes.update({"binding": {"path": path, "type": FIELDS[path]}}
                           if path else {"text": self.widget_text.text()})
            # The old exclusive text/binding property must be replaced, not merged.
            draft = deepcopy(self._draft)
            def rewrite(current):
                if current["id"] == node["id"]:
                    current.pop("text", None)
                    current.pop("binding", None)
                    current.update(changes)
                for child in current.get("children", []):
                    rewrite(child)
            rewrite(draft["root"])
            self._change(lambda: check_layout(draft))
            return
        if node["type"] == "button":
            changes.update(text=self.widget_text.text(), action=self.action.currentData())
        if node["type"] == "gauge":
            def edit():
                draft = edit_gauge_bindings(
                    self._draft, node["id"],
                    self.gauge_current.currentData(),
                    self.gauge_maximum.currentData())
                return edit_layout(
                    draft, "update", target=node["id"], changes=changes)
            self._change(edit)
            return
        self._change(lambda: edit_layout(
            self._draft, "update", target=node["id"], changes=changes))

    def add_breakpoint(self):
        if self._draft is None:
            return
        minimum, ok = QInputDialog.getInt(
            self, "Breakpoint", "Largeur minimale (px logiques)", 1280, 1, 16384)
        if not ok:
            return
        columns, ok = QInputDialog.getInt(
            self, "Breakpoint", "Colonnes", 2, 1, 4)
        if not ok:
            return
        points = deepcopy(self._draft["breakpoints"])
        points.append({"min_width": minimum, "columns": columns})
        points.sort(key=lambda row: row["min_width"])
        self._change(lambda: edit_breakpoints(self._draft, points))

    def remove_breakpoint(self):
        if self._draft is None or len(self._draft["breakpoints"]) <= 1:
            return
        self._change(lambda: edit_breakpoints(
            self._draft, self._draft["breakpoints"][:-1]))

    def _render(self, *_):
        if self._draft is None:
            self.report.setText("Créez un écran pour commencer.")
            return
        try:
            sample = editor_sample(self._draft, self.width_choice.value())
            root = self.preview.rootObject()
            if root is None:
                self.report.setText("Qt Quick indisponible : " +
                                    "; ".join(str(error) for error in self.preview.errors()))
                return
            root.setProperty("projection", sample)
            root.setProperty("allowActions", False)
            root.setProperty("permittedActions", [])
            root.setProperty("highContrast", self.contrast_preview.isChecked())
            root.setProperty("textScale", self.scale_preview.value() / 100.0)
            catalog = self.editor.inspect()["catalog"]
            catalog["layouts"][self._layout_id] = self._draft
            audit = ui_export_audit({
                "extensions": {
                    NAMESPACE: {"schema_version": VERSION, "data": catalog}
                }
            })
            if audit["errors"]:
                issues = " · Export bloqué : " + "; ".join(audit["errors"][:2])
            else:
                issues = " · Aucun blocage de capacités détecté (tests non certifiés)"
            self.report.setText(
                "Aperçu fictif · %d colonnes · aucune commande de jeu déclenchée%s"
                % (sample["columns"], issues))
        except (UiLayoutError, ValueError) as exc:
            self._notice(exc)

    def stage(self):
        if self._draft is None or self._layout_id is None:
            return
        try:
            self._pending = self.editor.preview_replace(
                self._layout_id, self._draft, expected_revision=self._revision)
            self.apply_button.setEnabled(True)
            self.report.setText("Preview R1 valide · Appliquer pour enregistrer.")
        except (UiLayoutError, AuthoringError, ValueError) as exc:
            self._invalidate()
            self._notice(exc)

    def apply_changes(self):
        if self._pending is None:
            return
        try:
            self.editor.apply(self._pending)
            self.updated.emit()
            self.refresh()
            self.report.setText("Layout enregistré en une transaction R1.")
        except (AuthoringError, UiLayoutError, ValueError) as exc:
            self._invalidate()
            self._notice(exc)

    def undo(self):
        try:
            self.editor.session.undo()
            self.updated.emit()
            self.refresh()
        except AuthoringError as exc:
            self._notice(exc)

    def redo(self):
        try:
            self.editor.session.redo()
            self.updated.emit()
            self.refresh()
        except AuthoringError as exc:
            self._notice(exc)
