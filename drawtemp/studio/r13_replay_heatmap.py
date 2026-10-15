"""Qt 6 R13.8 spatial heatmap and deterministic manual/automatic replay transport.

Both widgets are read-only views of validated SDK / canonical trace frames.
No Qt render loop advances the tactical engine or creates synthetic positions.
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)


class ReplayTransport(QWidget):
    """Timer only changes a discrete, observed command index 0..N."""

    stepChanged = Signal(int)
    playingChanged = Signal(bool)
    BASE_MS = 450

    def __init__(self, parent=None):
        super().__init__(parent)
        self.maximum = 0
        self.step = 0
        self._playing = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.restart_button = QPushButton("|◀")
        self.restart_button.setToolTip("Revenir à l'état initial")
        self.back_button = QPushButton("◀")
        self.back_button.setToolTip("Commande précédente")
        self.play_button = QPushButton("▶ Lire")
        self.next_button = QPushButton("▶")
        self.next_button.setToolTip("Commande suivante")
        for button in (self.restart_button, self.back_button,
                       self.play_button, self.next_button):
            layout.addWidget(button)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        layout.addWidget(self.slider, 1)
        self.position_label = QLabel("0 / 0")
        layout.addWidget(self.position_label)
        layout.addWidget(QLabel("Vitesse"))
        self.speed = QComboBox()
        for title, value in (("0,5×", .5), ("1×", 1.), ("2×", 2.), ("4×", 4.)):
            self.speed.addItem(title, value)
        self.speed.setCurrentIndex(1)
        layout.addWidget(self.speed)
        self.timer = QTimer(self)
        self.timer.setSingleShot(False)
        self.timer.timeout.connect(self._advance)
        self.restart_button.clicked.connect(lambda: self.seek(0))
        self.back_button.clicked.connect(lambda: self.seek(self.step - 1))
        self.next_button.clicked.connect(lambda: self.seek(self.step + 1))
        self.play_button.clicked.connect(self.toggle)
        self.slider.valueChanged.connect(self.seek)
        self.speed.currentIndexChanged.connect(self._update_interval)
        self._update_controls()

    @property
    def playing(self):
        return self._playing

    def _update_controls(self):
        has_trace = self.maximum > 0
        self.play_button.setEnabled(has_trace)
        self.back_button.setEnabled(has_trace and self.step > 0)
        self.restart_button.setEnabled(has_trace and self.step > 0)
        self.next_button.setEnabled(has_trace and self.step < self.maximum)
        self.slider.setEnabled(has_trace)
        self.position_label.setText(f"{self.step} / {self.maximum}")

    def _update_interval(self, _index=None):
        self.timer.setInterval(
            int(self.BASE_MS / float(self.speed.currentData() or 1.)))
        if self._playing:
            self.timer.start()

    def set_frames(self, count):
        if type(count) is not int or count < 0 or count > 5000:
            raise ValueError("Replay frame count must be 0..5000")
        self.pause()
        self.maximum = count
        self.step = 0
        self.slider.blockSignals(True)
        self.slider.setRange(0, count)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._update_controls()

    def seek(self, index, *, notify=True):
        if type(index) is not int:
            raise ValueError("Replay seeks require integer command indices")
        value = max(0, min(index, self.maximum))
        changed = value != self.step
        self.step = value
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._update_controls()
        if changed and notify:
            self.stepChanged.emit(value)
        if self._playing and value >= self.maximum:
            self.pause()

    def toggle(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self.maximum <= 0 or self._playing:
            return
        if self.step >= self.maximum:
            self.seek(0)
        self._playing = True
        self.play_button.setText("Ⅱ Pause")
        self._update_interval()
        self.playingChanged.emit(True)

    def pause(self):
        was_playing = self._playing
        self._playing = False
        self.timer.stop()
        self.play_button.setText("▶ Lire")
        if was_playing:
            self.playingChanged.emit(False)

    def _advance(self):
        if not self._playing:
            return
        if self.step >= self.maximum:
            self.pause()
            return
        self.seek(self.step + 1)


class HeatmapCanvas(QWidget):
    """Normalized observation counts, segregated by actor, team and floor."""

    cellSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.step = 0
        self.team = "all"
        self.unit = "all"
        self.level = 0
        self.mode = "moves"
        self._filtered = []
        self._counts = Counter()
        self._bounds = (0, 0, 0)
        self.setMinimumSize(440, 340)
        self.setMouseTracking(True)

    def set_report(self, model):
        self.model = model
        self.step = 0
        self._rebuild()

    def set_filter(self, *, team, unit, level, mode):
        self.team, self.unit = team, unit
        self.level, self.mode = level, mode
        self._rebuild()

    def _rebuild(self):
        self._filtered = []
        self._counts.clear()
        if self.model:
            self._filtered = [
                item for item in self.model["entries"]
                if item["level"] == self.level
                and (self.team == "all" or item["team"] == self.team)
                and (self.unit == "all" or item["unit"] == self.unit)
                and (self.mode == "visits" or item["kind"] == "move")
            ]
            for item in self._filtered:
                if item["step"] <= self.step:
                    self._counts[tuple(item["cell"])] += 1
        self.update()

    def set_step(self, step):
        if self.model is None:
            return
        if type(step) is not int or not 0 <= step <= self.model["commands"]:
            raise ValueError("Heatmap step outside verified replay")
        if step == self.step:
            return
        # Rebuild on a backwards seek; cheap incremental prefix for playback.
        if step < self.step:
            self.step = step
            self._rebuild()
            return
        for item in self._filtered:
            if self.step < item["step"] <= step:
                self._counts[tuple(item["cell"])] += 1
        self.step = step
        self.update()

    def _geometry(self):
        if self.model is None:
            return (0, 0, 0)
        width, height = self.model["width"], self.model["height"]
        margin_x, margin_y = 42, 34
        tile = max(3., min(32., (self.width() - margin_x*2) / width,
                           (self.height() - margin_y*2 - 36) / height))
        return (margin_x, margin_y, tile)

    def _pos(self, x, y):
        left, top, tile = self._geometry()
        if tile <= 0:
            return None
        col, row = int((x-left) // tile), int((y-top) // tile)
        if (self.model and 0 <= col < self.model["width"]
                and 0 <= row < self.model["height"]):
            return (col, row)
        return None

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), self.palette().base())
        painter.setPen(self.palette().text().color())
        painter.drawText(12, 23, "HEATMAP · ARRIVÉES OBSERVÉES, SANS TRAJET RECONSTRUIT")
        if self.model is None:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Exécuter une simulation pour afficher les déplacements.")
            painter.end()
            return
        left, top, size = self._geometry()
        peak = max([1, *self._counts.values()])
        base = self.palette().alternateBase().color()
        for y in range(self.model["height"]):
            for x in range(self.model["width"]):
                amount = self._counts.get((x, y), 0)
                if amount:
                    alpha = 60 + int(195 * amount / peak)
                    color = QColor(234, 104, 46, alpha)
                    painter.fillRect(QRectF(left+x*size, top+y*size,
                                            max(1, size-0.5), max(1, size-0.5)),
                                     color)
                else:
                    painter.fillRect(QRectF(left+x*size, top+y*size,
                                            max(1, size-0.5), max(1, size-0.5)),
                                     base)
        painter.setPen(QPen(self.palette().mid().color(), 1))
        painter.drawRect(QRectF(left, top,
                                self.model["width"]*size,
                                self.model["height"]*size))
        painter.setPen(self.palette().text().color())
        label = (f"Étage {self.level}  ·  {self.mode}  ·  "
                 f"max {peak} passage(s)/case  ·  "
                 f"commande {self.step}/{self.model['commands']}")
        painter.drawText(QRectF(10, top+self.model["height"]*size+8,
                               self.width()-20, 24),
                         Qt.AlignmentFlag.AlignLeft, label)
        painter.end()

    def mouseMoveEvent(self, event):
        cell = self._pos(event.position().x(), event.position().y())
        if cell is None:
            self.setToolTip("")
        else:
            self.setToolTip(
                f"Case {cell} / étage {self.level} : "
                f"{self._counts.get(cell, 0)} arrivée(s) observée(s)")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._pos(event.position().x(), event.position().y())
            if cell is not None:
                observations = [row for row in self._filtered
                                if tuple(row["cell"]) == cell
                                and row["step"] <= self.step
                                and row["step"] > 0]
                if observations:
                    self.cellSelected.emit(observations[-1]["step"])
                    event.accept()
                    return
        super().mousePressEvent(event)


class MovementHeatmapPanel(QWidget):
    stepSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report = None
        self._replay_step = 0
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        self.team = QComboBox()
        self.unit = QComboBox()
        self.floor = QComboBox()
        self.mode = QComboBox()
        self.mode.addItem("Déplacements", "moves")
        self.mode.addItem("Visites + apparitions", "visits")
        for caption, combo in (("Équipe", self.team), ("Unité", self.unit),
                               ("Étage", self.floor), ("Mesure", self.mode)):
            controls.addWidget(QLabel(caption))
            controls.addWidget(combo)
            combo.currentIndexChanged.connect(self._changed_filter)
        self.full_battle = QCheckBox("Toute la bataille")
        self.full_battle.setChecked(True)
        self.full_battle.setToolTip(
            "Afficher les déplacements de toutes les commandes, "
            "ou décocher pour suivre les commandes lues.")
        self.full_battle.toggled.connect(self._change_extent)
        controls.addWidget(self.full_battle)
        self.canvas = HeatmapCanvas()
        self.canvas.cellSelected.connect(self.stepSelected.emit)
        layout.addWidget(self.canvas, 1)
        self.description = QLabel(
            "Heatmap de déplacements : une case n'est comptée que lors "
            "d'une arrivée observée (jamais à chaque commande d'un autre acteur).")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)

    def clear(self):
        self.report = None
        self._replay_step = 0
        self.canvas.set_report(None)
        for combo in (self.team, self.unit, self.floor):
            combo.blockSignals(True)
            combo.clear()
            combo.blockSignals(False)
        self.description.setText("Simuler un combat pour observer les déplacements.")

    def set_report(self, model):
        if model.get("kind") != "r13_movement_heatmap":
            raise ValueError("Validated replay movement model required")
        self.report = model
        self._replay_step = 0
        for combo in (self.team, self.unit, self.floor):
            combo.blockSignals(True)
            combo.clear()
        self.team.addItem("Toutes", "all")
        for team in model["teams"]:
            self.team.addItem(team, team)
        self.unit.addItem("Toutes", "all")
        for item in model["units"]:
            self.unit.addItem(item["id"], item["id"])
        for level in model["levels"] or [0]:
            self.floor.addItem(f"Étage {level}", level)
        for combo in (self.team, self.unit, self.floor):
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.mode.setCurrentIndex(0)
        self.canvas.set_report(model)
        self.canvas.set_step(model["commands"] if self.full_battle.isChecked() else 0)
        self._changed_filter()
        self.description.setText(
            f"Mission {model['mission']} · seed {model['seed']} · "
            f"{model['commands']} commandes · {len(model['entries'])} "
            "arrivées (déplacements, positions initiales ou renforts). "
            "Les étages sont indépendants, les chemins intermédiaires ne "
            "sont pas interpolés.")

    def _changed_filter(self, _index=None):
        if self.report is None:
            return
        self.canvas.set_filter(
            team=self.team.currentData() or "all",
            unit=self.unit.currentData() or "all",
            level=self.floor.currentData() if self.floor.currentData() is not None else 0,
            mode=self.mode.currentData() or "moves")

    def _change_extent(self, _checked=None):
        if self.report is None:
            return
        self.canvas.set_step(
            self.report["commands"] if self.full_battle.isChecked()
            else self._replay_step)

    def set_step(self, step):
        self._replay_step = step
        if not self.full_battle.isChecked():
            self.canvas.set_step(step)
