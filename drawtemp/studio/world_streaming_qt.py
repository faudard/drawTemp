"""R54.B World Streaming Inspector — Qt Widgets metadata preview and authoring.

The dialog holds only a draft. Changes are committed through the active
AuthoringSession (one Undo/Redo transaction). Its cache loads safe scene
metadata, not assets or gameplay objects; GameSession remains untouched.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from drawtemp.studio.world_streaming_authoring import (
    DEFAULT_CACHE_BYTES, apply_streaming, inspect_streaming,
    manifest_from_routes, preview_streaming, prefetch_order,
)
from sporebound.world_streaming import EXTENSION, WorldCellCache


class WorldStreamingDialog(QDialog):
    """No-JSON R54 cell inspector with deterministic LOD and bounded prefetch."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._pending_preview = None
        self._tickets = {}
        self.cache = None
        self.document = None
        self._project = {}
        self._source_revision = None
        self.setObjectName("r54-world-inspector")
        self.setWindowTitle("World Streaming Inspector • R54.B")
        self.resize(1060, 720)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Cellules R25, liens, régions et budget. "
            "LOD = aperçu conceptuel ; cache = métadonnées, pas textures GPU.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        first = QHBoxLayout()
        self.generate = QPushButton("Construire depuis les portails R25")
        self.generate.setObjectName("r54-generate")
        self.generate.clicked.connect(self.generate_from_routes)
        first.addWidget(self.generate)
        self.reload = QPushButton("Actualiser le projet")
        self.reload.setObjectName("r54-reload")
        self.reload.clicked.connect(self.reload_from_project)
        first.addWidget(self.reload)
        first.addWidget(QLabel("Vue"))
        self.zoom = QComboBox()
        self.zoom.setObjectName("r54-zoom")
        for caption, value in (("25 %", 0.25), ("50 %", 0.5),
                               ("100 %", 1.0), ("200 %", 2.0)):
            self.zoom.addItem(caption, value)
        self.zoom.setCurrentIndex(2)
        self.zoom.currentIndexChanged.connect(self.render)
        first.addWidget(self.zoom)
        root.addLayout(first)

        body = QHBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setObjectName("r54-cell-tree")
        self.tree.setAccessibleName("Cellules et niveaux de détail du monde")
        self.tree.setHeaderLabels(["Cellule", "Région", "Scène", "LOD", "Voisins", "État"])
        self.tree.setMinimumWidth(460)
        self.tree.currentItemChanged.connect(self._on_selected)
        body.addWidget(self.tree, 2)
        self.graph = QGraphicsView()
        self.graph.setObjectName("r54-graph-view")
        self.graph.setAccessibleName("Prévisualisation des liens entre cellules")
        self.graph.setScene(QGraphicsScene(self.graph))
        body.addWidget(self.graph, 2)
        root.addLayout(body, 1)

        editor = QFormLayout()
        self.region = QLineEdit()
        self.region.setObjectName("r54-region")
        self.region.setPlaceholderText("Identifiant de région (ASCII, sans espace)")
        self.region.textEdited.connect(self._mark_dirty)
        editor.addRow("Région sélectionnée", self.region)
        self.update_region = QPushButton("Modifier région (brouillon)")
        self.update_region.setObjectName("r54-change-region")
        self.update_region.clicked.connect(self.change_region)
        editor.addRow(self.update_region)
        options = QWidget()
        row = QHBoxLayout(options)
        row.setContentsMargins(0, 0, 0, 0)
        self.budget = QSpinBox()
        self.budget.setObjectName("r54-budget-mib")
        self.budget.setRange(1, 32)
        self.budget.setSuffix(" MiB")
        self.budget.valueChanged.connect(self._budget_changed)
        row.addWidget(self.budget)
        self.prefetch = QPushButton("Précharger autour (métadonnées)")
        self.prefetch.setObjectName("r54-prefetch")
        self.prefetch.clicked.connect(self.prefetch_neighbors)
        row.addWidget(self.prefetch)
        editor.addRow("Budget du cache", options)
        root.addLayout(editor)

        self.status = QLabel("")
        self.status.setObjectName("r54-cache-status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r54-diagnostics")
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(135)
        root.addWidget(self.diagnostics)

        footer = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser les changements")
        self.preview_button.setObjectName("r54-preview")
        self.preview_button.clicked.connect(self.preview_changes)
        footer.addWidget(self.preview_button)
        self.apply_button = QPushButton("Appliquer (1 Undo)")
        self.apply_button.setObjectName("r54-apply")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        footer.addWidget(self.apply_button)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._poll)
        self.reload_from_project()

    def _error(self, exc):
        self.diagnostics.setPlainText(str(exc))
        QMessageBox.warning(self, "World Streaming R54", str(exc))

    def _mark_dirty(self, *_):
        self._pending_preview = None
        self.apply_button.setEnabled(False)

    def _close_cache(self):
        self.timer.stop()
        self._tickets.clear()
        if self.cache is not None:
            self.cache.close()
            self.cache = None

    def _budget_changed(self, value):
        if self.document is not None:
            self.document["max_cache_bytes"] = value * 1024 * 1024
            self._cache_metadata()
        self._mark_dirty()
        self.render()

    def _cache_metadata(self):
        self._close_cache()
        if self.document is None:
            return
        # Trusted detached R25 stage geometry, never external files.
        stages = {
            ident: (stage["width"], stage["height"],
                    len(stage.get("blocked", [])))
            for ident, stage in self._project["exploration"].items()}

        def loader(cell):
            width, height, blocked = stages[cell["scene"]]
            return {"id": cell["id"], "scene": cell["scene"],
                    "size": [width, height], "blocked": blocked}

        self.cache = WorldCellCache(self.document, loader, workers=2)

    def reload_from_project(self):
        snap = self.session.snapshot().to_dict()
        self._project = snap["project"]
        self._source_revision = snap["revision"]
        envelope = self._project.get("extensions", {}).get(EXTENSION)
        self.document = deepcopy(envelope["data"]) if envelope else None
        self._mark_dirty()
        self.budget.blockSignals(True)
        self.budget.setValue(
            max(1, self.document["max_cache_bytes"] // (1024 * 1024))
            if self.document else 4)
        self.budget.blockSignals(False)
        self._cache_metadata()
        self.render()

    def generate_from_routes(self):
        try:
            self.document = manifest_from_routes(
                self._project,
                max_cache_bytes=self.budget.value() * 1024 * 1024)
            self._mark_dirty()
            self._cache_metadata()
            self.render()
            self.diagnostics.setPlainText(
                "Brouillon généré depuis les portails bidirectionnels R25. "
                "Les scènes non reliées ne sont pas intégrées. "
                "Vérifiez puis appliquez (Undo/Redo).")
        except Exception as exc:
            self._error(exc)

    def _focus(self):
        item = self.tree.currentItem()
        if item is not None:
            return item.data(0, Qt.UserRole)
        return self.document["start"] if self.document is not None else None

    def _on_selected(self, current, _previous):
        cell_id = current.data(0, Qt.UserRole) if current else None
        cell = next((row for row in self.document["cells"]
                     if row["id"] == cell_id), None) if self.document else None
        self.region.blockSignals(True)
        self.region.setText(cell["region"] if cell else "")
        self.region.blockSignals(False)
        self.render()

    def change_region(self):
        if self.document is None or self._focus() is None:
            return
        cell_id, region = self._focus(), self.region.text().strip()
        try:
            candidate = deepcopy(self.document)
            for cell in candidate["cells"]:
                if cell["id"] == cell_id:
                    cell["region"] = region
                    break
            inspect_streaming(candidate, self._project, focus=cell_id)
            self.document = candidate
            self._mark_dirty()
            self.render()
        except Exception as exc:
            self._error(exc)

    def render(self, *_):
        if self.document is None:
            self.tree.clear()
            self.graph.scene().clear()
            self.diagnostics.setPlainText(
                "Aucune configuration R54. Créez d'abord des portails R25 "
                "réciproques, puis choisissez Construire.")
            self.status.setText("Cache désactivé")
            return
        focus = self._focus()
        if focus not in {cell["id"] for cell in self.document["cells"]}:
            focus = self.document["start"]
        try:
            report = inspect_streaming(
                self.document, self._project,
                focus=focus,
                zoom=self.zoom.currentData(),
                cache_stats=self.cache.stats() if self.cache else None)
        except Exception as exc:
            self.diagnostics.setPlainText(str(exc))
            return
        self.tree.blockSignals(True)
        self.tree.clear()
        loaded = set(report["cache"]["loaded"])
        for cell in report["cells"]:
            item = QTreeWidgetItem([
                cell["id"], cell["region"], cell["scene"],
                cell["lod"], ", ".join(cell["neighbors"]),
                "RAM" if cell["id"] in loaded else "hors cache"])
            item.setData(0, Qt.UserRole, cell["id"])
            self.tree.addTopLevelItem(item)
            if cell["id"] == report["focus"]:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        self._draw_graph(report)
        self.status.setText(
            f"Cache : {report['cache']['resident_bytes']} / "
            f"{report['cache']['budget_bytes']} octets • "
            f"{len(loaded)} cellules en RAM • "
            f"{report['cache']['pending']} tickets en attente")
        self.diagnostics.setPlainText(
            f"Cellules : {len(report['cells'])} | "
            f"Liens : {len(report['edges'])} | "
            f"Régions : {len({c['region'] for c in report['cells']})}\n"
            f"Préchargement suggéré : {', '.join(report['prefetch'])}\n"
            f"Estimation métadonnées grille : {report['estimated_total_bytes']} octets\n"
            f"Scènes non représentées : {', '.join(report['excluded_scenes']) or 'aucune'}\n"
            + report["note"])

    def _draw_graph(self, report):
        scene = self.graph.scene()
        scene.clear()
        positions = {cell["id"]: cell["position"] for cell in report["cells"]}
        for edge in report["edges"]:
            a, b = positions[edge["from"]], positions[edge["to"]]
            scene.addLine(a[0] + 60, a[1] + 25,
                          b[0] + 60, b[1] + 25,
                          QPen(QColor("#8792a5"), 2))
        colors = {"detail": "#357fbd", "overview": "#7c8da5",
                  "outline": "#9ba1ac"}
        for cell in report["cells"]:
            x, y = cell["position"]
            lod = cell["lod"]
            if lod == "outline":
                scene.addEllipse(x + 45, y + 12, 30, 26,
                                 QPen(QColor("#303845")),
                                 QBrush(QColor(colors[lod])))
                label = scene.addText(cell["id"])
                label.setDefaultTextColor(QColor("#b6becb"))
                label.setPos(x + 12, y + 44)
                continue
            scene.addRect(x, y, 120, 50,
                          QPen(QColor("#303845")),
                          QBrush(QColor(colors[lod])))
            label = scene.addText(cell["id"])
            label.setDefaultTextColor(QColor("#ffffff"))
            label.setPos(x + 4, y - 3)
            if lod == "overview":
                caption = scene.addText(
                    cell["region"] + " • " +
                    str(cell["map_size"][0]) + "×" +
                    str(cell["map_size"][1]))
                caption.setDefaultTextColor(QColor("#ffffff"))
                caption.setPos(x + 4, y + 22)
            elif lod == "detail":
                for line, values in enumerate(cell["tile_preview"]):
                    for col, value in enumerate(values):
                        scene.addRect(
                            x + 8 + col * 9, y + 23 + line * 6, 8, 5,
                            QPen(Qt.NoPen),
                            QBrush(QColor(
                                "#455363" if value == "#" else "#c8e1c2")))
        scene.setSceneRect(scene.itemsBoundingRect())

    def prefetch_neighbors(self):
        if self.document is None or self.cache is None:
            return
        try:
            self.timer.stop()
            for token in list(self._tickets):
                self.cache.cancel(token)
            self._tickets.clear()
            for ident in prefetch_order(self.document, self._focus()):
                ticket = self.cache.request(ident)
                if ticket is not None:
                    self._tickets[ticket] = ident
            if self._tickets:
                self.timer.start()
            self.render()
        except Exception as exc:
            self._error(exc)

    def _poll(self):
        if self.cache is None:
            self.timer.stop()
            return
        changed = False
        for token in list(self._tickets):
            try:
                result = self.cache.resolve(token, timeout=0)
            except Exception as exc:
                self._tickets.pop(token, None)
                self.diagnostics.setPlainText(str(exc))
                changed = True
                continue
            if result is not None:
                self._tickets.pop(token, None)
                changed = True
        if not self._tickets:
            self.timer.stop()
        if changed:
            self.render()

    def preview_changes(self):
        if self.document is None:
            return
        try:
            candidate = deepcopy(self.document)
            candidate["max_cache_bytes"] = self.budget.value() * 1024 * 1024
            pending = preview_streaming(
                self.session, candidate,
                expected_revision=self._source_revision)
            self._pending_preview = pending
            self.apply_button.setEnabled(True)
            self.diagnostics.setPlainText(
                f"Prévisualisation R1 valide à la révision "
                f"{pending.report['source_revision']} • "
                f"{pending.report['cells']} cellules. "
                "Appliquer crée une seule transaction Undo/Redo.")
        except Exception as exc:
            self._mark_dirty()
            self._error(exc)

    def apply_changes(self):
        if self._pending_preview is None:
            return
        try:
            apply_streaming(self.session, self._pending_preview)
            self.reload_from_project()
            self.diagnostics.setPlainText(
                "R54 enregistré dans le GameProject canonique ; "
                "Undo/Redo disponible dans le Studio.")
        except Exception as exc:
            self._mark_dirty()
            self._error(exc)

    def done(self, result):
        self._close_cache()
        super().done(result)

    def closeEvent(self, event):
        self._close_cache()
        super().closeEvent(event)
