"""Qt 6 standalone authoring and evidence window for R13.

The tactical simulation stays in the SDK/legacy canonical rules package.
Qt never owns Content and worker threads never touch widgets.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from threading import Thread


def launch(content_path):
    """Open the R13 workbench. Requires the optional PySide6 dependency."""
    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtGui import QColor, QBrush, QPen
    from PySide6.QtWidgets import (
        QApplication, QFileDialog, QFormLayout, QGraphicsScene,
        QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
        QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
        QTabWidget, QVBoxLayout, QWidget, QComboBox, QTextEdit,
    )

    from sporebound.model import Content
    from sporebound.rules import default_rules
    from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
    from drawtemp.sdk.r13_encounter_authoring import (
        compare_draft, preview_authoring,
    )
    from drawtemp.sdk.r13_combat_lab import (
        compare_encounters, evaluate_variant, human_review,
        inspect_encounter, simulate_encounter, trace_timeline,
    )

    class ResultBus(QObject):
        ready = Signal(int, object)
        failed = Signal(int, str)

    class TilePicker(QGraphicsView):
        """Click a map tile to move the currently selected actor in the draft."""
        tileChosen = Signal(int, int)

        def __init__(self, scene):
            super().__init__(scene)
            self.tile_size = 24
            self.tile_dims = (0, 0)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                point = self.mapToScene(event.position().toPoint())
                x = int(point.x() // self.tile_size)
                y = int(point.y() // self.tile_size)
                if 0 <= x < self.tile_dims[0] and 0 <= y < self.tile_dims[1]:
                    self.tileChosen.emit(x, y)
                    event.accept()
                    return
            super().mousePressEvent(event)

    class Workbench(QMainWindow):
        def __init__(self, content, authoring=None):
            super().__init__()
            self.content = content
            self.authoring = authoring
            self._approved_edits = None
            self.reference = None
            self.current = None
            self.inspection = None
            self._sequence = 0
            self.bus = ResultBus(self)
            self.bus.ready.connect(self._complete)
            self.bus.failed.connect(self._failed)
            self.setWindowTitle("DrawTemp 5.0 — R13 Combat Design & Balance Lab")
            self.resize(1250, 850)
            central = QWidget()
            self.setCentralWidget(central)
            outer = QVBoxLayout(central)
            toolbar = QHBoxLayout()
            outer.addLayout(toolbar)
            toolbar.addWidget(QLabel("Mission"))
            self.mission = QComboBox()
            self.mission.addItems(sorted(content.missions))
            self.mission.currentTextChanged.connect(self._refresh)
            toolbar.addWidget(self.mission)
            toolbar.addWidget(QLabel("Seeds"))
            self.seeds = QSpinBox()
            self.seeds.setRange(1, 32)
            self.seeds.setValue(4)
            toolbar.addWidget(self.seeds)
            toolbar.addWidget(QLabel("Max. commandes"))
            self.limit = QSpinBox()
            self.limit.setRange(10, 5000)
            self.limit.setValue(300)
            toolbar.addWidget(self.limit)
            toolbar.addStretch(1)
            self.status = QLabel("Prêt")
            outer.addWidget(self.status)

            self.tabs = QTabWidget()
            outer.addWidget(self.tabs, 1)
            designer = QWidget()
            self.tabs.addTab(designer, "Encounter Designer")
            design_layout = QVBoxLayout(designer)
            design_layout.addWidget(QLabel(
                "Cliquer une case pour déplacer l'unité sélectionnée. Prévisualisation non destructive ; "
                "application uniquement après validation explicite."))
            options = QHBoxLayout()
            design_layout.addLayout(options)
            options.addWidget(QLabel("Objectif"))
            self.objective = QComboBox()
            self.objective.addItems([key for key, _ in default_rules().objectives.entries])
            options.addWidget(self.objective)
            options.addWidget(QLabel("Cases d'objectif (x,y; x,y)"))
            self.goal_cells = QLineEdit()
            self.goal_cells.setPlaceholderText("2,3; 4,3")
            options.addWidget(self.goal_cells, 1)
            options.addWidget(QLabel("Ticks"))
            self.target_ticks = QSpinBox()
            self.target_ticks.setRange(1, 100000)
            options.addWidget(self.target_ticks)
            options.addWidget(QLabel("Protéger"))
            self.protected = QComboBox()
            options.addWidget(self.protected)
            split = QSplitter(Qt.Orientation.Horizontal)
            design_layout.addWidget(split, 1)
            self.scene = QGraphicsScene()
            self.map = TilePicker(self.scene)
            self.map.tileChosen.connect(self._move_selected_unit)
            split.addWidget(self.map)
            right = QWidget()
            right_layout = QVBoxLayout(right)
            self.units = QTableWidget(0, 6)
            self.units.setHorizontalHeaderLabels(
                ["Unité", "Équipe", "X", "Y", "Arme", "IA"])
            right_layout.addWidget(self.units, 1)
            self.trial = QPushButton("Prévisualiser & simuler A/B")
            self.trial.clicked.connect(self._start_trial)
            right_layout.addWidget(self.trial)
            author_actions = QHBoxLayout()
            right_layout.addLayout(author_actions)
            self.apply_button = QPushButton("Appliquer")
            self.apply_button.clicked.connect(self._apply_draft)
            author_actions.addWidget(self.apply_button)
            self.undo_button = QPushButton("Annuler")
            self.undo_button.clicked.connect(self._undo)
            author_actions.addWidget(self.undo_button)
            self.redo_button = QPushButton("Refaire")
            self.redo_button.clicked.connect(self._redo)
            author_actions.addWidget(self.redo_button)
            self.save_button = QPushButton("Enregistrer")
            self.save_button.clicked.connect(self._save_authoring)
            author_actions.addWidget(self.save_button)
            for widget in (self.apply_button, self.undo_button,
                           self.redo_button, self.save_button):
                widget.setEnabled(self.authoring is not None)
            self.apply_button.setEnabled(False)
            self.trial_result = QTextEdit()
            self.trial_result.setReadOnly(True)
            right_layout.addWidget(self.trial_result, 1)
            split.addWidget(right)
            split.setSizes([720, 420])

            lab = QWidget()
            self.tabs.addTab(lab, "Battle Lab / Visual Replay")
            lab_layout = QVBoxLayout(lab)
            actions = QHBoxLayout()
            lab_layout.addLayout(actions)
            self.run_button = QPushButton("Simuler + vérifier les replays")
            self.run_button.clicked.connect(self._start_simulation)
            actions.addWidget(self.run_button)
            load = QPushButton("Charger la référence")
            load.clicked.connect(self._load_reference)
            actions.addWidget(load)
            save = QPushButton("Exporter le rapport JSON")
            save.clicked.connect(self._export_report)
            actions.addWidget(save)
            human = QPushButton("Analyser un playtest opt-in")
            human.clicked.connect(self._load_human)
            actions.addWidget(human)
            self.summary = QTextEdit()
            self.summary.setReadOnly(True)
            self.summary.setMaximumHeight(200)
            lab_layout.addWidget(self.summary)
            self.outcomes = QTableWidget(0, 6)
            self.outcomes.setHorizontalHeaderLabels([
                "Seed", "Résultat", "CT ticks", "Commandes", "Activations", "Replay"])
            lab_layout.addWidget(self.outcomes, 1)
            lab_layout.addWidget(QLabel(
                "Trace des commandes réelles (sélection automatique : première seed)"))
            self.timeline = QTableWidget(0, 5)
            self.timeline.setHorizontalHeaderLabels([
                "#", "Acteur", "Action", "Position", "Événements"])
            lab_layout.addWidget(self.timeline, 1)
            self._refresh(self.mission.currentText())
            if self.authoring is None:
                self.status.setText(
                    "Essai uniquement : projet R1 non ouvert (GameProject manquant ou incompatible).")

        def _refresh(self, mission_id):
            if not mission_id:
                return
            # Any in-flight result belongs to an older mission snapshot.
            self._sequence += 1
            self.run_button.setEnabled(True)
            self.trial.setEnabled(True)
            self.status.setText("Mission : " + mission_id)
            self._approved_edits = None
            self.apply_button.setEnabled(False)
            try:
                self.inspection = inspect_encounter(self.content, mission_id)
            except Exception as exc:
                self._show_error(str(exc))
                return
            mission = self.content.missions[mission_id]
            if self.objective.findText(mission.objective) < 0:
                # Preserve custom authored objective ids instead of silently
                # substituting the first default ruleset objective.
                self.objective.addItem(mission.objective)
            self.objective.setCurrentText(mission.objective)
            self.goal_cells.setText("; ".join(
                "{},{}".format(*cell) for cell in mission.goal))
            self.target_ticks.setValue(mission.target_ticks)
            self.protected.clear()
            self.protected.addItem("")
            self.protected.addItems([u.id for u in mission.units
                                     if u.team == "player"])
            self.protected.setCurrentText(mission.protected_id)
            units = self.inspection["profile"]["units"]
            self.units.setRowCount(len(units))
            authored = {u.id: u for u in mission.units}
            for index, unit in enumerate(units):
                fields = [unit["id"], unit["team"], *map(str, unit["pos"]),
                          authored[unit["id"]].weapon, authored[unit["id"]].behavior]
                for col, value in enumerate(fields):
                    item = QTableWidgetItem(value)
                    if col < 2:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.units.setItem(index, col, item)
            self._draw_map(self.inspection)
            self.trial_result.setPlainText(
                "Objectif : {}\n{} joueur(s), {} adversaire(s)\n"
                "Menaces conditionnelles : {}\n"
                "Les durées humaines ne sont pas déduites des ticks CT.".format(
                    self.inspection["profile"]["objective"],
                    self.inspection["profile"]["player_count"],
                    self.inspection["profile"]["enemy_count"],
                    len(self.inspection["intent"]["danger"])))
            self.current = None
            self.summary.clear()
            self.outcomes.setRowCount(0)
            self.timeline.setRowCount(0)

        def _draw_map(self, inspected, positions=None, goals=None):
            self.scene.clear()
            dims = inspected["profile"]["map"]
            # Preview bounded to 64 x 64; never a substitute for the iso renderer.
            width, height = min(64, dims["width"]), min(64, dims["height"])
            cell = max(8, min(24, 700 // max(1, width, height)))
            terrain = {tuple(t["cell"]): t for t in inspected["tiles"]}
            for y in range(height):
                for x in range(width):
                    tile = terrain.get((x, y), {})
                    bg = ("#344451" if tile.get("blocked") else
                          "#675337" if tile.get("hazard") else
                          "#344735" if tile.get("cover", 0) else "#283a35")
                    self.scene.addRect(x*cell, y*cell, cell, cell,
                                       QPen(QColor("#53635a")), QBrush(QColor(bg)))
            for x, y in (goals if goals is not None else inspected["goal_cells"]):
                if x < width and y < height:
                    self.scene.addRect(x*cell+2, y*cell+2, cell-4, cell-4,
                                       QPen(QColor("#eed063"), 2))
            for unit in inspected["profile"]["units"]:
                x, y = (positions or {}).get(unit["id"], unit["pos"])
                if x < 0 or y < 0 or x >= width or y >= height:
                    continue
                color = "#64bbf7" if unit["team"] == "player" else "#f28c7a"
                self.scene.addEllipse(x*cell+3, y*cell+3, cell-6, cell-6,
                                      QPen(QColor("#202020")), QBrush(QColor(color)))
            self.scene.setSceneRect(0, 0, cell*width, cell*height)
            self.map.tile_size = cell
            self.map.tile_dims = (width, height)

        def _read_placements(self):
            updates = {}
            for row in range(self.units.rowCount()):
                uid = self.units.item(row, 0).text()
                original = next(u["pos"] for u in self.inspection["profile"]["units"]
                                if u["id"] == uid)
                pos = [int(self.units.item(row, col).text()) for col in (2, 3)]
                if pos != original:
                    updates[uid] = pos
            return updates

        def _move_selected_unit(self, x, y):
            row = self.units.currentRow()
            if row < 0:
                if self.units.rowCount() == 0:
                    return
                row = 0
                self.units.selectRow(row)
            for column, value in ((2, x), (3, y)):
                self.units.item(row, column).setText(str(value))
            try:
                edits = self._read_editor_changes()
                self._draw_map(self.inspection,
                               edits.get("unit_positions"),
                               edits.get("goal_cells"))
            except (ValueError, TypeError):
                pass
            self._approved_edits = None
            self.apply_button.setEnabled(False)

        def _read_editor_changes(self):
            mission = self.content.missions[self.mission.currentText()]
            changes = {}
            positions = self._read_placements()
            if positions:
                changes["unit_positions"] = positions
            original = {u.id: u for u in mission.units}
            overrides = {}
            for row in range(self.units.rowCount()):
                uid = self.units.item(row, 0).text()
                fields = {}
                for column, key in ((4, "weapon"), (5, "behavior")):
                    value = self.units.item(row, column).text().strip()
                    if value != getattr(original[uid], key):
                        fields[key] = value
                if fields:
                    overrides[uid] = fields
            if overrides:
                changes["unit_overrides"] = overrides
            objective = self.objective.currentText()
            if objective != mission.objective:
                changes["objective"] = objective
            raw = self.goal_cells.text().strip()
            goals = []
            if raw:
                for part in raw.split(";"):
                    pieces = part.split(",")
                    if len(pieces) != 2:
                        raise ValueError("Chaque objectif doit avoir la forme x,y")
                    goals.append([int(piece.strip()) for piece in pieces])
            if goals != [list(c) for c in mission.goal]:
                changes["goal_cells"] = goals
            if self.target_ticks.value() != mission.target_ticks:
                changes["target_ticks"] = self.target_ticks.value()
            if self.protected.currentText() != mission.protected_id:
                changes["protected_id"] = self.protected.currentText()
            return changes

        def _apply_draft(self):
            if self.authoring is None or self._approved_edits is None:
                self._show_error("Prévisualiser les modifications avant application")
                return
            try:
                edits = self._read_editor_changes()
                if edits != self._approved_edits:
                    raise ValueError("Le formulaire a changé : relancer Prévisualiser")
                plan = preview_authoring(
                    self.authoring, self.mission.currentText(), edits)
                if QMessageBox.question(
                        self, "Appliquer R13",
                        "Appliquer ce changement au projet en mémoire ? "
                        "Il sera annulable et ne sera pas enregistré avant "
                        "votre clic sur Enregistrer.") != QMessageBox.StandardButton.Yes:
                    return
                self.authoring.apply(plan)
                self.content = Content.from_dict(
                    self.authoring.snapshot().to_dict()["content"])
                self._refresh(self.mission.currentText())
                self.status.setText(
                    "Modification appliquée en mémoire. Enregistrer pour écrire les deux fichiers.")
            except (ValueError, AuthoringError, KeyError, TypeError) as exc:
                self._show_error(str(exc))

        def _undo(self):
            if self.authoring is None:
                return
            try:
                self.authoring.undo()
                self.content = Content.from_dict(
                    self.authoring.snapshot().to_dict()["content"])
                self._refresh(self.mission.currentText())
                self.status.setText("Modification annulée (non enregistrée)")
            except (AuthoringError, ValueError) as exc:
                self._show_error(str(exc))

        def _redo(self):
            if self.authoring is None:
                return
            try:
                self.authoring.redo()
                self.content = Content.from_dict(
                    self.authoring.snapshot().to_dict()["content"])
                self._refresh(self.mission.currentText())
                self.status.setText("Modification rétablie (non enregistrée)")
            except (AuthoringError, ValueError) as exc:
                self._show_error(str(exc))

        def _save_authoring(self):
            if self.authoring is None:
                return
            try:
                if not self.authoring.snapshot().dirty:
                    self.status.setText("Aucune modification à enregistrer")
                    return
                if QMessageBox.question(
                        self, "Enregistrer la mission",
                        "Enregistrer Content et GameProject de façon atomique ? "
                        "En cas de modification externe, le SDK refusera l'écrasement."
                        ) != QMessageBox.StandardButton.Yes:
                    return
                paths = self.authoring.save()
                self.status.setText(
                    "Projet enregistré : " + ", ".join(str(p) for p in paths))
            except (AuthoringError, OSError) as exc:
                self._show_error(str(exc))

        def _submit(self, operation, fn):
            self._sequence += 1
            seq = self._sequence
            self.status.setText("Calcul en cours : " + operation)
            self.run_button.setEnabled(False)
            self.trial.setEnabled(False)
            self.apply_button.setEnabled(False)

            def work():
                try:
                    result = fn()
                    self.bus.ready.emit(seq, (operation, result))
                except Exception as exc:
                    self.bus.failed.emit(seq, str(exc))

            Thread(target=work, daemon=True).start()

        def _start_trial(self):
            try:
                edits = self._read_editor_changes()
                if not edits:
                    raise ValueError("Aucune modification à prévisualiser")
            except (ValueError, TypeError, KeyError) as exc:
                self._show_error(str(exc))
                return
            self._approved_edits = None
            # Snapshot Qt state BEFORE starting the worker thread.
            snapshot = deepcopy(self.content)
            mission = self.mission.currentText()
            seeds = tuple(range(1, self.seeds.value()+1))
            limit = self.limit.value()
            self._submit("variante", lambda: compare_draft(
                snapshot, mission, edits, seeds=seeds, max_commands=limit))

        def _start_simulation(self):
            snapshot = deepcopy(self.content)
            mission = self.mission.currentText()
            seeds = tuple(range(1, self.seeds.value()+1))
            limit = self.limit.value()
            self._submit("simulation", lambda: simulate_encounter(
                snapshot, mission, seeds=seeds, max_commands=limit,
                trace_seed_id=seeds[0]))

        def _complete(self, sequence, payload):
            if sequence != self._sequence:
                return
            self.run_button.setEnabled(True)
            self.trial.setEnabled(True)
            operation, result = payload
            self.status.setText("Terminé : " + operation)
            if operation == "variante":
                try:
                    actual = self._read_editor_changes()
                except (ValueError, TypeError, KeyError):
                    actual = None
                if (self.mission.currentText() != result["mission"]
                        or actual != result["edits"]):
                    self.trial_result.setPlainText(
                        "Prévisualisation obsolète : formulaire modifié pendant le calcul.")
                    self._approved_edits = None
                    self.apply_button.setEnabled(False)
                    return
                self._approved_edits = deepcopy(result["edits"])
                self.apply_button.setEnabled(self.authoring is not None)
                old, new = result["baseline"], result["candidate"]
                self.trial_result.setPlainText(json.dumps({
                    "mission": result["mission"],
                    "victoire_avant": old["victory_rate"],
                    "victoire_après": new["victory_rate"],
                    "ticks_p95_avant": old["ticks_p95"],
                    "ticks_p95_après": new["ticks_p95"],
                    "commandes_p95_avant": old["commands_p95"],
                    "commandes_p95_après": new["commands_p95"],
                    "replays_verified": result["replays_verified"],
                    "objectif_modifié": result["objective_changed"],
                    "regression": result["comparison"]["issues"],
                    "revue_humaine_requise": result["comparison"]["human_signoff_required"],
                }, indent=2, ensure_ascii=False))
                self._draw_map(self.inspection,
                               actual.get("unit_positions"),
                               actual.get("goal_cells"))
                return
            self.current = result
            report = result["battle_lab"]
            stats = {
                "mission": report["mission"], "runs": report["runs"],
                "win_rate": report["victory_rate"],
                "CT p95": report["ticks_p95"],
                "commands p95": report["commands_p95"],
                "unresolved": report["outcomes"]["limit"],
            }
            if self.reference is not None:
                try:
                    stats["regression"] = compare_encounters(
                        self.reference, report)
                except Exception as exc:
                    stats["reference_error"] = str(exc)
            self.summary.setPlainText(json.dumps(stats, indent=2, ensure_ascii=False))
            self.outcomes.setRowCount(len(report["samples"]))
            for row, sample in enumerate(report["samples"]):
                columns = [sample["seed"], sample["result"], sample["ticks"],
                           sample["commands"], sample["activations_ct"],
                           sample["replay_verified"]]
                for col, value in enumerate(columns):
                    self.outcomes.setItem(row, col, QTableWidgetItem(str(value)))
            rows = trace_timeline(result["trace"], limit=200)["frames"]
            self.timeline.setRowCount(len(rows))
            for row, frame in enumerate(rows):
                actor = next((u for u in frame["positions"]
                              if u["id"] == frame["actor"]), None)
                fields = [frame["index"], frame["actor"],
                          frame["command"]["kind"],
                          actor["cell"] if actor else None,
                          [e["kind"] for e in frame["events"]]]
                for col, value in enumerate(fields):
                    self.timeline.setItem(row, col, QTableWidgetItem(str(value)))

        def _failed(self, sequence, error):
            if sequence == self._sequence:
                self.run_button.setEnabled(True)
                self.trial.setEnabled(True)
                self.status.setText("Erreur")
                self._show_error(error)

        def _load_reference(self):
            path, _ = QFileDialog.getOpenFileName(
                self, "Ouvrir rapport Battle Lab", "", "JSON (*.json)")
            if not path:
                return
            try:
                doc = json.loads(Path(path).read_text(encoding="utf-8"))
                if doc.get("kind") == "r13_simulation":
                    doc = doc["battle_lab"]
                if doc.get("kind") != "battle_lab":
                    raise ValueError("Rapport Battle Lab requis")
                self.reference = doc
                self.status.setText("Référence chargée : " + str(path))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self._show_error(str(exc))

        def _export_report(self):
            if self.current is None:
                self._show_error("Exécuter une simulation avant export")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter rapport R13", "r13-report.json", "JSON (*.json)")
            if path:
                try:
                    Path(path).write_text(json.dumps(
                        self.current, ensure_ascii=False, sort_keys=True, indent=2)
                        + "\n", encoding="utf-8")
                except OSError as exc:
                    self._show_error(str(exc))

        def _load_human(self):
            path, _ = QFileDialog.getOpenFileName(
                self, "Rapport de playtest local (opt-in)", "", "JSON (*.json)")
            if not path:
                return
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                review = human_review(data)
                self.summary.setPlainText(json.dumps(
                    review, indent=2, ensure_ascii=False))
                self.tabs.setCurrentIndex(1)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._show_error(str(exc))

        def closeEvent(self, event):
            if self.authoring is not None and self.authoring.snapshot().dirty:
                answer = QMessageBox.question(
                    self, "Fermer le Battle Lab",
                    "Des changements appliqués ne sont pas enregistrés. "
                    "Quitter et les perdre ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
            event.accept()

        def _show_error(self, error):
            QMessageBox.warning(self, "DrawTemp R13", error)

    content = Content.load(content_path)
    try:
        authoring = AuthoringSession.open(content_path)
    except (AuthoringError, OSError, ValueError):
        # A standalone Content may not have a companion .game.json; this
        # remains a read-only experiment workbench, never a fake save path.
        authoring = None
    app = QApplication.instance() or QApplication([])
    window = Workbench(content, authoring)
    window.show()
    # Keep a reference while the caller's QApplication is alive.
    app.r13_workbench = window
    return app.exec()


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5.0 R13 Battle Lab (Qt6)")
    parser.add_argument("--content", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.content is None:
        import sporebound
        args.content = Path(sporebound.__file__).parent / "content" / "jeanne.json"
    return launch(args.content)


if __name__ == "__main__":
    raise SystemExit(main())
