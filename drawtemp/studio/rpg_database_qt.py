"""Qt 6 RPG Database workspace (R8), backed by the R1 AuthoringSession.

Use the native Widgets controls; the legacy Tk studio remains available
during migration.  The right pane edits typed fields rather than raw JSON.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.rpg_database import DatabaseEditor, FAMILIES, LABELS
from sporebound.character_authoring import make_effect, parse_bonuses, parse_skill_levels
from sporebound.model import MOVEMENTS, REACTIONS, STATUSES, SUPPORTS, Unit, RuleError
from sporebound.rules import default_rules


# Field types are explicit and validated by the canonical authoring backend.
SPECS = {
    "archetypes": (
        ("kind", "Type", ("character", "monster", "summon")),
        ("max_hp", "PV maximum", (1, 9999)),
        ("attack", "Attaque", (0, 9999)),
        ("speed", "Vitesse", (1, 9999)),
        ("move", "Déplacement", (0, 99)),
        ("weapon", "Arme", ("melee", "spear", "ranged", "focus", "unarmed")),
        ("skills", "Compétences (IDs)", "csv"),
        ("behavior", "Comportement IA", tuple(sorted(key for key, _ in default_rules().behaviors.entries))),
        ("reaction", "Réaction", tuple(sorted(REACTIONS))),
        ("support", "Soutien", tuple(sorted(SUPPORTS))),
    ),
    "actors": (
        ("name", "Nom", "text"),
        ("max_hp", "PV maximum", (1, 9999)),
        ("attack", "Attaque", (0, 9999)),
        ("speed", "Vitesse", (1, 9999)),
        ("move", "Déplacement", (0, 99)),
        ("weapon", "Arme", ("melee", "spear", "ranged", "focus", "unarmed")),
        ("skills", "Compétences (IDs)", "csv"),
        ("reaction", "Réaction", tuple(sorted(REACTIONS))),
        ("support", "Soutien", tuple(sorted(SUPPORTS))),
        ("movement", "Mouvement spécial", tuple(sorted(MOVEMENTS))),
    ),
    "jobs": (
        ("name", "Nom", "text"),
        ("requires", "Classe préalable (ID)", "text"),
        ("requires_level", "Niveau requis", (1, 20)),
        ("bonuses", "Bonus stat=valeur", "bonuses"),
        ("skills", "Compétences ID=niveau", "levels"),
    ),
    "skills": (
        ("name", "Nom", "text"),
        ("target", "Cible", ("enemy", "ally", "unit", "self", "ground", "downed")),
        ("cost", "Coût PM", (0, 100)),
        ("range", "Portée maximum", (0, 100)),
        ("min_range", "Portée minimum", (0, 100)),
        ("radius", "Rayon", (0, 100)),
        ("accuracy", "Précision (%)", (0, 100)),
        ("shape", "Zone", ("diamond", "cross", "square")),
    ),
    "equipment": (
        ("name", "Nom", "text"),
        ("slot", "Emplacement", ("weapon", "armor", "accessory")),
        ("price", "Prix", (0, 1000000)),
        ("bonuses", "Bonus stat=valeur", "equipment_bonuses"),
    ),
}


def _display(value, kind):
    if kind == "csv":
        return ", ".join(value)
    if kind in ("bonuses", "equipment_bonuses", "levels"):
        return ", ".join(f"{key}={value[key]}" for key in sorted(value))
    return str(value)


def _parse(value, kind, skill_ids):
    if kind == "csv":
        return [piece.strip() for piece in value.split(",") if piece.strip()]
    if kind in ("bonuses", "equipment_bonuses"):
        return parse_bonuses(value, equipment=(kind == "equipment_bonuses"))
    if kind == "levels":
        return parse_skill_levels(value, skill_ids)
    return value


class DatabaseWindow(QMainWindow):
    def __init__(self, session, *, path=None):
        super().__init__()
        self.editor = DatabaseEditor(session)
        self.path = Path(path) if path else None
        self.family = "archetypes"
        self.selected = None
        self.fields = {}
        self.setWindowTitle("DrawTemp 5.0 — Base RPG")
        self.resize(1320, 800)
        self._build()
        self._reload()

    def _build(self):
        toolbar = self.addToolBar("Projet")
        for label, callback in (
            ("Ouvrir", self._open), ("Enregistrer", self._save),
            ("Enregistrer sous", self._save_as), ("Annuler", self._undo),
            ("Rétablir", self._redo),
        ):
            button = toolbar.addAction(label)
            button.triggered.connect(callback)

        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(180)
        splitter.addWidget(self.tree)
        for family in FAMILIES:
            item = QTreeWidgetItem([LABELS[family]])
            item.setData(0, Qt.UserRole, family)
            self.tree.addTopLevelItem(item)
        self.tree.currentItemChanged.connect(self._category_changed)

        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.addWidget(QLabel("Rechercher une ressource"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Nom, identifiant, mission…")
        self.search.setAccessibleName("Rechercher dans la base RPG")
        self.search.textChanged.connect(self._reload_items)
        middle_layout.addWidget(self.search)
        self.listing = QListWidget()
        self.listing.setAccessibleName("Ressources RPG")
        self.listing.currentRowChanged.connect(self._select_entry)
        middle_layout.addWidget(self.listing)
        buttons = QHBoxLayout()
        for label, slot in (("Créer", self._create), ("Dupliquer", self._duplicate),
                            ("Supprimer", self._delete)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        middle_layout.addLayout(buttons)
        splitter.addWidget(middle)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.header = QLabel("Sélectionnez une ressource")
        font = self.header.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.header.setFont(font)
        right_layout.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form_container = QWidget()
        self.form = QFormLayout(self.form_container)
        self.scroll.setWidget(self.form_container)
        right_layout.addWidget(self.scroll, 3)
        self.references = QPlainTextEdit()
        self.references.setReadOnly(True)
        self.references.setPlaceholderText("Références et diagnostics")
        self.references.setMaximumHeight(170)
        right_layout.addWidget(QLabel("Références / aperçu"))
        right_layout.addWidget(self.references)
        self.apply_button = QPushButton("Appliquer les modifications")
        self.apply_button.clicked.connect(self._apply)
        right_layout.addWidget(self.apply_button)
        splitter.addWidget(right)
        splitter.setSizes([225, 330, 765])
        self.statusBar().showMessage("La base utilise Content / GameProject et l'historique R1.")
        # Canonical Jeanne reference has no archetypes yet: show placed actors first.
        self.tree.setCurrentItem(self.tree.topLevelItem(1))

    def _category_changed(self, item, _old):
        if item is None:
            return
        self.family = item.data(0, Qt.UserRole)
        self._reload_items()

    def _reload(self, preferred=None):
        self._reload_items(preferred)
        snapshot = self.editor.snapshot()
        marker = " • modifié" if snapshot.dirty else ""
        self.setWindowTitle("DrawTemp 5.0 — Base RPG" + marker)
        self.statusBar().showMessage(
            f"Révision {snapshot.revision} — " +
            ("modifications non enregistrées" if snapshot.dirty else "enregistré"))
        self.apply_button.setEnabled(self.selected is not None and
                                     self.family in SPECS)

    def _reload_items(self, preferred=None):
        if not isinstance(preferred, tuple):
            preferred = self.selected
        rows = self.editor.entries(self.family, self.search.text())
        self.listing.blockSignals(True)
        self.listing.clear()
        index = -1
        for n, entry in enumerate(rows):
            prefix = f"[{entry.mission_id}] " if entry.mission_id else ""
            self.listing.addItem(prefix + entry.name + "  ·  " + entry.id)
            self.listing.item(n).setData(Qt.UserRole,
                                         (entry.family, entry.id, entry.mission_id))
            if preferred == (entry.family, entry.id, entry.mission_id):
                index = n
        self.listing.blockSignals(False)
        self.listing.setCurrentRow(index if index >= 0 else (0 if rows else -1))
        if not rows:
            self.selected = None
            self._show_detail()

    def _select_entry(self, row):
        item = self.listing.item(row)
        self.selected = item.data(Qt.UserRole) if item is not None else None
        self._show_detail()

    def _clear_form(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}

    def _show_detail(self):
        self._clear_form()
        self.apply_button.setEnabled(self.selected is not None and
                                     self.family in SPECS)
        if self.selected is None:
            self.header.setText(LABELS[self.family])
            self.references.setPlainText("Aucune ressource sélectionnée.")
            return
        family, key, mission = self.selected
        row = self.editor.detail(family, key, mission)
        self.header.setText(row.get("name", key) + "  ·  " + key)
        self.form.addRow("Identifiant stable", QLabel(key))
        if mission:
            self.form.addRow("Mission", QLabel(mission))
        if family == "flags":
            self.form.addRow(QLabel("Drapeau utilisé par les scènes et conditions. "
                                   "L'édition des valeurs de campagne relève du R10."))
        else:
            for field, label, kind in SPECS[family]:
                value = row.get(field)
                if value is None and family == "archetypes":
                    value = Unit.__dataclass_fields__[field].default
                if value is None:
                    continue
                if isinstance(kind, tuple) and len(kind) == 2 and all(
                        isinstance(n, int) for n in kind):
                    widget = QSpinBox()
                    widget.setRange(*kind)
                    widget.setValue(value)
                elif isinstance(kind, tuple):
                    widget = QComboBox()
                    widget.addItems(kind)
                    if value not in kind:
                        widget.addItem(str(value))
                    widget.setCurrentText(str(value))
                else:
                    widget = QLineEdit(_display(value, kind))
                widget.setAccessibleName(label)
                self.form.addRow(label, widget)
                self.fields[field] = (widget, kind, value)
            if family == "skills":
                effects = row.get("effects", [])
                text = "\n".join(
                    f"{index + 1}. {effect['kind']} — {effect.get('status') or effect.get('element', '')} "
                    f"· puissance {effect.get('power', 0)}"
                    for index, effect in enumerate(effects))
                self.form.addRow("Effets", QLabel(text or "Aucun effet"))
                effect_button = QPushButton("Éditer / ajouter / retirer / déplacer un effet…")
                effect_button.clicked.connect(self._edit_effects)
                self.form.addRow(effect_button)
            if family == "jobs":
                self.form.addRow("Arbre de classe", QLabel(
                    "Prérequis validés ; liens supplémentaires via l'API R8"))
        refs = self.editor.references(family, key)
        self.references.setPlainText(
            "\n".join(refs) if refs else "Aucune référence directe connue.")

    def _edit_effects(self):
        if not self.selected or self.selected[0] != "skills":
            return
        key = self.selected[1]
        effects = self.editor.detail("skills", key)["effects"]
        choices = ["Ajouter", "Modifier", "Retirer", "Monter", "Descendre"]
        action, ok = QInputDialog.getItem(self, "Effets de compétence",
                                           "Opération", choices, 0, False)
        if not ok:
            return
        index = len(effects)
        if action != "Ajouter":
            if not effects:
                return
            index, ok = QInputDialog.getInt(self, "Effets",
                "Indice d'effet (1 = premier)", 1, 1, len(effects))
            if not ok:
                return
            index -= 1
        try:
            if action in ("Ajouter", "Modifier"):
                base = effects[index] if action == "Modifier" else make_effect()
                kinds = sorted(key for key, _ in default_rules().effects.entries)
                kind, ok = QInputDialog.getItem(self, "Type d'effet", "Type",
                    kinds, kinds.index(base["kind"]) if base["kind"] in kinds else 0, False)
                if not ok:
                    return
                power, ok = QInputDialog.getInt(
                    self, "Puissance", "Puissance", base["power"], 0, 10000)
                if not ok:
                    return
                duration, ok = QInputDialog.getInt(
                    self, "Durée", "Ticks", base["duration"], 1, 10000)
                if not ok:
                    return
                status = base.get("status", "")
                if kind in ("status", "cleanse"):
                    statuses = sorted(STATUSES)
                    status, ok = QInputDialog.getItem(
                        self, "Statut", "Statut", statuses,
                        statuses.index(status) if status in statuses else 0, False)
                    if not ok:
                        return
                scope_values = ["target", "allies", "enemies", "all"]
                scope, ok = QInputDialog.getItem(
                    self, "Portée de l'effet", "Affecte",
                    scope_values, scope_values.index(base.get("scope", "target")), False)
                if not ok:
                    return
                effect = make_effect(kind, power=power, duration=duration,
                    status=status if kind in ("status", "cleanse") else "",
                    element=base.get("element", "physical"), scope=scope)
                self.editor.set_effect(key, index, effect, insert=(action == "Ajouter"))
            elif action == "Retirer":
                self.editor.remove_effect(key, index)
            elif action == "Monter":
                self.editor.move_effect(key, index, -1)
            else:
                self.editor.move_effect(key, index, 1)
            self._reload(self.selected)
        except (RuleError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Effet rejeté", str(exc))

    def _apply(self):
        if not self.selected or self.family not in SPECS:
            return
        family, key, mission = self.selected
        try:
            skills = {row.id for row in self.editor.entries("skills")}
            changes = {}
            for field, (widget, kind, original) in self.fields.items():
                if isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                else:
                    value = _parse(widget.text(), kind, skills)
                if value != original:
                    changes[field] = value
            if not changes:
                self.statusBar().showMessage("Aucune modification.")
                return
            self.editor.update(family, key, mission_id=mission, **changes)
            self._reload((family, key, mission))
        except (RuleError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Modification rejetée", str(exc))

    def _create(self):
        family = self.family
        if family not in {"archetypes", "jobs", "skills", "equipment"}:
            QMessageBox.information(self, "Création",
                "La création d'unités se fait sur la carte ; les variables "
                "sont créées par les événements narratifs.")
            return
        key, accepted = QInputDialog.getText(self, "Créer une ressource",
                                              "Identifiant stable (sans espaces)")
        if not accepted or not key.strip():
            return
        key = key.strip()
        name = key
        if family != "archetypes":
            name, accepted = QInputDialog.getText(
                self, "Créer une ressource", "Nom affiché", text=key)
            if not accepted:
                return
        try:
            if family == "archetypes":
                fields = {"kind": "character"}
            elif family == "jobs":
                fields = {"name": name}
            elif family == "skills":
                fields = {"name": name}
            else:
                fields = {"name": name, "slot": "weapon"}
            self.editor.create(family, key, **fields)
            self._reload((family, key, ""))
        except (RuleError, ValueError) as exc:
            QMessageBox.warning(self, "Création rejetée", str(exc))

    def _duplicate(self):
        if self.selected is None:
            return
        family, key, mission = self.selected
        new_key, accepted = QInputDialog.getText(
            self, "Dupliquer", "Nouvel identifiant", text=key + "_copie")
        if not accepted or not new_key.strip():
            return
        try:
            self.editor.duplicate(family, key, new_key.strip())
            self._reload((family, new_key.strip(), ""))
        except (RuleError, ValueError) as exc:
            QMessageBox.warning(self, "Duplication rejetée", str(exc))

    def _delete(self):
        if self.selected is None:
            return
        family, key, _mission = self.selected
        if QMessageBox.question(
            self, "Supprimer", f"Supprimer définitivement la définition « {key} » ?"
        ) != QMessageBox.Yes:
            return
        try:
            self.editor.remove(family, key)
            self._reload()
        except (RuleError, ValueError) as exc:
            QMessageBox.warning(self, "Suppression rejetée", str(exc))

    def _undo(self):
        try:
            self.editor.undo()
            self._reload()
        except (RuleError, ValueError) as exc:
            self.statusBar().showMessage(str(exc))

    def _redo(self):
        try:
            self.editor.redo()
            self._reload()
        except (RuleError, ValueError) as exc:
            self.statusBar().showMessage(str(exc))

    def _open(self):
        if not self._allow_leave():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir le contenu",
                                               "", "Contenu (*.json)")
        if not path:
            return
        try:
            new_session = AuthoringSession.open(path)
        except (RuleError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Ouverture impossible", str(exc))
            return
        self.editor = DatabaseEditor(new_session)
        self.path = Path(path)
        self.selected = None
        self._reload()

    def _save(self):
        try:
            if self.path is None:
                self._save_as()
            else:
                self.editor.save()
                self._reload()
        except (RuleError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le contenu",
                                               "", "Contenu (*.json)")
        if not path:
            return
        try:
            self.editor.save_as(path)
            self.path = Path(path)
            self._reload()
        except (RuleError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))

    def _allow_leave(self):
        if not self.editor.snapshot().dirty:
            return True
        return QMessageBox.question(
            self, "Modifications non enregistrées",
            "Abandonner les modifications non enregistrées ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def closeEvent(self, event):
        if self._allow_leave():
            event.accept()
        else:
            event.ignore()


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5.0 — RPG Database (Qt 6)")
    parser.add_argument("--content", type=Path, help="Existing Content JSON with .game.json")
    parser.add_argument("--smoke", action="store_true", help="Start Qt and exit automatically")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("Qt 6 preview supported on Python 3.12")
    if args.content:
        session = AuthoringSession.open(args.content)
    else:
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = DatabaseWindow(session, path=args.content)
    window.show()
    if args.smoke:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
