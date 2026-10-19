"""R28.C — visual Ability / Enemy designers over existing R8 + R25 contracts.

This Qt module is a view. It never stores independent gameplay state, and
never enables fake Action/RPG runtime authoring.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.genre_rules_designer import (
    GenreDesignError, GenreRulesDesigner,
)
from drawtemp.studio.r8_combat_ai import (
    BEHAVIORS, DOCTRINES, ELEMENTS, FORMATIONS, ROLES, STATUS_KEYS,
)
from sporebound.class_ai_authoring import parse_cells
from sporebound.model import RuleError
from sporebound.rules import default_rules


def _pick(widget, value):
    pos = widget.findData(value)
    if pos >= 0:
        widget.setCurrentIndex(pos)


def _values(title, values):
    combo = QComboBox()
    combo.setAccessibleName(title)
    for item in values:
        combo.addItem(str(item) or "Aucun", item)
    return combo


class _DesignPanel(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.designer = GenreRulesDesigner(session)
        self._pending = None
        self._loading = False
        self._loaded_revision = -1

    def _preview_box(self, layout, label):
        layout.addWidget(QLabel(label))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setAccessibleName("Diagnostics du designer")
        layout.addWidget(self.report, 1)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser")
        self.preview_button.clicked.connect(self.preview_changes)
        buttons.addWidget(self.preview_button)
        self.apply_button = QPushButton("Appliquer (1 Undo)")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_changes)
        buttons.addWidget(self.apply_button)
        reload_button = QPushButton("Actualiser")
        reload_button.clicked.connect(self.refresh)
        buttons.addWidget(reload_button)
        layout.addLayout(buttons)

    def _invalidate(self, *_):
        if self._loading:
            return
        self._pending = None
        self.apply_button.setEnabled(False)
        self.report.setPlainText(
            "Modifications non appliquées. Cliquez sur Prévisualiser.")

    def _show_preview(self, preview):
        self._pending = preview if preview.report["changed"] else None
        self.apply_button.setEnabled(self._pending is not None)
        self.report.setPlainText(json.dumps(
            preview.report, ensure_ascii=False, indent=2))

    def apply_changes(self):
        if self._pending is None:
            return
        try:
            self.designer.apply(self._pending)
        except (AuthoringError, GenreDesignError, ValueError) as exc:
            self._pending = None
            self.apply_button.setEnabled(False)
            self.report.setPlainText("Transaction refusée : " + str(exc))
            return
        self.refresh()
        self.updated.emit()


class AbilityDesignerPanel(_DesignPanel):
    """Skill and selected effect editing; no invented action skill schema."""

    def __init__(self, session, parent=None):
        super().__init__(session, parent)
        self.setObjectName("r28-ability-designer")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Ability Designer — compétences Content v1 validées par Battle"))
        form = QFormLayout()
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission pour le profil de combat")
        form.addRow("Contexte de scène", self.mission)
        self.skill_id = QComboBox()
        self.skill_id.setAccessibleName("Compétence éditée")
        form.addRow("Compétence", self.skill_id)
        self.target = _values(
            "Cible de la compétence", ("enemy", "ally", "unit", "self", "ground", "downed"))
        form.addRow("Cible", self.target)
        self.shape = _values("Forme de zone", ("diamond", "cross", "square"))
        form.addRow("Zone", self.shape)
        self.cost = QSpinBox()
        self.cost.setRange(0, 100)
        form.addRow("Coût PM", self.cost)
        self.max_range = QSpinBox()
        self.max_range.setRange(0, 100)
        form.addRow("Portée maximum", self.max_range)
        self.min_range = QSpinBox()
        self.min_range.setRange(0, 100)
        form.addRow("Portée minimum", self.min_range)
        self.accuracy = QSpinBox()
        self.accuracy.setRange(0, 100)
        form.addRow("Précision %", self.accuracy)
        self.effect_index = QComboBox()
        self.effect_index.setAccessibleName("Effet édité")
        form.addRow("Effet", self.effect_index)
        effects = tuple(sorted(key for key, _ in default_rules().effects.entries))
        self.effect_kind = _values("Type d'effet", effects)
        form.addRow("Type", self.effect_kind)
        self.element = _values("Élément", ELEMENTS)
        form.addRow("Élément", self.element)
        self.status = _values("État appliqué", ("", *STATUS_KEYS))
        form.addRow("État", self.status)
        self.scope = _values("Portée de l'effet", ("target", "allies", "enemies", "all"))
        form.addRow("Destinataires", self.scope)
        self.power = QSpinBox()
        self.power.setRange(0, 10000)
        form.addRow("Puissance", self.power)
        self.duration = QSpinBox()
        self.duration.setRange(1, 10000)
        form.addRow("Durée", self.duration)
        layout.addLayout(form)
        self.capabilities = QLabel("")
        self.capabilities.setWordWrap(True)
        layout.addWidget(self.capabilities)
        self._preview_box(layout, "Diff validé par le registre de compétences R8")
        self.mission.currentIndexChanged.connect(self._invalidate)
        self.skill_id.currentIndexChanged.connect(self._load_skill)
        self.effect_index.currentIndexChanged.connect(self._load_effect)
        for widget in (
            self.target, self.shape, self.effect_kind, self.element,
            self.status, self.scope, self.cost, self.max_range,
            self.min_range, self.accuracy, self.power, self.duration,
        ):
            widget.currentIndexChanged.connect(self._invalidate) if isinstance(
                widget, QComboBox) else widget.valueChanged.connect(self._invalidate)
        self.refresh()

    def refresh(self):
        old_mission = self.mission.currentData()
        old_skill = self.skill_id.currentData()
        self._loading = True
        self.mission.clear()
        for key, label in self.designer.missions():
            self.mission.addItem(label + " [" + key + "]", key)
        _pick(self.mission, old_mission)
        self.skill_id.clear()
        for row in self.designer.skills():
            self.skill_id.addItem(row.name + " [" + row.id + "]", row.id)
        _pick(self.skill_id, old_skill)
        self._loading = False
        self._load_skill()

    def _load_skill(self, *_):
        if self._loading:
            return
        key = self.skill_id.currentData()
        self._loading = True
        self._pending = None
        self.apply_button.setEnabled(False)
        if key is not None:
            row = self.designer.skill(key)
            _pick(self.target, row["target"])
            _pick(self.shape, row["shape"])
            self.cost.setValue(row["cost"])
            self.max_range.setValue(row["range"])
            self.min_range.setValue(row["min_range"])
            self.accuracy.setValue(row["accuracy"])
            self.effect_index.clear()
            for index, effect in enumerate(row["effects"]):
                self.effect_index.addItem(
                    str(index + 1) + " : " + effect["kind"], index)
        self._loaded_revision = self.designer.session.revision
        self._loading = False
        self._load_effect()
        self._show_compatibility()

    def _load_effect(self, *_):
        if self._loading:
            return
        key = self.skill_id.currentData()
        index = self.effect_index.currentData()
        if key is None or index is None:
            return
        effect = self.designer.skill(key)["effects"][index]
        self._loading = True
        for field, widget in (
            ("kind", self.effect_kind), ("element", self.element),
            ("status", self.status), ("scope", self.scope),
        ):
            _pick(widget, effect[field])
        self.power.setValue(effect["power"])
        self.duration.setValue(effect["duration"])
        self._loading = False
        self._invalidate()

    def _show_compatibility(self):
        scene = self.mission.currentData()
        if scene is None:
            return
        report = self.designer.compatibility(scene)
        self.preview_button.setEnabled(report["editable_in_this_workbench"])
        self.capabilities.setText(report["explanation"])
        if not report["editable_in_this_workbench"]:
            self.report.setPlainText(report["explanation"])

    def preview_changes(self):
        key, scene, index = (
            self.skill_id.currentData(), self.mission.currentData(),
            self.effect_index.currentData())
        if key is None or scene is None or index is None:
            return
        try:
            old = self.designer.skill(key)
            changes = {
                name: value for name, value in (
                    ("target", self.target.currentData()),
                    ("shape", self.shape.currentData()),
                    ("cost", self.cost.value()),
                    ("range", self.max_range.value()),
                    ("min_range", self.min_range.value()),
                    ("accuracy", self.accuracy.value()),
                ) if old[name] != value
            }
            previous = old["effects"][index]
            candidate = {
                "kind": self.effect_kind.currentData(),
                "element": self.element.currentData(),
                "status": self.status.currentData(),
                "scope": self.scope.currentData(),
                "power": self.power.value(),
                "duration": self.duration.value(),
            }
            updates = {k: v for k, v in candidate.items() if previous[k] != v}
            result = self.designer.preview_skill(
                scene, key, changes, effect_index=index if updates else None,
                effect=updates or None, expected_revision=self._loaded_revision)
            self._show_preview(result)
        except (AuthoringError, GenreDesignError, RuleError, TypeError,
                ValueError) as exc:
            self._pending = None
            self.apply_button.setEnabled(False)
            self.report.setPlainText("Validation bloquante : " + str(exc))


class EnemyDesignerPanel(_DesignPanel):
    """Real R8 tactical enemy policies, with a seeded Battle initial-state preview."""

    def __init__(self, session, parent=None):
        super().__init__(session, parent)
        self.setObjectName("r28-enemy-designer")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Enemy Designer — IA, rôles, formation et patrouille tactiques"))
        form = QFormLayout()
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission du designer ennemi")
        form.addRow("Mission", self.mission)
        self.actor = QComboBox()
        self.actor.setAccessibleName("Ennemi à éditer")
        form.addRow("Ennemi", self.actor)
        self.behavior = _values("Comportement IA", BEHAVIORS)
        form.addRow("Comportement", self.behavior)
        self.doctrine = _values("Doctrine tactique", DOCTRINES)
        form.addRow("Doctrine", self.doctrine)
        self.formation = _values("Formation tactique", FORMATIONS)
        form.addRow("Formation", self.formation)
        self.roles = QLineEdit()
        self.roles.setPlaceholderText("ex: protector, leader")
        self.roles.setAccessibleName("Rôles séparés par des virgules")
        form.addRow("Rôles", self.roles)
        self.squad = QLineEdit()
        self.squad.setAccessibleName("Identifiant de l'escouade")
        form.addRow("Escouade", self.squad)
        self.escort = QLineEdit()
        self.escort.setAccessibleName("ID de l'allié escorté")
        form.addRow("Escorter", self.escort)
        self.route = QLineEdit()
        self.route.setPlaceholderText("ex: 1,2; 3,2")
        self.route.setAccessibleName("Trajet de patrouille")
        form.addRow("Patrouille", self.route)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(1)
        form.addRow("Seed de prévisualisation", self.seed)
        layout.addLayout(form)
        self.capabilities = QLabel("")
        self.capabilities.setWordWrap(True)
        layout.addWidget(self.capabilities)
        self._preview_box(layout, "Battle réel au démarrage : digest, tags, patrouille (pas un futur simulé)")
        self.mission.currentIndexChanged.connect(self._load_mission)
        self.actor.currentIndexChanged.connect(self._load_actor)
        for widget in (self.behavior, self.doctrine, self.formation):
            widget.currentIndexChanged.connect(self._invalidate)
        for widget in (self.roles, self.squad, self.escort, self.route):
            widget.textChanged.connect(self._invalidate)
        self.seed.valueChanged.connect(self._invalidate)
        self.refresh()

    def refresh(self):
        current = self.mission.currentData()
        self._loading = True
        self.mission.clear()
        for key, title in self.designer.missions():
            self.mission.addItem(title + " [" + key + "]", key)
        _pick(self.mission, current)
        self._loading = False
        self._load_mission()

    def _load_mission(self, *_):
        if self._loading:
            return
        scene = self.mission.currentData()
        old_enemy = self.actor.currentData()
        self._loading = True
        self.actor.clear()
        if scene is not None:
            for actor_id, name in self.designer.enemies(scene):
                self.actor.addItem(name + " [" + actor_id + "]", actor_id)
        _pick(self.actor, old_enemy)
        self._loading = False
        self._load_actor()
        if scene is not None:
            info = self.designer.compatibility(scene)
            self.capabilities.setText(info["explanation"])

    def _load_actor(self, *_):
        if self._loading:
            return
        scene, actor_id = self.mission.currentData(), self.actor.currentData()
        self._pending = None
        self.apply_button.setEnabled(False)
        if scene is None or actor_id is None:
            self.preview_button.setEnabled(False)
            self.report.setPlainText("Aucun acteur ennemi dans la mission.")
            return
        detail = self.designer.enemy(scene, actor_id)
        tags = detail.get("tags", [])
        self._loading = True
        _pick(self.behavior, detail.get("behavior", "tactical"))
        _pick(self.doctrine, next(
            (t.split(":", 1)[1] for t in tags if t.startswith("doctrine:")), ""))
        form = next((t.split(":", 1)[1] for t in tags
                     if t.startswith("formation:")), "none")
        _pick(self.formation, form.split(":")[0])
        self.escort.setText(form.split(":", 1)[1] if ":" in form else "")
        self.roles.setText(", ".join(t for t in tags if t in ROLES))
        self.squad.setText(next(
            (t.split(":", 1)[1] for t in tags if t.startswith("squad:")), ""))
        self.route.setText("; ".join(
            str(x) + "," + str(y) for x, y in detail.get("patrol_route", ())))
        self._loaded_revision = self.designer.session.revision
        self._loading = False
        self.preview_button.setEnabled(True)
        self._invalidate()

    def preview_changes(self):
        mission, actor = self.mission.currentData(), self.actor.currentData()
        if mission is None or actor is None:
            return
        try:
            roles = tuple(part.strip() for part in self.roles.text().split(",")
                          if part.strip())
            preview = self.designer.preview_enemy(
                mission, actor, behavior=self.behavior.currentData(),
                doctrine=self.doctrine.currentData(),
                formation=self.formation.currentData(),
                roles=roles, squad=self.squad.text().strip(),
                escort_target=self.escort.text().strip(),
                route=parse_cells(self.route.text()), seed=self.seed.value(),
                expected_revision=self._loaded_revision)
            self._show_preview(preview)
        except (AuthoringError, GenreDesignError, RuleError, TypeError,
                ValueError) as exc:
            self._pending = None
            self.apply_button.setEnabled(False)
            self.report.setPlainText("Validation bloquante : " + str(exc))


class GenreRulesWorkspace(QWidget):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setObjectName("r28-gameplay-rules")
        self.session = session
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.abilities = AbilityDesignerPanel(session)
        self.enemies = EnemyDesignerPanel(session)
        self.tabs.addTab(self.abilities, "Ability Designer")
        self.tabs.addTab(self.enemies, "Enemy Designer")
        # R32.C shares this Gameplay tab, the R1 session and global Undo/Redo.
        from drawtemp.studio.platform_collider_qt import ColliderEditorPanel
        self.colliders = ColliderEditorPanel(session)
        self.tabs.addTab(self.colliders, "Colliders 2D (R32)")
        self.colliders.updated.connect(self.updated.emit)
        self.abilities.updated.connect(self.updated.emit)
        self.enemies.updated.connect(self.updated.emit)

    def refresh(self):
        self.abilities.refresh()
        self.enemies.refresh()
        self.colliders.refresh()
