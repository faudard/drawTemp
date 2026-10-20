"""R55.B native Qt graph editor over the canonical AuthoringSession.

Small, opt-in editor: no raw JSON entry or direct project writes. Lists and
graph are projections of one detached document; apply is one undoable commit.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
    QWidget,
)

from drawtemp.studio.system_design_authoring import (
    apply_system_design, forecast_system_design, preview_system_design)
from sporebound.system_design import EXTENSION, validate_systems
from drawtemp.studio.system_design_graph import edit_link
from drawtemp.studio.system_design_graph_qt import InteractiveSystemGraph


def _new_form(title, fields, parent):
    """One modal typed Qt form; caller receives detached values or None."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QFormLayout(dialog)
    controls = {}
    for key, label, kind, value, options in fields:
        if kind == "number":
            widget = QSpinBox()
            widget.setRange(options[0], options[1])
            widget.setValue(value)
        elif kind == "choice":
            widget = QComboBox()
            widget.addItems(options)
            widget.setCurrentText(value or (options[0] if options else ""))
        else:
            widget = QLineEdit(value)
        widget.setAccessibleName(label)
        controls[key] = widget
        layout.addRow(label, widget)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    result = {}
    for key, control in controls.items():
        if isinstance(control, QSpinBox):
            result[key] = control.value()
        elif isinstance(control, QComboBox):
            result[key] = control.currentText()
        else:
            result[key] = control.text().strip()
    return result


def _amount_text(values):
    return ", ".join(f"{key}:{value}" for key, value in sorted(values.items()))


def _parse_amount_text(text, allowed):
    """Parse typed resource ports without accepting Python/JSON expressions."""
    if type(text) is not str or not text.strip():
        raise ValueError("Les ports requièrent id:quantité séparés par des virgules.")
    rows = text.split(",")
    if len(rows) > 16:
        raise ValueError("Maximum 16 ressources par port.")
    values = {}
    for item in rows:
        parts = item.strip().split(":")
        if len(parts) != 2:
            raise ValueError("Format attendu: id:quantité, id:quantité")
        key, digits = (p.strip() for p in parts)
        if key not in allowed or key in values:
            raise ValueError("Ressource inconnue ou port répété: " + key)
        if not digits.isascii() or not digits.isdecimal():
            raise ValueError("Quantité entière positive requise pour " + key)
        value = int(digits)
        if not 1 <= value <= 1000:
            raise ValueError("Quantité hors de 1..1000 pour " + key)
        values[key] = value
    return values


