"""R43.B1 Qt Widgets ability/effect designer over the R43.A canonical contracts.

A disposable visual draft lives in the dialog; all project mutations go through
AuthoringSession.preview_pair/apply. The cell view is explicitly a schematic
overlay, not native game picking or LOS.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.ability_contracts import (
    AbilityError, EFFECTS, MODES, SCOPES, SHAPES, STATS, TEAMS,
    catalog_from_project,
)
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.ability_authoring_r43 import (
    AbilityDraft, area_preview,
)
from drawtemp.studio.ability_formula_graph_r43 import balance_lab
from sporebound.rules import default_rules


def _combo(label, values):
    widget = QComboBox()
    widget.setAccessibleName(label)
    for value in values:
        widget.addItem(value, value)
    return widget


def _select(widget, value):
    index = widget.findData(value)
    if index >= 0:
        widget.setCurrentIndex(index)


def _spin(label, minimum, maximum):
    widget = QSpinBox()
    widget.setAccessibleName(label)
    widget.setRange(minimum, maximum)
    return widget


class AbilityDesignerDialog(QDialog):
    """Editable effects and primitive formulas, visual preview, one R1 Undo."""

    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setObjectName("r43-ability-designer")
        self.setWindowTitle("R43 — Combat & Ability Designer 2.0")
        self.resize(1200, 850)
        self.draft = None
        self._loading = False
        self._active_effect = -1
        self._aim = (4, 3)
        self._unsupported_formula_index = None

        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        outer.addLayout(top)
        top.addWidget(QLabel("Compétence R43"))
        self.ability_select = _combo("Compétence existante", ())
        self.ability_select.currentIndexChanged.connect(self._select_ability)
        top.addWidget(self.ability_select, 1)
        self.new_button = QPushButton("Créer une compétence…")
        self.new_button.clicked.connect(self.create_ability)
        top.addWidget(self.new_button)
        self.reload_button = QPushButton("Recharger")
        self.reload_button.clicked.connect(self.reload)
        top.addWidget(self.reload_button)

        sections = QSplitter()
        outer.addWidget(sections, 1)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setAccessibleName("Paramètres de compétence")
        sections.addWidget(scroller)
        form_host = QWidget()
        scroller.setWidget(form_host)
        left = QVBoxLayout(form_host)

        identity = QFormLayout()
        self.identifier = QLineEdit()
        self.identifier.setAccessibleName("Identifiant de compétence")
        identity.addRow("Identifiant", self.identifier)
        self.name = QLineEdit()
        self.name.setAccessibleName("Nom affiché")
        identity.addRow("Nom", self.name)
        left.addLayout(identity)

        left.addWidget(QLabel("Profils autorisés (absence = exécution interdite)"))
        self.mode_checks = {}
        self.windups = {}
        self.cooldowns = {}
        for mode in ("TACTICAL_CT", "ACTION_REALTIME", "RPG_TURN"):
            line = QHBoxLayout()
            check = QCheckBox(mode)
            line.addWidget(check, 2)
            windup = _spin(mode + " windup", 0, 100)
            cooldown = _spin(mode + " cooldown", 0, 10000)
            line.addWidget(QLabel("Windup"))
            line.addWidget(windup)
            line.addWidget(QLabel("CD"))
            line.addWidget(cooldown)
            self.mode_checks[mode] = check
            self.windups[mode] = windup
            self.cooldowns[mode] = cooldown
            left.addLayout(line)

        core = QFormLayout()
        self.resource = _combo("Ressource", ("mp", "stamina"))
        self.cost = _spin("Coût", 0, 100)
        self.team = _combo("Cible", ("enemy", "ally", "unit", "self", "ground", "downed"))
        self.shape = _combo("Forme de zone", ("single", "diamond", "cross", "square"))
        self.min_range = _spin("Portée min", 0, 16)
        self.max_range = _spin("Portée max", 0, 16)
        self.radius = _spin("Rayon", 0, 8)
        for label, widget in (
            ("Ressource", self.resource), ("Coût", self.cost),
            ("Cible", self.team), ("Forme", self.shape),
            ("Portée min", self.min_range), ("Portée max", self.max_range),
            ("Rayon", self.radius),
        ):
            core.addRow(label, widget)
        left.addLayout(core)

        left.addWidget(QLabel("Effets ordonnés — 1 à 8"))
        self.effects = QListWidget()
        self.effects.setAccessibleName("Effets de la compétence")
        self.effects.currentRowChanged.connect(self._effect_selected)
        left.addWidget(self.effects)
        effect_buttons = QHBoxLayout()
        self.add_effect_button = QPushButton("+ Effet")
        self.remove_effect_button = QPushButton("− Effet")
        self.up_button = QPushButton("Monter")
        self.down_button = QPushButton("Descendre")
        for btn, callback in (
            (self.add_effect_button, self._add_effect),
            (self.remove_effect_button, self._remove_effect),
            (self.up_button, lambda: self._move_effect(-1)),
            (self.down_button, lambda: self._move_effect(1)),
        ):
            effect_buttons.addWidget(btn)
            btn.clicked.connect(callback)
        left.addLayout(effect_buttons)

        detail = QFormLayout()
        self.effect_kind = _combo("Nature de l'effet", sorted(EFFECTS))
        self.element = _combo(
            "Élément", ("physical", "fire", "ice", "lightning", "holy", "dark"))
        self.status = _combo(
            "État", ("", *sorted(key for key, _ in default_rules().statuses.entries)))
        self.scope = _combo("Portée des effets", sorted(SCOPES))
        self.duration = _spin("Durée", 1, 10000)
        self.formula_kind = _combo("Formule de puissance", ("constant", "stat_percent"))
        self.fixed_power = _spin("Puissance fixe", 0, 10000)
        self.stat = _combo("Statistique", sorted(STATS))
        self.percent = _spin("Pourcentage de stat", 0, 400)
        for label, widget in (
            ("Type", self.effect_kind), ("Élément", self.element),
            ("Statut", self.status), ("Destinataires", self.scope),
            ("Durée", self.duration), ("Formule", self.formula_kind),
            ("Valeur", self.fixed_power), ("Stat", self.stat),
            ("Pourcentage", self.percent),
        ):
            detail.addRow(label, widget)
        left.addLayout(detail)
        left.addWidget(QLabel(
            "Les formules sur statistiques sont prévisualisables uniquement. "
            "Le bridge CT R43.A refuse leur compilation jusqu'à un adaptateur natif."))

        self.graph_button = QPushButton("Éditer le graphe de formule R43.B2…")
        self.graph_button.setAccessibleName("Ouvrir l'arbre de formule typé")
        self.graph_button.clicked.connect(self.edit_formula_graph)
        left.addWidget(self.graph_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        sections.addWidget(right)
        sections.setSizes([680, 500])
        preview_controls = QHBoxLayout()
        preview_controls.addWidget(QLabel("Prévoir pour"))
        self.preview_mode = _combo(
            "Profil de prévisualisation", ("TACTICAL_CT", "ACTION_REALTIME", "RPG_TURN"))
        preview_controls.addWidget(self.preview_mode)
        right_layout.addLayout(preview_controls)
        right_layout.addWidget(QLabel(
            "Zone schématique 9×9 : origine = héros (C, centre) ; "
            "cliquer une case pour viser. Ni LOS ni obstacles."))

        self.target_grid = QTableWidget(9, 9)
        self.target_grid.setAccessibleName("Prévisualisation géométrique 9 par 9")
        self.target_grid.horizontalHeader().hide()
        self.target_grid.verticalHeader().hide()
        self.target_grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.target_grid.cellClicked.connect(self._aim_at)
        for row in range(9):
            for col in range(9):
                self.target_grid.setItem(row, col, QTableWidgetItem(""))
        right_layout.addWidget(self.target_grid)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Diagnostic R43 et contrat de compilation")
        right_layout.addWidget(self.report, 2)
        self.lab_button = QPushButton("Balance Lab — puissance brute (sans runtime)")
        self.lab_button.clicked.connect(self.preview_balance)
        right_layout.addWidget(self.lab_button)

        bottom = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser sans modifier")
        self.preview_button.clicked.connect(self.preview_changes)
        bottom.addWidget(self.preview_button)
        self.apply_button = QPushButton("Appliquer (1 Undo)")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        bottom.addWidget(self.apply_button)
        self.close_button = QPushButton("Fermer")
        self.close_button.clicked.connect(self.accept)
        bottom.addWidget(self.close_button)
        outer.addLayout(bottom)

        # All form changes invalidate a prior preview; button cannot apply a
        # previously prepared plan after any new user edit.
        widgets = [self.identifier, self.name, self.resource, self.cost, self.team,
                   self.shape, self.min_range, self.max_range, self.radius,
                   self.effect_kind, self.element, self.status, self.scope,
                   self.duration, self.formula_kind, self.fixed_power,
                   self.stat, self.percent, self.preview_mode]
        widgets.extend(self.windups.values())
        widgets.extend(self.cooldowns.values())
        for widget in widgets:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._invalidate)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._invalidate)
            else:
                widget.valueChanged.connect(self._invalidate)
        for checkbox in self.mode_checks.values():
            checkbox.toggled.connect(self._invalidate)
        self._reload_catalog()

    def _invalidate(self, *_):
        if self._loading:
            return
        if self.draft is not None:
            self.draft.pending = None
        self.apply_button.setEnabled(False)
        self.report.setPlainText(
            "Brouillon non appliqué. Prévisualiser pour valider Content + GameProject.")

    def _reload_catalog(self, selected=None):
        self._loading = True
        self.ability_select.clear()
        catalog = catalog_from_project(self.session.snapshot().to_dict()["project"])
        for row in catalog["abilities"]:
            self.ability_select.addItem(row["name"] + " [" + row["id"] + "]", row["id"])
        if selected is not None:
            _select(self.ability_select, selected)
        self._loading = False
        key = self.ability_select.currentData()
        if key is not None:
            self._load_draft(AbilityDraft.load(self.session, key))
        else:
            self._load_draft(AbilityDraft.create(self.session))

    def _select_ability(self, *_):
        if not self._loading and self.ability_select.currentData() is not None:
            self._load_draft(AbilityDraft.load(
                self.session, self.ability_select.currentData()))

    def create_ability(self):
        value, ok = QInputDialog.getText(
            self, "Nouvelle compétence R43", "ID stable (a-z, 0-9, tirets et _)",
            text="r43_new")
        if not ok:
            return
        self._loading = True
        self.ability_select.setCurrentIndex(-1)
        self._loading = False
        self._load_draft(AbilityDraft.create(self.session, value.strip()))

    def reload(self):
        self._reload_catalog(
            self.draft.document["id"] if self.draft else None)

    def _load_draft(self, draft):
        self.draft = draft
        self._loading = True
        self.identifier.setText(draft.document["id"])
        self.identifier.setReadOnly(draft.original_id is not None)
        self.name.setText(draft.document["name"])
        profiles = draft.document["profiles"]
        _select(self.preview_mode, profiles[0])
        for mode, checkbox in self.mode_checks.items():
            checkbox.setChecked(mode in profiles)
            t = draft.document["timing"].get(mode, {"windup": 0, "cooldown": 0})
            self.windups[mode].setValue(t["windup"])
            self.cooldowns[mode].setValue(t["cooldown"])
        _select(self.resource, draft.document["cost"]["resource"])
        self.cost.setValue(draft.document["cost"]["amount"])
        target = draft.document["target"]
        _select(self.team, target["team"])
        _select(self.shape, target["shape"])
        self.min_range.setValue(target["min_range"])
        self.max_range.setValue(target["range"])
        self.radius.setValue(target["radius"])
        self._refresh_effects(0)
        self._loading = False
        self._invalidate()
        self._render_grid(area_preview(target, aim=self._aim))

    def _refresh_effects(self, selection=0):
        self._loading = True
        self.effects.clear()
        for index, effect in enumerate(self.draft.document["effects"]):
            self.effects.addItem(f"{index + 1} — {effect['kind']} / {effect['element']}")
        self._active_effect = -1
        self.effects.setCurrentRow(selection)
        self._loading = False
        self._load_effect(selection)

    def _load_effect(self, index):
        if not 0 <= index < len(self.draft.document["effects"]):
            return
        self._loading = True
        row = self.draft.document["effects"][index]
        _select(self.effect_kind, row["kind"])
        _select(self.element, row["element"])
        _select(self.status, row["status"])
        _select(self.scope, row["scope"])
        self.duration.setValue(row["duration"])
        formula = row["formula"]
        self._unsupported_formula_index = None
        if formula["op"] == "constant":
            _select(self.formula_kind, "constant")
            self.fixed_power.setValue(formula["value"])
        elif formula["op"] == "percent" and formula["input"]["op"] == "stat":
            _select(self.formula_kind, "stat_percent")
            _select(self.stat, formula["input"]["name"])
            self.percent.setValue(formula["amount"])
        else:
            # R43.B2 edits complex formula ASTs explicitly; simple fields cannot.
            self._unsupported_formula_index = index
            _select(self.formula_kind, "constant")
            self.fixed_power.setValue(0)
            self.report.setPlainText(
                "Formule avancée préservée : utiliser le graphe R43.B2. "
                "CT refuse encore les formules dynamiques.")
        self._active_effect = index
        self._loading = False

    def _sync_effect(self):
        index = self._active_effect
        if index < 0 or not self.draft:
            return
        if index == self._unsupported_formula_index:
            # Preserve complex R43 AST while updating other effect fields.
            formula = self.draft.document["effects"][index]["formula"]
        elif self.formula_kind.currentData() == "constant":
            formula = {"op": "constant", "value": self.fixed_power.value()}
        else:
            formula = {
                "op": "percent", "input": {"op": "stat", "name": self.stat.currentData()},
                "amount": self.percent.value()}
        kind = self.effect_kind.currentData()
        self.draft.edit_effect(
            index, kind=kind, formula=formula, element=self.element.currentData(),
            status=self.status.currentData() if kind in ("status", "cleanse") else "",
            duration=self.duration.value(), scope=self.scope.currentData())

    def edit_formula_graph(self):
        index = self._active_effect
        if self.draft is None or index < 0:
            return False
        self._sync_effect()
        from drawtemp.studio.ability_formula_graph_r43_qt import FormulaGraphDialog
        dialog = FormulaGraphDialog(
            self.draft.document["effects"][index]["formula"], parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.result_formula is None:
            return False
        self.draft.document["effects"][index]["formula"] = dialog.result_formula
        self.draft.pending = None
        self._load_effect(index)
        self._invalidate()
        return True

    def preview_balance(self):
        if self.draft is None:
            return False
        self.apply_button.setEnabled(False)
        try:
            self._gather()
            result = balance_lab(self.draft.document)
            self.report.setPlainText(json.dumps(
                result, ensure_ascii=False, indent=2, sort_keys=True))
            return True
        except (AbilityError, AuthoringError, ValueError, KeyError, TypeError) as exc:
            self.report.setPlainText(
                "Balance Lab refusé : " + getattr(exc, "code", "invalid") +
                " — " + str(exc))
            return False

    def _effect_selected(self, index):
        if self._loading:
            return
        self._sync_effect()
        self._load_effect(index)
        self._invalidate()

    def _add_effect(self):
        self._sync_effect()
        try:
            self.draft.add_effect()
            self._refresh_effects(len(self.draft.document["effects"]) - 1)
        except AbilityError as exc:
            self.report.setPlainText(str(exc))
        self._invalidate()

    def _remove_effect(self):
        self._sync_effect()
        index = self._active_effect
        try:
            self.draft.remove_effect(index)
            self._refresh_effects(min(index, len(self.draft.document["effects"]) - 1))
        except AbilityError as exc:
            self.report.setPlainText(str(exc))
            self.apply_button.setEnabled(False)
            return
        self._invalidate()

    def _move_effect(self, direction):
        self._sync_effect()
        index = self._active_effect
        try:
            self.draft.move_effect(index, direction)
            self._refresh_effects(index + direction)
        except AbilityError as exc:
            self.report.setPlainText(str(exc))
            self.apply_button.setEnabled(False)
            return
        self._invalidate()

    def _gather(self):
        self._sync_effect()
        # Both editors preserve the exact R43.A AST; validation is canonical.
        profiles = [key for key in ("TACTICAL_CT", "ACTION_REALTIME", "RPG_TURN")
                    if self.mode_checks[key].isChecked()]
        timing = {key: {"windup": self.windups[key].value(),
                        "cooldown": self.cooldowns[key].value()} for key in profiles}
        self.draft.document["id"] = self.identifier.text().strip()
        self.draft.set_header(
            name=self.name.text(), profiles=profiles,
            resource=self.resource.currentData(), cost=self.cost.value(),
            team=self.team.currentData(), shape=self.shape.currentData(),
            min_range=self.min_range.value(), max_range=self.max_range.value(),
            radius=self.radius.value(), timing=timing)

    def _aim_at(self, row, col):
        self._aim = (col, row)
        self._invalidate()
        try:
            self._render_grid(area_preview(self._target_form(), aim=self._aim))
        except AbilityError as exc:
            self.report.setPlainText(str(exc))

    def _target_form(self):
        return {"team": self.team.currentData(),
                "shape": self.shape.currentData(),
                "min_range": self.min_range.value(),
                "range": self.max_range.value(), "radius": self.radius.value()}

    def _render_grid(self, data):
        covered = {tuple(cell) for cell in data["cells"]}
        for row in range(9):
            for col in range(9):
                item = self.target_grid.item(row, col)
                cell = (col, row)
                if cell == (4, 4):
                    glyph, color = "C", "#b7e4c7"
                elif cell == self._aim:
                    glyph, color = "X", "#fbcfe8"
                elif cell in covered:
                    glyph, color = "●", "#bfdbfe"
                else:
                    glyph, color = "·", "#ffffff"
                item.setText(glyph)
                item.setBackground(QBrush(QColor(color)))
        self.target_grid.setToolTip(data["note"] +
                                    (" — dans la portée" if data["in_range"]
                                     else " — hors portée"))

    def preview_changes(self):
        self.apply_button.setEnabled(False)
        try:
            self._gather()
            preview = self.draft.preview(
                mode=self.preview_mode.currentData(), aim=self._aim)
            self._render_grid(preview.report["target_preview"])
            self.report.setPlainText(json.dumps(
                preview.report, ensure_ascii=False, indent=2, sort_keys=True))
            self.apply_button.setEnabled(True)
            return True
        except (AbilityError, AuthoringError, ValueError, KeyError, TypeError) as exc:
            self.report.setPlainText(
                "Validation bloquante : " + getattr(exc, "code", "invalid") +
                " — " + str(exc))
            return False

    def apply_changes(self):
        if self.draft is None or self.draft.pending is None:
            self.apply_button.setEnabled(False)
            return False
        try:
            self.draft.apply()
            selected = self.draft.document["id"]
            self._reload_catalog(selected)
            self.updated.emit()
            self.report.setPlainText("Compétence appliquée en une transaction. "
                                     "Enregistrer le projet pour persister.")
            return True
        except (AbilityError, AuthoringError, ValueError, TypeError) as exc:
            self.apply_button.setEnabled(False)
            self.report.setPlainText(
                "Application refusée : " + getattr(exc, "code", "invalid") +
                " — " + str(exc))
            return False


__all__ = ["AbilityDesignerDialog"]
