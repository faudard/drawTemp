"""R55.B native Qt graph editor over the canonical AuthoringSession.

Small, opt-in editor: no raw JSON entry or direct project writes. Lists and
graph are projections of one detached document; apply is one undoable commit.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
    QWidget,
)

from drawtemp.studio.system_design_authoring import (
    apply_system_design, forecast_system_design, preview_system_design)
from sporebound.system_design import EXTENSION


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


class SystemDesignerDialog(QDialog):
    """Visual overview + typed authoring with transactional Apply/Undo."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        snap = session.snapshot().to_dict()
        self.source_revision = snap["revision"]
        self.scenes = sorted(
            {row["id"] for row in snap["content"]["missions"]}
            | set(snap["project"].get("exploration", {})))
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
        self.scene = QGraphicsScene(self)
        graph = QGraphicsView(self.scene)
        graph.setAccessibleName("Graphe des ressources, ateliers et contrats")
        graph.setMinimumHeight(270)
        root.addWidget(graph, 2)
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
            row.addWidget(add)
            row.addWidget(remove)
            layout.addLayout(row)
            self.tabs.addTab(page, title)
            self.lists[category] = view
        root.addWidget(self.tabs, 2)
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

    def _dialog(self, category):
        ids = self._resource_ids()
        if category == "resources":
            return _new_form("Nouvelle ressource", [
                ("id", "Identifiant", "text", "", None),
                ("initial", "Stock initial", "number", 0, (0, 1_000_000)),
                ("capacity", "Capacité", "number", 100, (1, 1_000_000)),
            ], self)
        if not ids:
            QMessageBox.warning(self, "Dépendance", "Ajoutez d'abord une ressource.")
            return None
        if category == "producers":
            return _new_form("Nouvel atelier", [
                ("id", "Identifiant", "text", "", None),
                ("source", "Consomme", "choice", ids[0], ids),
                ("input_quantity", "Quantité consommée", "number", 1, (1, 1000)),
                ("target", "Produit", "choice", ids[-1], ids),
                ("output_quantity", "Quantité produite", "number", 1, (1, 1000)),
                ("interval", "Tous les N ticks", "number", 2, (1, 256)),
            ], self)
        if category == "merchants":
            if not self.scenes:
                QMessageBox.warning(self, "Scène", "Créez d'abord une scène.")
                return None
            return _new_form("Nouveau marchand", [
                ("id", "Identifiant", "text", "", None),
                ("resource", "Ressource échangée", "choice", ids[0], ids),
                ("scene", "Scène", "choice", self.scenes[0], self.scenes),
                ("buy_price", "Prix d'achat joueur", "number", 5, (0, 1_000_000)),
                ("sell_price", "Prix de vente joueur", "number", 2, (0, 1_000_000)),
            ], self)
        return _new_form("Nouveau contrat de livraison", [
            ("id", "Identifiant de quête", "text", "", None),
            ("resource", "Ressource à livrer", "choice", ids[0], ids),
            ("quantity", "Quantité", "number", 1, (1, 1000)),
            ("flag", "Flag narratif une fois livré", "text", "", None),
        ], self)

    def add_item(self, category):
        result = self._dialog(category)
        if result is None:
            return
        if category == "producers":
            row = {"id": result["id"],
                   "inputs": {result["source"]: result["input_quantity"]},
                   "outputs": {result["target"]: result["output_quantity"]},
                   "interval": result["interval"]}
        else:
            row = result
        if not row["id"] or any(item["id"] == row["id"]
                                for item in self.document[category]):
            QMessageBox.warning(self, "Identifiant", "Identifiant vide ou déjà utilisé.")
            return
        if category == "resources" and row["initial"] > row["capacity"]:
            QMessageBox.warning(self, "Capacité", "Stock initial supérieur à la capacité.")
            return
        if category == "producers" and result["source"] == result["target"]:
            QMessageBox.warning(self, "Cycle", "Un atelier ne peut boucler sur sa ressource.")
            return
        if category == "merchants" and row["sell_price"] > row["buy_price"]:
            QMessageBox.warning(self, "Prix", "Prix de vente supérieur au prix d'achat.")
            return
        self.document[category].append(row)
        self.refresh()

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
                QMessageBox.warning(
                    self, "Référence active",
                    "Supprimez d'abord les producteurs/marchands/quêtes liés.")
                return
        del self.document[category][index]
        self.refresh()

    def refresh(self):
        self.scene.clear()
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
        positions = {}
        groups = [
            ("resources", 30),
            ("producers", 350),
            ("merchants", 670),
            ("quests", 670),
        ]
        for category, x in groups:
            for i, row in enumerate(self.document[category]):
                y = 18 + i * 54 + (280 if category == "quests" else 0)
                self.scene.addRect(x, y, 238, 38, QPen(QColor("#64748b")))
                text = self.scene.addText(row["id"] + " (" + category + ")")
                text.setPos(x + 8, y + 6)
                positions[(category, row["id"])] = (x, y)
        for row in self.document["producers"]:
            target = positions[("producers", row["id"])]
            for rid in row["inputs"]:
                src = positions[("resources", rid)]
                self.scene.addLine(src[0] + 238, src[1] + 18,
                                   target[0], target[1] + 18,
                                   QPen(QColor("#1e88e5"), 2))
            for rid in row["outputs"]:
                # Back-edges are intentional resource flows, not script cycles.
                dest = positions[("resources", rid)]
                self.scene.addLine(target[0], target[1] + 30,
                                   dest[0] + 238, dest[1] + 30,
                                   QPen(QColor("#16a34a"), 2))
        for category in ("merchants", "quests"):
            for row in self.document[category]:
                src = positions[("resources", row["resource"])]
                dest = positions[(category, row["id"])]
                self.scene.addLine(src[0] + 238, src[1] + 18,
                                   dest[0], dest[1] + 18,
                                   QPen(QColor("#ca8a04"), 2))
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

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
