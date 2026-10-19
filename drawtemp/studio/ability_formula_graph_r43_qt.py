"""R43.B2 Qt expression-tree editing; projections only, no gameplay engine."""
from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.ability_contracts import AbilityError, evaluate_formula, STATS
from drawtemp.studio.ability_formula_graph_r43 import (
    CASES, DEFAULT_STATS, OPERATORS, describe_nodes, node_at, replace_node,
)


class FormulaGraphDialog(QDialog):
    """Structural AST editor that returns an independent validated tree.

    Replacing a node creates no reference edges; all changes are provisional
    until the parent AbilityDraft submits a canonical R1 preview/apply.
    """

    def __init__(self, formula, parent=None):
        super().__init__(parent)
        self.setObjectName("r43-formula-graph")
        self.setWindowTitle("R43.B2 — Graphe de formule typé")
        self.resize(940, 620)
        self.formula = deepcopy(formula)
        self.result_formula = None
        self._loading = False

        frame = QVBoxLayout(self)
        note = QLabel(
            "Arbre d'expression R43.A, maximum 31 nœuds et profondeur 5. "
            "Aucun script ni lien cyclique; conversion uniquement explicite."
        )
        note.setWordWrap(True)
        frame.addWidget(note)
        split = QSplitter()
        frame.addWidget(split, 1)

        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Nœuds de formule et ports structurés")
        self.tree.setHeaderLabels(["Opérateur / valeur", "Chemin canonique"])
        self.tree.currentItemChanged.connect(self._selected)
        split.addWidget(self.tree)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        split.addWidget(detail)
        split.setSizes([480, 460])
        form = QFormLayout()
        self.operator = QComboBox()
        self.operator.setAccessibleName("Opérateur")
        self.operator.addItems(OPERATORS)
        form.addRow("Opérateur", self.operator)
        self.constant = QSpinBox()
        self.constant.setRange(0, 10000)
        self.constant.setAccessibleName("Constante entière")
        form.addRow("Constante", self.constant)
        self.stat = QComboBox()
        self.stat.setAccessibleName("Statistique")
        self.stat.addItems(sorted(STATS))
        form.addRow("Stat", self.stat)
        self.amount = QSpinBox()
        self.amount.setRange(0, 400)
        self.amount.setAccessibleName("Pourcentage entier")
        form.addRow("Pourcentage", self.amount)
        detail_layout.addLayout(form)

        self.replace_button = QPushButton("Remplacer ce nœud / définir ses ports")
        self.replace_button.clicked.connect(self.replace_selected)
        detail_layout.addWidget(self.replace_button)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setAccessibleName("Résultat de formule par profils")
        self.diagnostics.setReadOnly(True)
        detail_layout.addWidget(self.diagnostics, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        frame.addWidget(buttons)
        self.buttons = buttons

        self._render(())

    def _render(self, selection):
        self._loading = True
        self.tree.clear()
        items = {(): self.tree.invisibleRootItem()}
        for row in describe_nodes(self.formula):
            key = row["path"]
            parent = items[key[:-1]] if key else items[()]
            item = QTreeWidgetItem(parent, [row["label"], "/".join(key) or "root"])
            item.setData(0, Qt.UserRole, key)
            items[key] = item
            if key == selection:
                self.tree.setCurrentItem(item)
        self.tree.expandAll()
        if self.tree.currentItem() is None:
            self.tree.setCurrentItem(items[()])
        self._loading = False
        self._selected(self.tree.currentItem(), None)
        self._update_report()

    def _selected(self, item, _previous):
        if self._loading or item is None:
            return
        path = item.data(0, Qt.UserRole)
        row = node_at(self.formula, tuple(path))
        self._loading = True
        self.operator.setCurrentText(row["op"])
        if "value" in row:
            self.constant.setValue(row["value"])
        if "name" in row:
            self.stat.setCurrentText(row["name"])
        if "amount" in row:
            self.amount.setValue(row["amount"])
        self._loading = False

    def _update_report(self):
        lines = [
            "Formule déterministe : aucune mutation de Content/Player.",
            f"Nœuds : {len(describe_nodes(self.formula))} / 31",
        ]
        for label, stats in CASES:
            lines.append(
                f"{label}: {evaluate_formula(self.formula, stats)} "
                f"(valeur brute; statistiques {stats})")
        self.diagnostics.setPlainText("\n".join(lines))

    def replace_selected(self):
        item = self.tree.currentItem()
        if item is None:
            return False
        path = tuple(item.data(0, Qt.UserRole))
        try:
            next_formula = replace_node(
                self.formula, path, op=self.operator.currentText(),
                value=self.constant.value(), name=self.stat.currentText(),
                amount=self.amount.value())
            self.formula = next_formula
            self._render(path)
            return True
        except (AbilityError, KeyError, TypeError, ValueError) as exc:
            self.diagnostics.setPlainText(
                "Changement refusé : " + getattr(exc, "code", "invalid") +
                " — " + str(exc))
            return False

    def _accept(self):
        try:
            evaluate_formula(self.formula, DEFAULT_STATS)
        except AbilityError as exc:
            self.diagnostics.setPlainText("Validation : " + str(exc))
            return
        self.result_formula = deepcopy(self.formula)
        self.accept()


__all__ = ["FormulaGraphDialog"]
