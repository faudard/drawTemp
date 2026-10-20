"""R43.B3 Qt read-only tactical target inspector embedded in the R3 viewport.

Uses the exact IsoViewport.qml + make_controller shared by Map Studio/Player.
No private grid painter or alternate picking/LOS model is installed.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from drawtemp.core import Content
from drawtemp.render.iso_scene import scene_from_mission
from drawtemp.render.qt_viewport import make_controller
from drawtemp.sdk.ability_contracts import AbilityError
from drawtemp.sdk.ability_targeting_r43 import native_target_preview


class NativeTargetingDialog(QDialog):
    """One-session CT preview. R3 selects tile; Battle owns target legality."""

    def __init__(self, session, ability, parent=None):
        super().__init__(parent)
        self.setObjectName("r43-native-targeting")
        self.setWindowTitle("R43.B3 — Ciblage natif CT / viewport R3")
        self.resize(1100, 840)
        self.session = session
        self.ability = ability
        self.revision = session.revision
        self.aim = None
        self.renderer = None
        self.viewport = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Clic sur une case R3 pour viser : portée, LOS, zone et cibles "
            "sont vérifiées par Battle sans muter GameSession."
        ))
        controls = QHBoxLayout()
        layout.addLayout(controls)
        controls.addWidget(QLabel("Mission"))
        self.missions = QComboBox()
        self.missions.setAccessibleName("Mission pour le ciblage natif")
        controls.addWidget(self.missions, 2)
        controls.addWidget(QLabel("Lanceur"))
        self.casters = QComboBox()
        self.casters.setAccessibleName("Unité lanceuse")
        controls.addWidget(self.casters, 2)

        self.viewport_host = QWidget()
        self.viewport_layout = QVBoxLayout(self.viewport_host)
        layout.addWidget(self.viewport_host, 3)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setAccessibleName("Ciblage CT natif / refus")
        layout.addWidget(self.diagnostics, 1)
        close = QPushButton("Fermer l'aperçu")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        content = session.snapshot().to_dict()["content"]
        for m in content["missions"]:
            self.missions.addItem(m["name"] + " [" + m["id"] + "]", m["id"])
        self.missions.currentIndexChanged.connect(self._load_mission)
        self.casters.currentIndexChanged.connect(self.refresh_target)
        self._load_mission()

    def _fresh(self):
        if self.session.revision != self.revision:
            self.diagnostics.setPlainText(
                "stale_revision : projet modifié; fermer et rouvrir le ciblage.")
            return False
        return True

    def _load_mission(self, *_):
        if not self._fresh():
            return
        mid = self.missions.currentData()
        if mid is None:
            return
        try:
            content = Content.from_dict(self.session.snapshot().to_dict()["content"])
            mission = content.missions[mid]
            self.casters.blockSignals(True)
            self.casters.clear()
            for actor in mission.units:
                if actor.alive:
                    self.casters.addItem(
                        actor.name + " [" + actor.id + "]", actor.id)
            self.casters.blockSignals(False)
            self.aim = None

            old = self.viewport
            if old is not None:
                self.viewport_layout.removeWidget(old)
                old.setParent(None)
                old.deleteLater()
            self.renderer = make_controller(scene_from_mission(mission))
            self.viewport = QQuickWidget(self)
            self.viewport.setObjectName("r43-r3-viewport")
            self.renderer.attach_engine(self.viewport.engine())
            self.viewport.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.viewport.rootContext().setContextProperty("renderer", self.renderer)
            qml = Path(__file__).resolve().parents[1] / "render" / "IsoViewport.qml"
            self.viewport.setSource(QUrl.fromLocalFile(str(qml)))
            if self.viewport.status() == QQuickWidget.Error:
                raise RuntimeError("\n".join(
                    e.toString() for e in self.viewport.errors()))
            root = self.viewport.rootObject()
            if root is None:
                raise RuntimeError("R3 viewport root unavailable")
            root.setProperty("interactionMode", "select")
            root.setProperty("showLegend", False)
            root.cellSelected.connect(self.aim_at)
            self.viewport_layout.addWidget(self.viewport)
            if self.casters.count():
                caster = next(a for a in mission.units
                              if a.id == self.casters.currentData())
                self.aim = tuple(caster.pos)
            self.refresh_target()
        except (AbilityError, ValueError, KeyError, RuntimeError) as exc:
            self.diagnostics.setPlainText("Aperçu refusé : " + str(exc))

    def aim_at(self, x, y):
        if type(x) is not int or type(y) is not int:
            self.diagnostics.setPlainText("Coordonnées R3 invalides")
            return
        self.aim = (x, y)
        self.refresh_target()

    def refresh_target(self, *_):
        if not self._fresh():
            return False
        caster_id = self.casters.currentData()
        mission_id = self.missions.currentData()
        if caster_id is None or mission_id is None:
            self.diagnostics.setPlainText("Mission ou lanceur absent")
            return False
        try:
            if self.aim is None:
                content = Content.from_dict(self.session.snapshot().to_dict()["content"])
                self.aim = tuple(next(a.pos for a in content.missions[mission_id].units
                                      if a.id == caster_id))
            report = native_target_preview(
                self.session, self.ability, mission_id, caster_id, self.aim)
            self.diagnostics.setPlainText(json.dumps(
                report, ensure_ascii=False, indent=2, sort_keys=True))
            if self.renderer is not None:
                overlays = {"reach": report["available"]}
                if report["legal"]:
                    overlays["intent"] = report["area"]
                else:
                    overlays["danger"] = [report["aim"]]
                self.renderer.setOverlays(overlays)
            return report["legal"]
        except (AbilityError, ValueError, KeyError, RuntimeError) as exc:
            if self.renderer is not None:
                self.renderer.clearOverlays()
            self.diagnostics.setPlainText(
                "Aperçu natif refusé : " + getattr(exc, "code", "invalid") +
                " — " + str(exc))
            return False


__all__ = ["NativeTargetingDialog"]
