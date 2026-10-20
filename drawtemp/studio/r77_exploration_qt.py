"""R77.B Qt Widgets Exploration Lab for explicit R26 scene review.

Only reads an author-selected R26 JSON scene; never changes the canonical
AuthoringSession. Offscreen tests are API-only, not an onscreen/UX certificate.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.quality.r77_exploratory import explore_action_scene
from drawtemp.quality.r77_lab import (
    REVIEW_CHOICES, build_lab_view, compare_lab_views, minimize_runtime_failure,
    triage_finding,
)
from drawtemp.studio.workspace_model import resources
from sporebound.action_runtime import validate_scene

MAX_SCENE_BYTES = 256 * 1024
HEAT_WINDOW = 24


class ExplorationLabDialog(QDialog):
    """Standalone R26 JSON analysis, with optional exact-ID Studio deep links."""

    def __init__(self, owner=None, *, scene=None):
        super().__init__(owner)
        self.owner = owner
        self.scene = None
        self.view = None
        self.report = None
        self.reference = None  # Verified in-memory view from an earlier run.
        self.reviews = {}
        self.comparison = None
        self.setObjectName("r77-exploration-lab")
        self.setWindowTitle("R77.B • Exploration Lab (R26, non certifié)")
        self.resize(1000, 740)
        outer = QVBoxLayout(self)
        intro = QLabel(
            "Exploration déterministe du vrai runtime R26. Les risques R29 sont "
            "abstraits ; la validation humaine, le GPU et le Player ne sont PAS certifiés.")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        settings = QFormLayout()
        pick = QHBoxLayout()
        self.scene_label = QLabel("Aucune scène R26 sélectionnée")
        self.scene_label.setObjectName("r77-scene-label")
        pick.addWidget(self.scene_label, 1)
        choose = QPushButton("Charger scène R26 JSON…")
        choose.setObjectName("r77-choose-scene")
        choose.clicked.connect(self.choose_scene)
        pick.addWidget(choose)
        settings.addRow("Scène", pick)
        self.goals = QLineEdit("3,2")
        self.goals.setObjectName("r77-goals")
        self.goals.setAccessibleName("Cellules objectif, séparées par un point-virgule")
        self.goals.setPlaceholderText("3,2;4,3")
        settings.addRow("Objectifs (x,y;x,y)", self.goals)
        self.seeds = QLineEdit("0,1,2")
        self.seeds.setObjectName("r77-seeds")
        self.seeds.setAccessibleName("Seeds entiers d'exploration")
        settings.addRow("Seeds (1 à 8)", self.seeds)
        limits = QHBoxLayout()
        self.ticks = QSpinBox()
        self.ticks.setObjectName("r77-ticks")
        self.ticks.setRange(1, 512)
        self.ticks.setValue(128)
        self.ticks.setAccessibleName("Ticks maximum par seed")
        limits.addWidget(QLabel("Ticks par seed"))
        limits.addWidget(self.ticks)
        self.state_budget = QSpinBox()
        self.state_budget.setObjectName("r77-state-budget")
        self.state_budget.setRange(1, 200000)
        self.state_budget.setValue(5000)
        self.state_budget.setAccessibleName("Budget d'états R29")
        limits.addWidget(QLabel("États R29"))
        limits.addWidget(self.state_budget)
        settings.addRow("Budgets", limits)
        outer.addLayout(settings)

        controls = QHBoxLayout()
        self.analyze_button = QPushButton("Exécuter l'exploration")
        self.analyze_button.setObjectName("r77-run")
        self.analyze_button.clicked.connect(self.analyze)
        self.analyze_button.setEnabled(False)
        controls.addWidget(self.analyze_button)
        self.pin_button = QPushButton("Geler comme référence")
        self.pin_button.setObjectName("r77-pin")
        self.pin_button.clicked.connect(self.pin_reference)
        self.pin_button.setEnabled(False)
        controls.addWidget(self.pin_button)
        self.map_button = QPushButton("Ouvrir la carte Studio")
        self.map_button.setObjectName("r77-open-map")
        self.map_button.clicked.connect(lambda: self.open_resource("maps"))
        controls.addWidget(self.map_button)
        self.graph_button = QPushButton("Ouvrir le graphe Studio")
        self.graph_button.setObjectName("r77-open-graph")
        self.graph_button.clicked.connect(lambda: self.open_resource("scenes"))
        controls.addWidget(self.graph_button)
        outer.addLayout(controls)

        self.status = QLabel("Chargez une scène R26 ; aucune analyse n'a été exécutée.")
        self.status.setWordWrap(True)
        self.status.setObjectName("r77-status")
        self.status.setAccessibleName("Résultat de l'exploration R77")
        outer.addWidget(self.status)

        tabs = QTabWidget()
        self.tabs = tabs
        outer.addWidget(tabs, 1)

        heat = QWidget()
        heat_layout = QVBoxLayout(heat)
        self.heat_label = QLabel("Aucune occupation disponible")
        heat_layout.addWidget(self.heat_label)
        viewport = QHBoxLayout()
        self.x_offset = QSpinBox()
        self.y_offset = QSpinBox()
        for name, field in (("x", self.x_offset), ("y", self.y_offset)):
            field.setObjectName("r77-offset-" + name)
            field.setAccessibleName("Décalage " + name + " de la heatmap")
            field.valueChanged.connect(self.draw_heatmap)
            viewport.addWidget(QLabel("Décalage " + name))
            viewport.addWidget(field)
        heat_layout.addLayout(viewport)
        self.heatmap = QTableWidget()
        self.heatmap.setObjectName("r77-heatmap")
        self.heatmap.setAccessibleName("Heatmap des visites par cellule et seed")
        self.heatmap.setEditTriggers(QTableWidget.NoEditTriggers)
        self.heatmap.cellClicked.connect(self.select_heat_cell)
        heat_layout.addWidget(self.heatmap, 1)
        self.cell_info = QLabel("")
        self.cell_info.setObjectName("r77-cell-info")
        heat_layout.addWidget(self.cell_info)
        tabs.addTab(heat, "Heatmap")

        trace = QWidget()
        trace_layout = QHBoxLayout(trace)
        left = QVBoxLayout()
        self.runs = QListWidget()
        self.runs.setObjectName("r77-runs")
        self.runs.setAccessibleName("Parcours exploratoires par seed")
        self.runs.currentRowChanged.connect(self.show_run)
        left.addWidget(QLabel("Parcours"))
        left.addWidget(self.runs)
        self.paths = QListWidget()
        self.paths.setObjectName("r77-critical-paths")
        self.paths.setAccessibleName("Plus courts chemins statiques R29")
        self.paths.currentRowChanged.connect(self.show_path)
        left.addWidget(QLabel("Chemins critiques (R29 abstrait)"))
        left.addWidget(self.paths)
        trace_layout.addLayout(left, 1)
        right = QVBoxLayout()
        self.steps = QListWidget()
        self.steps.setObjectName("r77-steps")
        self.steps.setAccessibleName("Timeline tick et commandes reproductibles")
        right.addWidget(QLabel("Timeline de reproduction"))
        right.addWidget(self.steps, 2)
        self.witness = QPlainTextEdit()
        self.witness.setReadOnly(True)
        self.witness.setObjectName("r77-witness")
        self.witness.setAccessibleName("Témoin et statut de reproduction")
        right.addWidget(self.witness, 1)
        trace_layout.addLayout(right, 2)
        tabs.addTab(trace, "Traces / chemins")

        review = QWidget()
        review_layout = QVBoxLayout(review)
        self.findings = QListWidget()
        self.findings.setObjectName("r77-findings")
        self.findings.setAccessibleName("Constats à qualifier humainement")
        self.findings.currentRowChanged.connect(self.show_finding)
        review_layout.addWidget(self.findings, 2)
        self.minimize_button = QPushButton("Réduire le reproducteur R26 (si exception)")
        self.minimize_button.setObjectName("r77-minimize")
        self.minimize_button.setEnabled(False)
        self.minimize_button.clicked.connect(self.minimize_selected)
        review_layout.addWidget(self.minimize_button)
        self.review_type = QComboBox()
        self.review_type.setObjectName("r77-review-decision")
        for choice in REVIEW_CHOICES:
            self.review_type.addItem(choice.replace("_", " "), choice)
        review_layout.addWidget(self.review_type)
        self.reason = QPlainTextEdit()
        self.reason.setPlaceholderText("Justification humaine (au moins 8 caractères)")
        self.reason.setObjectName("r77-review-reason")
        review_layout.addWidget(self.reason, 1)
        annotate = QPushButton("Qualifier le constat (mémoire locale)")
        annotate.setObjectName("r77-review-save")
        annotate.clicked.connect(self.annotate)
        review_layout.addWidget(annotate)
        self.review_status = QLabel("Aucune qualification enregistrée.")
        self.review_status.setWordWrap(True)
        self.review_status.setObjectName("r77-review-status")
        review_layout.addWidget(self.review_status)
        tabs.addTab(review, "Faux positifs / revue")

        compare = QWidget()
        compare_layout = QVBoxLayout(compare)
        self.compare_details = QPlainTextEdit()
        self.compare_details.setReadOnly(True)
        self.compare_details.setObjectName("r77-comparison")
        self.compare_details.setPlainText(
            "Gelez une référence, chargez une seconde scène R26 et relancez l'analyse. "
            "La comparaison reste exploratoire, sans verdict de régression.")
        compare_layout.addWidget(self.compare_details)
        tabs.addTab(compare, "Comparer versions")

        close = QPushButton("Fermer sans modifier le projet")
        close.clicked.connect(self.accept)
        outer.addWidget(close)
        if scene is not None:
            self.set_scene(scene)
        else:
            self._refresh_navigation()

    def _refresh_navigation(self):
        available = {"maps": False, "scenes": False}
        if self.scene is not None and self.owner is not None:
            session = getattr(self.owner, "session", None)
            if session is not None:
                for item in resources(session.snapshot()):
                    if (item.family in available and
                            item.resource_id == self.scene["id"]):
                        available[item.family] = True
        self.map_button.setEnabled(available["maps"])
        self.graph_button.setEnabled(available["scenes"])

    def set_scene(self, scene):
        """A detached in-memory R26 scene; caller retains ownership."""
        self.scene = validate_scene(deepcopy(scene))
        self.view = None
        self.report = None
        self.reviews = {}
        self.comparison = None
        self.scene_label.setText(self.scene["id"] +
                                 f" ({self.scene['width']}×{self.scene['height']})")
        self.goals.setText(f"{self.scene['width']-2},{self.scene['height']-2}")
        self.analyze_button.setEnabled(True)
        self.pin_button.setEnabled(False)
        self.status.setText("Scène chargée en lecture seule. Analyse non exécutée.")
        self.heatmap.clear()
        self.heatmap.setRowCount(0)
        self.heatmap.setColumnCount(0)
        self.runs.clear()
        self.paths.clear()
        self.findings.clear()
        self.steps.clear()
        self.witness.clear()
        self._refresh_navigation()

    def load_scene(self, path):
        """Explicit, bounded JSON read; never writes or edits the author file."""
        target = Path(path)
        if not target.is_file() or target.stat().st_size > MAX_SCENE_BYTES:
            raise ValueError("La scène est absente ou dépasse 256 Kio")
        source = target.read_bytes()
        if len(source) > MAX_SCENE_BYTES:
            raise ValueError("La scène dépasse 256 Kio")
        self.set_scene(json.loads(source.decode("utf-8")))
        return self.scene

    def choose_scene(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger une scène ActionRuntime R26", "", "Scène JSON (*.json)")
        if path:
            try:
                self.load_scene(path)
            except (ValueError, OSError, UnicodeError, TypeError) as exc:
                self.status.setText("Lecture refusée : " + str(exc))

    @staticmethod
    def _int_list(text, *, separator):
        pieces = [part.strip() for part in text.split(separator)]
        if not 1 <= len(pieces) <= 8 or any(not item or not item.isascii() or
                                             not item.isdecimal() for item in pieces):
            raise ValueError("Liste numérique invalide")
        return [int(v) for v in pieces]

    def _parameters(self):
        seed_values = self._int_list(self.seeds.text(), separator=",")
        goal_cells = []
        for value in self.goals.text().split(";"):
            coords = self._int_list(value, separator=",")
            if len(coords) != 2:
                raise ValueError("Chaque objectif doit être x,y")
            goal_cells.append(coords)
        if self.scene is None:
            raise ValueError("Scène R26 requise")
        if (not 1 <= len(goal_cells) <= 8 or
                self.ticks.value() * len(seed_values) > 4096):
            raise ValueError("Limite de seeds/objectifs/ticks dépassée")
        return seed_values, goal_cells

    def analyze(self):
        if self.scene is None:
            self.status.setText("Chargez d'abord une scène R26.")
            return None
        self.analyze_button.setEnabled(False)
        try:
            seed_values, goal_cells = self._parameters()
            result = explore_action_scene(
                self.scene, goal_cells, seeds=seed_values,
                ticks_per_seed=self.ticks.value(),
                state_budget=self.state_budget.value(),
            )
            view = build_lab_view(self.scene, result)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            self.status.setText("Exploration refusée : " + str(exc))
            return None
        finally:
            self.analyze_button.setEnabled(True)
        self.report, self.view = result, view
        self.reviews = {}  # Annotations must not leak between evidence versions.
        self.pin_button.setEnabled(True)
        self.status.setText(
            "R77.B : " + result["status"] + " · " +
            str(len(view["coverage"]["zones"])) + " cellules · " +
            str(len(view["findings"])) + " constats · " +
            str(len(view["runs"])) + " seeds. Vérifié headless, non certifié.")
        self.render()
        return view

    def render(self):
        self.draw_heatmap()
        self.runs.clear()
        self.paths.clear()
        self.findings.clear()
        if self.view is None:
            return
        for run in self.view["runs"]:
            self.runs.addItem(f"Seed {run['seed']} · {run['outcome']} · {run['ticks']} ticks")
        for path in self.view["critical_paths"]:
            self.paths.addItem(
                f"{path['goal']} · {path['length']} actions (R29 abstrait)")
        for finding in self.view["findings"]:
            self.findings.addItem(finding["id"] + " · " + finding["kind"])
        if self.runs.count():
            self.runs.setCurrentRow(0)
        if self.findings.count():
            self.findings.setCurrentRow(0)
        self._render_comparison()

    def draw_heatmap(self, *_):
        if self.view is None:
            return
        width, height = self.view["dimensions"]
        x_max, y_max = max(0, width - HEAT_WINDOW), max(0, height - HEAT_WINDOW)
        for field, maximum in ((self.x_offset, x_max), (self.y_offset, y_max)):
            field.blockSignals(True)
            field.setRange(0, maximum)
            field.blockSignals(False)
        left, top = self.x_offset.value(), self.y_offset.value()
        w, h = min(width, HEAT_WINDOW), min(height, HEAT_WINDOW)
        counts = {tuple(row["cell"]): row["visits"] for row in self.view["heatmap"]}
        peak = max(counts.values(), default=1)
        self.heatmap.setUpdatesEnabled(False)
        try:
            self.heatmap.clear()
            self.heatmap.setRowCount(h)
            self.heatmap.setColumnCount(w)
            self.heatmap.setHorizontalHeaderLabels([str(left + x) for x in range(w)])
            self.heatmap.setVerticalHeaderLabels([str(top + y) for y in range(h)])
            for y in range(h):
                for x in range(w):
                    cell = (left + x, top + y)
                    visits = counts.get(cell, 0)
                    item = QTableWidgetItem(str(visits) if visits else "·")
                    shade = int(235 - (visits / peak) * 150) if visits else 250
                    item.setBackground(QColor(shade, shade, 255))
                    item.setForeground(QColor("#141923"))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    item.setToolTip(f"({cell[0]},{cell[1]}) : {visits} visites")
                    self.heatmap.setItem(y, x, item)
            self.heat_label.setText(
                f"{width}×{height} · fenêtre x={left}..{left+w-1}, "
                f"y={top}..{top+h-1} · visites par tick (pas FPS)")
        finally:
            self.heatmap.setUpdatesEnabled(True)

    def select_heat_cell(self, row, column):
        if self.view is None:
            return
        x, y = column + self.x_offset.value(), row + self.y_offset.value()
        match = next((entry for entry in self.view["heatmap"]
                      if entry["cell"] == [x, y]), None)
        visits = match["visits"] if match else 0
        seeds = match["seeds"] if match else []
        self.cell_info.setText(
            f"Cellule ({x}, {y}) : {visits} visites · seeds {seeds}")

    def show_run(self, index):
        self.steps.clear()
        if self.view is None or index < 0 or index >= len(self.view["runs"]):
            return
        run = self.view["runs"][index]
        for row in run["timeline"]:
            command = row["command"]
            line = (f"t={row['tick']} · {row['cell']} · " +
                    (json.dumps(command, sort_keys=True) if command else "spawn"))
            self.steps.addItem(line)
        self.witness.setPlainText(
            f"Seed {run['seed']} · SHA trace : {run['trace_sha256']}\n"
            "Actions réelles, non réduites. Toute tentative de reproduction "
            "doit conserver les ticks et le même digest de scène.")

    def show_path(self, index):
        if self.view is None or index < 0 or index >= len(self.view["critical_paths"]):
            return
        path = self.view["critical_paths"][index]
        self.witness.setPlainText(
            "Chemin BFS statique (PAS une preuve Player) :\n" +
            json.dumps(path, ensure_ascii=False, indent=2))

    def show_finding(self, index):
        if self.view is None or index < 0 or index >= len(self.view["findings"]):
            return
        finding = self.view["findings"][index]
        self.witness.setPlainText(json.dumps(finding, ensure_ascii=False, indent=2))
        self.minimize_button.setEnabled(
            finding["kind"] == "runtime_exception" and
            isinstance(finding.get("failed_command"), dict))
        annotation = self.reviews.get(finding["id"])
        self.reason.setPlainText(annotation["reason"] if annotation else "")
        if annotation:
            self.review_type.setCurrentIndex(
                self.review_type.findData(annotation["decision"]))
        self.review_status.setText(
            ("Qualification humaine : " + annotation["decision"]
             if annotation else "Constat non qualifié · aucune preuve Player."))

    def minimize_selected(self):
        """Explicit bounded reduction; a failed reproduction is not hidden."""
        if (self.view is None or self.report is None or
                self.findings.currentRow() < 0):
            return None
        finding = self.view["findings"][self.findings.currentRow()]
        if finding["kind"] != "runtime_exception" or (
                not isinstance(finding.get("failed_command"), dict)):
            return None
        run = next((row for row in self.report["runs"]
                    if row["seed"] == finding["seed"]), None)
        if run is None:
            return None
        error = next((row for row in run["failures"]
                      if row.get("tick") == finding["tick"] and
                      row.get("command") == finding["failed_command"]), None)
        if error is None:
            return None
        try:
            reduced = minimize_runtime_failure(
                self.scene, run["trace"], finding["failed_command"],
                error_type=error["error_type"], message=error["message"],
                max_replays=32)
        except (ValueError, TypeError) as exc:
            self.witness.setPlainText("Réduction refusée : " + str(exc))
            return None
        self.witness.setPlainText(
            "Reproducteur R26 (" + reduced["status"] + ") ; "
            "réduction bornée non nécessairement globale.\\n" +
            json.dumps(reduced, ensure_ascii=False, indent=2))
        return reduced

    def annotate(self):
        if self.view is None or self.findings.currentRow() < 0:
            self.review_status.setText("Sélectionnez un constat avant la qualification.")
            return None
        finding = self.view["findings"][self.findings.currentRow()]
        try:
            self.reviews = triage_finding(
                self.view, finding["id"], self.review_type.currentData(),
                self.reason.toPlainText(), existing=self.reviews)
        except ValueError as exc:
            self.review_status.setText("Revue refusée : " + str(exc))
            return None
        self.review_status.setText(
            "Qualification locale enregistrée, sans modifier le projet. "
            "Aucune certification implicite.")
        return self.reviews[finding["id"]]

    def pin_reference(self):
        if self.view is None:
            return False
        self.reference = deepcopy(self.view)
        self.compare_details.setPlainText(
            "Référence vérifiée gelée en mémoire. Chargez ou relancez une "
            "autre version de la même scène pour comparer ses visites.")
        return True

    def _render_comparison(self):
        self.comparison = None
        if self.reference is None or self.view is None:
            return
        try:
            self.comparison = compare_lab_views(self.reference, self.view)
        except ValueError as exc:
            self.compare_details.setPlainText("Comparaison refusée : " + str(exc))
            return
        self.compare_details.setPlainText(
            json.dumps(self.comparison, ensure_ascii=False, indent=2) +
            "\nComparaison informative uniquement ; conditions de seeds et "
            "budgets à comparer avant d'interpréter les deltas.")

    def open_resource(self, family):
        if self.scene is None or self.owner is None or family not in ("maps", "scenes"):
            return False
        session = getattr(self.owner, "session", None)
        if session is None:
            return False
        matches = [row for row in resources(session.snapshot()) if
                   row.family == family and row.resource_id == self.scene["id"]]
        if not matches:
            return False
        destination = "maps" if family == "maps" else "events"
        if self.owner.navigate(destination) is False:
            self.status.setText("Navigation Studio refusée : saisie en cours.")
            return False
        if family == "maps":
            child = self.owner._models.get("maps")
            if child is None:
                return False
            child.studio.select_map(matches[0].mission_id or matches[0].resource_id)
            child.refresh_maps()
        self.accept()
        return True
