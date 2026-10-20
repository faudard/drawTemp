"""R78.B — optional local team review, comments and release board dialog.

Read-only toward the game editor: all writes are explicit metadata-only
R48 note or R78 board journal events, never Content/GameProject modifications.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.review_notes import ReviewNoteStore
from drawtemp.sdk.team_review_board import TeamReviewBoard, TeamTaskStore
from drawtemp.sdk.team_workflows import TeamAccessPolicy
from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace


def _item(value):
    item = QTableWidgetItem(str(value))
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    return item


class TeamReviewDialog(QDialog):
    """R78.B Studio adapter: explicit history import, comments, tasks and votes."""

    def __init__(self, session: AuthoringSession, *, actor: str,
                 policy: TeamAccessPolicy, graph=None, parent=None):
        super().__init__(parent)
        self.setObjectName("r78-team-dialog")
        self.setWindowTitle("DrawTemp — Revues d'équipe R78.B (local)")
        self.resize(1060, 770)
        self.actor = actor
        self.policy = policy
        self.role = policy.require(actor)
        self.workspace = ProjectHistoryWorkspace(session, graph=graph)
        self.board = None
        self._notes_head = None
        self._tasks_head = None
        self._tasks = ()
        self._threads = ()
        self._reviewed_node = None

        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setObjectName("r78-scroll")
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        summary = QLabel(
            f"Mode local — acteur {actor} ({self.role}). Les avis, tâches et "
            "commentaires ne modifient jamais le projet ni n'autorisent une fusion. "
            "Aucune synchronisation cloud, sauvegarde ou publication implicite.")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        history_row = QHBoxLayout()
        self.history_button = QPushButton("Ouvrir historique R48…")
        self.history_button.setObjectName("r78-load-history")
        self.history_button.clicked.connect(self.choose_history)
        history_row.addWidget(self.history_button)
        self.journal_button = QPushButton("Choisir dossier de revue…")
        self.journal_button.setObjectName("r78-choose-journal")
        self.journal_button.clicked.connect(self.choose_journal)
        history_row.addWidget(self.journal_button)
        self.reload_button = QPushButton("Actualiser les journaux")
        self.reload_button.setObjectName("r78-reload")
        self.reload_button.clicked.connect(self.refresh)
        history_row.addWidget(self.reload_button)
        layout.addLayout(history_row)

        chooser = QHBoxLayout()
        chooser.addWidget(QLabel("Avant"))
        self.local_combo = QComboBox()
        self.local_combo.setObjectName("r78-before")
        self.local_combo.setAccessibleName("Révision de départ")
        chooser.addWidget(self.local_combo, 2)
        chooser.addWidget(QLabel("Après / annotée"))
        self.incoming_combo = QComboBox()
        self.incoming_combo.setObjectName("r78-after")
        self.incoming_combo.setAccessibleName("Révision relue")
        self.incoming_combo.currentIndexChanged.connect(self.refresh)
        chooser.addWidget(self.incoming_combo, 2)
        self.compare_button = QPushButton("Afficher les changements")
        self.compare_button.setObjectName("r78-diff")
        self.compare_button.clicked.connect(self.compare)
        chooser.addWidget(self.compare_button)
        layout.addLayout(chooser)

        self.diff_table = QTableWidget(0, 4)
        self.diff_table.setObjectName("r78-diff-table")
        self.diff_table.setHorizontalHeaderLabels(("Opération", "Chemin", "Avant", "Après"))
        self.diff_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diff_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.diff_table.setMinimumHeight(130)
        self.diff_table.itemSelectionChanged.connect(self.choose_diff_path)
        layout.addWidget(self.diff_table)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Chemin d'entité / diff"))
        self.path_edit = QLineEdit("/project")
        self.path_edit.setObjectName("r78-anchor-path")
        self.path_edit.setAccessibleName("Chemin sémantique ancré sur la révision relue")
        target_row.addWidget(self.path_edit)
        layout.addLayout(target_row)

        layout.addWidget(QLabel("Commentaires liés à la révision et à l'entité"))
        self.notes_table = QTableWidget(0, 4)
        self.notes_table.setObjectName("r78-comments")
        self.notes_table.setHorizontalHeaderLabels(("Fil", "Auteur", "Message", "État"))
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.setMinimumHeight(110)
        layout.addWidget(self.notes_table)
        note_row = QHBoxLayout()
        self.note_text = QPlainTextEdit()
        self.note_text.setObjectName("r78-note-text")
        self.note_text.setPlaceholderText("Commentaire de revue (publication explicite)")
        self.note_text.setMaximumHeight(75)
        note_row.addWidget(self.note_text, 4)
        self.thread_combo = QComboBox()
        self.thread_combo.setObjectName("r78-note-thread")
        self.thread_combo.addItem("Nouvelle discussion", 0)
        self.thread_combo.setAccessibleName("Discussion sélectionnée")
        note_row.addWidget(self.thread_combo)
        self.note_button = QPushButton("Commenter / répondre")
        self.note_button.setObjectName("r78-post-note")
        self.note_button.clicked.connect(self.post_note)
        note_row.addWidget(self.note_button)
        self.thread_button = QPushButton("Résoudre / rouvrir")
        self.thread_button.setObjectName("r78-toggle-thread")
        self.thread_button.clicked.connect(self.toggle_thread)
        note_row.addWidget(self.thread_button)
        layout.addLayout(note_row)

        review_row = QHBoxLayout()
        review_row.addWidget(QLabel("Avis sur cette version"))
        self.review_choice = QComboBox()
        self.review_choice.setObjectName("r78-review-choice")
        self.review_choice.addItem("Modifications demandées", "changes_requested")
        self.review_choice.addItem("Approuvé (consultatif)", "approved")
        review_row.addWidget(self.review_choice)
        self.review_summary = QLineEdit()
        self.review_summary.setObjectName("r78-review-summary")
        self.review_summary.setPlaceholderText("Motif de l'avis")
        review_row.addWidget(self.review_summary, 3)
        self.review_button = QPushButton("Consigner l'avis")
        self.review_button.setObjectName("r78-review-submit")
        self.review_button.clicked.connect(self.post_review)
        review_row.addWidget(self.review_button)
        layout.addLayout(review_row)
        self.votes_status = QLabel("Aucun avis chargé.")
        self.votes_status.setObjectName("r78-votes-status")
        layout.addWidget(self.votes_status)

        layout.addWidget(QLabel("Tâches et tableau de release (journal séparé)"))
        self.tasks_table = QTableWidget(0, 6)
        self.tasks_table.setObjectName("r78-tasks")
        self.tasks_table.setHorizontalHeaderLabels(
            ("Tâche", "Objet", "Assigné", "État", "Release", "Ancre"))
        self.tasks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tasks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tasks_table.setMinimumHeight(120)
        layout.addWidget(self.tasks_table)

        task_row = QHBoxLayout()
        self.task_title = QLineEdit()
        self.task_title.setObjectName("r78-task-title")
        self.task_title.setPlaceholderText("Titre de la tâche")
        task_row.addWidget(self.task_title, 3)
        self.task_assignee = QLineEdit()
        self.task_assignee.setObjectName("r78-task-assignee")
        self.task_assignee.setPlaceholderText("Assigné à (identité)")
        task_row.addWidget(self.task_assignee, 2)
        self.task_release = QLineEdit()
        self.task_release.setObjectName("r78-task-release")
        self.task_release.setPlaceholderText("Release (ex. 12.0)")
        task_row.addWidget(self.task_release)
        self.task_button = QPushButton("Créer une tâche")
        self.task_button.setObjectName("r78-create-task")
        self.task_button.clicked.connect(self.create_task)
        task_row.addWidget(self.task_button)
        layout.addLayout(task_row)

        status_row = QHBoxLayout()
        self.task_state = QComboBox()
        self.task_state.setObjectName("r78-task-state")
        for title, value in (("À faire", "todo"), ("En cours", "in_progress"),
                             ("Terminé", "done")):
            self.task_state.addItem(title, value)
        status_row.addWidget(self.task_state)
        self.task_update_button = QPushButton("Changer l'état sélectionné")
        self.task_update_button.setObjectName("r78-update-task")
        self.task_update_button.clicked.connect(self.update_task)
        status_row.addWidget(self.task_update_button)
        layout.addLayout(status_row)

        self.status = QLabel("Choisir un dossier local pour créer les journaux à la demande.")
        self.status.setObjectName("r78-status")
        self.status.setAccessibleName("Diagnostic des revues d'équipe")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        done = QPushButton("Fermer")
        done.clicked.connect(self.reject)
        layout.addWidget(done)

        enabled = self.role in ("owner", "editor", "reviewer")
        for button in (self.note_button, self.thread_button,
                       self.review_button, self.task_button):
            button.setEnabled(enabled)
        self.task_update_button.setEnabled(enabled)
        self._populate_history()

    def _node_id(self):
        return self.incoming_combo.currentData()

    def _populate_history(self):
        previous_before = self.local_combo.currentData()
        previous_after = self.incoming_combo.currentData()
        for combo in (self.local_combo, self.incoming_combo):
            combo.blockSignals(True)
            combo.clear()
            for node in self.workspace.revisions():
                combo.addItem(
                    f"{node.label or 'Révision'} — {node.revision.author} ({node.node_id[:10]})",
                    node.node_id)
        for combo, selected in ((self.local_combo, previous_before),
                                 (self.incoming_combo, previous_after)):
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.diff_table.setRowCount(0)
        self.refresh()

    def choose_history(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un historique R48 vérifié", "", "Historique JSON (*.json)")
        if path:
            self.load_history(path)

    def load_history(self, path):
        try:
            self.workspace.load_history(path)
            if self.board is not None:
                self.board.graph = self.workspace.graph
            self._populate_history()
            self.status.setText("Historique R48 chargé et rattaché au Studio actuel.")
            return True
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Historique refusé : " + str(exc))
            return False

    def choose_journal(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier de journaux R78 (aucune création automatique)")
        if directory:
            self.use_directory(directory)

    def use_directory(self, directory):
        try:
            folder = Path(directory).absolute()
            if not folder.is_dir() or folder.resolve() != folder:
                raise ValueError("Dossier absent ou lien symbolique")
            notes = ReviewNoteStore(folder / "r78_review_notes.jsonl")
            tasks = TeamTaskStore(folder / "r78_team_board.jsonl")
            note_head = notes.inspect()["head"]
            task_head = tasks.inspect()["head"]
            board = TeamReviewBoard(self.workspace.graph, self.policy, notes, tasks)
            # Both sidecars must belong to the same validated R48 project
            # history. A structurally valid foreign notes file is not safe.
            board.verify_journals(self.actor)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Journaux refusés : " + str(exc))
            return False
        self.board = board
        self._notes_head, self._tasks_head = note_head, task_head
        self.refresh()
        self.status.setText(f"Journaux ouverts dans {folder} — pas de sauvegarde du jeu.")
        return True

    def compare(self):
        try:
            a, b = self.local_combo.currentData(), self.incoming_combo.currentData()
            if a is None or b is None:
                raise ValueError("Choisir deux révisions")
            # Semantic diff from immutable validated revision nodes.
            from drawtemp.sdk.semantic_review import semantic_diff
            left, right = self.workspace.graph.node(a), self.workspace.graph.node(b)
            lc, lp = left.revision.documents()
            rc, rp = right.revision.documents()
            changes = semantic_diff(lc, lp, rc, rp, typed_sequences=True)
            self.diff_table.setRowCount(len(changes))
            for i, change in enumerate(changes):
                for j, value in enumerate((
                        change.kind, change.path, str(change.before), str(change.after))):
                    self.diff_table.setItem(i, j, _item(value[:300]))
            self.status.setText(f"{len(changes)} changement(s) — aucune fusion appliquée.")
            return changes
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Comparaison refusée : " + str(exc))
            return None

    def choose_diff_path(self):
        rows = self.diff_table.selectionModel().selectedRows()
        if rows:
            item = self.diff_table.item(rows[0].row(), 1)
            if item is not None:
                self.path_edit.setText(item.text())
        self.refresh()

    def refresh(self, *_):
        self.notes_table.setRowCount(0)
        self.tasks_table.setRowCount(0)
        self._threads = ()
        if self.board is None or self._node_id() is None:
            return None
        try:
            notes = self.board.discussions(self.actor, self._node_id())
            tasks = self.board.tasks_for(self.actor)
            votes = self.board.decisions(self.actor, node_id=self._node_id())
            self._notes_head = self.board.notes.inspect()["head"]
            self._tasks_head = self.board.tasks.inspect()["head"]
            self._tasks = tasks
            rows = [(thread, note) for thread in notes for note in thread["comments"]]
            self.notes_table.setRowCount(len(rows))
            chosen_thread = self.thread_combo.currentData()
            self.thread_combo.blockSignals(True)
            self.thread_combo.clear()
            self.thread_combo.addItem("Nouvelle discussion", 0)
            try:
                target = self.board._anchor(self.path_edit.text())
            except ValueError:
                target = None
            self._threads = tuple(t for t in notes if t["anchor"] == target)
            for thread in self._threads:
                self.thread_combo.addItem(
                    f"#{thread['id']} — {'résolu' if thread['resolved'] else 'ouvert'}",
                    thread["id"])
            index = self.thread_combo.findData(chosen_thread)
            if index >= 0:
                self.thread_combo.setCurrentIndex(index)
            self.thread_combo.blockSignals(False)
            for i, (thread, note) in enumerate(rows):
                for j, value in enumerate((
                        f"#{thread['id']} ({thread['anchor']})",
                        note["author"], note["text"],
                        "Résolu" if thread["resolved"] else "Ouvert")):
                    self.notes_table.setItem(i, j, _item(value))
            self.tasks_table.setRowCount(len(tasks))
            for i, task in enumerate(tasks):
                for j, value in enumerate((
                        task["task"], task["title"], task["assignee"],
                        task["status"], task["release"], task["anchor"])):
                    self.tasks_table.setItem(i, j, _item(value))
            approvals = sum(vote["status"] == "approved" for vote in votes)
            requests = sum(vote["status"] == "changes_requested" for vote in votes)
            self.votes_status.setText(
                f"Avis consultatifs : {approvals} approbation(s), "
                f"{requests} demande(s) de changements. Aucune fusion automatique.")
            return {"notes": len(rows), "tasks": len(tasks), "votes": len(votes)}
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Rechargement refusé : " + str(exc))
            return None

    def _write(self, callback, *, note=False):
        if self.board is None or self._node_id() is None:
            self.status.setText("Configurer un dossier et une révision avant publication.")
            return None
        try:
            event = callback()
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Publication refusée (recharger pour résoudre un conflit) : " + str(exc))
            return None
        if note:
            self._notes_head = event["digest"]
        else:
            self._tasks_head = event["digest"]
        self.refresh()
        self.status.setText(
            f"Événement #{event['sequence']} enregistré explicitement. "
            "Le projet et l'historique Undo restent inchangés.")
        return event

    def post_note(self):
        text = self.note_text.toPlainText()
        result = self._write(lambda: self.board.note(
            self.actor, node_id=self._node_id(), path=self.path_edit.text(),
            expected_head=self._notes_head, text=text,
            thread=self.thread_combo.currentData() or 0), note=True)
        if result:
            self.note_text.clear()
        return result

    def toggle_thread(self):
        selected = self.thread_combo.currentData()
        thread = next((row for row in self._threads if row["id"] == selected), None)
        if thread is None:
            self.status.setText("Sélectionner une discussion avant de changer son état.")
            return None
        kind = "reopen" if thread["resolved"] else "resolve"
        return self._write(lambda: self.board.note(
            self.actor, node_id=self._node_id(), path=self.path_edit.text(),
            expected_head=self._notes_head, kind=kind, thread=selected), note=True)

    def post_review(self):
        return self._write(lambda: self.board.review(
            self.actor, node_id=self._node_id(), path=self.path_edit.text(),
            expected_head=self._tasks_head, decision=self.review_choice.currentData(),
            summary=self.review_summary.text()))

    def create_task(self):
        return self._write(lambda: self.board.create_task(
            self.actor, node_id=self._node_id(), path=self.path_edit.text(),
            expected_head=self._tasks_head, title=self.task_title.text(),
            assignee=self.task_assignee.text(), release=self.task_release.text()))

    def update_task(self):
        rows = self.tasks_table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._tasks):
            self.status.setText("Sélectionner une tâche existante.")
            return None
        task_id = self._tasks[rows[0].row()]["task"]
        return self._write(lambda: self.board.change_task(
            self.actor, task_id=task_id, expected_head=self._tasks_head,
            status=self.task_state.currentData()))