class SystemDesignerDialog(QDialog):
    """Visual overview + typed authoring with transactional Apply/Undo."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        snap = session.snapshot().to_dict()
        self.source_revision = snap["revision"]
        # A merchant must be in exploration; CT mission scenes are not
        # tradable and are rejected by the canonical GameProject validator.
        self.scenes = sorted(snap["project"].get("exploration", {}))
        envelope = snap["project"].get("extensions", {}).get(EXTENSION)
        self.document = deepcopy(envelope["data"]) if envelope else {
            "version": 1, "resources": [], "producers": [],
            "merchants": [], "quests": []}
        self.setWindowTitle("System Designer R55 — ressources et cycles")
        self.resize(1050, 760)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Graphe déclaratif sans scripts. Validation, preview et commit "
            "utilisent l'historique partagé du projet."))
        self.positions = {}
        # Local draft history is independent of the project's single
        # AuthoringSession transaction committed by Apply.
        self._draft_history = [(deepcopy(self.document), {})]
        self._draft_index = 0
        self._selection = None
        self.graph = InteractiveSystemGraph(
            on_select=self._selected_graph, on_connect=self._port_connect,
            on_move=self._node_moved, on_status=self._status, parent=self)
        self.scene = self.graph.canvas  # Compatible with original Qt smoke.
        self.graph.setMinimumHeight(270)
        root.addWidget(self.graph, 2)
        self.tabs = QTabWidget()
        self.lists = {}
        for category, title in (
                ("resources", "Ressources"),
                ("producers", "Ateliers"),
                ("merchants", "Marchands"),
                ("quests", "Quêtes")):
            page = QWidget()
            layout = QVBoxLayout(page)
            view = QListWidget()
            view.setAccessibleName(title + " déclaratifs")
            layout.addWidget(view)
            row = QHBoxLayout()
            add = QPushButton("Ajouter")
            add.clicked.connect(lambda checked=False, k=category: self.add_item(k))
            remove = QPushButton("Supprimer")
            remove.clicked.connect(lambda checked=False, k=category: self.remove_item(k))
            edit = QPushButton("Modifier")
            edit.clicked.connect(lambda checked=False, k=category: self.edit_item(k))
            row.addWidget(add)
            row.addWidget(edit)
            row.addWidget(remove)
            layout.addLayout(row)
            self.tabs.addTab(page, title)
            self.lists[category] = view
        root.addWidget(self.tabs, 2)
        self.inspector = QPlainTextEdit()
        self.inspector.setObjectName("r55GraphInspector")
        self.inspector.setAccessibleName("Inspecteur du nœud ou lien sélectionné")
        self.inspector.setReadOnly(True)
        self.inspector.setMaximumHeight(115)
        root.addWidget(self.inspector)
        inspect_row = QHBoxLayout()
        self.connect_button = QPushButton("Relier des nœuds…")
        self.connect_button.setAccessibleName("Créer une liaison au clavier")
        self.connect_button.clicked.connect(self._choose_link)
        inspect_row.addWidget(self.connect_button)
        self.edit_selected = QPushButton("Modifier la sélection")
        self.edit_selected.clicked.connect(self._edit_selected)
        inspect_row.addWidget(self.edit_selected)
        self.unlink_selected = QPushButton("Supprimer la liaison")
        self.unlink_selected.clicked.connect(self._remove_selected_link)
        inspect_row.addWidget(self.unlink_selected)
        self.undo_button = QPushButton("Annuler (brouillon)")
        self.undo_button.clicked.connect(self.undo_draft)
        inspect_row.addWidget(self.undo_button)
        self.redo_button = QPushButton("Rétablir (brouillon)")
        self.redo_button.clicked.connect(self.redo_draft)
        inspect_row.addWidget(self.redo_button)
        root.addLayout(inspect_row)
        self.status = QLabel("Cliquez sur une sortie verte, puis sur une entrée bleue.")
        self.status.setAccessibleName("État des connexions du graphe")
        root.addWidget(self.status)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_draft)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.redo_shortcut.activated.connect(self.redo_draft)
        line = QHBoxLayout()
        line.addWidget(QLabel("Projection (ticks)"))
        self.ticks = QSpinBox()
        self.ticks.setRange(1, 256)
        self.ticks.setValue(16)
        line.addWidget(self.ticks)
        preview = QPushButton("Analyser les flux")
        preview.clicked.connect(self.preview)
        line.addWidget(preview)
        line.addStretch()
        root.addLayout(line)
        self.report = QPlainTextEdit()
        self.report.setAccessibleName("Analyse statique et prévision des flux")
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(135)
        root.addWidget(self.report)
        footer = QHBoxLayout()
        apply = QPushButton("Appliquer au projet (Undo/Redo)")
        apply.clicked.connect(self.apply)
        footer.addWidget(apply)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        root.addLayout(footer)
        self.refresh()

    def _resource_ids(self):
        return [r["id"] for r in self.document["resources"]]

    def _dialog(self, category, item=None):
        item = item or {}
        ids = self._resource_ids()
        editing = bool(item)
        title = "Modifier" if editing else "Ajouter"
        if category == "resources":
            return _new_form(title + " la ressource", [
                ("id", "Identifiant", "text", item.get("id", ""), None),
                ("initial", "Stock initial", "number", item.get("initial", 0), (0, 1_000_000)),
                ("capacity", "Capacité", "number", item.get("capacity", 100), (1, 1_000_000)),
            ], self)
        if not ids:
            QMessageBox.warning(self, "Dépendance", "Ajoutez d'abord une ressource.")
            return None
        if category == "producers":
            return _new_form(title + " l'atelier", [
                ("id", "Identifiant", "text", item.get("id", ""), None),
                ("inputs", "Entrées (id:qté,...)", "text",
                 _amount_text(item["inputs"]) if editing else ids[0] + ":1", None),
                ("outputs", "Sorties (id:qté,...)", "text",
                 _amount_text(item["outputs"]) if editing else ids[-1] + ":1", None),
                ("interval", "Tous les N ticks", "number",
                 item.get("interval", 2), (1, 256)),
            ], self)
        if category == "merchants":
            if not self.scenes:
                QMessageBox.warning(self, "Scène", "Créez d'abord une scène.")
                return None
            return _new_form(title + " le marchand", [
                ("id", "Identifiant", "text", item.get("id", ""), None),
                ("resource", "Ressource échangée", "choice",
                 item.get("resource", ids[0]), ids),
                ("scene", "Scène", "choice",
                 item.get("scene", self.scenes[0]), self.scenes),
                ("buy_price", "Prix d'achat joueur", "number",
                 item.get("buy_price", 5), (0, 1_000_000)),
                ("sell_price", "Prix de vente joueur", "number",
                 item.get("sell_price", 2), (0, 1_000_000)),
            ], self)
        return _new_form(title + " la livraison", [
            ("id", "Identifiant de quête", "text", item.get("id", ""), None),
            ("resource", "Ressource à livrer", "choice",
             item.get("resource", ids[0]), ids),
            ("quantity", "Quantité", "number",
             item.get("quantity", 1), (1, 1000)),
            ("flag", "Flag narratif une fois livré", "text",
             item.get("flag", ""), None),
        ], self)

    def _push_draft(self, document, positions=None, *, selected=None,
                    refresh=True):
        target_positions = deepcopy(self.positions if positions is None else positions)
        if (document, target_positions) == self._draft_history[self._draft_index]:
            return False
        self._draft_history = self._draft_history[:self._draft_index + 1]
        self._draft_history.append((deepcopy(document), target_positions))
        if len(self._draft_history) > 51:
            self._draft_history.pop(0)
        self._draft_index = len(self._draft_history) - 1
        self.document = deepcopy(document)
        self.positions = target_positions
        if refresh:
            self.refresh(selected=selected)
        self._update_history_buttons()
        return True

    def _update_history_buttons(self):
        self.undo_button.setEnabled(self._draft_index > 0)
        self.redo_button.setEnabled(self._draft_index + 1 < len(self._draft_history))

    def undo_draft(self):
        if self._draft_index <= 0:
            return False
        self._draft_index -= 1
        self.document, self.positions = deepcopy(self._draft_history[self._draft_index])
        self.refresh()
        self._update_history_buttons()
        self._status("Brouillon précédent restauré ; projet non modifié.")
        return True

    def redo_draft(self):
        if self._draft_index + 1 >= len(self._draft_history):
            return False
        self._draft_index += 1
        self.document, self.positions = deepcopy(self._draft_history[self._draft_index])
        self.refresh()
        self._update_history_buttons()
        self._status("Brouillon rétabli ; projet non modifié.")
        return True

    def _commit_row(self, category, result, index=None):
        try:
            if category == "producers":
                row = {
                    "id": result["id"],
                    "inputs": _parse_amount_text(
                        result["inputs"], set(self._resource_ids())),
                    "outputs": _parse_amount_text(
                        result["outputs"], set(self._resource_ids())),
                    "interval": result["interval"]}
            else:
                row = result
            candidate = deepcopy(self.document)
            items = candidate[category]
            if index is None:
                items.append(row)
            else:
                # Node identity changes cannot orphan ports and references.
                if row["id"] != items[index]["id"]:
                    raise ValueError(
                        "Renommer un nœud référencé exige une migration explicite.")
                items[index] = row
            if candidate["resources"]:
                validate_systems(candidate, self.scenes)
            elif any(candidate[key] for key in ("producers", "merchants", "quests")):
                raise ValueError("Le graphe requiert au moins une ressource.")
        except (ValueError, TypeError, KeyError) as exc:
            self._status("Graphe invalide : " + str(exc))
            QMessageBox.warning(self, "Graphe invalide", str(exc))
            return
        self._push_draft(candidate, selected=(category, row["id"]))
    def add_item(self, category):
        result = self._dialog(category)
        if result is not None:
            self._commit_row(category, result)

    def edit_item(self, category):
        index = self.lists[category].currentRow()
        if index < 0:
            return
        result = self._dialog(category, self.document[category][index])
        if result is not None:
            self._commit_row(category, result, index)

    def remove_item(self, category):
        index = self.lists[category].currentRow()
        if index < 0:
            return
        entry = self.document[category][index]
        if category == "resources":
            name = entry["id"]
            used = any(name in p["inputs"] or name in p["outputs"]
                       for p in self.document["producers"])
            used |= any(row["resource"] == name
                        for key in ("merchants", "quests")
                        for row in self.document[key])
            if used:
                self._status("Retirez d'abord les connexions de " + name)
                return
        candidate = deepcopy(self.document)
        del candidate[category][index]
        if candidate["resources"]:
            validate_systems(candidate, self.scenes)
        self._push_draft(candidate)

    def connect_nodes(self, source, target, quantity=1):
        """Headless-callable typed port edit used by mouse interaction."""
        candidate = edit_link(
            self.document, source, target,
            quantity=quantity, scenes=self.scenes)
        return self._push_draft(candidate, selected=target)

    def disconnect_nodes(self, source, target):
        candidate = edit_link(
            self.document, source, target, scenes=self.scenes, remove=True)
        return self._push_draft(candidate)

    def _choose_link(self):
        """Keyboard-accessible alternative to mouse ports, with typed IDs."""
        sources = [(kind, row["id"])
                   for kind in ("resources", "producers")
                   for row in self.document[kind]]
        destinations = [(kind, row["id"])
                        for kind in ("resources", "producers", "merchants", "quests")
                        for row in self.document[kind]]
        if not sources or not destinations:
            self._status("Ajoutez des nœuds avant de créer une liaison.")
            return
        labels = [kind + " / " + ident for kind, ident in sources]
        label, ok = QInputDialog.getItem(
            self, "Créer une liaison", "Source :", labels, 0, False)
        if not ok:
            return
        source = sources[labels.index(label)]
        targets = [(kind, ident) for kind, ident in destinations
                   if (source[0] == "resources" and kind in
                       ("producers", "merchants", "quests"))
                   or (source[0] == "producers" and kind == "resources")]
        if not targets:
            self._status("Aucune destination compatible.")
            return
        choices = [kind + " / " + ident for kind, ident in targets]
        label, ok = QInputDialog.getItem(
            self, "Créer une liaison", "Destination :", choices, 0, False)
        if not ok:
            return
        self._port_connect(source, targets[choices.index(label)])

    def _port_connect(self, source, target):
        quantity = 1
        if source[0] == "producers" or target[0] == "producers":
            quantity, accepted = QInputDialog.getInt(
                self, "Quantité du port", "Quantité par cycle :", 1, 1, 1000)
            if not accepted:
                self._status("Connexion annulée.")
                return
        try:
            self.connect_nodes(source, target, quantity)
        except ValueError as exc:
            self._status("Connexion refusée : " + str(exc))
        else:
            self._status(source[1] + " → " + target[1] + " connecté.")

    def _node_moved(self, key, old, new):
        if old == new:
            return
        positions = deepcopy(self.positions)
        positions[key] = new
        self._push_draft(self.document, positions, refresh=False)
        self._status("Nœud déplacé : " + key[1])

    def move_node(self, key, x, y):
        """Keyboard, mouse and QTest-compatible single layout command."""
        if key not in self.graph.nodes:
            raise ValueError("Nœud graphique introuvable")
        old = self.graph.nodes[key].pos()
        self.graph.nodes[key].setPos(float(x), float(y))
        self._node_moved(key, (old.x(), old.y()), (float(x), float(y)))

    def _selected_graph(self, selection):
        self._selection = selection
        if selection is None:
            self.inspector.setPlainText("Sélectionner un nœud ou une liaison.")
        elif selection[0] == "node":
            category, ident = selection[1]
            item = next((row for row in self.document[category]
                         if row["id"] == ident), None)
            if item is not None:
                index = self.document[category].index(item)
                self.tabs.setCurrentIndex(
                    ("resources", "producers", "merchants", "quests").index(category))
                self.lists[category].setCurrentRow(index)
                lines = [f"{category} · {ident}"]
                lines.extend(f"{key}: {value}" for key, value
                             in sorted(item.items()) if key != "id")
                self.inspector.setPlainText("\n".join(lines))
        else:
            source, target = selection[1]
            self.inspector.setPlainText(
                "Liaison : " + source[1] + " → " + target[1] +
                "\nSupprimer la liaison (ports recette obligatoires).")
        self.edit_selected.setEnabled(
            selection is not None and selection[0] == "node")
        self.unlink_selected.setEnabled(
            selection is not None and selection[0] == "link")

    def _edit_selected(self):
        if self._selection and self._selection[0] == "node":
            category, _ = self._selection[1]
            self.edit_item(category)

    def _remove_selected_link(self):
        if not self._selection or self._selection[0] != "link":
            return
        source, target = self._selection[1]
        try:
            self.disconnect_nodes(source, target)
        except ValueError as exc:
            self._status("Suppression refusée : " + str(exc))
        else:
            self._status("Liaison supprimée.")

    def _status(self, message):
        self.status.setText(message)

    def refresh(self, *, selected=None):
        self._selection = None
        for kind, view in self.lists.items():
            view.clear()
            for row in self.document[kind]:
                if kind == "resources":
                    title = f'{row["id"]}: {row["initial"]} / {row["capacity"]}'
                elif kind == "producers":
                    title = (f'{row["id"]}: {row["inputs"]} → {row["outputs"]}'
                             f' / {row["interval"]} ticks')
                elif kind == "merchants":
                    title = f'{row["id"]}: {row["resource"]} @ {row["scene"]}'
                else:
                    title = f'{row["id"]}: {row["quantity"]} {row["resource"]} → {row["flag"]}'
                view.addItem(title)
        self.graph.rebuild(self.document, self.positions, selected)
        self._selected_graph(None)
        if selected is not None:
            self._selected_graph(("node", selected))
        self._update_history_buttons()

    def preview(self):
        try:
            result = forecast_system_design(
                self.document, self.scenes, ticks=self.ticks.value())
        except (ValueError, TypeError) as exc:
            self.report.setPlainText("Graph invalid: " + str(exc))
            return
        rows = [
            f'Ticks : {result["ticks"]}',
            *[f'{key}: {result["before"][key]} → {result["after"][key]} '
              f'({result["delta"][key]:+d})'
              for key in sorted(result["delta"])],
            "Chaînes en impasse (stocks insuffisants): "
            + (", ".join(result["stalled"]) or "aucune"),
        ]
        self.report.setPlainText("\n".join(rows))

    def apply(self):
        try:
            preview = preview_system_design(
                self.session, self.document, expected_revision=self.source_revision)
            apply_system_design(self.session, preview)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Validation ou révision R55", str(exc))
            return
        self.accept()
