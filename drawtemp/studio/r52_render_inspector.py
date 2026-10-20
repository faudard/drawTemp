"""R52.B1 Qt Widgets look inspector on the canonical R3 renderer.

Preview/apply/cancel only affect the live Qt presentation. They do not write
Content/GameProject or alter any save/replay and cannot change projection.
"""
from copy import deepcopy

from drawtemp.render.ambient_presentation import normalize_lighting_profile

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
        QLineEdit, QMessageBox, QPushButton, QSlider, QSpinBox,
        QVBoxLayout, QWidget,
    )
except ImportError:
    QWidget = object


class RenderLookInspector(QWidget):
    """Single-viewport transaction for authored presentation experiments."""

    def __init__(self, renderer, parent=None):
        super().__init__(parent)
        self.renderer = renderer
        self._baseline = self._snapshot()
        self._selected_camera = 0

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("R52.B — aperçu local, sans modification de la sauvegarde"))
        form = QFormLayout()
        self.camera = QComboBox(self)
        self.camera.setObjectName("r52_camera_preset")
        self._presets = renderer.cameraPresets
        self.camera.addItem("Libre (caméra actuelle)", "custom")
        for preset in self._presets:
            label = preset["title"]
            if not preset["enabled"]:
                label += " (indisponible)"
            self.camera.addItem(label, preset["id"])
        form.addRow("Caméra", self.camera)

        self.day_tint = QLineEdit(self)
        self.day_tint.setObjectName("r52_day_tint")
        self.night_tint = QLineEdit(self)
        self.night_tint.setObjectName("r52_night_tint")
        form.addRow("Couleur jour (#RRGGBB)", self.day_tint)
        form.addRow("Couleur nuit (#RRGGBB)", self.night_tint)
        self.day_opacity = QDoubleSpinBox(self)
        self.day_opacity.setRange(0.0, 1.0)
        self.day_opacity.setSingleStep(0.05)
        self.night_opacity = QDoubleSpinBox(self)
        self.night_opacity.setRange(0.0, 1.0)
        self.night_opacity.setSingleStep(0.05)
        form.addRow("Filtre jour", self.day_opacity)
        form.addRow("Filtre nuit", self.night_opacity)
        self.phase = QSlider(Qt.Orientation.Horizontal, self)
        self.phase.setObjectName("r52_ambient_phase")
        self.phase.setRange(0, 100)
        form.addRow("Nuit (%)", self.phase)
        self.duration = QSpinBox(self)
        self.duration.setRange(0, 60000)
        self.duration.setValue(1200)
        self.duration.setSuffix(" ms")
        form.addRow("Transition", self.duration)
        layout.addLayout(form)

        row = QHBoxLayout()
        for label, target in (("Vers jour", 0.0), ("Vers nuit", 1.0)):
            button = QPushButton(label, self)
            button.clicked.connect(lambda _checked=False, value=target: self._transition(value))
            row.addWidget(button)
        layout.addLayout(row)
        row2 = QHBoxLayout()
        for label, handler in (("Prévisualiser", self.preview),
                               ("Appliquer localement", self.apply),
                               ("Annuler aperçu", self.cancel)):
            button = QPushButton(label, self)
            button.clicked.connect(handler)
            row2.addWidget(button)
        layout.addLayout(row2)
        layout.addStretch(1)
        self._fill(self._baseline["lighting"])
        self.camera.currentIndexChanged.connect(self._choose_camera)
        renderer.presentationChanged.connect(self._sync_phase)

    def _snapshot(self):
        camera = self.renderer.camera
        return {
            "lighting": dict(self.renderer.lightingProfile),
            "camera": (camera.zoom, camera.pan_x, camera.pan_y),
        }

    def _fill(self, profile):
        self.day_tint.setText(profile["dayTint"])
        self.night_tint.setText(profile["nightTint"])
        self.day_opacity.setValue(profile["dayOpacity"])
        self.night_opacity.setValue(profile["nightOpacity"])
        self.phase.blockSignals(True)
        self.phase.setValue(round(profile["phase"] * 100))
        self.phase.blockSignals(False)

    def _candidate(self):
        return normalize_lighting_profile({
            "dayTint": self.day_tint.text().strip(),
            "nightTint": self.night_tint.text().strip(),
            "dayOpacity": self.day_opacity.value(),
            "nightOpacity": self.night_opacity.value(),
            "phase": self.phase.value() / 100,
        })

    def preview(self):
        try:
            candidate = self._candidate()
        except ValueError as exc:
            QMessageBox.warning(self, "Profil refusé", str(exc))
            return False
        self.renderer.setLightingProfile(candidate)
        return True

    def _transition(self, target):
        if not self.preview():
            return
        self.renderer.transitionLighting(target, self.duration.value())

    def _sync_phase(self):
        phase = self.renderer.lightingProfile["phase"]
        self.phase.blockSignals(True)
        self.phase.setValue(round(100 * phase))
        self.phase.blockSignals(False)

    def _choose_camera(self, index):
        if index < 0:
            return
        try:
            preset_id = self.camera.itemData(index)
            if preset_id != "custom":
                self.renderer.setCameraPreset(preset_id)
        except ValueError as exc:
            self.camera.blockSignals(True)
            self.camera.setCurrentIndex(self._selected_camera)
            self.camera.blockSignals(False)
            QMessageBox.information(self, "Caméra non disponible", str(exc))
            return
        self._selected_camera = index

    def apply(self):
        if self.preview():
            self._baseline = self._snapshot()
            return True
        return False

    def cancel(self):
        """Discard a local preview, including zoom/pan; leave Core unchanged."""
        baseline = deepcopy(self._baseline)
        self.renderer.setLightingProfile(baseline["lighting"])
        camera = self.renderer.camera
        camera.zoom, camera.pan_x, camera.pan_y = baseline["camera"]
        self.renderer.refresh()
        self._fill(baseline["lighting"])
        self.camera.blockSignals(True)
        self.camera.setCurrentIndex(0)  # Restored view may be custom zoom/pan.
        self.camera.blockSignals(False)
        self._selected_camera = 0
