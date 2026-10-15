"""Native Qt 6 R8.D workbench. All writes go through R1 AuthoringSession."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from drawtemp.studio.r8_combat_ai import (
    BEHAVIORS, DOCTRINES, ELEMENTS, FORMATIONS, MOVEMENT_KEYS, REACTION_KEYS,
    ROLES, STATUS_KEYS, SUPPORT_KEYS, CombatAIEditor,
)
from sporebound.class_ai_authoring import parse_cells
from sporebound.model import RuleError


def _combo(values):
    widget = QComboBox()
    widget.addItems([str(value) for value in values])
    return widget


class CombatAIDialog(QDialog):
    """Editable initial states and tactical policies on existing mission actors."""

    def __init__(self, session, *, mission_id="", actor_id="", on_change=None,
                 parent=None):
        super().__init__(parent)
        self.editor = CombatAIEditor(session)
        self.on_change = on_change
        self.setWindowTitle("R8.D — États, réactions et profils IA")
        self.resize(1020, 790)
        self.initial_statuses = {}
        self.initial_resistances = {}
        outer = QVBoxLayout(self)
        selection = QHBoxLayout()
        outer.addLayout(selection)
        selection.addWidget(QLabel("Mission"))
        self.mission = QComboBox()
        for key, label in self.editor.missions():
            self.mission.addItem(f"{label} · {key}", key)
        selection.addWidget(self.mission, 2)
        selection.addWidget(QLabel("Unité"))
        self.actor = QComboBox()
        selection.addWidget(self.actor, 2)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 3)
        states_page = QWidget()
        self.tabs.addTab(states_page, "États, résistances et réactions")
        state_layout = QVBoxLayout(states_page)

        state_layout.addWidget(QLabel("États initiaux (durée en ticks ; -1 = permanent)"))
        add_status = QHBoxLayout()
        state_layout.addLayout(add_status)
        self.status_name = _combo(STATUS_KEYS)
        self.status_duration = QSpinBox()
        self.status_duration.setRange(-1, 10000)
        self.status_duration.setValue(24)
        add_status.addWidget(self.status_name, 2)
        add_status.addWidget(self.status_duration)
        add = QPushButton("Ajouter / modifier")
        add.clicked.connect(self._add_status)
        add_status.addWidget(add)
        remove = QPushButton("Retirer")
        remove.clicked.connect(self._remove_status)
        add_status.addWidget(remove)
        self.status_list = QListWidget()
        self.status_list.setAccessibleName("États initiaux de l'acteur")
        state_layout.addWidget(self.status_list, 1)

        state_layout.addWidget(QLabel(
            "Résistance élémentaire (-100..100 %) ; 100 % bloque les dégâts "
            "de cet élément, pas l'application d'un état"))
        resist_row = QHBoxLayout()
        state_layout.addLayout(resist_row)
        self.element = _combo(ELEMENTS)
        self.resistance = QSpinBox()
        self.resistance.setRange(-100, 100)
        resist_row.addWidget(self.element, 2)
        resist_row.addWidget(self.resistance)
        add_resist = QPushButton("Ajouter / modifier")
        add_resist.clicked.connect(self._add_resistance)
        resist_row.addWidget(add_resist)
        remove_resist = QPushButton("Retirer")
        remove_resist.clicked.connect(self._remove_resistance)
        resist_row.addWidget(remove_resist)
        self.resistance_list = QListWidget()
        self.resistance_list.setAccessibleName("Résistances élémentaires de l'acteur")
        state_layout.addWidget(self.resistance_list, 1)

        state_form = QFormLayout()
        state_layout.addLayout(state_form)
        self.reaction = _combo(REACTION_KEYS)
        self.support = _combo(SUPPORT_KEYS)
        self.movement = _combo(MOVEMENT_KEYS)
        state_form.addRow("Réaction passive", self.reaction)
        state_form.addRow("Soutien passif", self.support)
        state_form.addRow("Mouvement passif", self.movement)
        save_states = QPushButton("Valider les états et réactions (Undo/Redo unique)")
        save_states.clicked.connect(self._save_states)
        state_layout.addWidget(save_states)

        ai_page = QWidget()
        self.tabs.addTab(ai_page, "Stratégie, doctrine et formation")
        ai_layout = QVBoxLayout(ai_page)
        ai_form = QFormLayout()
        ai_layout.addLayout(ai_form)
        self.behavior = _combo(BEHAVIORS)
        self.doctrine = _combo(DOCTRINES)
        self.squad = QLineEdit()
        self.squad.setPlaceholderText("escouade_nord (facultatif)")
        ai_form.addRow("Comportement moteur", self.behavior)
        ai_form.addRow("Doctrine tactique", self.doctrine)
        ai_form.addRow("Escouade", self.squad)
        ai_layout.addWidget(QLabel("Rôles IA (plusieurs possibles)"))
        roles_box = QHBoxLayout()
        ai_layout.addLayout(roles_box)
        self.roles = {}
        for role in ROLES:
            check = QCheckBox(role)
            roles_box.addWidget(check)
            self.roles[role] = check
        self.formation = _combo(FORMATIONS)
        self.escort = QLineEdit()
        self.escort.setPlaceholderText("ID allié, seulement pour escorte")
        self.route = QLineEdit()
        self.route.setPlaceholderText("x,y; x,y; x,y — uniquement sans doctrine")
        ai_form.addRow("Formation", self.formation)
        ai_form.addRow("Unité à escorter", self.escort)
        ai_form.addRow("Route de patrouille", self.route)
        ai_layout.addWidget(QLabel(
            "Les doctrines contrôlent les actions par les règles existantes. "
            "Un itinéraire de patrouille ne peut pas être associé à une doctrine."))
        save_ai = QPushButton("Valider la stratégie (Undo/Redo unique)")
        save_ai.clicked.connect(self._save_ai)
        ai_layout.addWidget(save_ai)

        effect_page = QWidget()
        self.tabs.addTab(effect_page, "Effet d'état d'une compétence")
        effect_form = QFormLayout(effect_page)
        self.skill = QComboBox()
        self.skill.addItems([row["id"] for row in
                             self.editor._data()["skills"]])
        self.effect_index = QSpinBox()
        self.effect_index.setRange(1, 1)
        self.effect_kind = _combo(("status", "cleanse"))
        self.effect_status = _combo(STATUS_KEYS)
        self.effect_duration = QSpinBox()
        self.effect_duration.setRange(1, 10000)
        self.effect_duration.setValue(24)
        self.effect_scope = _combo(("target", "allies", "enemies", "all"))
        effect_form.addRow("Compétence existante", self.skill)
        effect_form.addRow("Index effet à remplacer (1 = premier)", self.effect_index)
        effect_form.addRow("Action", self.effect_kind)
        effect_form.addRow("État", self.effect_status)
        effect_form.addRow("Durée (ticks)", self.effect_duration)
        effect_form.addRow("Portée de l'effet", self.effect_scope)
        skill_apply = QPushButton("Remplacer l'effet (validation canonique)")
        skill_apply.clicked.connect(self._save_effect)
        effect_form.addRow(skill_apply)
        self.skill.currentTextChanged.connect(self._refresh_effects)
        self._refresh_effects()

        preview_row = QHBoxLayout()
        outer.addLayout(preview_row)
        button = QPushButton("Prévisualiser les règles réelles / intentions connues")
        button.clicked.connect(self._preview)
        preview_row.addWidget(button)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        preview_row.addWidget(close)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Aperçu Battle au début de la mission")
        outer.addWidget(self.report, 1)
        self.mission.currentIndexChanged.connect(self._mission_changed)
        self.actor.currentIndexChanged.connect(self._refresh)
        if mission_id:
            index = self.mission.findData(mission_id)
            if index >= 0:
                self.mission.setCurrentIndex(index)
        self._mission_changed()
        if actor_id:
            index = self.actor.findData(actor_id)
            if index >= 0:
                self.actor.setCurrentIndex(index)

    def _mission_id(self):
        return self.mission.currentData()

    def _actor_id(self):
        return self.actor.currentData()

    def _mission_changed(self, *_):
        self.actor.blockSignals(True)
        self.actor.clear()
        if self._mission_id():
            for key, name, team in self.editor.actors(self._mission_id()):
                self.actor.addItem(f"{name} · {key} ({team})", key)
        self.actor.blockSignals(False)
        self._refresh()

    def _refresh(self, *_):
        if not self._mission_id() or not self._actor_id():
            return
        row = self.editor.detail(self._mission_id(), self._actor_id())
        self.initial_statuses = dict(row.get("statuses", {}))
        self.initial_resistances = dict(row.get("resistances", {}))
        self._show_states()
        self.reaction.setCurrentText(row.get("reaction", "none"))
        self.support.setCurrentText(row.get("support", "none"))
        self.movement.setCurrentText(row.get("movement", "none"))
        self.behavior.setCurrentText(row.get("behavior", "tactical"))
        tags = row.get("tags", [])
        self.doctrine.setCurrentText(next(
            (t.split(":", 1)[1] for t in tags if t.startswith("doctrine:")), ""))
        self.squad.setText(next(
            (t.split(":", 1)[1] for t in tags if t.startswith("squad:")), ""))
        form = next((t.split(":", 1)[1] for t in tags
                     if t.startswith("formation:")), "none")
        self.formation.setCurrentText(form.split(":")[0])
        self.escort.setText(form.split(":", 1)[1] if ":" in form else "")
        for key, check in self.roles.items():
            check.setChecked(key in tags)
        self.route.setText("; ".join(
            f"{x},{y}" for x, y in row.get("patrol_route", ())))
        self.report.setPlainText(
            "Aperçu non calculé. Cliquer sur « Prévisualiser » pour inspecter "
            "le véritable état Battle ; seules les intentions de l'ennemi "
            "actif peuvent être affichées.")

    def _show_states(self):
        self.status_list.clear()
        for key, duration in sorted(self.initial_statuses.items()):
            self.status_list.addItem(f"{key} = {duration}")
        self.resistance_list.clear()
        for key, percentage in sorted(self.initial_resistances.items()):
            self.resistance_list.addItem(f"{key} = {percentage} %")

    def _add_status(self):
        duration = self.status_duration.value()
        if duration == 0:
            QMessageBox.warning(self, "Durée invalide", "Utiliser -1 ou 1..10000.")
            return
        self.initial_statuses[self.status_name.currentText()] = duration
        self._show_states()

    def _remove_status(self):
        item = self.status_list.currentItem()
        if item:
            self.initial_statuses.pop(item.text().split(" = ", 1)[0], None)
            self._show_states()

    def _add_resistance(self):
        self.initial_resistances[self.element.currentText()] = self.resistance.value()
        self._show_states()

    def _remove_resistance(self):
        item = self.resistance_list.currentItem()
        if item:
            self.initial_resistances.pop(item.text().split(" = ", 1)[0], None)
            self._show_states()

    def _run(self, operation, *args, **kwargs):
        try:
            result = operation(*args, **kwargs)
        except (RuleError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Modification non appliquée", str(exc))
            return None
        self._refresh()
        if self.on_change:
            self.on_change()
        return result

    def _save_states(self):
        self._run(self.editor.states, self._mission_id(), self._actor_id(),
                  statuses=self.initial_statuses,
                  resistances=self.initial_resistances,
                  reaction=self.reaction.currentText(),
                  support=self.support.currentText(),
                  movement=self.movement.currentText())

    def _save_ai(self):
        try:
            route = parse_cells(self.route.text())
        except (RuleError, ValueError) as exc:
            QMessageBox.warning(self, "Patrouille invalide", str(exc))
            return
        self._run(
            self.editor.ai, self._mission_id(), self._actor_id(),
            behavior=self.behavior.currentText(),
            roles=tuple(key for key, check in self.roles.items() if check.isChecked()),
            doctrine=self.doctrine.currentText(), squad=self.squad.text().strip(),
            route=route, formation=self.formation.currentText(),
            escort_target=self.escort.text().strip())

    def _refresh_effects(self, *_):
        key = self.skill.currentText()
        spec = next((row for row in self.editor._data()["skills"]
                     if row["id"] == key), None)
        self.effect_index.setMaximum(max(1, len(spec["effects"]) if spec else 1))

    def _save_effect(self):
        key = self.skill.currentText()
        spec = next((row for row in self.editor._data()["skills"]
                     if row["id"] == key), None)
        if spec is None:
            return
        index = self.effect_index.value() - 1
        previous = spec["effects"][index]["kind"]
        if QMessageBox.question(
            self, "Remplacer un effet",
            f"Remplacer l'effet {index + 1} ({previous}) de {key} ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._run(self.editor.set_status_effect, key, index,
                  self.effect_status.currentText(), self.effect_duration.value(),
                  kind=self.effect_kind.currentText(),
                  scope=self.effect_scope.currentText())

    def _preview(self):
        try:
            report = self.editor.preview(self._mission_id(), self._actor_id())
        except (RuleError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Aperçu impossible", str(exc))
            return
        self.report.setPlainText(json.dumps(
            report, indent=2, sort_keys=True, ensure_ascii=False))
