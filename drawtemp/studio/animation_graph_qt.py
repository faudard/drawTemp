"""R36.A Qt Animation Controller panel over R28 assets and R1 history.

Opt-in visual state/transition editing. No JSON text entry and no second runtime.
The panel previews resolved sprite IDs; GPU/goldens are a separate R36.C gate.
"""
from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
from sporebound.animation_graph import AnimationStateController, AnimationGraphError
from sporebound.assets import AssetRegistry


class AnimationControllerPanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.editor = AnimationControllerAuthoring(session)
        self._revision = -1
        self._plan = None
        self.draft = None
        self.setObjectName("r36-animation-controller")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "R36.A — États et transitions d'animation (registre R28 ; visuel seul)"))
        controller_row = QHBoxLayout()
        self.saved = QComboBox()
        self.saved.currentIndexChanged.connect(self.load_selected)
        controller_row.addWidget(self.saved)
        new_button = QPushButton("Nouveau")
        new_button.clicked.connect(self.new_draft)
        controller_row.addWidget(new_button)
        layout.addLayout(controller_row)
        self.identifier = QLineEdit("hero_controller")
        self.identifier.textChanged.connect(self._invalidate)
        layout.addWidget(QLabel("Identifiant du contrôleur"))
        layout.addWidget(self.identifier)
        layout.addWidget(QLabel("États : ID et animation déjà enregistrée"))
        self.states = QListWidget()
        layout.addWidget(self.states, 1)
        state_row = QHBoxLayout()
        self.state_id = QLineEdit()
        self.state_id.setPlaceholderText("idle, attack, dodge, death...")
        self.animation = QComboBox()
        state_row.addWidget(self.state_id)
        state_row.addWidget(self.animation)
        state_add = QPushButton("+ État")
        state_add.clicked.connect(self.add_state)
        state_row.addWidget(state_add)
        layout.addLayout(state_row)
        state_remove = QPushButton("Supprimer l'état sélectionné")
        state_remove.clicked.connect(self.remove_state)
        layout.addWidget(state_remove)
        layout.addWidget(QLabel("Transitions ordonnées par priorité (0–100)"))
        self.edges = QListWidget()
        layout.addWidget(self.edges, 1)
        edge_form = QFormLayout()
        self.source = QComboBox()
        self.target = QComboBox()
        self.event = QLineEdit("attack")
        self.priority = QSpinBox()
        self.priority.setRange(0, 100)
        edge_form.addRow("Depuis", self.source)
        edge_form.addRow("Vers", self.target)
        edge_form.addRow("Événement commité", self.event)
        edge_form.addRow("Priorité", self.priority)
        layout.addLayout(edge_form)
        edge_row = QHBoxLayout()
        plus = QPushButton("+ Transition")
        plus.clicked.connect(self.add_transition)
        minus = QPushButton("− Transition")
        minus.clicked.connect(self.remove_transition)
        edge_row.addWidget(plus)
        edge_row.addWidget(minus)
        layout.addLayout(edge_row)
        actions = QHBoxLayout()
        preview = QPushButton("Prévisualiser / vérifier")
        preview.clicked.connect(self.preview)
        actions.addWidget(preview)
        self.apply_button = QPushButton("Appliquer (Undo/Redo R1)")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        actions.addWidget(self.apply_button)
        delete = QPushButton("Supprimer")
        delete.clicked.connect(self.delete)
        actions.addWidget(delete)
        layout.addLayout(actions)
        sample_form = QFormLayout()
        self.tick = QSpinBox()
        self.tick.setRange(0, 1000000)
        sample_form.addRow("Tick simulation (échantillon)", self.tick)
        inspect = QPushButton("Échantillonner le sprite (sans rendu)")
        inspect.clicked.connect(self.sample)
        sample_form.addRow(inspect)
        layout.addLayout(sample_form)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(170)
        self.report.setAccessibleName("Diagnostics animation controller R36")
        layout.addWidget(self.report)
        self.refresh()

    def _invalidate(self, *_):
        self._plan = None
        self.apply_button.setEnabled(False)

    def _asset_registry(self):
        project = self.editor.session.snapshot().to_dict()["project"]
        return AssetRegistry(project.get("assets") or None)

    def _show(self, value):
        self.report.setPlainText(
            json.dumps(value, ensure_ascii=False, indent=2, default=str)
            if isinstance(value, (dict, list)) else str(value))

    def refresh(self):
        self._revision = self.editor.session.revision
        selected = self.saved.currentData()
        self.saved.blockSignals(True)
        self.saved.clear()
        for row in self.editor.controllers():
            self.saved.addItem(row["id"], row["id"])
        self.saved.blockSignals(False)
        self.animation.clear()
        for row in self._asset_registry().to_dict()["entries"]:
            if row["kind"] == "animation":
                self.animation.addItem(row["id"], row["id"])
        index = self.saved.findData(selected)
        if index >= 0:
            self.saved.setCurrentIndex(index)
        self.load_selected()

    def new_draft(self):
        self.draft = {"schema_version": 1, "id": "hero_controller",
                      "initial": "", "states": [], "transitions": []}
        self.identifier.setText(self.draft["id"])
        self._draw()

    def load_selected(self, *_):
        key = self.saved.currentData()
        item = next((row for row in self.editor.controllers()
                     if row["id"] == key), None)
        if item is None:
            self.new_draft()
        else:
            self.draft = deepcopy(item)
            self.identifier.setText(item["id"])
            self._draw()
        self._revision = self.editor.session.revision

    def _draw(self):
        self._invalidate()
        self.states.clear()
        self.edges.clear()
        self.source.clear()
        self.target.clear()
        if self.draft is None:
            return
        for state in self.draft["states"]:
            sid = state["id"]
            self.states.addItem(sid + " → " + state["animation"])
            self.source.addItem(sid, sid)
            self.target.addItem(sid, sid)
        for edge in self.draft["transitions"]:
            self.edges.addItem(
                f'{edge["source"]} → {edge["target"]} '
                f'[{edge["on"]}; priorité {edge["priority"]}]')
        self._show({"initial": self.draft["initial"],
                    "states": len(self.draft["states"]),
                    "transitions": len(self.draft["transitions"])})

    def add_state(self):
        sid, animation = self.state_id.text().strip(), self.animation.currentData()
        if not sid or not animation or sid in {s["id"] for s in self.draft["states"]}:
            self._show("ID d'état manquant/déjà utilisé ou animation R28 absente.")
            return
        self.draft["states"].append({"id": sid, "animation": animation})
        if not self.draft["initial"]:
            self.draft["initial"] = sid
        self._draw()

    def remove_state(self):
        index = self.states.currentRow()
        if index < 0:
            return
        sid = self.draft["states"].pop(index)["id"]
        self.draft["transitions"] = [
            edge for edge in self.draft["transitions"]
            if sid not in (edge["source"], edge["target"])]
        if self.draft["initial"] == sid:
            self.draft["initial"] = (
                self.draft["states"][0]["id"] if self.draft["states"] else "")
        self._draw()

    def add_transition(self):
        a, b, event = self.source.currentData(), self.target.currentData(), self.event.text().strip()
        if not a or not b or not event:
            self._show("Sélectionnez deux états et un événement.")
            return
        self.draft["transitions"].append({
            "source": a, "target": b, "on": event,
            "priority": self.priority.value()})
        self._draw()

    def remove_transition(self):
        index = self.edges.currentRow()
        if index >= 0:
            self.draft["transitions"].pop(index)
            self._draw()

    def _document(self):
        candidate = deepcopy(self.draft)
        candidate["id"] = self.identifier.text().strip()
        return candidate

    def preview(self):
        try:
            self._plan = self.editor.preview(
                self._document(), expected_revision=self._revision)
            self.apply_button.setEnabled(True)
            self._show({"status": "Plan valide, non appliqué",
                        "controller": self._document()["id"],
                        "revision": self._revision})
        except (ValueError, TypeError) as exc:
            self._invalidate()
            self._show("Prévisualisation refusée : " + str(exc))

    def apply(self):
        if self._plan is None:
            return
        try:
            self.editor.apply(self._plan)
            self.refresh()
            self.updated.emit()
        except (ValueError, TypeError) as exc:
            self._invalidate()
            self._show("Application refusée : " + str(exc))

    def delete(self):
        key = self.saved.currentData()
        if not key:
            return
        try:
            plan = self.editor.preview_remove(key, expected_revision=self._revision)
            self.editor.apply(plan)
            self.refresh()
            self.updated.emit()
        except (ValueError, TypeError) as exc:
            self._show("Suppression refusée : " + str(exc))

    def sample(self):
        try:
            controller = AnimationStateController(
                self._document(), self._asset_registry())
            self._show(controller.sample(self.tick.value()))
        except (ValueError, TypeError) as exc:
            self._show("Échantillon refusé : " + str(exc))
