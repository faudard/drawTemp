"""R56.B Qt QA Lab — read-only scenarios and deterministic replay inspection.

All gameplay runs on a worker thread using detached Content/GameProject.
The active AuthoringSession is never mutated, saved or used from that thread.
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QVBoxLayout,
)

from drawtemp.quality.r56_scenarios import OPERATIONS
from drawtemp.quality.r56_lab import (
    build_suite, capture_case, diff_batches, inspect_case, read_report,
    read_suite, run_batch, save_json,
)
from drawtemp.studio.workspace_model import resources
from sporebound.game_project import GameProject
from sporebound.model import Content


class BatchWorker(QObject):
    completed = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, suite, content, project, revision, interval):
        super().__init__()
        self.suite, self.content, self.project = suite, content, project
        self.revision, self.interval = revision, interval

    @Slot()
    def run(self):
        try:
            result = run_batch(self.suite, self.content, self.project,
                               revision=self.revision,
                               checkpoint_every=self.interval)
            self.completed.emit(result)
        except Exception as exc:
            self.error.emit("%s: %s" % (type(exc).__name__, str(exc)[:400]))
        finally:
            self.finished.emit()


class GameplayQALabDialog(QDialog):
    """Author explicit command captures, run batches, inspect and navigate.

    This is *not* passive capture of real Player input, a video recorder, or a
    GPU/Studio playtest certification. The visible trace is a command sequence.
    """

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._snapshot = owner.session.snapshot()
        data = self._snapshot.to_dict()
        self._content = Content.from_dict(data["content"])
        self._project = GameProject.from_dict(data["project"], self._content)
        self._identity_keys = {entry.key for entry in resources(self._snapshot)}
        self._cases = []
        self._draft = []
        self._draft_links = []
        self._batch = None
        self._baseline = None
        self._source_path = None
        self._thread = None
        self._worker = None

        self.setObjectName("r56-qa-lab")
        self.setWindowTitle("R56.B • QA Lab du gameplay")
        self.resize(1000, 800)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Scénarios explicites sur une copie du projet courant, sans édition "
            "ni sauvegarde du Studio. Rejeu headless uniquement : pas de preuve "
            "GPU, de capture Player passive, ni de certification release.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.revision = QLineEdit()
        self.revision.setObjectName("r56-qa-revision")
        self.revision.setPlaceholderText("SHA complet de git rev-parse HEAD (40 caractères)")
        form.addRow("Révision Git déclarée :", self.revision)
        self.case_id = QLineEdit("scenario-01")
        self.case_id.setObjectName("r56-qa-case-id")
        form.addRow("Identifiant scénario :", self.case_id)
        self.campaign = QLineEdit("main")
        form.addRow("Campagne :", self.campaign)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(17)
        form.addRow("Seed :", self.seed)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.operation = QComboBox()
        self.operation.setObjectName("r56-qa-operation")
        for operation, arity in sorted(OPERATIONS.items()):
            self.operation.addItem(operation + " (" + str(arity) + ")", operation)
        actions.addWidget(self.operation)
        self.args = QLineEdit("[]")
        self.args.setObjectName("r56-qa-args")
        self.args.setPlaceholderText('Arguments JSON : [1,0], ["enter"], …')
        actions.addWidget(self.args, 1)
        layout.addLayout(actions)

        assert_row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setPlaceholderText("Invariant (facultatif) : mode, scene_route.current…")
        assert_row.addWidget(self.path)
        self.expected = QLineEdit()
        self.expected.setPlaceholderText('Valeur JSON : "campaign", 2, true…')
        assert_row.addWidget(self.expected)
        layout.addLayout(assert_row)

        source = QHBoxLayout()
        self.resource = QComboBox()
        self.resource.setObjectName("r56-qa-resource")
        self.resource.addItem("Aucune ressource liée", None)
        for entry in resources(self._snapshot):
            self.resource.addItem(
                entry.family + " / " + (entry.mission_id + " / " if entry.mission_id else "")
                + entry.title, list(entry.key))
        source.addWidget(self.resource, 1)
        self.add = QPushButton("Capturer cette commande")
        self.add.setObjectName("r56-qa-add-step")
        self.add.clicked.connect(self.add_step)
        source.addWidget(self.add)
        self.capture = QPushButton("Créer scénario")
        self.capture.setObjectName("r56-qa-capture")
        self.capture.clicked.connect(self.capture_case)
        source.addWidget(self.capture)
        layout.addLayout(source)

        self.status = QLabel("Aucun scénario. Chaque commande correspond à une étape logique.")
        self.status.setObjectName("r56-qa-status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        commands = QHBoxLayout()
        self.import_button = QPushButton("Importer suite…")
        self.import_button.clicked.connect(self.import_suite)
        commands.addWidget(self.import_button)
        self.export_button = QPushButton("Exporter suite…")
        self.export_button.clicked.connect(self.export_suite)
        commands.addWidget(self.export_button)
        self.run_button = QPushButton("Exécuter le lot")
        self.run_button.setObjectName("r56-qa-run")
        self.run_button.clicked.connect(self.run_cases)
        commands.addWidget(self.run_button)
        self.report_button = QPushButton("Exporter rapport…")
        self.report_button.clicked.connect(self.export_report)
        commands.addWidget(self.report_button)
        self.compare_button = QPushButton("Comparer un rapport…")
        self.compare_button.clicked.connect(self.compare_report)
        commands.addWidget(self.compare_button)
        layout.addLayout(commands)

        self.cases = QListWidget()
        self.cases.setObjectName("r56-qa-cases")
        self.cases.setAccessibleName("Scénarios du lot et statuts")
        self.cases.currentRowChanged.connect(self.select_case)
        layout.addWidget(self.cases, 1)
        self.steps = QListWidget()
        self.steps.setObjectName("r56-qa-steps")
        self.steps.setAccessibleName("Commandes et points de reprise")
        self.steps.currentRowChanged.connect(self.inspect_step)
        layout.addWidget(self.steps, 2)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("r56-qa-inspector")
        self.detail.setAccessibleName("Diagnostic de l'étape de gameplay")
        layout.addWidget(self.detail, 2)

        footer = QHBoxLayout()
        self.navigate_button = QPushButton("Localiser dans le Studio")
        self.navigate_button.setObjectName("r56-qa-navigate")
        self.navigate_button.clicked.connect(self.navigate_source)
        self.navigate_button.setEnabled(False)
        footer.addWidget(self.navigate_button)
        self.close_button = QPushButton("Fermer")
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _error(self, message):
        self.status.setText("R56.B bloqué : " + str(message)[:500])

    def _ensure_snapshot(self):
        if self.owner.session.revision != self._snapshot.revision:
            raise ValueError("Le projet a changé : rouvrir QA Lab pour une nouvelle copie")

    def add_step(self):
        try:
            operation = self.operation.currentData()
            args = json.loads(self.args.text())
            if type(args) is not list or len(args) != OPERATIONS[operation]:
                raise ValueError("Arity/JSON arguments do not match selected operation")
            expectation = []
            if self.path.text().strip():
                if not self.expected.text().strip():
                    raise ValueError("An invariant path requires a JSON expected value")
                expectation = [{
                    "path": self.path.text().strip().split("."),
                    "equals": json.loads(self.expected.text()),
                }]
            step = {"operation": operation, "args": args, "expect": expectation}
            # Validate the full R56.A contract when the capture is committed.
            if len(self._draft) >= 256:
                raise ValueError("Maximum 256 actions")
            self._draft.append(step)
            identity = self.resource.currentData()
            if identity is not None:
                self._draft_links.append({
                    "step": len(self._draft), "resource": list(identity)})
            self.status.setText(
                str(len(self._draft)) + " commande(s) capturée(s), non exécutées")
        except (ValueError, TypeError, KeyError) as exc:
            self._error(exc)

    def capture_case(self):
        try:
            self._ensure_snapshot()
            case = capture_case(
                self._content, self._project,
                identifier=self.case_id.text().strip(),
                starter="studio-active", revision=self.revision.text().strip(),
                campaign=self.campaign.text().strip(), seed=self.seed.value(),
                steps=self._draft, links=self._draft_links)
            # Apply uniqueness and count checks *before* mutating the draft.
            build_suite(self._cases + [case])
            self._cases.append(case)
            self._draft, self._draft_links = [], []
            self._batch = None
            self.status.setText("Scénario capturé : " + case["scenario"]["id"]
                                + " (exécution non encore prouvée)")
            self.refresh_cases()
            self.cases.setCurrentRow(len(self._cases) - 1)
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            self._error(exc)

    def refresh_cases(self):
        selected = self.cases.currentRow()
        self.cases.clear()
        for i, case in enumerate(self._cases):
            status = (self._batch["cases"][i]["status"]
                      if self._batch is not None else "non exécuté")
            self.cases.addItem(case["scenario"]["id"] + " — " + status)
        if self._cases:
            self.cases.setCurrentRow(max(0, min(selected, len(self._cases) - 1)))

    def select_case(self, row):
        self.steps.clear()
        self.navigate_button.setEnabled(False)
        if not 0 <= row < len(self._cases):
            return
        case = self._cases[row]["scenario"]
        report = self._batch["cases"][row]["report"] if self._batch else None
        seen = {entry["step"] for entry in report["trace"]} if report else set()
        failure = report.get("counterexample") if report else None
        self.steps.addItem("0 — état initial" + (" ✓" if 0 in seen else ""))
        for index, item in enumerate(case["steps"], 1):
            state = (" ✕" if failure and failure["step"] == index else
                     " ✓" if index in seen else " ·")
            self.steps.addItem(str(index) + " — " + item["operation"] + state)
        self.steps.setCurrentRow(
            failure["step"] if failure and 0 <= failure["step"] < self.steps.count()
            else max(0, self.steps.count() - 1))

    def inspect_step(self, step):
        self.navigate_button.setEnabled(False)
        row = self.cases.currentRow()
        if not 0 <= row < len(self._cases) or step < 0:
            self.detail.clear()
            return
        case = self._cases[row]
        if self._batch:
            report = self._batch["cases"][row]["report"]
            try:
                view = inspect_case(report, case, step)
            except ValueError as exc:
                self._error(exc)
                return
        else:
            view = {"step": step, "command": (
                case["scenario"]["steps"][step - 1] if step else None),
                "trace": None, "failure": None,
                "resource": next((link["resource"] for link in case["links"]
                                  if link["step"] == step), None),
                "description": "Non exécuté", "reproduced_through_step": False}
        self.detail.setPlainText(
            json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True))
        self.navigate_button.setEnabled(
            view["resource"] is not None and
            tuple(view["resource"]) in self._identity_keys and
            self.owner.session.revision == self._snapshot.revision)

    def navigate_source(self):
        row, step = self.cases.currentRow(), self.steps.currentRow()
        if not (0 <= row < len(self._cases) and step > 0):
            return
        match = next(
            (entry["resource"] for entry in self._cases[row]["links"]
             if entry["step"] == step), None)
        if match is None or tuple(match) not in self._identity_keys:
            self._error("Lien de source introuvable dans le projet")
            return
        if self.owner.session.revision != self._snapshot.revision:
            self._error("Projet changé : relancer QA Lab")
            return
        self.accept()
        if not self.owner.focus_resource(tuple(match)):
            self.owner.statusBar().showMessage("R56.B : ressource non visible")

    def import_suite(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une suite R56.B", "", "QA JSON (*.json)")
        if not path:
            return
        try:
            self._ensure_snapshot()
            suite = read_suite(path)
            self._cases = suite["cases"]
            self._source_path = path
            pins = {case["scenario"]["revision"] for case in self._cases}
            if len(pins) == 1:
                self.revision.setText(next(iter(pins)))
            self._batch = None
            self.status.setText(str(len(self._cases)) + " scénarios importés, non validés")
            self.refresh_cases()
        except (ValueError, OSError, UnicodeError, TypeError) as exc:
            self._error(exc)

    def export_suite(self):
        if not self._cases:
            self._error("Aucun scénario à exporter")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la suite R56.B", "r56-suite.json", "QA JSON (*.json)")
        if path:
            try:
                save_json(path, build_suite(self._cases),
                          forbidden=[self._source_path] if self._source_path else [])
                self.status.setText("Suite exportée, non certifiée : " + path)
            except (ValueError, OSError) as exc:
                self._error(exc)

    def run_cases(self):
        if self._thread is not None:
            return
        try:
            self._ensure_snapshot()
            suite = build_suite(self._cases)
            revision = self.revision.text().strip()
            # Capture a new suite before creating a thread, no QObject crosses
            # the worker boundary and no mutable AuthoringSession is shared.
            self._thread = QThread(self)
            self._worker = BatchWorker(suite, self._content, self._project,
                                       revision, 1)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.completed.connect(self._completed)
            self._worker.error.connect(self._error)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread_done)
            self._thread.finished.connect(self._thread.deleteLater)
            self.run_button.setEnabled(False)
            self.close_button.setEnabled(False)
            self.status.setText("Exécution headless en cours ; aucune action Studio modifiée")
            self._thread.start()
        except (ValueError, TypeError, RuntimeError) as exc:
            self._error(exc)

    @Slot(object)
    def _completed(self, batch):
        self._batch = batch
        counts = batch["counts"]
        self.status.setText(
            batch["status"] + " · "
            + ", ".join(k + "=" + str(v) for k, v in counts.items())
            + " · aucune certification release")
        self.refresh_cases()

    @Slot()
    def _thread_done(self):
        self._worker = None
        self._thread = None
        self.run_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def export_report(self):
        if self._batch is None:
            self._error("Aucun rapport exécuté")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les diagnostics R56.B", "r56-report.json",
            "QA JSON (*.json)")
        if path:
            try:
                save_json(path, self._batch,
                          forbidden=[self._source_path] if self._source_path else [])
                self.status.setText("Rapport headless exporté ; release non certifiée")
            except (ValueError, OSError) as exc:
                self._error(exc)

    def compare_report(self):
        if self._batch is None:
            self._error("Exécuter une suite avant de comparer")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger un rapport R56.B de référence", "", "QA JSON (*.json)")
        if not path:
            return
        try:
            diff = diff_batches(read_report(path), self._batch)
            self.detail.setPlainText(
                json.dumps(diff, ensure_ascii=False, indent=2, sort_keys=True))
            self.status.setText(
                "Comparaison : " + str(len(diff["changes"])) +
                " scénario(s) divergent(s) ; provenance non certifiée")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self._error(exc)

    def reject(self):
        if self._thread is not None:
            self._error("Fermer le QA Lab après la fin du traitement")
            return
        super().reject()

    def closeEvent(self, event):
        if self._thread is not None:
            event.ignore()
            self._error("Traitement QA en cours")
            return
        super().closeEvent(event)
