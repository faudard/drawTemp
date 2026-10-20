"""R65.B Qt Widgets Combat Composer, backed by a single R1 Studio session.

No authored boss patterns are executed here: this window only edits validated
declarative metadata. Schematic hitbox is computed from real R65.A geometry.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.studio.combat_composer_r65 import (
    CombatComposerDraft, inspect_combat_presets,
)
from sporebound.action_combat_catalog_r65 import (
    hitbox_preview, starter_preset, windows_preview,
)


def _table(columns, name):
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setAccessibleName(name)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setMinimumHeight(120)
    return table


def _cell(table, row, column):
    item = table.item(row, column)
    return item.text().strip() if item is not None else ""


class CombatComposerDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.draft = None
        self._loading = False
        self.setObjectName("r65-combat-composer")
        self.setWindowTitle("R65.B — Combat Composer")
        self.resize(1140, 840)

        main = QVBoxLayout(self)
        explanation = QLabel(
            "Composer des fenêtres d'attaque, projectiles et télégraphies. "
            "Les patterns boss sont déclaratifs (exécution prévue en R65.C). "
            "Aucune animation R36 ni FPS réel n'est simulé dans cet aperçu.")
        explanation.setWordWrap(True)
        main.addWidget(explanation)

        top = QHBoxLayout()
        main.addLayout(top)
        top.addWidget(QLabel("Preset"))
        self.presets = QComboBox()
        self.presets.setObjectName("r65-presets")
        self.presets.setAccessibleName("Preset de combat à éditer")
        top.addWidget(self.presets, 1)
        self.new_button = QPushButton("Nouveau preset")
        self.new_button.setObjectName("r65-new")
        top.addWidget(self.new_button)

        identity = QFormLayout()
        self.identifier = QLineEdit()
        self.identifier.setObjectName("r65-id")
        self.identifier.setAccessibleName("Identifiant du preset")
        self.label = QLineEdit()
        self.label.setObjectName("r65-label")
        self.label.setAccessibleName("Libellé du preset")
        identity.addRow("Identifiant", self.identifier)
        identity.addRow("Nom", self.label)
        main.addLayout(identity)

        main.addWidget(QLabel(
            "Combo (ticks entiers, 60 Hz) : windup → active → recovery"))
        self.moves = _table(
            ["Windup", "Active", "Recovery", "Range", "Damage", "Stagger", "Burn"],
            "Séquence de combo et fenêtres de frappe")
        self.moves.setObjectName("r65-combo-table")
        main.addWidget(self.moves, 2)
        move_controls = QHBoxLayout()
        main.addLayout(move_controls)
        for label, callback in (
            ("+ Coup", self.add_move), ("− Coup", self.remove_move),
            ("↑", lambda: self.move_row(self.moves, -1)),
            ("↓", lambda: self.move_row(self.moves, 1)),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            move_controls.addWidget(button)
        move_controls.addStretch()

        main.addWidget(QLabel("Projectile : vitesse, durée de vie, cadence et impact"))
        projectile = QWidget()
        projectile_layout = QGridLayout(projectile)
        self.shot = {}
        for i, (field, lower, upper) in enumerate(
            (("speed", 100, 1000), ("ttl", 1, 60), ("cooldown", 1, 120),
             ("damage", 1, 30), ("stagger", 0, 60), ("burn_ticks", 0, 120))
        ):
            spin = QSpinBox()
            spin.setRange(lower, upper)
            spin.setAccessibleName("Projectile " + field)
            self.shot[field] = spin
            projectile_layout.addWidget(QLabel(field), i // 3, (i % 3) * 2)
            projectile_layout.addWidget(spin, i // 3, (i % 3) * 2 + 1)
            spin.valueChanged.connect(self.invalidate)
        main.addWidget(projectile)

        main.addWidget(QLabel("Télégraphies : indices de coup 0..N−1, −1 hors mêlée"))
        self.cues = _table(
            ["Texte", "Type", "Coup", "Avance (ticks)"],
            "Télégraphies déclaratives; elles ne jouent pas d'animation")
        self.cues.setObjectName("r65-cues")
        main.addWidget(self.cues, 1)
        cue_controls = QHBoxLayout()
        main.addLayout(cue_controls)
        for label, cb in (("+ Télégraphie", self.add_cue),
                          ("− Télégraphie", lambda: self.remove_row(self.cues))):
            button = QPushButton(label)
            button.clicked.connect(cb)
            cue_controls.addWidget(button)
        cue_controls.addStretch()

        main.addWidget(QLabel(
            "Boss : chaque ligne est une étape (même ID/phase/seuil = même pattern). "
            "Prévisualisation seulement."))
        self.patterns = _table(
            ["ID pattern", "Phase", "PV ≤ %", "Action", "Répétitions", "Attente"],
            "Chorégraphie boss déclarative, non exécutée")
        self.patterns.setObjectName("r65-boss-patterns")
        main.addWidget(self.patterns, 1)
        boss_controls = QHBoxLayout()
        main.addLayout(boss_controls)
        for label, cb in (("+ Étape boss", self.add_pattern),
                          ("− Étape boss", lambda: self.remove_row(self.patterns))):
            button = QPushButton(label)
            button.clicked.connect(cb)
            boss_controls.addWidget(button)
        boss_controls.addStretch()

        lower = QHBoxLayout()
        main.addLayout(lower, 2)
        hitbox_column = QVBoxLayout()
        lower.addLayout(hitbox_column, 1)
        hitbox_column.addWidget(QLabel(
            "Hitbox géométrique R65.A (H héros, X touche, E ennemi)"))
        self.hitbox = QTableWidget(9, 9)
        self.hitbox.setObjectName("r65-hitbox-preview")
        self.hitbox.setAccessibleName("Carte 9 par 9 des cases couvertes")
        self.hitbox.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hitbox.horizontalHeader().hide()
        self.hitbox.verticalHeader().hide()
        hitbox_column.addWidget(self.hitbox)
        self.report = QPlainTextEdit()
        self.report.setObjectName("r65-report")
        self.report.setAccessibleName("Rapport des fenêtres et preview de combat")
        self.report.setReadOnly(True)
        lower.addWidget(self.report, 2)

        actions = QHBoxLayout()
        main.addLayout(actions)
        self.preview_button = QPushButton("Prévisualiser")
        self.preview_button.setObjectName("r65-preview")
        self.apply_button = QPushButton("Appliquer au projet")
        self.apply_button.setObjectName("r65-apply")
        self.undo_button = QPushButton("Annuler")
        self.redo_button = QPushButton("Rétablir")
        self.reload_button = QPushButton("Recharger")
        for button, callback in (
            (self.preview_button, self.preview),
            (self.apply_button, self.apply),
            (self.undo_button, self.undo),
            (self.redo_button, self.redo),
            (self.reload_button, self.reload),
        ):
            actions.addWidget(button)
            button.clicked.connect(callback)
        self.apply_button.setEnabled(False)

        self.presets.currentIndexChanged.connect(self.load_selected)
        self.new_button.clicked.connect(self.new_preset)
        self.identifier.textChanged.connect(self.invalidate)
        self.label.textChanged.connect(self.invalidate)
        for table in (self.moves, self.cues, self.patterns):
            table.itemChanged.connect(self.invalidate)
        self.reload()

    def invalidate(self, *_):
        if not self._loading:
            if self.draft is not None:
                self.draft.pending = None
            self.apply_button.setEnabled(False)

    def _rows(self, table, fields):
        return [[_cell(table, row, col) for col in range(fields)]
                for row in range(table.rowCount())]

    def _fill(self, table, rows):
        table.blockSignals(True)
        try:
            table.setRowCount(0)
            for row in rows:
                index = table.rowCount()
                table.insertRow(index)
                for col, value in enumerate(row):
                    table.setItem(index, col, QTableWidgetItem(str(value)))
        finally:
            table.blockSignals(False)

    def load_selected(self, *_):
        if self._loading:
            return
        name = self.presets.currentData()
        if name is None:
            self.new_preset()
        else:
            self._display(CombatComposerDraft.load(self.session, name))

    def new_preset(self):
        existing = {row["id"] for row in
                    inspect_combat_presets(self.session.snapshot())["presets"]}
        index = 1
        while ("r65_custom_" + str(index)) in existing:
            index += 1
        self._display(CombatComposerDraft.create(
            self.session, "r65_custom_" + str(index)))

    def _display(self, draft):
        self._loading = True
        try:
            self.draft = draft
            preset = draft.document
            self.identifier.setText(preset["id"])
            self.identifier.setReadOnly(draft.original_id is not None)
            self.label.setText(preset["label"])
            self._fill(self.moves, [
                [item[key] for key in (
                    "windup", "active", "recovery", "range",
                    "damage", "stagger", "burn_ticks")]
                for item in preset["rules"]["combo"]])
            for name, value in preset["rules"]["projectile"].items():
                self.shot[name].setValue(value)
            self._fill(self.cues, [[item[k] for k in (
                "cue", "kind", "stage", "lead_ticks")]
                for item in preset["telegraphs"]])
            self._fill(self.patterns, [
                [pattern["id"], pattern["phase"], pattern["hp_at_or_below"],
                 step["kind"], step["repeat"], step["wait_ticks"]]
                for pattern in preset["boss_patterns"] for step in pattern["steps"]])
            self.apply_button.setEnabled(False)
            self.report.setPlainText("État non modifié. Prévisualiser puis appliquer.")
            self._render_hitbox(preset)
        finally:
            self._loading = False

    def reload(self, *_):
        current = self.presets.currentData()
        catalog = inspect_combat_presets(self.session.snapshot())
        self._loading = True
        self.presets.clear()
        for row in catalog["presets"]:
            self.presets.addItem(row["label"] + " (" + row["id"] + ")", row["id"])
        if current is None:
            current = catalog["default"]
        selected = self.presets.findData(current)
        if selected >= 0:
            self.presets.setCurrentIndex(selected)
        self._loading = False
        self.load_selected()

    def add_move(self):
        if self.moves.rowCount() < 4:
            self._fill(self.moves, self._rows(self.moves, 7) +
                       [[4, 3, 8, 1200, 2, 6, 0]])
            self.invalidate()

    def remove_move(self):
        if self.moves.rowCount() > 1:
            index = self.moves.currentRow()
            if index < 0:
                index = self.moves.rowCount() - 1
            rows = self._rows(self.moves, 7)
            del rows[index]
            self._fill(self.moves, rows)
            self.invalidate()

    def move_row(self, table, delta):
        index = table.currentRow()
        other = index + delta
        if index < 0 or not 0 <= other < table.rowCount():
            return
        rows = self._rows(table, table.columnCount())
        rows[index], rows[other] = rows[other], rows[index]
        self._fill(table, rows)
        table.selectRow(other)
        self.invalidate()

    def add_cue(self):
        if self.cues.rowCount() < 24:
            self._fill(self.cues, self._rows(self.cues, 4) +
                       [["Avertissement", "melee", 0, 4]])
            self.invalidate()

    def add_pattern(self):
        if self.patterns.rowCount() < 128:
            self._fill(self.patterns, self._rows(self.patterns, 6) +
                       [["boss_phase1", 1, 100, "melee", 1, 12]])
            self.invalidate()

    def remove_row(self, table):
        index = table.currentRow()
        if index < 0:
            return
        rows = self._rows(table, table.columnCount())
        del rows[index]
        self._fill(table, rows)
        self.invalidate()

    @staticmethod
    def _sample_scene():
        return {"id": "r65_preview", "width": 9, "height": 9,
                "walls": [], "hero": {"pos": [4, 4], "hp": 20},
                "enemies": [{"id": "preview_enemy", "pos": [5, 4],
                             "hp": 10, "patrol": []}], "objects": []}

    def _render_hitbox(self, preset):
        overlay = hitbox_preview(self._sample_scene(), preset)
        active = {tuple(pos) for pos in overlay["cells"]}
        self.hitbox.setUpdatesEnabled(False)
        try:
            for row in range(9):
                for col in range(9):
                    name = ("H" if (col, row) == (4, 4) else
                            "E" if (col, row) == (5, 4) else
                            "X" if (col, row) in active else "·")
                    self.hitbox.setItem(row, col, QTableWidgetItem(name))
        finally:
            self.hitbox.setUpdatesEnabled(True)

    def _collect(self):
        rules = {
            "version": 1,
            "combo": [
                dict(zip(("windup", "active", "recovery", "range", "damage",
                          "stagger", "burn_ticks"), map(int, row)))
                for row in self._rows(self.moves, 7)],
            "projectile": {key: widget.value() for key, widget in self.shot.items()},
        }
        telegraphs = [
            {"cue": row[0], "kind": row[1], "stage": int(row[2]),
             "lead_ticks": int(row[3])}
            for row in self._rows(self.cues, 4)]
        patterns = []
        by_id = {}
        for ident, phase, hp, kind, repeat, wait in self._rows(self.patterns, 6):
            if ident not in by_id:
                by_id[ident] = {"id": ident, "phase": int(phase),
                                "hp_at_or_below": int(hp), "steps": []}
                patterns.append(by_id[ident])
            else:
                if by_id[ident]["phase"] != int(phase) or (
                        by_id[ident]["hp_at_or_below"] != int(hp)):
                    raise ValueError("Chaque ID boss doit garder phase et seuil identiques")
            by_id[ident]["steps"].append(
                {"kind": kind, "repeat": int(repeat), "wait_ticks": int(wait)})
        return {"id": self.identifier.text().strip(),
                "label": self.label.text().strip(), "rules": rules,
                "telegraphs": telegraphs, "boss_patterns": patterns}

    def preview(self, *_):
        self.apply_button.setEnabled(False)
        try:
            self.draft.replace(self._collect())
            report = self.draft.preview(scene=self._sample_scene())
            self.report.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))
            self._render_hitbox(self.draft.document)
            self.apply_button.setEnabled(True)
        except Exception as exc:
            self.report.setPlainText("Prévisualisation refusée : " + str(exc))

    def apply(self, *_):
        try:
            self.draft.apply()
            self.updated.emit()
            self.reload()
        except Exception as exc:
            self.apply_button.setEnabled(False)
            self.report.setPlainText("Application refusée : " + str(exc))

    def undo(self, *_):
        try:
            self.session.undo()
            self.updated.emit()
            self.reload()
        except Exception as exc:
            self.report.setPlainText("Annulation refusée : " + str(exc))

    def redo(self, *_):
        try:
            self.session.redo()
            self.updated.emit()
            self.reload()
        except Exception as exc:
            self.report.setPlainText("Rétablissement refusé : " + str(exc))
