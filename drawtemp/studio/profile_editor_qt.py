"""R28.B — Qt Widgets profile inspector for canonical R25 game_modes.

A profile preview is declarative (not a Player simulation). All changes go
through the same R1 AuthoringSession used by the other Studio workspaces.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.profile_authoring import (
    FIELDS, PRESETS, VALUES, ProfileEditorError, apply_profile_edit,
    inspect_profile, preview_profile_edit, profile_targets,
)


class ProfileEditorWidget(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._loading = False
        self._pending = None
        self.setObjectName("r28-profile-inspector")
        layout = QVBoxLayout(self)
        heading = QLabel("Profils de jeu — projet et scènes (R28.B)")
        layout.addWidget(heading)
        description = QLabel(
            "Paramètres persistés dans GameProject (R25). "
            "Les profils action/RPG/narratif ne rendent pas encore ces modes "
            "jouables dans le Player. Les missions tactiques restent CT.")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.scope = QComboBox()
        self.scope.setAccessibleName("Portée du profil")
        form.addRow("Projet / scène", self.scope)
        self.selection = QComboBox()
        self.selection.setAccessibleName("Profil de jeu")
        self.selection.addItem("Hériter / retour au défaut", None)
        for key, label in (
            ("srpg", "SRPG tactique"), ("action", "Action-aventure"),
            ("classic_rpg", "RPG classique"), ("narrative", "Narratif"),
            ("hybrid", "Hybride")):
            self.selection.addItem(label, key)
        self.selection.addItem("Personnalisé (capacités typées)", "custom")
        form.addRow("Modèle", self.selection)
        self.fields = {}
        for field in FIELDS:
            widget = QComboBox()
            widget.setAccessibleName("Capacité " + field)
            for value in sorted(VALUES[field]):
                widget.addItem(value, value)
            form.addRow(field.capitalize(), widget)
            self.fields[field] = widget
        layout.addLayout(form)
        self.pin_ct = QCheckBox("Conserver les missions existantes en CT (overrides explicites)")
        self.pin_ct.setChecked(True)
        layout.addWidget(self.pin_ct)

        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        layout.addWidget(QLabel("Aperçu transactionnel — aucune écriture avant Appliquer"))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName("r28-profile-preview")
        self.diagnostics.setAccessibleName("Diagnostics et différences de profil")
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.diagnostics, 1)
        bar = QHBoxLayout()
        self.apply_button = QPushButton("Appliquer à la session")
        self.apply_button.setObjectName("r28-profile-apply")
        self.apply_button.clicked.connect(self.apply_changes)
        bar.addWidget(self.apply_button)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        self.scope.currentIndexChanged.connect(self._load_scope)
        self.selection.currentIndexChanged.connect(self._on_change)
        self.pin_ct.toggled.connect(self._on_change)
        for field in FIELDS:
            self.fields[field].currentIndexChanged.connect(self._on_change)
        self.refresh()

    def refresh(self):
        """Also called after shell undo/redo, project open, or external editor."""
        old = self.scope.currentData()
        self._loading = True
        self.scope.clear()
        for scene_id, label in profile_targets(self.session.snapshot()):
            self.scope.addItem(label + ("  [" + scene_id + "]" if scene_id else ""), scene_id)
        index = self.scope.findData(old)
        self.scope.setCurrentIndex(index if index >= 0 else 0)
        self._loading = False
        self._load_scope()

    def _load_scope(self, *_):
        if self._loading:
            return
        self._loading = True
        info = inspect_profile(self.session.snapshot(), self.scope.currentData())
        choice = info["selection"]
        if choice is None:
            key = None
        elif "preset" in choice:
            key = choice["preset"]
        else:
            key = "custom"
        idx = self.selection.findData(key)
        self.selection.setCurrentIndex(idx if idx >= 0 else 0)
        for name, value in info["effective"].items():
            self.fields[name].setCurrentIndex(self.fields[name].findData(value))
        self.source_label.setText(
            "Origine : " + info["source"] + " | révision " + str(info["revision"]))
        self._loading = False
        self._on_change()

    def _on_change(self, *_):
        if self._loading:
            return
        custom = self.selection.currentData() == "custom"
        for widget in self.fields.values():
            widget.setEnabled(custom)
        project_scope = self.scope.currentData() is None
        self.pin_ct.setEnabled(project_scope)
        self._pending = None
        self.apply_button.setEnabled(False)
        key = self.selection.currentData()
        entry = ({"profile": {name: self.fields[name].currentData() for name in FIELDS}}
                 if key == "custom" else ({"preset": key} if key is not None else None))
        try:
            preview = preview_profile_edit(
                self.session, self.scope.currentData(), entry,
                expected_revision=self.session.revision,
                protect_tactical=project_scope and self.pin_ct.isChecked())
            self._pending = preview if preview.report["changed"] else None
            self.apply_button.setEnabled(self._pending is not None)
            self.diagnostics.setPlainText(
                json.dumps(preview.report, indent=2, ensure_ascii=False))
        except (AuthoringError, ProfileEditorError, ValueError, TypeError) as exc:
            self.diagnostics.setPlainText("Validation bloquante : " + str(exc))

    def apply_changes(self):
        if self._pending is None:
            return
        try:
            apply_profile_edit(self.session, self._pending)
        except (AuthoringError, ProfileEditorError, ValueError) as exc:
            self.diagnostics.setPlainText("Modification refusée : " + str(exc))
            self._pending = None
            self.apply_button.setEnabled(False)
            return
        self.refresh()
        self.updated.emit()
