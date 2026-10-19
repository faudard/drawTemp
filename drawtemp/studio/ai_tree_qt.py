"""R37.C — interactive Qt Behavior Tree workbench (R1 authoring, no runtime fork).

A hierarchical visual tree editor with bounded add/edit/reorder/delete actions,
transactional Apply/Undo and a read-only step debugger. No Qt dependency in
the headless evaluator or game session.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.ai_decision import new_blackboard
from drawtemp.sdk.behavior_tree import (
    BehaviorTreeDebugger, evaluate_behavior_tree,
)
from drawtemp.studio.ai_tree_authoring import BehaviorTreeDraft
from sporebound.advanced_ai import EXTENSION


class BehaviorTreeDialog(QDialog):
    updated = Signal()

    def __init__(self, session, *, game_session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.game_session = game_session
        self.draft = None
        self.debugger = None
        self.last_report = None
        self.setObjectName("r37-behavior-dialog")
        self.setWindowTitle("DrawTemp · Advanced AI Studio R37.C")
        self.resize(1000, 660)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Agent"))
        self.agent = QComboBox()
        self.agent.setObjectName("r37-agent")
        self.agent.setAccessibleName("Acteur IA sélectionné")
        top.addWidget(self.agent)
        self.reload_button = QPushButton("Recharger")
        self.reload_button.clicked.connect(self.refresh)
        top.addWidget(self.reload_button)
        root.addLayout(top)
        toolbar = QHBoxLayout()
        diagnostics_toolbar = QHBoxLayout()
        self.buttons = {}
        for key, label, callback in (
            ("sequence", "+ Séquence", lambda: self.add_node("sequence")),
            ("selector", "+ Sélecteur", lambda: self.add_node("selector")),
            ("condition", "+ Condition", lambda: self.add_node("condition")),
            ("action", "+ Action", lambda: self.add_node("action")),
            ("invert", "Inverser", self.wrap_inverter),
            ("edit", "Modifier feuille", self.edit_leaf),
            ("delete", "Supprimer", self.remove_node),
            ("up", "Monter", lambda: self.reorder(-1)),
            ("down", "Descendre", lambda: self.reorder(1)),
            ("preview", "Diagnostiquer", self.preview),
            ("step", "Pas-à-pas", self.step),
            ("apply", "Appliquer", self.apply),
            ("undo", "Annuler", self.undo),
            ("redo", "Rétablir", self.redo),
        ):
            button = QPushButton(label)
            button.setObjectName("r37-" + key)
            button.clicked.connect(callback)
            (toolbar if key in ("sequence", "selector", "condition",
                                "action", "invert", "edit", "delete",
                                "up", "down") else diagnostics_toolbar).addWidget(button)
            self.buttons[key] = button
        root.addLayout(toolbar)
        root.addLayout(diagnostics_toolbar)

        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)
        self.tree = QTreeWidget()
        self.tree.setObjectName("r37-tree")
        self.tree.setAccessibleName("Arbre de comportement visuel")
        self.tree.setHeaderLabels(["Nœud", "Type", "Description"])
        split.addWidget(self.tree)
        right = QWidget()
        side = QVBoxLayout(right)
        props = QFormLayout()
        self.fact = QLineEdit("same_scene")
        self.fact.setObjectName("r37-fact")
        self.expected = QLineEdit("true")
        self.expected.setObjectName("r37-expected")
        self.action = QLineEdit("wait")
        self.action.setObjectName("r37-action")
        props.addRow("Fait", self.fact)
        props.addRow("Égal à (JSON)", self.expected)
        props.addRow("Action (identifiant)", self.action)
        side.addLayout(props)
        side.addWidget(QLabel("Contexte de diagnostic (JSON, aucun effet sur le jeu)"))
        self.context = QPlainTextEdit()
        self.context.setObjectName("r37-context")
        self.context.setMaximumHeight(112)
        side.addWidget(self.context)
        side.addWidget(QLabel("Trace / score / nœud sélectionné"))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r37-diagnostics")
        self.diagnostics.setReadOnly(True)
        side.addWidget(self.diagnostics, 1)
        split.addWidget(right)
        split.setSizes([620, 380])
        self.agent.currentIndexChanged.connect(self.load_actor)
        self.tree.currentItemChanged.connect(self._selected_changed)
        self.refresh()

    def _agents(self):
        project = self.session.snapshot().to_dict()["project"]
        return project.get("extensions", {}).get(EXTENSION, {}).get(
            "data", {}).get("agents", [])

    def refresh(self):
        previous = self.agent.currentData()
        self.agent.blockSignals(True)
        self.agent.clear()
        for row in self._agents():
            self.agent.addItem(row["id"] + " (" + row["mode"] + ")",
                               row["id"])
        index = self.agent.findData(previous)
        if index >= 0:
            self.agent.setCurrentIndex(index)
        self.agent.blockSignals(False)
        self.load_actor()

    def load_actor(self, *_):
        actor = self.agent.currentData()
        self.debugger = None
        self.last_report = None
        self.draft = BehaviorTreeDraft(self.session, actor) if actor else None
        self.render_tree()
        if self.draft:
            row = next(a for a in self._agents() if a["id"] == actor)
            context = {"schema_version": 1, "actor_id": actor,
                       "mode": row["mode"], "tick": 0, "seed": 1,
                       "facts": {"same_scene": True}}
            self.context.setPlainText(json.dumps(context, indent=2))
        else:
            self.context.clear()

    def _current_id(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def _node(self, identifier):
        if self.draft is None:
            raise ValueError("Select an authored R37 agent")
        return next(n for n in self.draft.tree["nodes"] if n["id"] == identifier)

    def render_tree(self, select_id=None):
        self.tree.clear()
        if self.draft is None:
            return
        by_id = {n["id"]: n for n in self.draft.tree["nodes"]}
        def add(parent, identifier):
            node = by_id[identifier]
            detail = (node.get("action", "") or node.get("fact", "")
                      or node.get("op", ""))
            item = QTreeWidgetItem([identifier, node["kind"], detail])
            item.setData(0, Qt.UserRole, identifier)
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in (node.get("children", []) +
                          ([node["child"]] if "child" in node else [])):
                add(item, child)
            item.setExpanded(True)
        add(None, self.draft.tree["root"])
        matches = self.tree.findItems(
            select_id or self.draft.tree["root"],
            Qt.MatchExactly | Qt.MatchRecursive, 0)
        if matches:
            self.tree.setCurrentItem(matches[0])

    def _selected_changed(self, current, previous):
        if current is None or self.draft is None:
            return
        node = self._node(current.data(0, Qt.UserRole))
        if node["kind"] == "condition":
            self.fact.setText(node["fact"])
            self.expected.setText(json.dumps(node["equals"]))
        elif node["kind"] == "action":
            self.action.setText(node["action"])

    def _perform(self, callback, *, selection=None):
        if self.draft is None:
            return
        try:
            node_id = callback()
            self.debugger = None
            self.last_report = None
            self.render_tree(select_id=node_id or selection)
            self.diagnostics.setPlainText("Brouillon validé ; Appliquer pour enregistrer.")
        except (ValueError, KeyError, TypeError) as exc:
            self.diagnostics.setPlainText("Modification refusée : " + str(exc))

    def _expected_value(self):
        return json.loads(self.expected.text())

    def add_node(self, kind):
        parent = self._current_id()
        if parent is None:
            return
        self._perform(lambda: self.draft.add(
            parent, kind, fact=self.fact.text(),
            equals=self._expected_value(), action=self.action.text()))

    def wrap_inverter(self):
        node_id = self._current_id()
        if node_id is not None:
            self._perform(lambda: self.draft.wrap_inverter(node_id))

    def edit_leaf(self):
        node_id = self._current_id()
        if node_id is None:
            return
        def change():
            node = self._node(node_id)
            if node["kind"] == "action":
                self.draft.edit(node_id, action=self.action.text())
            elif node["kind"] == "condition":
                self.draft.edit(node_id, fact=self.fact.text(),
                                equals=self._expected_value())
            else:
                raise ValueError("Select an action or condition")
            return node_id
        self._perform(change)

    def remove_node(self):
        node_id = self._current_id()
        if node_id is not None:
            self._perform(lambda: self.draft.remove(node_id))

    def reorder(self, offset):
        node_id = self._current_id()
        if node_id is not None:
            self._perform(lambda: self.draft.reorder(node_id, offset),
                          selection=node_id)

    def preview(self):
        if self.draft is None:
            return
        try:
            tree = self.draft.document()
            if self.game_session is not None:
                context = self.game_session.ai_decision_context(
                    self.draft.actor_id)
                blackboard = self.game_session.ai_state(self.draft.actor_id)
            else:
                context = json.loads(self.context.toPlainText())
                blackboard = new_blackboard(self.draft.actor_id)
            report = evaluate_behavior_tree(context, blackboard, tree)
            self.last_report = report
            self.debugger = BehaviorTreeDebugger(report)
            self.diagnostics.setPlainText(json.dumps(
                report, ensure_ascii=False, indent=2))
        except (ValueError, KeyError, TypeError) as exc:
            self.debugger = None
            self.last_report = None
            self.diagnostics.setPlainText("Diagnostic refusé : " + str(exc))

    def step(self):
        if self.debugger is None:
            self.preview()
        if self.debugger is None:
            return
        event = self.debugger.step()
        if event is not None:
            self.render_tree(select_id=event["node_id"])
            self.diagnostics.setPlainText(json.dumps({
                "event": event, "cursor": self.debugger.state()},
                ensure_ascii=False, indent=2))

    def apply(self):
        if self.draft is None:
            return
        try:
            self.draft.apply()
            self.updated.emit()
            self.refresh()
            self.diagnostics.setPlainText("Arbre appliqué au projet (1 transaction).")
        except (ValueError, TypeError) as exc:
            self.diagnostics.setPlainText("Application refusée : " + str(exc))

    def undo(self):
        try:
            self.session.undo()
            self.updated.emit()
            self.refresh()
        except ValueError as exc:
            self.diagnostics.setPlainText(str(exc))

    def redo(self):
        try:
            self.session.redo()
            self.updated.emit()
            self.refresh()
        except ValueError as exc:
            self.diagnostics.setPlainText(str(exc))
