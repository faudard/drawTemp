"""R53.B1 — accessible Qt Party Composer backed by R1 AuthoringSession.

A preview is mandatory before Apply. Runtime party state is never edited by
this dialog: only initial project defaults and the shared R53 combo catalogue.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from drawtemp.studio.party_authoring import party_campaigns
from drawtemp.studio.party_orchestration_authoring import (
    apply_orchestration_edit, combo_impact_preview, inspect_orchestration,
    native_damage_choices, preview_orchestration_edit,
)


class R53PartyComposerDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._draft = None
        self._combo_skills = []
        self._rebuilding = False
        self.setObjectName("r53-party-composer")
        self.setWindowTitle("R53.B — Party Composer")
        self.resize(820, 760)

        layout = QVBoxLayout(self)
        note = QLabel(
            "Composition initiale, formation et capacités coopératives. "
            "Personnages et compétences proviennent du groupe R41 et de Content. "
            "Les changements passent par Prévisualiser → Appliquer ; "
            "Annuler/Rétablir utilise l'historique commun du Studio.")
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        self.campaign = QComboBox()
        self.campaign.setObjectName("r53-campaign")
        self.campaign.setAccessibleName("Campagne du Party Composer")
        for cid, name in party_campaigns(session.snapshot()):
            self.campaign.addItem(name, cid)
        form.addRow("Campagne", self.campaign)
        self.leader = QComboBox()
        self.leader.setObjectName("r53-leader")
        self.leader.setAccessibleName("Leader initial")
        form.addRow("Leader initial", self.leader)
        layout.addLayout(form)

        layout.addWidget(QLabel("Positions des membres actifs au départ"))
        self.formation = QTableWidget()
        self.formation.setObjectName("r53-formation")
        self.formation.setAccessibleName("Cases de formation des membres actifs")
        self.formation.setColumnCount(2)
        self.formation.setHorizontalHeaderLabels(["Personnage", "Position"])
        self.formation.setMaximumHeight(185)
        layout.addWidget(self.formation)

        layout.addWidget(QLabel(
            "Combos (héros dans l'ordre : le premier déclenche l'action)"))
        self.combos = QTableWidget()
        self.combos.setObjectName("r53-combos")
        self.combos.setAccessibleName("Catalogue des capacités coopératives")
        self.combos.setColumnCount(3)
        self.combos.setHorizontalHeaderLabels(
            ["Identifiant", "Héros (IDs séparés par virgule)",
             "Modes (RPG_TURN, TACTICAL_CT, ACTION_REALTIME)"])
        self.combos.setMinimumHeight(130)
        layout.addWidget(self.combos, 1)

        controls = QHBoxLayout()
        self.add_button = QPushButton("Ajouter un combo")
        self.add_button.setObjectName("r53-add-combo")
        self.remove_button = QPushButton("Supprimer le combo")
        self.remove_button.setObjectName("r53-remove-combo")
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        layout.addLayout(controls)

        self.skills = QTableWidget()
        self.skills.setObjectName("r53-combo-skills")
        self.skills.setAccessibleName("Compétences natives des participants du combo")
        self.skills.setColumnCount(2)
        self.skills.setHorizontalHeaderLabels(
            ["Héros participant", "Compétence native de dégâts (optionnelle)"])
        self.skills.setMaximumHeight(145)
        layout.addWidget(self.skills)
        explanation = QLabel(
            "Sans compétences : combo déclaratif uniquement. Pour un combo "
            "RPG jouable, sélectionner une compétence de dégâts pour CHAQUE héros. "
            "Le mode CT/action reste déclaratif.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.report = QPlainTextEdit()
        self.report.setObjectName("r53-composer-preview")
        self.report.setAccessibleName("Prévisualisation du groupe et des combos")
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(145)
        layout.addWidget(self.report)

        actions = QHBoxLayout()
        self.preview_button = QPushButton("Prévisualiser")
        self.preview_button.setObjectName("r53-preview")
        self.apply_button = QPushButton("Appliquer")
        self.apply_button.setObjectName("r53-apply")
        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.setObjectName("r53-refresh")
        self.close_button = QPushButton("Fermer")
        for widget in (self.preview_button, self.apply_button,
                       self.refresh_button, self.close_button):
            actions.addWidget(widget)
        layout.addLayout(actions)

        self.campaign.currentIndexChanged.connect(self.refresh)
        self.leader.currentIndexChanged.connect(self._invalidate)
        self.combos.itemChanged.connect(self._combo_changed)
        self.combos.itemSelectionChanged.connect(self._refresh_skill_editor)
        self.add_button.clicked.connect(self.add_combo)
        self.remove_button.clicked.connect(self.remove_combo)
        self.preview_button.clicked.connect(self.preview)
        self.apply_button.clicked.connect(self.apply)
        self.refresh_button.clicked.connect(self.refresh)
        self.close_button.clicked.connect(self.close)
        self.refresh()

    def _invalidate(self, *_):
        if not self._rebuilding:
            self._draft = None
            self.apply_button.setEnabled(False)

    def refresh(self, *_):
        self._rebuilding = True
        self._draft = None
        self.apply_button.setEnabled(False)
        try:
            cid = self.campaign.currentData()
            if cid is None:
                return
            view = inspect_orchestration(self.session.snapshot(), cid)
            self.leader.clear()
            for uid in view["active"]:
                self.leader.addItem(uid, uid)
            self.leader.setCurrentIndex(self.leader.findData(view["leader"]))

            self.formation.setRowCount(len(view["active"]))
            for idx, uid in enumerate(view["active"]):
                item = QTableWidgetItem(uid)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.formation.setItem(idx, 0, item)
                choice = QComboBox()
                choice.setAccessibleName("Position de " + uid)
                for slot in view["slots"]:
                    choice.addItem(slot, slot)
                choice.setCurrentIndex(choice.findData(view["formation"][idx]))
                choice.currentIndexChanged.connect(self._invalidate)
                self.formation.setCellWidget(idx, 1, choice)

            self.combos.blockSignals(True)
            self.combos.setRowCount(len(view["combos"]))
            self._combo_skills = []
            for idx, combo in enumerate(view["combos"]):
                self._combo_skills.append(dict(combo.get("skills", {})))
                self._set_combo_row(idx, combo)
            self.combos.blockSignals(False)
            if view["combos"]:
                self.combos.selectRow(0)
            self._refresh_skill_editor()
            self.report.setPlainText(
                "État actuel : " + ("R53 activé" if view["enabled"]
                                    else "R53 non activé") +
                ". Modifier puis prévisualiser. Aucun changement à ce stade.")
        except Exception as exc:
            self.report.setPlainText("Configuration indisponible : " + str(exc))
            self.combos.setRowCount(0)
            self.formation.setRowCount(0)
            self.skills.setRowCount(0)
        finally:
            self._rebuilding = False

    def _set_combo_row(self, row, combo):
        for col, value in enumerate((
                combo["id"], ", ".join(combo["members"]),
                ", ".join(combo["modes"]))):
            item = QTableWidgetItem(value)
            item.setToolTip("Éditez cette cellule puis prévisualisez")
            self.combos.setItem(row, col, item)

    def _combo_changed(self, *_):
        self._invalidate()
        self._refresh_skill_editor()

    def _active_ids(self):
        return [self.formation.item(row, 0).text()
                for row in range(self.formation.rowCount())]

    def add_combo(self):
        active = self._active_ids()
        if len(active) < 2:
            self.report.setPlainText(
                "Il faut au moins deux héros actifs pour créer un combo.")
            return
        used = {self.combos.item(i, 0).text()
                for i in range(self.combos.rowCount())}
        index = 1
        while "combo_" + str(index) in used:
            index += 1
        self._rebuilding = True
        row = self.combos.rowCount()
        self.combos.setRowCount(row + 1)
        self._combo_skills.append({})
        self._set_combo_row(row, {
            "id": "combo_" + str(index), "members": active[:2],
            "modes": ["RPG_TURN"]})
        self._rebuilding = False
        self.combos.selectRow(row)
        self._invalidate()

    def remove_combo(self):
        row = self.combos.currentRow()
        if row < 0:
            return
        self._rebuilding = True
        self.combos.removeRow(row)
        self._combo_skills.pop(row)
        self._rebuilding = False
        if self.combos.rowCount():
            self.combos.selectRow(min(row, self.combos.rowCount() - 1))
        self._refresh_skill_editor()
        self._invalidate()

    def _refresh_skill_editor(self):
        self._rebuilding = True
        try:
            row = self.combos.currentRow()
            self.skills.setRowCount(0)
            if not 0 <= row < len(self._combo_skills):
                return
            members_item = self.combos.item(row, 1)
            if members_item is None:
                return
            members = [x.strip() for x in members_item.text().split(",") if x.strip()]
            configured = self._combo_skills[row]
            for index, uid in enumerate(members):
                self.skills.insertRow(index)
                item = QTableWidgetItem(uid)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.skills.setItem(index, 0, item)
                widget = QComboBox()
                widget.setAccessibleName("Compétence native de " + uid)
                widget.addItem("Déclaratif (aucune)", None)
                for skill_id, title in native_damage_choices(
                        self.session.snapshot(), uid):
                    widget.addItem(title + " (" + skill_id + ")", skill_id)
                existing = configured.get(uid)
                widget.setCurrentIndex(max(0, widget.findData(existing)))
                widget.currentIndexChanged.connect(
                    lambda _n, r=row, h=uid, w=widget:
                    self._skill_changed(r, h, w.currentData()))
                self.skills.setCellWidget(index, 1, widget)
        finally:
            self._rebuilding = False

    def _skill_changed(self, row, hero, skill):
        if self._rebuilding or row >= len(self._combo_skills):
            return
        if skill is None:
            self._combo_skills[row].pop(hero, None)
        else:
            self._combo_skills[row][hero] = skill
        self._invalidate()

    def _read_combos(self):
        combos = []
        for row in range(self.combos.rowCount()):
            fields = [self.combos.item(row, col).text().strip()
                      for col in range(3)]
            result = {
                "id": fields[0],
                "members": [part.strip() for part in fields[1].split(",")
                            if part.strip()],
                "modes": [part.strip() for part in fields[2].split(",")
                          if part.strip()],
            }
            if self._combo_skills[row]:
                result["skills"] = dict(self._combo_skills[row])
            combos.append(result)
        return combos

    def preview(self):
        try:
            combos = self._read_combos()
            slots = [self.formation.cellWidget(row, 1).currentData()
                     for row in range(self.formation.rowCount())]
            self._draft = preview_orchestration_edit(
                self.session, self.campaign.currentData(),
                leader=self.leader.currentData(), formation=slots,
                combos=combos, expected_revision=self.session.revision)
            details = combo_impact_preview(self.session.snapshot(), combos)
            self.report.setPlainText(json.dumps({
                "campaign": self._draft.campaign,
                "before": self._draft.before, "after": self._draft.after,
                "native_impact": details,
                "note": "Puissances natives et coûts MP; dégâts finaux dépendent de la cible",
                "revision": self._draft.revision},
                ensure_ascii=False, indent=2))
            self.apply_button.setEnabled(True)
            return self._draft
        except Exception as exc:
            self._invalidate()
            self.report.setPlainText("Prévisualisation refusée : " + str(exc))
            return None

    def apply(self):
        if self._draft is None:
            return None
        try:
            result = apply_orchestration_edit(self.session, self._draft)
        except Exception as exc:
            self._invalidate()
            QMessageBox.warning(self, "R53 Party Composer", str(exc))
            return None
        self.updated.emit()
        self.refresh()
        self.report.setPlainText(
            "R53 appliqué dans GameProject. Enregistrez depuis le Studio; "
            "Annuler/Rétablir utilise l'historique R1 partagé.")
        return result


__all__ = ["R53PartyComposerDialog"]
