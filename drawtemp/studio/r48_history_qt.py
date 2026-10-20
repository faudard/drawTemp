"""R48.B — Project History & Review as an opt-in Qt Widgets Studio dialog.

Qt only presents the validated R48.A3 DAG and R30 semantic review. The live
AuthoringSession owns all changes; Save/Undo remain under the main Studio.
Imported two-file snapshots are read-only; graph ancestry is operator-declared.
No hosted VCS service, Git mutation, automatic conflict choice or autosave.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.audit_reconciliation import reconcile_audit
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.review_notes import ReviewNoteStore, anchor_from_path, validate_anchor
from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace


def _cell(value):
    item = QTableWidgetItem(str(value))
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    return item


def _short(value):
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return rendered if len(rendered) <= 130 else rendered[:127] + "..."


def _label(node):
    return f"{node.label or 'Révision'} — {node.revision.author} ({node.node_id[:10]})"


class ProjectHistoryDialog(QDialog):
    """Review immutable history nodes, manually resolve conflicts, apply via Undo."""

    def __init__(self, session: AuthoringSession, *, graph=None, parent=None):
        super().__init__(parent)
        self.setObjectName("r48-history-dialog")
        self.setWindowTitle("DrawTemp — Project History & Review (R48.B)")
        self.resize(1120, 790)
        self.workspace = ProjectHistoryWorkspace(session, graph=graph)
        self._review = None
        self._choices = {}
        self._audit = None
        self._audit_head = None
        self._notes = None
        self._notes_head = None
        self._note_anchor = None

        # Keep every review/annotation control keyboard-reachable even on
        # laptop-height screens; never allow a fixed-height dialog to clip notes.
        outer = QVBoxLayout(self)
        scroller = QScrollArea(self)
        scroller.setObjectName("r48-history-scroll")
        scroller.setAccessibleName("Contenu défilant de la revue R48")
        scroller.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroller.setWidget(content)
        outer.addWidget(scroller)
        description = QLabel(
            "Historique LOCAL en mémoire. La filiation est déclarée, non vérifiée "
            "par Git. Importer une paire Content/GameProject, comparer deux "
            "versions, choisir chaque conflit. Appliquer = un Undo, sans sauvegarde disque.")
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(QLabel("Historique des snapshots"))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setObjectName("r48-history-table")
        self.history_table.setAccessibleName("Historique des révisions de projet")
        self.history_table.setHorizontalHeaderLabels(
            ("Version", "Auteur", "Libellé", "Parents", "SHA contenu"))
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setMinimumHeight(120)
        layout.addWidget(self.history_table)

        capture = QHBoxLayout()
        capture.addWidget(QLabel("Parent déclaré"))
        self.parent_combo = QComboBox()
        self.parent_combo.setObjectName("r48-parent")
        self.parent_combo.setAccessibleName("Parent du prochain snapshot")
        capture.addWidget(self.parent_combo, 2)
        capture.addWidget(QLabel("Auteur"))
        self.author_edit = QLineEdit("local")
        self.author_edit.setMaxLength(80)
        self.author_edit.setAccessibleName("Auteur déclaratif du snapshot")
        capture.addWidget(self.author_edit)
        capture.addWidget(QLabel("Libellé"))
        self.label_edit = QLineEdit("Version de travail")
        self.label_edit.setMaxLength(120)
        self.label_edit.setAccessibleName("Libellé de la version")
        capture.addWidget(self.label_edit, 2)
        layout.addLayout(capture)
        history_actions = QHBoxLayout()
        self.capture_button = QPushButton("Capturer le Studio actif")
        self.capture_button.setObjectName("r48-capture")
        self.capture_button.clicked.connect(self.capture_live)
        history_actions.addWidget(self.capture_button)
        self.import_button = QPushButton("Importer Content/GameProject…")
        self.import_button.setObjectName("r48-import")
        self.import_button.clicked.connect(self._choose_import)
        history_actions.addWidget(self.import_button)
        layout.addLayout(history_actions)
        durable_row = QHBoxLayout()
        self.history_path = QLineEdit()
        self.history_path.setObjectName("r48-history-path")
        self.history_path.setReadOnly(True)
        self.history_path.setAccessibleName("Fichier de l'historique R48 conservé séparément")
        self.history_path.setPlaceholderText("Historique non enregistré — choisir un fichier")
        durable_row.addWidget(self.history_path, 3)
        self.history_save_button = QPushButton("Enregistrer l'historique…")
        self.history_save_button.setObjectName("r48-history-save")
        self.history_save_button.setAccessibleName(
            "Enregistrer explicitement les révisions dans un fichier local")
        self.history_save_button.clicked.connect(self._save_history_dialog)
        durable_row.addWidget(self.history_save_button)
        self.history_load_button = QPushButton("Ouvrir un historique…")
        self.history_load_button.setObjectName("r48-history-load")
        self.history_load_button.clicked.connect(self._load_history_dialog)
        durable_row.addWidget(self.history_load_button)
        layout.addLayout(durable_row)

        compare_row = QHBoxLayout()
        compare_row.addWidget(QLabel("Locale (Studio actuel)"))
        self.local_combo = QComboBox()
        self.local_combo.setObjectName("r48-local")
        self.local_combo.setAccessibleName("Version locale correspondant au Studio")
        compare_row.addWidget(self.local_combo, 2)
        compare_row.addWidget(QLabel("Entrante"))
        self.incoming_combo = QComboBox()
        self.incoming_combo.setObjectName("r48-incoming")
        self.incoming_combo.setAccessibleName("Version entrante à fusionner")
        compare_row.addWidget(self.incoming_combo, 2)
        layout.addLayout(compare_row)

        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Ancêtre commun"))
        self.base_combo = QComboBox()
        self.base_combo.setObjectName("r48-base")
        self.base_combo.setAccessibleName("Ancêtre commun maximal")
        base_row.addWidget(self.base_combo, 3)
        self.compare_button = QPushButton("Comparer les versions")
        self.compare_button.setObjectName("r48-compare")
        self.compare_button.setShortcut("Alt+C")
        self.compare_button.setToolTip("Alt+C : comparer les versions sélectionnées")
        self.compare_button.clicked.connect(self.compare_selected)
        base_row.addWidget(self.compare_button)
        layout.addLayout(base_row)

        self.review_table = QTableWidget(0, 6)
        self.review_table.setObjectName("r48-review-table")
        self.review_table.setAccessibleName("Différences et conflits sémantiques R48")
        self.review_table.setHorizontalHeaderLabels(
            ("Origine", "Chemin", "Base", "Local", "Entrant", "Décision"))
        self.review_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.review_table.setMinimumHeight(180)
        self.review_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.review_table.setAccessibleDescription(
            "Naviguer par lignes avec les flèches. Les conflits se résolvent "
            "via les menus de la colonne Décision. Les notes sont indépendantes.")
        layout.addWidget(self.review_table)

        review_actions = QHBoxLayout()
        self.apply_button = QPushButton("Appliquer la revue au Studio…")
        self.apply_button.setObjectName("r48-apply")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._confirm_apply)
        review_actions.addWidget(self.apply_button)
        layout.addLayout(review_actions)

        notes_title = QLabel("Commentaires de revue (fichier local séparé)")
        notes_title.setObjectName("r48-notes-heading")
        layout.addWidget(notes_title)
        notes_header = QHBoxLayout()
        self.notes_path = QLineEdit()
        self.notes_path.setReadOnly(True)
        self.notes_path.setObjectName("r48-notes-path")
        self.notes_path.setPlaceholderText("Choisir explicitement le fichier de revue (.jsonl)")
        self.notes_path.setAccessibleName("Chemin du journal de commentaires")
        notes_header.addWidget(self.notes_path, 3)
        choose_notes = QPushButton("Choisir un journal…")
        choose_notes.setObjectName("r48-notes-select")
        choose_notes.clicked.connect(self._choose_notes)
        notes_header.addWidget(choose_notes)
        self.notes_refresh_button = QPushButton("Recharger les notes")
        self.notes_refresh_button.setEnabled(False)
        self.notes_refresh_button.setObjectName("r48-notes-refresh")
        self.notes_refresh_button.clicked.connect(self.refresh_notes)
        notes_header.addWidget(self.notes_refresh_button)
        layout.addLayout(notes_header)

        note_target = QHBoxLayout()
        note_target.addWidget(QLabel("Version annotée"))
        self.note_revision_combo = QComboBox()
        self.note_revision_combo.setObjectName("r48-note-revision")
        self.note_revision_combo.setAccessibleName("Révision à laquelle rattacher une note")
        self.note_revision_combo.currentIndexChanged.connect(self._update_note_target)
        note_target.addWidget(self.note_revision_combo, 2)
        note_target.addWidget(QLabel("Identifiant de ressource"))
        self.note_anchor_edit = QLineEdit()
        self.note_anchor_edit.setReadOnly(True)
        self.note_anchor_edit.setObjectName("r48-note-anchor")
        self.note_anchor_edit.setAccessibleName("Chemin d'ancrage stable de la ressource")
        note_target.addWidget(self.note_anchor_edit, 3)
        layout.addLayout(note_target)

        self.notes_table = QTableWidget(0, 4)
        self.notes_table.setObjectName("r48-notes-table")
        self.notes_table.setAccessibleName("Discussions de revue de la ressource")
        self.notes_table.setAccessibleDescription(
            "Chaque ligne indique un commentaire ou une réponse, son auteur "
            "et le statut du fil. Les annotations ne résolvent pas les conflits.")
        self.notes_table.setHorizontalHeaderLabels(
            ("Fil", "Auteur", "Message", "État"))
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notes_table.setMaximumHeight(110)
        layout.addWidget(self.notes_table)

        note_edit_row = QHBoxLayout()
        note_edit_row.addWidget(QLabel("Fil"))
        self.note_thread_combo = QComboBox()
        self.note_thread_combo.setObjectName("r48-note-thread")
        self.note_thread_combo.setAccessibleName("Discussion à laquelle répondre")
        self.note_thread_combo.currentIndexChanged.connect(self._update_note_buttons)
        note_edit_row.addWidget(self.note_thread_combo)
        self.note_text = QPlainTextEdit()
        self.note_text.setObjectName("r48-note-message")
        self.note_text.setAccessibleName("Commentaire de revue")
        self.note_text.setPlaceholderText("Nouveau commentaire ou réponse…")
        self.note_text.setMaximumHeight(72)
        self.note_text.textChanged.connect(self._update_note_buttons)
        note_edit_row.addWidget(self.note_text, 4)
        self.post_note_button = QPushButton("Publier la note")
        self.post_note_button.setObjectName("r48-note-post")
        self.post_note_button.setShortcut("Alt+P")
        self.post_note_button.setToolTip("Alt+P ou Ctrl+Entrée : publier le commentaire")
        self.post_note_button.setEnabled(False)
        self.post_note_button.clicked.connect(self.post_note)
        note_edit_row.addWidget(self.post_note_button)
        self.resolve_note_button = QPushButton("Résoudre / rouvrir")
        self.resolve_note_button.setObjectName("r48-note-resolve")
        self.resolve_note_button.setEnabled(False)
        self.resolve_note_button.clicked.connect(self.toggle_note)
        note_edit_row.addWidget(self.resolve_note_button)
        layout.addLayout(note_edit_row)
        self.notes_status = QLabel("Les commentaires restent distincts du jeu et des conflits.")
        self.notes_status.setObjectName("r48-notes-status")
        self.notes_status.setAccessibleName("Diagnostic des commentaires de revue")
        self.notes_status.setWordWrap(True)
        layout.addWidget(self.notes_status)

        audit_row = QHBoxLayout()
        self.audit_path = QLineEdit()
        self.audit_path.setReadOnly(True)
        self.audit_path.setPlaceholderText("Journal d'audit facultatif (lecture seule)")
        self.audit_path.setAccessibleName("Journal d'audit inspecté")
        audit_row.addWidget(self.audit_path, 3)
        audit_button = QPushButton("Choisir un audit…")
        audit_button.clicked.connect(self._choose_audit)
        audit_row.addWidget(audit_button)
        self.audit_button = QPushButton("Vérifier l'audit")
        self.audit_button.setEnabled(False)
        self.audit_button.clicked.connect(self.check_audit)
        audit_row.addWidget(self.audit_button)
        layout.addLayout(audit_row)
        self.audit_status = QLabel("Aucun journal sélectionné. Aucune écriture automatique.")
        self.audit_status.setObjectName("r48-audit-status")
        self.audit_status.setWordWrap(True)
        self.audit_status.setAccessibleName("Résultat du contrôle d'audit")
        layout.addWidget(self.audit_status)

        self.status = QLabel("Capturer le Studio ou importer un snapshot pour commencer.")
        self.status.setObjectName("r48-status")
        self.status.setAccessibleName("Diagnostic de la revue des versions")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button)

        self.local_combo.currentIndexChanged.connect(self._update_bases)
        self.incoming_combo.currentIndexChanged.connect(self._update_bases)
        self.base_combo.currentIndexChanged.connect(self._invalidate_review)
        self.review_table.itemSelectionChanged.connect(self._update_note_target)
        self._notes_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self._notes_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._notes_shortcut.activated.connect(self.post_note)
        self._populate_history()

    def _invalidate_review(self, *_):
        self.workspace.invalidate()
        self._review = None
        self._choices.clear()
        self.review_table.setRowCount(0)
        self.apply_button.setEnabled(False)
        self._note_anchor = None
        self.note_anchor_edit.clear()
        self._update_note_buttons()

    def _populate_history(self, *, selected_local=None, selected_incoming=None):
        self._invalidate_review()
        nodes = self.workspace.revisions()
        self.history_table.setRowCount(len(nodes))
        for row, node in enumerate(nodes):
            values = (node.node_id[:12], node.revision.author, node.label,
                      ", ".join(parent[:10] for parent in node.parents) or "racine",
                      node.revision.digest[:16])
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, _cell(value))
            self.history_table.item(row, 0).setToolTip(node.node_id)
        combos = (self.parent_combo, self.local_combo, self.incoming_combo)
        previous = tuple(combo.currentData() for combo in combos)
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            for node in nodes:
                combo.addItem(_label(node), node.node_id)
        def select(combo, identity):
            index = combo.findData(identity)
            if index >= 0:
                combo.setCurrentIndex(index)
        select(self.parent_combo, previous[0])
        select(self.local_combo, selected_local or previous[1])
        select(self.incoming_combo, selected_incoming or previous[2])
        for combo in combos:
            combo.blockSignals(False)
        selected_note = self.note_revision_combo.currentData()
        self.note_revision_combo.blockSignals(True)
        self.note_revision_combo.clear()
        for node in nodes:
            self.note_revision_combo.addItem(_label(node), node.node_id)
        preferred = selected_incoming or selected_local or selected_note
        index = self.note_revision_combo.findData(preferred)
        if index >= 0:
            self.note_revision_combo.setCurrentIndex(index)
        self.note_revision_combo.blockSignals(False)
        self._update_bases()
        self._update_note_target()

    def _update_bases(self, *_):
        self._invalidate_review()
        selected = self.base_combo.currentData()
        self.base_combo.blockSignals(True)
        self.base_combo.clear()
        self.base_combo.addItem("Automatique (uniquement si ancêtre unique)", None)
        local, incoming = self.local_combo.currentData(), self.incoming_combo.currentData()
        if local and incoming and local != incoming:
            try:
                for node_id in self.workspace.graph.common_bases(local, incoming):
                    node = self.workspace.graph.node(node_id)
                    self.base_combo.addItem(_label(node), node_id)
            except ValueError:
                pass
        if selected is not None:
            index = self.base_combo.findData(selected)
            if index >= 0:
                self.base_combo.setCurrentIndex(index)
        self.base_combo.blockSignals(False)

    def capture_live(self):
        self._invalidate_review()
        try:
            node = self.workspace.capture_live(
                parent_id=self.parent_combo.currentData(),
                author=self.author_edit.text().strip(),
                label=self.label_edit.text().strip())
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Capture refusée : " + str(exc))
            return None
        self._populate_history(selected_local=node.node_id)
        self.status.setText("Snapshot local en mémoire : " + node.node_id[:12] +
                            ". Aucun fichier modifié.")
        return node

    def _save_history_dialog(self):
        if self.workspace.history_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Enregistrer un historique R48 indépendant", "",
                "Historique DrawTemp (*.r48.json);;JSON (*.json)")
            if not path:
                return
        else:
            path = self.workspace.history_path
        self.save_history(path)

    def save_history(self, path=None):
        try:
            digest = self.workspace.save_history(path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Historique non enregistré : " + str(exc))
            return None
        self.history_path.setText(str(self.workspace.history_path))
        self.status.setText(
            f"Historique enregistré explicitement ({len(self.workspace.graph)} révisions, "
            f"SHA {digest[:12]}). Les fichiers du jeu sont inchangés.")
        return digest

    def _load_history_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un historique R48 validé", "",
            "Historique DrawTemp (*.r48.json);;JSON (*.json)")
        if path:
            self.load_history(path)

    def load_history(self, path):
        try:
            graph = self.workspace.load_history(path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Chargement de l'historique refusé : " + str(exc))
            return None
        self.history_path.setText(str(self.workspace.history_path))
        self._populate_history()
        self.status.setText(
            f"{len(graph)} versions validées rechargées. "
            "Aucun Content/GameProject ni commentaire modifié.")
        return graph

    def _choose_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer Content (GameProject adjacent requis)", "",
            "Content JSON (*.json)")
        if path:
            self.import_pair(path)

    def import_pair(self, path):
        self._invalidate_review()
        try:
            node = self.workspace.import_pair(
                path, parent_id=self.parent_combo.currentData(),
                author=self.author_edit.text().strip(),
                label=self.label_edit.text().strip())
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Import refusé : " + str(exc))
            return None
        self._populate_history(selected_incoming=node.node_id)
        self.status.setText("Paire Content/GameProject validée et importée : " +
                            node.node_id[:12] + ". Projet original inchangé.")
        return node

    def compare_selected(self):
        self._invalidate_review()
        try:
            preview = self.workspace.compare(
                self.local_combo.currentData(), self.incoming_combo.currentData(),
                base_id=self.base_combo.currentData())
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText("Comparaison refusée : " + str(exc))
            return None
        self._review = preview
        self._render_review(preview)
        return preview

    def _render_review(self, preview):
        changes = ([("Local", row) for row in preview.local_changes] +
                   [("Entrant", row) for row in preview.incoming_changes])
        self.review_table.setRowCount(len(changes) + len(preview.conflicts))
        for i, (origin, change) in enumerate(changes):
            values = (origin, change.path, _short(change.before),
                      _short(change.after) if origin == "Local" else "",
                      _short(change.after) if origin == "Entrant" else "", "")
            for j, value in enumerate(values):
                self.review_table.setItem(i, j, _cell(value))
        self._choices.clear()
        for i, conflict in enumerate(preview.conflicts, start=len(changes)):
            values = ("Conflit", conflict.path, _short(conflict.base),
                      _short(conflict.local), _short(conflict.incoming))
            for j, value in enumerate(values):
                self.review_table.setItem(i, j, _cell(value))
            selector = QComboBox()
            selector.addItem("Choisir…", None)
            selector.addItem("Conserver local", "local")
            selector.addItem("Accepter entrant", "incoming")
            selector.setAccessibleName("Résolution du conflit " + conflict.path)
            selector.currentIndexChanged.connect(self._update_apply)
            self.review_table.setCellWidget(i, 5, selector)
            self._choices[conflict.path] = selector
        self.status.setText(
            f"{len(changes)} changement(s), {len(preview.conflicts)} conflit(s). "
            "Une décision explicite est obligatoire pour chaque conflit. "
            "L'application modifie la session, pas le disque.")
        self._update_apply()
        self._update_note_target()

    def _update_apply(self, *_):
        has_changes = (self._review is not None and
                       bool(self._review.local_changes or
                            self._review.incoming_changes))
        complete = all(combo.currentData() in ("local", "incoming")
                       for combo in self._choices.values())
        self.apply_button.setEnabled(bool(has_changes and complete))

    def _confirm_apply(self):
        if not self.apply_button.isEnabled():
            return
        approved = QMessageBox.question(
            self, "Confirmer la fusion R48",
            "Appliquer dans le Studio actif ? Un Undo reste possible. "
            "Aucun enregistrement disque ni commit Git ne sera réalisé.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if approved == QMessageBox.Yes:
            self.apply_review()

    def apply_review(self):
        if not self.apply_button.isEnabled():
            return None
        choices = {path: combo.currentData() for path, combo in self._choices.items()}
        try:
            transition = self.workspace.apply(choices)
        except (ValueError, OSError, TypeError) as exc:
            self._invalidate_review()
            self.status.setText("Application refusée : " + str(exc))
            return None
        self._invalidate_review()
        self.status.setText(
            f"Fusion appliquée à la révision Studio {transition.snapshot.revision}. "
            "Utilisez Enregistrer dans le Studio ou Annuler (Undo). "
            "Capturez la nouvelle version pour l'ajouter à cet historique.")
        return transition

    def _choose_notes(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Journal de revue distinct du Content/GameProject", "",
            "Commentaires JSONL (*.jsonl)")
        if path:
            self.load_notes(path)

    def load_notes(self, path):
        try:
            store = ReviewNoteStore(path)
            status = store.inspect()  # Integrity check; never silently repair.
        except (ValueError, OSError) as exc:
            self._notes = None
            self._notes_head = None
            self.notes_path.clear()
            self.notes_refresh_button.setEnabled(False)
            self.notes_status.setText("Journal de commentaires refusé : " + str(exc))
            self._update_note_target()
            return False
        self._notes = store
        self._notes_head = status["head"]
        self.notes_path.setText(str(store.path))
        self.notes_refresh_button.setEnabled(True)
        self.notes_status.setText(
            f"{status['count']} événement(s) vérifié(s). HEAD épinglé ; "
            "aucune écriture sans publication explicite.")
        self._update_note_target()
        return True

    def refresh_notes(self):
        if self._notes is None:
            return None
        try:
            status = self._notes.inspect()
        except (ValueError, OSError) as exc:
            self.notes_status.setText("Journal non vérifiable : " + str(exc))
            self._update_note_buttons()
            return None
        self._notes_head = status["head"]
        self._update_note_target()
        self.notes_status.setText(
            f"{status['count']} événement(s) rechargé(s) explicitement. "
            "Aucun contenu Studio modifié.")
        return status

    def _note_node(self):
        identity = self.note_revision_combo.currentData()
        if identity is None:
            return None
        return self.workspace.graph.node(identity)

    def _update_note_target(self, *_):
        self._note_anchor = None
        self.note_anchor_edit.clear()
        rows = self.review_table.selectionModel().selectedRows()
        if rows:
            cell = self.review_table.item(rows[0].row(), 1)
            if cell is not None:
                try:
                    anchor = anchor_from_path(cell.text())
                    node = self._note_node()
                    if node is not None:
                        validate_anchor(node, anchor)
                        self._note_anchor = anchor
                        self.note_anchor_edit.setText(anchor)
                except (ValueError, TypeError):
                    pass
        self._populate_notes()

    def _populate_notes(self):
        selected = self.note_thread_combo.currentData()
        self.note_thread_combo.blockSignals(True)
        self.note_thread_combo.clear()
        self.note_thread_combo.addItem("Nouvelle discussion", 0)
        self.notes_table.setRowCount(0)
        if self._notes is not None and self._note_anchor is not None:
            try:
                node = self._note_node()
                threads = self._notes.threads(
                    node_id=node.node_id, anchor=self._note_anchor)
            except (ValueError, OSError, TypeError) as exc:
                self.notes_status.setText("Notes non vérifiables : " + str(exc))
                threads = ()
            self.notes_table.setRowCount(
                sum(len(thread["comments"]) for thread in threads))
            row_index = 0
            for thread in threads:
                state = "Résolu" if thread["resolved"] else "Ouvert"
                for index, comment in enumerate(thread["comments"]):
                    values = (
                        f"#{thread['id']}" if not index else
                        f"#{thread['id']} ↳ {index}",
                        comment["author"], comment["text"], state,
                    )
                    for column, value in enumerate(values):
                        self.notes_table.setItem(row_index, column, _cell(value))
                    row_index += 1
                self.note_thread_combo.addItem(
                    f"Fil #{thread['id']} — {'résolu' if thread['resolved'] else 'ouvert'}",
                    thread["id"])
        if selected:
            idx = self.note_thread_combo.findData(selected)
            if idx >= 0:
                self.note_thread_combo.setCurrentIndex(idx)
        self.note_thread_combo.blockSignals(False)
        self._update_note_buttons()

    def _update_note_buttons(self, *_):
        ready = (self._notes is not None and self._note_anchor is not None and
                 self.note_revision_combo.currentData() is not None)
        self.post_note_button.setEnabled(bool(
            ready and self.note_text.toPlainText().strip() and
            len(self.note_text.toPlainText()) <= 2000))
        self.resolve_note_button.setEnabled(bool(
            ready and self.note_thread_combo.currentData()))

    def _publish_note_event(self, *, kind, text=""):
        if self._notes is None or self._note_anchor is None:
            return None
        node = self._note_node()
        try:
            record = self._notes.append(
                node, expected_head=self._notes_head,
                anchor=self._note_anchor, author=self.author_edit.text().strip(),
                text=text, kind=kind, thread=self.note_thread_combo.currentData() or 0)
        except (ValueError, OSError, TypeError) as exc:
            self.notes_status.setText(
                "Publication refusée (recharger après conflit externe) : " + str(exc))
            return None
        self._notes_head = record["digest"]
        self._populate_notes()
        self.notes_status.setText(
            f"Événement de revue #{record['sequence']} enregistré séparément. "
            "Aucune décision de fusion ni sauvegarde du jeu.")
        return record

    def post_note(self):
        if not self.post_note_button.isEnabled():
            return None
        result = self._publish_note_event(
            kind="comment", text=self.note_text.toPlainText())
        if result is not None:
            self.note_text.clear()
        return result

    def toggle_note(self):
        if not self.resolve_note_button.isEnabled():
            return None
        # Use the verified materialized state rather than trusting UI labels.
        try:
            node = self._note_node()
            threads = self._notes.threads(
                node_id=node.node_id, anchor=self._note_anchor)
            thread = next(row for row in threads
                          if row["id"] == self.note_thread_combo.currentData())
            kind = "reopen" if thread["resolved"] else "resolve"
        except (ValueError, OSError, StopIteration, TypeError) as exc:
            self.notes_status.setText("Fil non vérifiable : " + str(exc))
            return None
        return self._publish_note_event(kind=kind)

    def _choose_audit(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Journal d'audit R48 (lecture seule)", "", "Journal JSONL (*.jsonl)")
        if path:
            self.load_audit(path)

    def load_audit(self, path):
        try:
            audit = LocalAuditLog(Path(path))
            head = audit.inspect()["head"]
        except (ValueError, OSError) as exc:
            self.audit_status.setText("Audit refusé : " + str(exc))
            self.audit_button.setEnabled(False)
            self._audit = None
            self._audit_head = None
            self.audit_path.clear()
            return False
        self._audit = audit
        self._audit_head = head
        self.audit_path.setText(str(audit.path))
        self.audit_button.setEnabled(True)
        self.audit_status.setText(
            "Journal inspecté (HEAD épinglé localement). Vérification en lecture seule.")
        return True

    def check_audit(self):
        if self._audit is None:
            return None
        try:
            report = reconcile_audit(
                self._audit, self.workspace.session,
                known_revisions=tuple(node.revision
                                      for node in self.workspace.revisions()),
                expected_head=self._audit_head)
        except (ValueError, OSError) as exc:
            self.audit_status.setText("Audit non vérifiable : " + str(exc))
            return None
        self.audit_status.setText(
            f"Audit : {report.state} — {report.count} entrée(s), "
            f"{len(report.unknown_records)} preuve(s) absente(s), "
            f"{len(report.discontinuities)} discontinuité(s). "
            "Diagnostic seulement, sans autorisation d'écrasement.")
        return report
