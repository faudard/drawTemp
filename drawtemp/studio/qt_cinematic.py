"""R11 Qt 6 Cinematic Studio: canonical events, not a parallel authoring format."""
from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtGui import QColor, QBrush, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSlider, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from sporebound.cinematics import KINDS, EASINGS, EXPRESSIONS, FX_KINDS, SHOT_TRANSITIONS, TRIGGERS
from sporebound.event_cinematic_qa import audit_event_cinematic_path
from sporebound.cinematics import cinematic_template, event_template
from sporebound.model import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.player.qt_cinematic import CinematicStage

LANES = ("background", "camera", "actor", "dialogue", "fade",
         "music", "ambience", "voice", "sfx", "fx")
COLORS = {
    "background": "#607d8b", "camera": "#40b4c4", "actor": "#65b976",
    "dialogue": "#e4b675", "fade": "#8f7eac", "music": "#d688be",
    "ambience": "#ae79ce", "voice": "#ed8b6a", "sfx": "#bb7069", "fx": "#e2a341",
}


def _lane(event):
    return event.get("bus", "sfx") if event["kind"] == "sound" else event["kind"]


class CinematicEditor(QMainWindow):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.clip_id = ""
        self.event_id = ""
        self.fields = {}
        self.setWindowTitle("DrawTemp 5.0 — Cinématiques, audio et effets")
        self.resize(1460, 880)
        body = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(body)

        left = QWidget()
        l = QVBoxLayout(left)
        l.addWidget(QLabel("Cinématiques du projet"))
        self.clip_list = QListWidget()
        self.clip_list.currentRowChanged.connect(self._select_clip)
        l.addWidget(self.clip_list)
        for label, callback in (("Créer une cinématique", self._create_clip),
                                ("Introduction Jeanne", self._jeanne),
                                ("Supprimer", self._delete_clip),
                                ("Enregistrer le projet", self._save),
                                ("Annuler  Ctrl+Z", self._undo),
                                ("Rétablir  Ctrl+Y", self._redo)):
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            l.addWidget(btn)
        configure = QPushButton("Configurer le déclencheur")
        configure.clicked.connect(self._configure_trigger)
        l.addWidget(configure)
        audit = QPushButton("QA événement → cinématique")
        audit.clicked.connect(self._audit_path)
        l.addWidget(audit)
        body.addWidget(left)

        middle = QWidget()
        ml = QVBoxLayout(middle)
        self.stage = CinematicStage(
            self._empty_clip(), registry=document.project.asset_registry(),
            asset_root=document.source_path.parent if document.source_path else None)
        self.stage.pause()
        ml.addWidget(self.stage, 4)
        controls = QHBoxLayout()
        self.play_button = QPushButton("Lire")
        self.play_button.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_button)
        restart = QPushButton("Début")
        restart.clicked.connect(self.stage.restart)
        controls.addWidget(restart)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 8000)
        self.slider.sliderMoved.connect(self.stage.seek)
        self.stage.positionChanged.connect(self._position)
        controls.addWidget(self.slider, 1)
        self.clock_label = QLabel("0.00 / 8.00 s")
        controls.addWidget(self.clock_label)
        self.speed = QComboBox()
        for factor in (.25, .5, 1.0, 1.5, 2.0):
            self.speed.addItem(f"{factor:g}×", factor)
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(
            lambda _: self.stage.set_speed(self.speed.currentData()))
        controls.addWidget(self.speed)
        ml.addLayout(controls)
        ml.addWidget(QLabel("Timeline multipiste · sélectionner un événement pour l'éditer"))
        self.timeline_scene = QGraphicsScene(self)
        self.timeline_scene.selectionChanged.connect(self._on_track_selected)
        self.timeline = QGraphicsView(self.timeline_scene)
        self.timeline.setMinimumHeight(280)
        ml.addWidget(self.timeline, 3)
        body.addWidget(middle)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Inspecteur / propriétés"))
        self.inspector_host = QWidget()
        self.inspector = QFormLayout(self.inspector_host)
        rl.addWidget(self.inspector_host, 1)
        add_controls = QHBoxLayout()
        self.new_kind = QComboBox()
        self.new_kind.addItems(KINDS)
        add_controls.addWidget(self.new_kind)
        add = QPushButton("+ Piste")
        add.clicked.connect(self._add_event)
        add_controls.addWidget(add)
        rl.addLayout(add_controls)
        for label, callback in (("Appliquer les propriétés", self._apply_event),
                                ("Ajouter image-clé au curseur", self._keyframe),
                                ("Supprimer événement", self._delete_event)):
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            rl.addWidget(btn)
        body.addWidget(right)
        body.setSizes([240, 900, 320])
        self.stage.finished.connect(lambda: self.play_button.setText("Lire"))
        QShortcut(QKeySequence.Undo, self, activated=self._undo)
        QShortcut(QKeySequence.Redo, self, activated=self._redo)
        self.statusBar().showMessage("Les données de jeu et les choix narratifs restent inchangés.")
        self._refresh()

    def _empty_clip(self):
        return cinematic_template("preview", "Sélectionnez une cinématique",
                                  "campaign_start", self.document.project.campaigns[0]["id"])

    def _alert(self, exc):
        QMessageBox.warning(self, "Cinématique non modifiée", str(exc))

    def _apply(self, method, *args):
        try:
            result = method(*args)
        except (RuleError, ValueError, OSError) as exc:
            self._alert(exc)
            return False
        self._refresh()
        return result if result is not None else True

    def _refresh(self):
        clips = self.document.clips
        with QSignalBlocker(self.clip_list):
            self.clip_list.clear()
            for clip in clips:
                self.clip_list.addItem(f"{clip['name']}  ·  {clip['id']}")
            valid = [c["id"] for c in clips]
            if self.clip_id not in valid:
                self.clip_id = valid[0] if valid else ""
                self.event_id = ""
            if self.clip_id:
                self.clip_list.setCurrentRow(valid.index(self.clip_id))
        clip = self.document.clip(self.clip_id) if self.clip_id else self._empty_clip()
        self.slider.setRange(0, clip["duration_ms"])
        self.stage.set_clip(clip)
        self.stage.pause()
        self.play_button.setText("Lire")
        self._draw_timeline()
        self._draw_inspector()
        suffix = " • non enregistré" if self.document.dirty else ""
        self.setWindowTitle("DrawTemp 5.0 — Cinématiques" + suffix)

    def _select_clip(self, row):
        if row < 0 or row >= len(self.document.clips):
            return
        self.clip_id = self.document.clips[row]["id"]
        self.event_id = ""
        self._refresh()

    def _create_clip(self):
        name, ok = QInputDialog.getText(self, "Créer", "Nom de la cinématique")
        if not ok or not name.strip():
            return
        cid, ok = QInputDialog.getText(self, "Identifiant stable", "ID (lettres/chiffres/_/-)")
        if not ok or not cid:
            return
        clip = cinematic_template(cid, name, "campaign_start",
                                  self.document.project.campaigns[0]["id"])
        if self._apply(self.document.add_clip, clip):
            self.clip_id = cid
            self._refresh()

    def _jeanne(self):
        try:
            self.clip_id = self.document.add_jeanne_intro()
            self.event_id = ""
            self._refresh()
        except RuleError as exc:
            self._alert(exc)

    def _delete_clip(self):
        if self.clip_id and QMessageBox.question(
                self, "Supprimer", "Supprimer cette cinématique ?") == QMessageBox.Yes:
            self._apply(self.document.delete_clip, self.clip_id)

    def _configure_trigger(self):
        if not self.clip_id:
            return
        current = self.document.clip(self.clip_id)["trigger"]
        kind, ok = QInputDialog.getItem(self, "Déclencheur", "Type",
                                        list(TRIGGERS),
                                        list(TRIGGERS).index(current["kind"]), False)
        if not ok:
            return
        content = self.document.content
        project = self.document.project
        if kind == "campaign_start":
            targets = [c["id"] for c in project.campaigns]
        elif kind == "scene":
            targets = [s["id"] for s in project.story.get("scenes", [])]
        elif kind == "tactical_event":
            targets = [f"{mission.id}/{trigger['id']}"
                       for mission in content.missions.values()
                       for trigger in mission.triggers]
        else:
            targets = list(content.missions)
        if not targets:
            self._alert(RuleError("Aucune cible disponible pour ce type de déclencheur"))
            return
        index = targets.index(current["target"]) if current["target"] in targets else 0
        target, ok = QInputDialog.getItem(self, "Déclencheur", "Cible", targets, index, False)
        if ok:
            self._apply(self.document.edit_clip, self.clip_id,
                        {"trigger": {"kind": kind, "target": target}})

    def _audit_path(self):
        if not self.clip_id:
            return
        clip = self.document.clip(self.clip_id)
        if clip["trigger"]["kind"] != "scene":
            self._alert(RuleError("L'audit de conséquences exige une cinématique liée à une scène."))
            return
        source, ok = QInputDialog.getItem(self, "Source", "Événement source",
                                          ["tactical_event", "strategic_event"], 0, False)
        if not ok:
            return
        target, ok = QInputDialog.getText(self, "Source", "ID événement (mission/ID)")
        if not ok or not target:
            return
        choice, ok = QInputDialog.getText(self, "Choix narratif", "ID du choix/conséquence")
        if not ok or not choice:
            return
        try:
            report = audit_event_cinematic_path(
                self.document.project, self.document.content,
                source_kind=source, source_id=target, choice_id=choice)
            if self.clip_id not in report.cinematic_ids:
                raise RuleError("La scène auditée ne déclenche pas cette cinématique")
        except (RuleError, StopIteration, ValueError) as exc:
            self._alert(exc)
            return
        QMessageBox.information(
            self, "Chaîne validée",
            f"Événement : {report.source_id}\n"
            f"Scène : {report.scene_id}\n"
            f"Clips : {', '.join(report.cinematic_ids)}\n"
            f"Effets : {', '.join(report.gameplay_effects)}\n"
            f"SHA256 : {report.timeline_sha256}")

    def _save(self):
        try:
            try:
                self.document.save()
            except AuthoringError as exc:
                if exc.code != "no_destination" or self.document.session is None:
                    raise
                path, _ = QFileDialog.getSaveFileName(
                    self, "Enregistrer contenu + GameProject", "jeanne.json",
                    "Content JSON (*.json)")
                if not path:
                    return
                self.document.save(path)
            self.statusBar().showMessage("Content et GameProject enregistrés.", 5000)
            self._refresh()
        except (RuleError, ValueError, OSError) as exc:
            self._alert(exc)

    def _undo(self):
        if self.document.undo():
            self._refresh()

    def _redo(self):
        if self.document.redo():
            self._refresh()

    def _position(self, ms):
        with QSignalBlocker(self.slider):
            self.slider.setValue(ms)
        self.clock_label.setText(f"{ms/1000:.2f} / {self.stage.clip['duration_ms']/1000:.2f} s")
        # Lightweight playhead only; never redraw the timeline on each tick.
        if hasattr(self, "_playhead"):
            self._playhead.setX(130 + 920 * ms / self.stage.clip["duration_ms"])

    def _toggle_play(self):
        if self.stage.playing:
            self.stage.pause()
            self.play_button.setText("Lire")
        else:
            self.stage.play()
            self.play_button.setText("Pause")

    def _draw_timeline(self):
        scene = self.timeline_scene
        scene.blockSignals(True)
        scene.clear()
        clip = self.document.clip(self.clip_id) if self.clip_id else self._empty_clip()
        scene.setSceneRect(0, 0, 1080, 28 + len(LANES) * 32)
        for lane_index, lane in enumerate(LANES):
            y = 25 + lane_index * 32
            scene.addText(lane).setPos(2, y)
            scene.addLine(128, y + 24, 1060, y + 24,
                          QPen(QColor("#444b59")))
        for event in clip["events"]:
            row = LANES.index(_lane(event))
            x = 130 + 920 * event["start_ms"] / clip["duration_ms"]
            width = max(5, 920 * event["duration_ms"] / clip["duration_ms"])
            y = 26 + row * 32
            item = scene.addRect(x, y, width, 21, QPen(QColor("#202e3c")),
                                 QBrush(QColor(COLORS[_lane(event)])))
            item.setData(0, event["id"])
            item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            if event["id"] == self.event_id:
                item.setSelected(True)
            label = scene.addText(event["id"])
            label.setDefaultTextColor(QColor("#f5f1e9"))
            label.setPos(x + 3, y - 2)
            label.setAcceptedMouseButtons(Qt.NoButton)
            for key in event.get("keyframes", ()):
                kx = x + 920 * key["at_ms"] / clip["duration_ms"]
                diamond = scene.addEllipse(kx - 3, y + 6, 7, 7,
                                           QPen(QColor("white")), QBrush(QColor("white")))
                diamond.setAcceptedMouseButtons(Qt.NoButton)
        self._playhead = scene.addLine(0, 15, 0, 25 + len(LANES)*32,
                                        QPen(QColor("#f7e3a2"), 2))
        self._position(self.stage.time_ms)
        scene.blockSignals(False)

    def _on_track_selected(self):
        ids = [item.data(0) for item in self.timeline_scene.selectedItems()
               if item.data(0)]
        if ids and ids[0] != self.event_id:
            self.event_id = ids[0]
            self._draw_inspector()

    def _clear_form(self):
        self.fields.clear()
        while self.inspector.count():
            item = self.inspector.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _field(self, name, value, *, options=None, minimum=None, maximum=None,
               step=None, multiline=False):
        if options is not None:
            widget = QComboBox()
            widget.addItems(options)
            if str(value) in options:
                widget.setCurrentText(str(value))
        elif multiline:
            widget = QPlainTextEdit(str(value))
            widget.setMaximumHeight(90)
        elif isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
        elif isinstance(value, int) or isinstance(value, float):
            widget = QSpinBox() if isinstance(value, int) else QDoubleSpinBox()
            widget.setRange(minimum if minimum is not None else -100000,
                            maximum if maximum is not None else 100000)
            if step is not None:
                widget.setSingleStep(step)
            if isinstance(widget, QDoubleSpinBox):
                widget.setDecimals(3)
            widget.setValue(value)
        else:
            widget = QLineEdit(str(value))
        self.inspector.addRow(name, widget)
        self.fields[name] = widget

    def _value(self, name):
        widget = self.fields[name]
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        return widget.text()

    def _draw_inspector(self):
        self._clear_form()
        if not self.clip_id:
            self.inspector.addRow(QLabel("Créez une cinématique pour commencer."))
            return
        events = self.document.clip(self.clip_id)["events"]
        event = next((e for e in events if e["id"] == self.event_id), None)
        if event is None:
            self.inspector.addRow(QLabel("Sélectionnez un bloc de la timeline."))
            return
        self._field("Début (ms)", event["start_ms"], minimum=0, maximum=180000)
        self._field("Durée (ms)", event["duration_ms"], minimum=1, maximum=180000)
        kind = event["kind"]
        if kind in ("actor", "camera"):
            if kind == "actor":
                self._field("Acteur", event["actor"])
                self._field("Pose", event.get("pose", ""))
                self._field("Animation", event.get("animation", ""))
            for field in ("from", "to"):
                for index, suffix in enumerate(("X", "Y")):
                    self._field(field + " " + suffix, event[field][index],
                                minimum=-2.0, maximum=2.0, step=.05)
            self._field("Easing", event.get("easing", "linear"), options=list(EASINGS))
            if kind == "camera":
                for field in ("zoom_from", "zoom_to"):
                    self._field(field, event[field], minimum=.25, maximum=4.0, step=.05)
                self._field("Plan", event.get("shot", ""))
                self._field("Transition", event.get("transition", "cut"),
                            options=list(SHOT_TRANSITIONS))
        elif kind == "dialogue":
            self._field("Personnage", event["speaker"])
            self._field("Texte", event["text"], multiline=True)
            self._field("Portrait", event.get("portrait", ""))
            self._field("Expression", event.get("expression", "neutral"),
                        options=list(EXPRESSIONS))
            self._field("Caractères/s", event.get("chars_per_second", 0),
                        minimum=0, maximum=120)
        elif kind == "sound":
            self._field("Cue", event["cue"])
            self._field("Bus", event.get("bus", "sfx"),
                        options=["music", "ambience", "voice", "sfx"])
            for key in ("volume", "volume_to"):
                self._field(key, event.get(key, event.get("volume", 100)),
                            minimum=0, maximum=100)
            self._field("Boucle", event.get("loop", False))
            for key in ("fade_in_ms", "fade_out_ms"):
                self._field(key, event.get(key, 0), minimum=0, maximum=180000)
            self._field("Duck (%)", event.get("duck_percent", 40),
                        minimum=0, maximum=100)
        elif kind == "fx":
            self._field("Effet", event["effect"], options=list(FX_KINDS))
            self._field("Intensité", event["intensity"], minimum=0.0, maximum=1.0, step=.05)
            self._field("Seed", event["seed"], minimum=0, maximum=2147483647)
            for index, suffix in enumerate(("X", "Y")):
                self._field("Position " + suffix, event["at"][index],
                            minimum=-2.0, maximum=2.0, step=.05)
        elif kind in ("background", "fade"):
            self._field("Couleur", event["color"])

    def _apply_event(self):
        if not self.clip_id or not self.event_id:
            return
        event = next((e for e in self.document.clip(self.clip_id)["events"]
                      if e["id"] == self.event_id), None)
        if not event:
            return
        kind = event["kind"]
        updates = {"start_ms": self._value("Début (ms)"),
                   "duration_ms": self._value("Durée (ms)")}
        if kind in ("actor", "camera"):
            updates.update({"from": [self._value("from X"), self._value("from Y")],
                            "to": [self._value("to X"), self._value("to Y")],
                            "easing": self._value("Easing")})
            if kind == "actor":
                updates["actor"] = self._value("Acteur")
                if self._value("Pose"):
                    updates["pose"] = self._value("Pose")
                if self._value("Animation"):
                    updates["animation"] = self._value("Animation")
            else:
                updates.update(zoom_from=self._value("zoom_from"),
                               zoom_to=self._value("zoom_to"),
                               transition=self._value("Transition"))
                if self._value("Plan"):
                    updates["shot"] = self._value("Plan")
                elif "shot" in event:
                    # No silent removal of unknown fields: patch validated explicitly.
                    updates["shot"] = event["shot"]
        elif kind == "dialogue":
            updates.update(speaker=self._value("Personnage"),
                           text=self._value("Texte"),
                           expression=self._value("Expression"),
                           chars_per_second=self._value("Caractères/s"))
            if self._value("Portrait"):
                updates["portrait"] = self._value("Portrait")
        elif kind == "sound":
            updates.update(cue=self._value("Cue"), bus=self._value("Bus"),
                           volume=self._value("volume"), volume_to=self._value("volume_to"),
                           loop=self._value("Boucle"),
                           fade_in_ms=self._value("fade_in_ms"),
                           fade_out_ms=self._value("fade_out_ms"))
            if updates["bus"] == "voice":
                updates["duck_percent"] = self._value("Duck (%)")
            elif "duck_percent" in event:
                self._alert(RuleError("Retirer le ducking en mode voix avant de changer le bus"))
                return
        elif kind == "fx":
            updates.update(effect=self._value("Effet"), intensity=self._value("Intensité"),
                           seed=self._value("Seed"),
                           at=[self._value("Position X"), self._value("Position Y")])
        else:
            updates["color"] = self._value("Couleur")
        self._apply(self.document.edit_event, self.clip_id, self.event_id, updates)

    def _add_event(self):
        if not self.clip_id:
            return
        cid = self.clip_id
        event_id, ok = QInputDialog.getText(self, "Nouvelle piste", "Identifiant unique")
        if not ok or not event_id:
            return
        kind = self.new_kind.currentText()
        clip = self.document.clip(cid)
        start = min(self.stage.time_ms, clip["duration_ms"] - 1)
        event = event_template(kind, event_id, start,
                               min(2000, clip["duration_ms"] - start))
        if self._apply(self.document.add_event, cid, event):
            self.event_id = event_id
            self._refresh()

    def _delete_event(self):
        if self.clip_id and self.event_id:
            self._apply(self.document.delete_event, self.clip_id, self.event_id)

    def _keyframe(self):
        if not self.clip_id or not self.event_id:
            return
        event = next((e for e in self.document.clip(self.clip_id)["events"]
                      if e["id"] == self.event_id), None)
        if event and event["kind"] in ("actor", "camera"):
            local = self.stage.time_ms - event["start_ms"]
            self._apply(self.document.add_keyframe, self.clip_id, self.event_id, local)

    def closeEvent(self, event):
        if self.document.dirty:
            choice = QMessageBox.question(self, "Document non enregistré",
                         "Quitter et abandonner les modifications ?",
                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if choice != QMessageBox.Yes:
                event.ignore()
                return
        self.stage.pause()
        self.stage.audio.close()
        super().closeEvent(event)
