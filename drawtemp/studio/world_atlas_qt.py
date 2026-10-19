"""R44.B — visual regional World Atlas, using the canonical R1 Studio owner.

QGraphicsScene is only a graph diagram. Gameplay rendering/transition stays
in the shared Player/Studio renderer and R25 SceneRouter.
"""
from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.world_atlas_authoring import (
    apply_world_atlas, assign_scene, default_portal_source,
    default_world_atlas, edit_object, edit_portal, place_scene,
    preview_world_atlas, set_region,
)
from sporebound.model import RuleError
from sporebound.world_graph44 import BIOMES, EXTENSION, OBJECT_KINDS, PROJECTIONS


class WorldAtlasDialog(QDialog):
    """Author regions, scene placement, portal annotations and persistent flags."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setObjectName("r44_world_atlas")
        self.setWindowTitle("R44 • World Atlas 2.0")
        self.resize(1050, 720)
        self.session = session
        self._revision = -1
        self._draft = None
        self._pending = None
        self._syncing = False
        self._routes = {}
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(
            "Régions et routes R25 existantes • modifications validées avant Apply. "
            "Le graphe ne déclenche aucune transition du Player."))
        splitter = QSplitter(Qt.Horizontal)
        self.canvas = QGraphicsView()
        self.canvas.setObjectName("r44_atlas_graph")
        self.graph_scene = QGraphicsScene(self)
        self.canvas.setScene(self.graph_scene)
        splitter.addWidget(self.canvas)

        panel = QWidget()
        formbox = QVBoxLayout(panel)
        self.scenes = QListWidget()
        self.scenes.setObjectName("r44_scene_list")
        self.scenes.currentRowChanged.connect(self._load_scene)
        formbox.addWidget(QLabel("Scènes (sélectionner pour inspecter)"))
        formbox.addWidget(self.scenes)

        form = QFormLayout()
        self.region = QComboBox()
        self.region.setObjectName("r44_region_select")
        form.addRow("Région de la scène", self.region)
        self.x = QSpinBox()
        self.y = QSpinBox()
        for widget in (self.x, self.y):
            widget.setRange(0, 100000)
            widget.valueChanged.connect(self._move_scene)
        form.addRow("Origine X", self.x)
        form.addRow("Origine Y", self.y)
        self.biome = QComboBox()
        self.biome.addItems(sorted(BIOMES))
        self.projection = QComboBox()
        self.projection.addItems(sorted(PROJECTIONS))
        form.addRow("Biome de la région", self.biome)
        form.addRow("Projection", self.projection)
        self.biome.currentTextChanged.connect(self._edit_region)
        self.projection.currentTextChanged.connect(self._edit_region)
        formbox.addLayout(form)

        buttons = QHBoxLayout()
        move = QPushButton("Déplacer vers région")
        move.clicked.connect(self._assign_scene)
        buttons.addWidget(move)
        create = QPushButton("Nouvelle région…")
        create.clicked.connect(self._create_region)
        buttons.addWidget(create)
        formbox.addLayout(buttons)

        formbox.addWidget(QLabel("Passages R25 disponibles"))
        self.portals = QListWidget()
        self.portals.setObjectName("r44_portal_list")
        self.portals.currentRowChanged.connect(self._load_portal)
        formbox.addWidget(self.portals)
        self.include = QCheckBox("Inclure dans l'atlas")
        self.include.stateChanged.connect(self._toggle_portal)
        formbox.addWidget(self.include)
        portform = QFormLayout()
        self.cost = QSpinBox()
        self.cost.setRange(1, 10000)
        self.cost.valueChanged.connect(self._edit_portal)
        portform.addRow("Coût du trajet", self.cost)
        self.from_x = QSpinBox()
        self.from_y = QSpinBox()
        for widget in (self.from_x, self.from_y):
            widget.setRange(0, 100000)
            widget.valueChanged.connect(self._edit_portal)
        portform.addRow("Sortie X", self.from_x)
        portform.addRow("Sortie Y", self.from_y)
        formbox.addLayout(portform)
        self.condition = QLabel("")
        self.condition.setWordWrap(True)
        formbox.addWidget(self.condition)

        self.object_id = QLineEdit()
        self.object_id.setPlaceholderText("Identifiant de l'objet")
        self.object_kind = QComboBox()
        self.object_kind.addItems(sorted(OBJECT_KINDS))
        self.object_flag = QLineEdit()
        self.object_flag.setPlaceholderText("world44_coffre_ouvert")
        object_line = QHBoxLayout()
        object_line.addWidget(self.object_id)
        object_line.addWidget(self.object_kind)
        object_line.addWidget(self.object_flag)
        formbox.addWidget(QLabel("Objet persistant de la scène sélectionnée"))
        formbox.addLayout(object_line)
        save_object = QPushButton("Ajouter / modifier l'objet")
        save_object.clicked.connect(self._upsert_object)
        formbox.addWidget(save_object)
        splitter.addWidget(panel)
        splitter.setSizes([630, 420])
        outer.addWidget(splitter, 1)

        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setObjectName("r44_validation_report")
        self.report.setMaximumHeight(100)
        outer.addWidget(self.report)
        bar = QHBoxLayout()
        for label, action in (
            ("Prévisualiser/valider", self.preview),
            ("Appliquer (1 Undo)", self.apply),
            ("Annuler", self.undo),
            ("Rétablir", self.redo),
            ("Actualiser", self.refresh),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            bar.addWidget(button)
            if label.startswith("Appliquer"):
                self.apply_button = button
        outer.addLayout(bar)
        self.apply_button.setEnabled(False)
        self.refresh()

    def _snapshot(self):
        return self.session.snapshot().to_dict()

    def _scene_id(self):
        row = self.scenes.currentItem()
        return row.data(Qt.UserRole) if row else None

    def _portal_id(self):
        row = self.portals.currentItem()
        return row.data(Qt.UserRole) if row else None

    def _region_for(self, scene_id):
        return next((r for r in self._draft["regions"]
                     if any(s["id"] == scene_id for s in r["scenes"])), None)

    def _scene_entry(self, scene_id):
        region = self._region_for(scene_id)
        return next(s for s in region["scenes"] if s["id"] == scene_id)

    def _changed(self, candidate):
        self._draft = candidate
        self._pending = None
        self.apply_button.setEnabled(False)
        self.report.setPlainText("Brouillon modifié. Prévisualiser pour valider.")
        self._draw()

    def refresh(self):
        prior_scene, prior_route = self._scene_id(), self._portal_id()
        self._syncing = True
        try:
            state = self._snapshot()
            self._revision = state["revision"]
            project = state["project"]
            self._routes = {r["id"]: r for r in
                            project.get("scene_routes", {}).get("links", [])}
            extension = project.get("extensions", {}).get(EXTENSION)
            self._draft = deepcopy(extension["data"]) if extension else (
                default_world_atlas(self.session))
            self._pending = None
            self.scenes.clear()
            for region in self._draft["regions"]:
                for scene in region["scenes"]:
                    self.scenes.addItem(scene["id"])
                    self.scenes.item(self.scenes.count() - 1).setData(
                        Qt.UserRole, scene["id"])
            self.portals.clear()
            for ident, link in sorted(self._routes.items()):
                self.portals.addItem(
                    f'{ident}: {link["source"]} → {link["destination"]}')
                self.portals.item(self.portals.count()-1).setData(
                    Qt.UserRole, ident)
            self.scenes.setCurrentRow(max(0, next((
                i for i in range(self.scenes.count())
                if self.scenes.item(i).data(Qt.UserRole) == prior_scene), 0)))
            self.portals.setCurrentRow(max(0, next((
                i for i in range(self.portals.count())
                if self.portals.item(i).data(Qt.UserRole) == prior_route), 0)))
            self.report.setPlainText(
                "Projet chargé. Cliquez sur Prévisualiser pour valider "
                "l'initialisation et les modifications.")
            self._draw()
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            self._draft = None
            self.report.setPlainText("Atlas indisponible : " + str(exc))
        finally:
            self._syncing = False
        self._load_scene()
        self._load_portal()
        self.apply_button.setEnabled(False)

    def _load_scene(self, *_):
        if self._draft is None:
            return
        sid = self._scene_id()
        if sid is None:
            return
        previous = self._syncing
        self._syncing = True
        try:
            region = self._region_for(sid)
            scene = self._scene_entry(sid)
            self.region.clear()
            for row in self._draft["regions"]:
                self.region.addItem(row["title"], row["id"])
            self.region.setCurrentIndex(self.region.findData(region["id"]))
            self.x.setValue(scene["origin"][0])
            self.y.setValue(scene["origin"][1])
            self.biome.setCurrentText(region["biome"])
            self.projection.setCurrentText(region["projection"])
        finally:
            self._syncing = previous

    def _load_portal(self, *_):
        if self._draft is None:
            return
        ident = self._portal_id()
        if ident is None:
            return
        previous = self._syncing
        self._syncing = True
        try:
            portal = next((p for p in self._draft["portals"]
                           if p["route"] == ident), None)
            self.include.setChecked(portal is not None)
            if portal:
                self.cost.setValue(portal["travel_cost"])
                self.from_x.setValue(portal["source"][0])
                self.from_y.setValue(portal["source"][1])
            link = self._routes[ident]
            self.condition.setText(
                "Condition R25 : " + json.dumps(
                    link.get("when", True), ensure_ascii=False))
        finally:
            self._syncing = previous

    def _guard_edit(self, operation):
        if self._syncing or self._draft is None:
            return
        try:
            self._changed(operation())
        except (RuleError, ValueError, TypeError, KeyError) as exc:
            self.report.setPlainText("Modification refusée : " + str(exc))
            self._load_scene()
            self._load_portal()

    def _move_scene(self, *_):
        sid = self._scene_id()
        if sid is not None:
            self._guard_edit(lambda: place_scene(
                self._draft, sid, [self.x.value(), self.y.value()]))

    def _edit_region(self, *_):
        sid = self._scene_id()
        if sid is not None:
            self._guard_edit(lambda: set_region(
                self._draft, self._region_for(sid)["id"],
                biome=self.biome.currentText(),
                projection=self.projection.currentText()))

    def _assign_scene(self):
        sid, region_id = self._scene_id(), self.region.currentData()
        if sid and region_id:
            self._guard_edit(lambda: assign_scene(self._draft, sid, region_id))
            self._load_scene()

    def _create_region(self):
        sid = self._scene_id()
        if sid is None:
            return
        ident, ok = QInputDialog.getText(
            self, "Nouvelle région", "Identifiant stable (lettres/chiffres/_/-) :")
        if ok and ident:
            self._guard_edit(lambda: assign_scene(
                self._draft, sid, ident.strip()))
            self._load_scene()

    def _toggle_portal(self, *_):
        ident = self._portal_id()
        if ident is None:
            return
        state = self._snapshot()
        def transform():
            source = default_portal_source(
                state["content"], state["project"], self._routes[ident]["source"])
            return edit_portal(self._draft, ident,
                               enabled=self.include.isChecked(),
                               default_source=source)
        self._guard_edit(transform)
        self._load_portal()

    def _edit_portal(self, *_):
        ident = self._portal_id()
        if ident and self.include.isChecked():
            self._guard_edit(lambda: edit_portal(
                self._draft, ident,
                source=[self.from_x.value(), self.from_y.value()],
                travel_cost=self.cost.value()))

    def _upsert_object(self):
        sid = self._scene_id()
        if sid:
            self._guard_edit(lambda: edit_object(
                self._draft, sid, self.object_id.text().strip(),
                self.object_kind.currentText(), self.object_flag.text().strip()))

    def _draw(self):
        self.graph_scene.clear()
        if not self._draft:
            return
        lookup = {}
        for region in self._draft["regions"]:
            for entry in region["scenes"]:
                lookup[entry["id"]] = entry["origin"]
        for p in self._draft["portals"]:
            link = self._routes.get(p["route"])
            if not link:
                continue
            a, b = lookup.get(link["source"]), lookup.get(link["destination"])
            if a is not None and b is not None:
                self.graph_scene.addLine(a[0]*6, a[1]*6, b[0]*6, b[1]*6,
                                         QPen(QColor("#8793aa"), 2))
        for region in self._draft["regions"]:
            for entry in region["scenes"]:
                x, y = (v*6 for v in entry["origin"])
                selected = entry["id"] == self._scene_id()
                pen = QPen(QColor("#2563eb" if selected else "#505d70"), 2)
                brush = QBrush(QColor("#dbeafe" if selected else "#edf0f5"))
                self.graph_scene.addEllipse(x-8, y-8, 16, 16, pen, brush)
                label = self.graph_scene.addText(entry["id"] + " (" + region["id"] + ")")
                label.setPos(x+10, y-11)
        self.canvas.fitInView(self.graph_scene.itemsBoundingRect().adjusted(
            -30, -30, 30, 30), Qt.KeepAspectRatio)

    def preview(self):
        if self._draft is None:
            return
        self._pending = None
        self.apply_button.setEnabled(False)
        try:
            self._pending = preview_world_atlas(
                self.session, self._draft, expected_revision=self._revision)
            self.report.setPlainText(json.dumps(
                self._pending.report, ensure_ascii=False, indent=2))
            self.apply_button.setEnabled(self._pending.report["changed"])
        except (AuthoringError, RuleError, ValueError) as exc:
            self.report.setPlainText("Validation refusée : " + str(exc))

    def apply(self):
        if self._pending is None:
            return
        try:
            apply_world_atlas(self.session, self._pending)
        except (AuthoringError, RuleError, ValueError) as exc:
            self._pending = None
            self.apply_button.setEnabled(False)
            self.report.setPlainText("Apply refusé : " + str(exc))
            return
        self.refresh()

    def undo(self):
        try:
            self.session.undo()
            self.refresh()
        except AuthoringError as exc:
            self.report.setPlainText(str(exc))

    def redo(self):
        try:
            self.session.redo()
            self.refresh()
        except AuthoringError as exc:
            self.report.setPlainText(str(exc))


__all__ = ["WorldAtlasDialog"]
