"""R28.D — Qt animation/hitbox, event-quest and isolated playtest workspaces.

Every authoring command is routed to the existing R1 session and the R9 graph.
No parallel runtime, bitmap cache, collision authoring or game-save schema.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.event_graph_qt import EventGraphView
from drawtemp.studio.r28d_workflow import (
    AnimationHitboxStudio, EventQuestGraph, IsolatedPlaytest, R28DError,
)
from sporebound.model import RuleError


def _select(widget, key):
    index = widget.findData(key)
    if index >= 0:
        widget.setCurrentIndex(index)


def _message(exc):
    return "Opération refusée : " + str(exc)


class AnimationHitboxPanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.editor = AnimationHitboxStudio(session)
        self._pending = None
        self._revision = -1
        self.setObjectName("r28d-animation-hitbox")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Animation & Hitbox Studio — registres PNG portables, collisions CT observées"))
        sub = QTabWidget()
        layout.addWidget(sub, 1)
        binding_tab = QWidget()
        sub.addTab(binding_tab, "Animations")
        form = QFormLayout(binding_tab)

        self.sprite_id = QLineEdit()
        self.sprite_id.setPlaceholderText("ex : jeanne_walk_0")
        form.addRow("Nouvel ID de sprite", self.sprite_id)
        self.sprite_path = QLineEdit()
        self.sprite_path.setPlaceholderText("art/jeanne_walk_0.png")
        form.addRow("Chemin PNG relatif", self.sprite_path)
        register = QPushButton("Prévisualiser l'ajout du sprite")
        register.clicked.connect(self.preview_sprite)
        form.addRow(register)

        self.animation_id = QLineEdit("jeanne_move")
        form.addRow("ID animation", self.animation_id)
        self.binding_slot = QLineEdit("hero_move")
        form.addRow("Slot présentation (hero_move...)", self.binding_slot)
        self.frames = QPlainTextEdit()
        self.frames.setPlaceholderText("sprite_a,120\nsprite_b,120")
        self.frames.setMaximumHeight(108)
        form.addRow("Images sprite,durée_ms (une par ligne)", self.frames)
        self.loop = QCheckBox("Boucle")
        self.loop.setChecked(True)
        form.addRow(self.loop)
        preview_animation = QPushButton("Prévisualiser la timeline")
        preview_animation.clicked.connect(self.preview_animation)
        form.addRow(preview_animation)
        self.apply_button = QPushButton("Appliquer (transaction R1)")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        form.addRow(self.apply_button)

        self.elapsed = QSpinBox()
        self.elapsed.setRange(0, 1000000)
        form.addRow("Échantillon à (ms)", self.elapsed)
        sample_button = QPushButton("Vérifier le sprite sélectionné par MotionDirector")
        sample_button.clicked.connect(self.sample)
        form.addRow(sample_button)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Diagnostics animations et hitboxes")
        form.addRow(self.preview)
        for widget in (self.sprite_id, self.sprite_path, self.animation_id,
                       self.binding_slot, self.frames):
            widget.textChanged.connect(self._invalidate)
        self.loop.toggled.connect(self._invalidate)

        hitbox_tab = QWidget()
        sub.addTab(hitbox_tab, "Hitboxes tactiques")
        hit_layout = QVBoxLayout(hitbox_tab)
        hit_layout.addWidget(QLabel(
            "Footprints de Content.missions.units : non modifiables ici. "
            "Les hitboxes temps réel R26 ne sont pas encore un contrat éditable."))
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission des hitboxes")
        self.mission.currentIndexChanged.connect(self.render_hitboxes)
        hit_layout.addWidget(self.mission)
        self.view = QGraphicsView()
        self.view.setAccessibleName("Plan visuel des footprints tactiques")
        hit_layout.addWidget(self.view, 1)
        self.hitbox_report = QPlainTextEdit()
        self.hitbox_report.setReadOnly(True)
        self.hitbox_report.setMaximumHeight(132)
        hit_layout.addWidget(self.hitbox_report)
        self.refresh()

    def _invalidate(self, *_):
        self._pending = None
        self.apply_button.setEnabled(False)

    def refresh(self):
        session = self.editor.session
        self._revision = session.revision
        previous = self.mission.currentData()
        self.mission.blockSignals(True)
        self.mission.clear()
        snapshot = session.snapshot().to_dict()
        for row in snapshot["content"]["missions"]:
            self.mission.addItem(row["name"] + " [" + row["id"] + "]", row["id"])
        _select(self.mission, previous)
        self.mission.blockSignals(False)
        self._invalidate()
        self.render_hitboxes()

    def _stage(self, operation):
        try:
            self._pending = operation()
            self.apply_button.setEnabled(True)
            if hasattr(self._pending, "after"):
                payload = {
                    "animation": self._pending.animation_id,
                    "assets_before": self._pending.before,
                    "assets_after": self._pending.after,
                }
            else:
                payload = {
                    "new_assets": self._pending.project,
                    "note": "Plan R1 validé, non appliqué.",
                }
            self.preview.setPlainText(json.dumps(
                payload, indent=2, ensure_ascii=False, default=str))
        except (R28DError, AuthoringError, RuleError, ValueError, TypeError) as exc:
            self._invalidate()
            self.preview.setPlainText(_message(exc))

    def preview_sprite(self):
        self._stage(lambda: self.editor.preview_sprite(
            self.sprite_id.text().strip(), self.sprite_path.text().strip(),
            expected_revision=self._revision))

    def _parsed_frames(self):
        rows = []
        for line in self.frames.toPlainText().splitlines():
            if not line.strip():
                continue
            fields = [part.strip() for part in line.split(",")]
            if len(fields) != 2:
                raise R28DError("Format attendu : sprite_id,durée_ms")
            rows.append({"sprite": fields[0], "duration_ms": int(fields[1])})
        return rows

    def preview_animation(self):
        self._stage(lambda: self.editor.preview_animation(
            self.animation_id.text().strip(), self._parsed_frames(),
            loop=self.loop.isChecked(), slot=self.binding_slot.text().strip(),
            expected_revision=self._revision))

    def apply_changes(self):
        if self._pending is None:
            return
        try:
            self.editor.apply(self._pending)
        except (AuthoringError, R28DError, RuleError, ValueError) as exc:
            self._invalidate()
            self.preview.setPlainText(_message(exc))
            return
        self._revision = self.editor.session.revision
        self._invalidate()
        self.updated.emit()

    def sample(self):
        try:
            # Actor/team/pose convention belongs to MotionDirector. This is
            # a registry-only lookup; do not claim rendered playback.
            slot = self.binding_slot.text().strip()
            pose = slot.split("_")
            actor = pose[0] if pose else "hero"
            action = pose[1] if len(pose) > 1 else "idle"
            direction = pose[2] if len(pose) > 2 else "south"
            result = self.editor.sample(
                slot, self.elapsed.value(), actor_id=actor,
                team="player", action=action, direction=direction)
            self.preview.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        except (R28DError, AuthoringError, RuleError, ValueError) as exc:
            self.preview.setPlainText(_message(exc))

    def render_hitboxes(self, *_):
        mission = self.mission.currentData()
        if not mission:
            return
        report = self.editor.hitboxes(mission)
        scene = QGraphicsScene(self.view)
        width, height = report["board"]
        cell = min(28, max(8, int(800 / max(width, height))))
        for y in range(height):
            for x in range(width):
                scene.addRect(x * cell, y * cell, cell, cell,
                              QPen(QColor("#64748b")),
                              QBrush(QColor("#f8fafc")))
        for row in report["units"]:
            color = QColor("#2563eb" if row["team"] == "player" else "#c2410c")
            for x, y in row["occupied_cells"]:
                scene.addRect(x * cell + 2, y * cell + 2,
                              cell - 4, cell - 4, QPen(color), QBrush(color.lighter(155)))
            x, y = row["origin"]
            text = scene.addText(row["id"])
            text.setDefaultTextColor(QColor("#111827"))
            text.setPos(x * cell, y * cell - 16)
        self.view.setScene(scene)
        self.hitbox_report.setPlainText(json.dumps(
            report, indent=2, ensure_ascii=False))


class EventQuestPanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.editor = EventQuestGraph(session)
        self.setObjectName("r28d-event-quest")
        self._revision = -1
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Event / Quest Graph : Mission.triggers R9 et scènes narratives R25"))
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission du graphe d'événements")
        self.mission.currentIndexChanged.connect(self.render_graph)
        layout.addWidget(self.mission)
        self.graph_view = EventGraphView()
        self.graph_view.eventSelected.connect(self._event_selected)
        self.graph_view.connectRequested.connect(self._connect)
        layout.addWidget(self.graph_view, 2)
        self.connect_mode = QCheckBox("Relier par clic : prédécesseur → déclencheur")
        self.connect_mode.toggled.connect(self._update_connect)
        layout.addWidget(self.connect_mode)
        self.any_of = QCheckBox("Lien OU (after_any) plutôt que ET (after)")
        self.any_of.toggled.connect(self._update_connect)
        layout.addWidget(self.any_of)
        self.selected = QLabel("Événement sélectionné : aucun")
        layout.addWidget(self.selected)
        layout.addWidget(QLabel(
            "Scènes narratives et capacités : lecture seule. "
            "Le graphe CT n'est pas un routeur temps réel."))
        self.scenes = QListWidget()
        self.scenes.setMaximumHeight(112)
        self.scenes.setAccessibleName("Scènes narratives existantes")
        layout.addWidget(self.scenes)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(155)
        layout.addWidget(self.report)
        self.refresh()

    def _event_selected(self, event_id):
        self.selected.setText("Événement sélectionné : " + event_id)

    def _update_connect(self, *_):
        self.graph_view.set_connect_mode(
            self.connect_mode.isChecked(), any_of=self.any_of.isChecked())

    def refresh(self):
        old = self.mission.currentData()
        self.mission.blockSignals(True)
        self.mission.clear()
        for key, name in self.editor.missions():
            self.mission.addItem(name + " [" + key + "]", key)
        _select(self.mission, old)
        self.mission.blockSignals(False)
        self.render_graph()

    def render_graph(self, *_):
        key = self.mission.currentData()
        if key is None:
            return
        self._revision = self.editor.session.revision
        result = self.editor.inspect(key)
        self.graph_view.render_events(result["events"], key)
        self._update_connect()
        self.scenes.clear()
        for scene in result["story_scenes"]:
            self.scenes.addItem(
                scene["title"] + " [" + scene["id"] + "] — " + scene["combat"])
        self.report.setPlainText(json.dumps({
            "mission": key, "mode": result["mode"],
            "diagnostics": result["diagnostics"],
            "runtime_note": result["runtime_note"],
        }, ensure_ascii=False, indent=2))

    def _connect(self, source, target, any_of):
        try:
            self.editor.link(self.mission.currentData(), target, source,
                             any_of=any_of, expected_revision=self._revision)
            self.updated.emit()
        except (AuthoringError, RuleError, R28DError, ValueError) as exc:
            self.report.setPlainText(_message(exc))
        self.render_graph()


class PlaytestRoundtripPanel(QWidget):
    """One-shot headless checkpoint test against exact AuthoringSession revision."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.editor = IsolatedPlaytest(session)
        self._revision = -1
        self.setObjectName("r28d-playtest")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Studio → GameSession → restauration vérifiée → Studio (isolé)"))
        layout.addWidget(QLabel(
            "Ne démarre pas le Player graphique. N'édite pas le projet, "
            "ne débloque aucune mission, n'écrit pas de sauvegarde."))
        form = QFormLayout()
        self.campaign = QComboBox()
        self.campaign.setAccessibleName("Campagne du playtest")
        form.addRow("Campagne", self.campaign)
        self.choice = QLineEdit()
        self.choice.setPlaceholderText("ex : enter (facultatif)")
        form.addRow("Choix narratif (ID)", self.choice)
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission du playtest")
        form.addRow("Mission à lancer", self.mission)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(11)
        form.addRow("Seed", self.seed)
        layout.addLayout(form)
        self.run_button = QPushButton("Exécuter et vérifier le roundtrip")
        self.run_button.setObjectName("r28d-run-playtest")
        self.run_button.clicked.connect(self.run_test)
        layout.addWidget(self.run_button)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Résultat du playtest et digest")
        layout.addWidget(self.report, 1)
        self.refresh()

    def refresh(self):
        old_campaign, old_mission = self.campaign.currentData(), self.mission.currentData()
        self.campaign.clear()
        for key, label in self.editor.campaigns():
            self.campaign.addItem(label + " [" + key + "]", key)
        _select(self.campaign, old_campaign)
        self.mission.clear()
        self.mission.addItem("Campagne seule, sans combat", None)
        for row in self.editor.session.snapshot().to_dict()["content"]["missions"]:
            self.mission.addItem(row["name"] + " [" + row["id"] + "]", row["id"])
        _select(self.mission, old_mission)
        self._revision = self.editor.session.revision

    def run_test(self):
        try:
            result = self.editor.run(
                self.campaign.currentData(),
                choice_id=self.choice.text().strip() or None,
                mission_id=self.mission.currentData(),
                seed=self.seed.value(),
                expected_revision=self._revision)
            self.report.setPlainText(json.dumps(
                result, ensure_ascii=False, indent=2))
        except (R28DError, AuthoringError, RuleError, ValueError) as exc:
            self.report.setPlainText(_message(exc))


class R28DWorkspace(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setObjectName("r28d-workspace")
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.animation = AnimationHitboxPanel(session)
        from drawtemp.studio.animation_graph_qt import AnimationControllerPanel
        self.animation_controller = AnimationControllerPanel(session)
        self.events = EventQuestPanel(session)
        self.playtest = PlaytestRoundtripPanel(session)
        self.tabs.addTab(self.animation, "Animation / Hitbox")
        self.tabs.addTab(self.animation_controller, "Contrôleur R36")
        self.tabs.addTab(self.events, "Événements / Quêtes")
        self.tabs.addTab(self.playtest, "Playtest")
        self.animation.updated.connect(self.animation_controller.refresh)
        self.animation.updated.connect(self.updated.emit)
        self.animation_controller.updated.connect(self.updated.emit)
        self.events.updated.connect(self.updated.emit)

    def refresh(self):
        self.animation.refresh()
        self.animation_controller.refresh()
        self.events.refresh()
        self.playtest.refresh()
