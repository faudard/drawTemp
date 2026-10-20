"""R36.B2 Qt visual-cue marker panel; canonical R1 undo/redo, no script entry."""
from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring
from sporebound.animation_graph import controllers_from_project
from sporebound.animation_timeline import CUES, cues_crossed
from sporebound.assets import AssetRegistry


class AnimationTimelinePanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.editor = AnimationTimelineAuthoring(session)
        self.draft = None
        self._revision = -1
        self._plan = None
        self.setObjectName("r36-visual-timeline")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "R36.B2 — Marqueurs purement visuels, jamais des dégâts ni des hitboxes"))
        form = QFormLayout()
        self.controllers = QComboBox()
        self.controllers.currentIndexChanged.connect(self.load_controller)
        form.addRow("Contrôleur R36", self.controllers)
        self.identifier = QLineEdit()
        self.identifier.textChanged.connect(self._invalidate)
        form.addRow("ID timeline", self.identifier)
        self.states = QComboBox()
        self.states.currentIndexChanged.connect(self._redraw_markers)
        form.addRow("État d'animation", self.states)
        layout.addLayout(form)

        self.markers = QListWidget()
        layout.addWidget(self.markers, 1)
        row = QHBoxLayout()
        self.marker_id = QLineEdit()
        self.marker_id.setPlaceholderText("spark_start")
        self.at_ms = QSpinBox()
        self.at_ms.setRange(0, 1000000)
        self.cue = QComboBox()
        for kind in sorted(CUES):
            self.cue.addItem(kind, kind)
        row.addWidget(self.marker_id)
        row.addWidget(self.at_ms)
        row.addWidget(self.cue)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        add = QPushButton("Ajouter un marqueur")
        add.clicked.connect(self.add_marker)
        remove = QPushButton("Retirer le marqueur sélectionné")
        remove.clicked.connect(self.remove_marker)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)

        sample_form = QFormLayout()
        self.from_tick = QSpinBox()
        self.from_tick.setRange(-1, 1000000)
        self.from_tick.setValue(-1)
        self.to_tick = QSpinBox()
        self.to_tick.setRange(0, 1000000)
        self.to_tick.setValue(60)
        sample_form.addRow("Tick précédent", self.from_tick)
        sample_form.addRow("Tick commité", self.to_tick)
        layout.addLayout(sample_form)
        actions = QHBoxLayout()
        sample = QPushButton("Prévisualiser les marqueurs")
        sample.clicked.connect(self.sample)
        preview = QPushButton("Vérifier / planifier")
        preview.clicked.connect(self.preview)
        self.apply_button = QPushButton("Appliquer (Undo/Redo R1)")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        self.delete_button = QPushButton("Supprimer timeline")
        self.delete_button.clicked.connect(self.delete_timeline)
        actions.addWidget(sample)
        actions.addWidget(preview)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(140)
        self.report.setAccessibleName("Diagnostics marqueurs visuels R36")
        layout.addWidget(self.report)
        self.refresh()

    def _show(self, value):
        self.report.setPlainText(
            json.dumps(value, ensure_ascii=False, indent=2)
            if isinstance(value, (dict, list)) else str(value))

    def _invalidate(self, *_):
        self._plan = None
        self.apply_button.setEnabled(False)

    def _project(self):
        return self.editor.session.snapshot().to_dict()["project"]

    def _controller(self):
        return next(
            (row for row in controllers_from_project(self._project())
             if row["id"] == self.controllers.currentData()), None)

    def refresh(self):
        previous = self.controllers.currentData()
        self._revision = self.editor.session.revision
        self.controllers.blockSignals(True)
        self.controllers.clear()
        for controller in controllers_from_project(self._project()):
            self.controllers.addItem(controller["id"], controller["id"])
        index = self.controllers.findData(previous)
        if index >= 0:
            self.controllers.setCurrentIndex(index)
        self.controllers.blockSignals(False)
        self.load_controller()

    def load_controller(self, *_):
        controller = self._controller()
        self.states.blockSignals(True)
        self.states.clear()
        if controller is None:
            self.draft = None
        else:
            for state in controller["states"]:
                self.states.addItem(state["id"], state["id"])
            self.draft = deepcopy(next((
                row for row in self.editor.timelines()
                if row["controller_id"] == controller["id"]), None))
            if self.draft is None:
                self.draft = {
                    "schema_version": 1, "id": controller["id"] + "_timeline",
                    "controller_id": controller["id"],
                    "tracks": [{"state": controller["initial"], "markers": []}],
                }
            self.identifier.setText(self.draft["id"])
        self.states.blockSignals(False)
        self._revision = self.editor.session.revision
        self._redraw_markers()

    def _track(self, create=False):
        if not self.draft:
            return None
        state = self.states.currentData()
        track = next((t for t in self.draft["tracks"] if t["state"] == state), None)
        if track is None and create and state:
            track = {"state": state, "markers": []}
            self.draft["tracks"].append(track)
        return track

    def _redraw_markers(self, *_):
        self._invalidate()
        self.markers.clear()
        track = self._track()
        for marker in track["markers"] if track else []:
            self.markers.addItem(
                f'{marker["id"]} @ {marker["at_ms"]}ms: {marker["cue"]}')

    def add_marker(self):
        track = self._track(create=True)
        if track is None:
            self._show("Créez un contrôleur R36 avant la timeline.")
            return
        marker_id = self.marker_id.text().strip()
        if not marker_id or any(x["id"] == marker_id for x in track["markers"]):
            self._show("ID de marqueur manquant ou déjà utilisé.")
            return
        track["markers"].append({
            "id": marker_id, "at_ms": self.at_ms.value(),
            "cue": self.cue.currentData()})
        track["markers"].sort(key=lambda row: (row["at_ms"], row["id"]))
        self._redraw_markers()

    def remove_marker(self):
        track, index = self._track(), self.markers.currentRow()
        if track is not None and 0 <= index < len(track["markers"]):
            track["markers"].pop(index)
            self._redraw_markers()

    def _document(self):
        document = deepcopy(self.draft)
        if document:
            document["id"] = self.identifier.text().strip()
        return document

    def preview(self):
        try:
            self._plan = self.editor.preview(
                self._document(), expected_revision=self._revision)
            self.apply_button.setEnabled(True)
            self._show("Plan R1 valide, non encore appliqué.")
        except (ValueError, TypeError) as exc:
            self._invalidate()
            self._show("Timeline refusée : " + str(exc))

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

    def delete_timeline(self):
        try:
            saved = next((row for row in self.editor.timelines()
                          if row["controller_id"] == self.controllers.currentData()), None)
            if saved is None:
                self._show("Aucune timeline enregistrée pour ce contrôleur.")
                return
            plan = self.editor.preview_remove(
                saved["id"], expected_revision=self._revision)
            self.editor.apply(plan)
            self.refresh()
            self.updated.emit()
        except (ValueError, TypeError) as exc:
            self._invalidate()
            self._show("Suppression refusée : " + str(exc))

    def sample(self):
        try:
            controller = self._controller()
            rows = cues_crossed(
                self._document(), controller,
                AssetRegistry(self._project().get("assets") or None),
                state=self.states.currentData(), entered_tick=0,
                from_tick=self.from_tick.value(), to_tick=self.to_tick.value())
            self._show({"markers": rows, "only_presentation": True})
        except (ValueError, TypeError) as exc:
            self._show("Lecture timeline refusée : " + str(exc))
