"""R62.B.2: typed Qt Relationship Studio, reusing R35 schedules and R1 history."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from drawtemp.studio.relationship_authoring import RelationshipDraft


def _spin(low, high, value=0):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


class RelationshipStudioDialog(QDialog):
    """Author NPC talk/gift policies without scripts or another NPC calendar."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.draft = RelationshipDraft(session)
        self._loaded_npc = None
        self._gift_rows = []
        self.setWindowTitle("Relationship Studio R62.B.2 — relations PNJ")
        self.resize(700, 600)
        root = QVBoxLayout(self)
        instruction = QLabel(
            "Les horaires PNJ sont ceux du Monde vivant R35. Chaque PNJ "
            "peut parler et recevoir un cadeau par jour ; les affinités "
            "sont enregistrées par GameSession et non par l'éditeur.")
        instruction.setWordWrap(True)
        root.addWidget(instruction)
        self.people = QListWidget()
        self.people.setObjectName("r62SocialPeople")
        self.people.setAccessibleName("Relations PNJ disponibles")
        self.people.currentRowChanged.connect(self._select_person)
        root.addWidget(self.people, 2)
        form = QFormLayout()
        self.npc = QComboBox()
        self.npc.setAccessibleName("Identifiant PNJ R35")
        self.npc.addItems(self.draft.npcs)
        self.npc.currentTextChanged.connect(self._refresh_activities)
        self.initial = _spin(-100, 100)
        self.talk_gain = _spin(0, 20, 2)
        self.activity = QComboBox()
        self.activity.setAccessibleName("Activité requise pour parler")
        form.addRow("PNJ du monde vivant", self.npc)
        form.addRow("Affinité initiale", self.initial)
        form.addRow("Points par conversation", self.talk_gain)
        form.addRow("Activité horaire R35", self.activity)
        root.addLayout(form)
        root.addWidget(QLabel("Cadeaux autorisés (objets canoniques du projet)"))
        self.gifts = QListWidget()
        self.gifts.setObjectName("r62SocialGifts")
        self.gifts.setAccessibleName("Préférences de cadeaux du PNJ")
        root.addWidget(self.gifts, 1)
        gift_form = QHBoxLayout()
        self.gift_item = QComboBox()
        self.gift_item.setAccessibleName("Objet accepté comme cadeau")
        self.gift_item.addItems(self.draft.items)
        self.gift_gain = _spin(-20, 20, 5)
        gift_form.addWidget(QLabel("Objet"))
        gift_form.addWidget(self.gift_item, 2)
        gift_form.addWidget(QLabel("Affinité"))
        gift_form.addWidget(self.gift_gain)
        add_gift = QPushButton("Ajouter / Modifier le cadeau")
        add_gift.clicked.connect(self._upsert_gift)
        gift_form.addWidget(add_gift)
        root.addLayout(gift_form)
        gift_buttons = QHBoxLayout()
        remove_gift = QPushButton("Supprimer cadeau sélectionné")
        remove_gift.clicked.connect(self._remove_gift)
        gift_buttons.addWidget(remove_gift)
        root.addLayout(gift_buttons)
        edit_buttons = QHBoxLayout()
        new = QPushButton("Nouvelle relation")
        new.clicked.connect(self._new)
        save = QPushButton("Valider le PNJ")
        save.setObjectName("r62SocialSave")
        save.clicked.connect(self._save_person)
        remove = QPushButton("Supprimer le PNJ")
        remove.clicked.connect(self._remove_person)
        edit_buttons.addWidget(new)
        edit_buttons.addWidget(save)
        edit_buttons.addWidget(remove)
        root.addLayout(edit_buttons)
        history = QHBoxLayout()
        self.undo_btn = QPushButton("Annuler brouillon")
        self.undo_btn.setObjectName("r62SocialUndo")
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn = QPushButton("Rétablir brouillon")
        self.redo_btn.setObjectName("r62SocialRedo")
        self.redo_btn.clicked.connect(self._redo)
        schedule = QPushButton("Éditer les horaires PNJ R35…")
        schedule.clicked.connect(self._open_r35)
        history.addWidget(self.undo_btn)
        history.addWidget(self.redo_btn)
        history.addWidget(schedule)
        root.addLayout(history)
        self.status = QLabel("")
        self.status.setAccessibleName("Diagnostic social R62")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        footer = QHBoxLayout()
        check = QPushButton("Prévisualiser")
        check.setObjectName("r62SocialPreview")
        check.clicked.connect(self._preview)
        apply = QPushButton("Appliquer au projet")
        apply.setObjectName("r62SocialApply")
        apply.clicked.connect(self._apply)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        footer.addWidget(check)
        footer.addWidget(apply)
        footer.addWidget(close)
        root.addLayout(footer)
        self._refresh_activities()
        self._refresh()

    def _show_error(self, exc):
        self.status.setText("R62 : " + str(exc))
        QMessageBox.warning(self, "Relationship Studio", str(exc))

    def _refresh_activities(self, *_):
        selected = self.activity.currentText()
        npc = self.npc.currentText()
        self.activity.clear()
        self.activity.addItems(["any"] + sorted(
            self.draft.activities.get(npc, set()) - {"any"}))
        index = self.activity.findText(selected)
        if index >= 0:
            self.activity.setCurrentIndex(index)

    def _refresh_gifts(self):
        self.gifts.clear()
        for gift in self._gift_rows:
            self.gifts.addItem(f'{gift["item"]} : {gift["gain"]:+d}')

    def _upsert_gift(self):
        item = self.gift_item.currentText()
        if not item:
            self._show_error(ValueError("Aucun objet canonique disponible"))
            return
        row = {"item": item, "gain": self.gift_gain.value()}
        index = next((i for i, value in enumerate(self._gift_rows)
                      if value["item"] == item), -1)
        if index < 0:
            self._gift_rows.append(row)
        else:
            self._gift_rows[index] = row
        self._refresh_gifts()

    def _remove_gift(self):
        index = self.gifts.currentRow()
        if index >= 0:
            del self._gift_rows[index]
            self._refresh_gifts()

    def _select_person(self, index):
        if index < 0:
            return
        row = self.draft.document["relationships"][index]
        self._loaded_npc = row["npc"]
        self.npc.setCurrentText(row["npc"])
        self.initial.setValue(row["initial"])
        self.talk_gain.setValue(row["talk_gain"])
        self._refresh_activities()
        self.activity.setCurrentText(row["talk_activity"])
        self._gift_rows = deepcopy(row["gifts"])
        self._refresh_gifts()

    def _new(self):
        self.people.clearSelection()
        self.people.setCurrentRow(-1)
        self._loaded_npc = None
        self.initial.setValue(0)
        self.talk_gain.setValue(2)
        self.activity.setCurrentText("any")
        self._gift_rows = []
        self._refresh_gifts()

    def _refresh(self):
        selected = self._loaded_npc
        self.people.blockSignals(True)
        self.people.clear()
        for row in self.draft.document["relationships"]:
            self.people.addItem(row["npc"])
            if row["npc"] == selected:
                self.people.setCurrentRow(self.people.count() - 1)
        self.people.blockSignals(False)
        self.undo_btn.setEnabled(self.draft.can_undo)
        self.redo_btn.setEnabled(self.draft.can_redo)

    def _save_person(self):
        row = {
            "npc": self.npc.currentText(), "initial": self.initial.value(),
            "talk_gain": self.talk_gain.value(),
            "talk_activity": self.activity.currentText(),
            "gifts": deepcopy(self._gift_rows)}
        try:
            self.draft.upsert(row, original_npc=self._loaded_npc)
            self._loaded_npc = row["npc"]
            self._refresh()
            self.status.setText("Relation validée dans le brouillon.")
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)

    def _remove_person(self):
        try:
            if self._loaded_npc is None:
                raise ValueError("Sélectionnez une relation PNJ")
            self.draft.remove(self._loaded_npc)
            self._loaded_npc = None
            self._refresh()
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)

    def _undo(self):
        if self.draft.undo():
            self._loaded_npc = None
            self._refresh()

    def _redo(self):
        if self.draft.redo():
            self._loaded_npc = None
            self._refresh()

    def _open_r35(self):
        from drawtemp.studio.living_world_qt import LivingWorldDialog
        prior = self.session.revision
        LivingWorldDialog(self.session, parent=self).exec()
        if self.session.revision != prior:
            self.status.setText(
                "Le calendrier a changé : rouvrir Relationship Studio "
                "avant d'appliquer ce brouillon.")

    def _preview(self):
        try:
            report = self.draft.preview().report
            self.status.setText(
                f"Validation canonique : {report['npc_count']} PNJ, "
                f"{report['gift_count']} préférences de cadeau ; "
                "aucun changement de partie ni de calendrier.")
            return report
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)
            return None

    def _apply(self):
        if self._preview() is None:
            return
        try:
            self.draft.apply()
            self.accept()
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)


__all__ = ["RelationshipStudioDialog"]
