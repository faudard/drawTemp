"""R35.C2 — native Qt Widgets NPC schedule editor over R1 AuthoringSession.

No direct writes to the source file, no second editor history and no timer-based
simulation. The timeline preview uses the headless clock with empty story flags;
a Player session must provide real campaign flags at runtime.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QTimeEdit, QVBoxLayout, QWidget,
)

from drawtemp.studio.living_world_authoring import (
    apply_living_world, preview_living_world)
from sporebound.living_world import EXTENSION, LivingWorld
from sporebound.living_world_diagnostics import timeline


class LivingWorldDialog(QDialog):
    """Human-editable NPC stops, previews and transactional save in Studio."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        snap = session.snapshot().to_dict()
        self.scenes = sorted(
            {m["id"] for m in snap["content"]["missions"]}
            | set(snap["project"].get("exploration", {})))
        envelope = snap["project"].get("extensions", {}).get(EXTENSION)
        self.document = deepcopy(envelope["data"]) if envelope else {
            "version": 1, "start_minute": 480, "ticks_per_minute": 60,
            "clock_policy": "exploration_only", "npcs": []}
        self.setWindowTitle("Monde vivant — horaires PNJ (R35)")
        self.resize(760, 660)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Modifier les horaires, prévisualiser puis appliquer via Undo/Redo."
            " Le diagnostic utilise des flags de quête inactifs."))
        world_row = QHBoxLayout()
        self.start = QTimeEdit()
        self.start.setDisplayFormat("HH:mm")
        minute = self.document["start_minute"]
        self.start.setTime(QTime(minute // 60, minute % 60))
        self.rate = QSpinBox()
        self.rate.setRange(1, 3600)
        self.rate.setValue(self.document["ticks_per_minute"])
        world_row.addWidget(QLabel("Début"))
        world_row.addWidget(self.start)
        world_row.addWidget(QLabel("Ticks/minute"))
        world_row.addWidget(self.rate)
        layout.addLayout(world_row)
        npc_row = QHBoxLayout()
        self.npc_select = QComboBox()
        self.npc_select.setAccessibleName("PNJ sélectionné")
        self.npc_select.currentIndexChanged.connect(self._load_stops)
        npc_row.addWidget(QLabel("PNJ"))
        npc_row.addWidget(self.npc_select, 1)
        for text, callback in (
                ("Ajouter PNJ", self._add_npc),
                ("Supprimer PNJ", self._remove_npc)):
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            npc_row.addWidget(btn)
        layout.addLayout(npc_row)
        self.stops = QListWidget()
        self.stops.setAccessibleName("Horaires et activités du PNJ")
        self.stops.currentRowChanged.connect(self._load_stop)
        layout.addWidget(self.stops, 1)
        self.stop_time = QTimeEdit()
        self.stop_time.setDisplayFormat("HH:mm")
        self.stop_scene = QComboBox()
        self.stop_scene.addItems(self.scenes)
        self.stop_activity = QLineEdit()
        self.stop_activity.setPlaceholderText("idle, trade, guard…")
        self.stop_flag = QLineEdit()
        self.stop_flag.setPlaceholderText("Flag facultatif")
        self.stop_expected = QCheckBox("Valeur attendue : vrai")
        self.stop_pos = QCheckBox("Coordonnées PNJ (exploration)")
        self.stop_x = QSpinBox()
        self.stop_y = QSpinBox()
        for coordinate in (self.stop_x, self.stop_y):
            coordinate.setRange(0, 31)
        self.stop_x.setAccessibleName("Position PNJ colonne")
        self.stop_y.setAccessibleName("Position PNJ ligne")
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("X"))
        coord_row.addWidget(self.stop_x)
        coord_row.addWidget(QLabel("Y"))
        coord_row.addWidget(self.stop_y)
        form = QFormLayout()
        form.addRow("Heure", self.stop_time)
        form.addRow("Scène", self.stop_scene)
        form.addRow("Activité", self.stop_activity)
        form.addRow("Condition", self.stop_flag)
        form.addRow("", self.stop_expected)
        form.addRow("", self.stop_pos)
        form.addRow("Cellule (x, y)", coord_row)
        host = QWidget()
        host.setLayout(form)
        layout.addWidget(host)
        buttons = QHBoxLayout()
        for name, callback in (
                ("Ajouter horaire", self._new_stop),
                ("Modifier horaire", self._update_stop),
                ("Supprimer horaire", self._delete_stop)):
            btn = QPushButton(name)
            btn.clicked.connect(callback)
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setAccessibleName("Diagnostic des horaires")
        layout.addWidget(self.diagnostics, 1)
        action_row = QHBoxLayout()
        for name, callback in (
                ("Prévisualiser", self._preview),
                ("Appliquer au projet", self._apply),
                ("Fermer", self.reject)):
            button = QPushButton(name)
            button.clicked.connect(callback)
            action_row.addWidget(button)
        layout.addLayout(action_row)
        self._load_npcs()

    def _npc(self):
        key = self.npc_select.currentText()
        return next((npc for npc in self.document["npcs"]
                     if npc["id"] == key), None)

    def _load_npcs(self, key=None):
        self.npc_select.blockSignals(True)
        self.npc_select.clear()
        self.npc_select.addItems([npc["id"] for npc in self.document["npcs"]])
        if key:
            self.npc_select.setCurrentText(key)
        self.npc_select.blockSignals(False)
        self._load_stops()

    def _load_stops(self, *_):
        self.stops.clear()
        npc = self._npc()
        if npc is None:
            return
        for stop in npc["schedule"]:
            minute = stop["minute"]
            coordinates = (f' @ {stop["pos"][0]},{stop["pos"][1]}'
                           if "pos" in stop else "")
            self.stops.addItem(
                f'{minute//60:02}:{minute%60:02} • '
                f'{stop["scene"]} / {stop["activity"]}{coordinates}')
        if self.stops.count():
            self.stops.setCurrentRow(0)

    def _load_stop(self, index):
        npc = self._npc()
        if npc is None or not 0 <= index < len(npc["schedule"]):
            return
        stop = npc["schedule"][index]
        m = stop["minute"]
        self.stop_time.setTime(QTime(m // 60, m % 60))
        self.stop_scene.setCurrentText(stop["scene"])
        self.stop_activity.setText(stop["activity"])
        cond = stop.get("when", {})
        self.stop_flag.setText(cond.get("flag", ""))
        self.stop_expected.setChecked(cond.get("eq", True))
        self.stop_pos.setChecked("pos" in stop)
        self.stop_x.setValue(stop.get("pos", [0, 0])[0])
        self.stop_y.setValue(stop.get("pos", [0, 0])[1])

    def _read_stop(self):
        if not self.stop_scene.currentText():
            raise ValueError("Sélectionnez une scène existante.")
        t = self.stop_time.time()
        stop = {"minute": t.hour() * 60 + t.minute(),
                "scene": self.stop_scene.currentText(),
                "activity": self.stop_activity.text().strip()}
        if self.stop_flag.text().strip():
            stop["when"] = {"flag": self.stop_flag.text().strip(),
                            "eq": self.stop_expected.isChecked()}
        if self.stop_pos.isChecked():
            stop["pos"] = [self.stop_x.value(), self.stop_y.value()]
        return stop

    def _mutate_stop(self, replace):
        npc = self._npc()
        if npc is None:
            QMessageBox.warning(self, "Horaires", "Ajoutez d'abord un PNJ.")
            return
        index = self.stops.currentRow()
        if replace and index < 0:
            return
        try:
            stop = self._read_stop()
            kept = [s for n, s in enumerate(npc["schedule"])
                    if not (replace and n == index)]
            if any(s["minute"] == stop["minute"] for s in kept):
                raise ValueError("Deux activités ne peuvent partager la même minute.")
            kept.append(stop)
            npc["schedule"] = sorted(kept, key=lambda s: s["minute"])
            self._load_stops()
            self.stops.setCurrentRow(npc["schedule"].index(stop))
        except ValueError as exc:
            QMessageBox.warning(self, "Horaire invalide", str(exc))

    def _new_stop(self):
        self._mutate_stop(False)

    def _update_stop(self):
        self._mutate_stop(True)

    def _delete_stop(self):
        npc = self._npc()
        if npc is None or self.stops.currentRow() < 0:
            return
        if len(npc["schedule"]) == 1:
            QMessageBox.warning(self, "Horaires", "Conservez au moins un horaire.")
            return
        del npc["schedule"][self.stops.currentRow()]
        self._load_stops()

    def _add_npc(self):
        ident, ok = QInputDialog.getText(self, "Nouveau PNJ", "Identifiant")
        if not ok or not ident.strip():
            return
        ident = ident.strip()
        if any(n["id"] == ident for n in self.document["npcs"]):
            QMessageBox.warning(self, "PNJ", "Cet identifiant existe déjà.")
            return
        if not self.scenes:
            QMessageBox.warning(self, "PNJ", "Créez d'abord une scène.")
            return
        self.document["npcs"].append({
            "id": ident, "schedule": [
                {"minute": 0, "scene": self.scenes[0], "activity": "idle"}]})
        self._load_npcs(ident)

    def _remove_npc(self):
        npc = self._npc()
        if npc is not None:
            self.document["npcs"].remove(npc)
            self._load_npcs()

    def _current_document(self):
        copy = deepcopy(self.document)
        t = self.start.time()
        copy["start_minute"] = t.hour() * 60 + t.minute()
        copy["ticks_per_minute"] = self.rate.value()
        return copy

    def _validated_preview(self):
        return preview_living_world(
            self.session, self._current_document(),
            expected_revision=self.session.revision)

    def _preview(self):
        try:
            draft = self._current_document()
            plan = self._validated_preview()
            world = LivingWorld(
                draft, set(self.scenes),
                exploration=self.session.snapshot().to_dict()["project"].get(
                    "exploration", {}))
            report = timeline(world, {}, limit=80)
            text = [f'PNJ : {plan.report["npc_count"]} | '
                    f'Boutiques : {plan.report["shop_count"]} | '
                    f'Quêtes : {plan.report["quest_count"]}',
                    "Horaires projetés avec flags de campagne non définis :"]
            text += [
                f'{e["minute"]//60:02}:{e["minute"]%60:02} '
                f'{e["kind"]} {e["id"]} {e.get("activity", "")}'
                for e in report["entries"]]
            if report["truncated"]:
                text.append("… suite tronquée (80 premières transitions)")
            self.diagnostics.setPlainText("\n".join(text))
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Prévisualisation impossible", str(exc))

    def _apply(self):
        try:
            preview = self._validated_preview()
            apply_living_world(self.session, preview)
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Modification refusée", str(exc))
            return
        self.accept()
