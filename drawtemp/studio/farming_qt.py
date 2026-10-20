"""R62.B.1 — Native, typed Farm Studio over canonical R1 AuthoringSession.

The widget never saves a sidecar, writes raw JSON, runs a separate world clock
or mutates Campaign. Local edit history is capped, and Apply is a single
validated AuthoringSession transaction. R35 NPC routines are edited via the
existing editor, rather than duplicating schedule ownership.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from drawtemp.studio.farming_authoring import FarmDraft
from sporebound.farming_life import FarmingLife, SEASONS, SOILS


def _combo(items, selected=""):
    combo = QComboBox()
    combo.addItems(list(items))
    if selected:
        index = combo.findText(selected)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            # A broken reference must never silently turn into another value.
            combo.insertItem(0, selected)
            combo.setCurrentIndex(0)
    return combo


def _spin(low, high, value):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


class FarmRecordEditor(QDialog):
    """All plot/crop/animal properties use typed widgets, not a JSON editor."""

    def __init__(self, family, draft, record=None, parent=None):
        super().__init__(parent)
        if family not in FarmDraft.FAMILIES:
            raise ValueError("Unknown R62 record family")
        self.family = family
        self.draft = draft
        self.record = None
        row = record or {}
        self.setWindowTitle({
            "plots": "Parcelle", "crops": "Culture", "animals": "Animal",
        }[family] + " — R62")
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.ident = QLineEdit(row.get("id", ""))
        self.ident.setAccessibleName("Identifiant stable")
        form.addRow("Identifiant", self.ident)
        if family == "plots":
            self.scene = _combo(draft.scenes, row.get("scene", ""))
            self.soil = _combo(SOILS, row.get("soil", "loam"))
            form.addRow("Scène", self.scene)
            form.addRow("Sol", self.soil)
        elif family == "crops":
            self.seed_item = _combo(draft.items, row.get("seed_item", ""))
            self.yield_item = _combo(draft.items, row.get("yield_item", ""))
            self.yield_quantity = _spin(1, 99, row.get("yield_quantity", 1))
            self.grow_days = _spin(1, 120, row.get("grow_days", 1))
            form.addRow("Graine / objet consommé", self.seed_item)
            form.addRow("Produit récolté", self.yield_item)
            form.addRow("Quantité récoltée", self.yield_quantity)
            form.addRow("Croissance (jours)", self.grow_days)
            self.soil_checks = []
            self.season_checks = []
            for name, choices, current, store in (
                    ("Sols autorisés", SOILS, row.get("soils", ["loam"]),
                     self.soil_checks),
                    ("Saisons autorisées", SEASONS,
                     row.get("seasons", ["spring"]), self.season_checks)):
                strip = QWidget()
                layout = QHBoxLayout(strip)
                layout.setContentsMargins(0, 0, 0, 0)
                for value in choices:
                    item = QCheckBox(value)
                    item.setChecked(value in current)
                    layout.addWidget(item)
                    store.append(item)
                form.addRow(name, strip)
        else:
            self.scene = _combo(draft.scenes, row.get("scene", ""))
            self.feed_item = _combo(draft.items, row.get("feed_item", ""))
            self.yield_item = _combo(draft.items, row.get("yield_item", ""))
            self.yield_quantity = _spin(1, 99, row.get("yield_quantity", 1))
            self.interval = _spin(1, 120, row.get("interval_days", 1))
            form.addRow("Scène", self.scene)
            form.addRow("Nourriture consommée", self.feed_item)
            form.addRow("Production", self.yield_item)
            form.addRow("Quantité produite", self.yield_quantity)
            form.addRow("Intervalle de production (jours)", self.interval)
        root.addLayout(form)
        buttons = QHBoxLayout()
        save = QPushButton("Valider")
        save.setObjectName("r62RecordAccept")
        save.clicked.connect(self._accept_record)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

    def _accept_record(self):
        ident = self.ident.text().strip()
        if self.family == "plots":
            value = {"id": ident, "scene": self.scene.currentText(),
                     "soil": self.soil.currentText()}
        elif self.family == "crops":
            value = {
                "id": ident, "seed_item": self.seed_item.currentText(),
                "yield_item": self.yield_item.currentText(),
                "yield_quantity": self.yield_quantity.value(),
                "grow_days": self.grow_days.value(),
                "soils": [box.text() for box in self.soil_checks if box.isChecked()],
                "seasons": [box.text() for box in self.season_checks
                            if box.isChecked()],
            }
        else:
            value = {
                "id": ident, "scene": self.scene.currentText(),
                "feed_item": self.feed_item.currentText(),
                "yield_item": self.yield_item.currentText(),
                "yield_quantity": self.yield_quantity.value(),
                "interval_days": self.interval.value(),
            }
        # Keep the form open when values are missing. The full canonical
        # validator still runs before any draft or project mutation.
        if not ident:
            QMessageBox.warning(self, "R62", "Identifiant requis.")
            return
        self.record = value
        self.accept()


class FarmStudioDialog(QDialog):
    """Farm authoring, local history, read-only forecast, global project apply."""

    LABELS = {"plots": "Parcelles", "crops": "Cultures",
              "animals": "Animaux"}

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.draft = FarmDraft(session)
        self.session = session
        self.setWindowTitle("Farm Studio R62.B.1 — parcelles, cultures, élevage")
        self.resize(820, 670)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Édition typée de la ferme. Les saisons et la croissance utilisent "
            "l'horloge R35 ; les routines PNJ sont modifiées dans Monde vivant."))
        self.seed = _spin(0, 2 ** 31 - 1, self.draft.document["seed"])
        self.season_days = _spin(2, 120, self.draft.document["season_days"])
        self.weather = QCheckBox("Météo déterministe")
        self.weather.setChecked(self.draft.document["weather"])
        self.initialize_clock = QCheckBox(
            "Initialiser le calendrier R35 (si absent)")
        self.initialize_clock.setEnabled(not self.draft.clock_present)
        self.initialize_clock.setChecked(False)
        params = QHBoxLayout()
        params.addWidget(QLabel("Seed"))
        params.addWidget(self.seed)
        params.addWidget(QLabel("Jours / saison"))
        params.addWidget(self.season_days)
        params.addWidget(self.weather)
        root.addLayout(params)
        root.addWidget(self.initialize_clock)
        setting_button = QPushButton("Valider paramètres")
        setting_button.clicked.connect(self._settings)
        root.addWidget(setting_button)
        self.tabs = QTabWidget()
        self.lists = {}
        for family in FarmDraft.FAMILIES:
            page = QWidget()
            layout = QVBoxLayout(page)
            listing = QListWidget()
            listing.setObjectName("r62_" + family)
            listing.setAccessibleName("Liste R62 : " + self.LABELS[family])
            self.lists[family] = listing
            layout.addWidget(listing)
            buttons = QHBoxLayout()
            for label, callback in (
                    ("Ajouter", lambda checked=False, kind=family: self._edit(kind)),
                    ("Modifier", lambda checked=False, kind=family: self._edit(
                        kind, selected=True)),
                    ("Supprimer", lambda checked=False, kind=family: self._delete(kind))):
                button = QPushButton(label)
                button.clicked.connect(callback)
                buttons.addWidget(button)
            layout.addLayout(buttons)
            self.tabs.addTab(page, self.LABELS[family])
        root.addWidget(self.tabs)
        actions = QHBoxLayout()
        self.undo_button = QPushButton("Annuler brouillon")
        self.undo_button.setObjectName("r62Undo")
        self.undo_button.clicked.connect(self._undo)
        self.redo_button = QPushButton("Rétablir brouillon")
        self.redo_button.setObjectName("r62Redo")
        self.redo_button.clicked.connect(self._redo)
        routines = QPushButton("Modifier les horaires PNJ R35…")
        routines.clicked.connect(self._edit_schedules)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        actions.addWidget(routines)
        root.addLayout(actions)
        self.diagnostics = QLabel("")
        self.diagnostics.setAccessibleName("Diagnostic de la ferme R62")
        self.diagnostics.setWordWrap(True)
        root.addWidget(self.diagnostics)
        footer = QHBoxLayout()
        preview = QPushButton("Prévisualiser")
        preview.setObjectName("r62Preview")
        preview.clicked.connect(self._preview)
        apply = QPushButton("Appliquer au projet")
        apply.setObjectName("r62Apply")
        apply.clicked.connect(self._apply)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        footer.addWidget(preview)
        footer.addWidget(apply)
        footer.addWidget(close)
        root.addLayout(footer)
        self._refresh()

    def _show_error(self, error):
        self.diagnostics.setText("R62 : " + str(error))
        QMessageBox.warning(self, "Farm Studio R62", str(error))

    def _refresh(self):
        document = self.draft.document
        for family, widget in self.lists.items():
            selected = widget.currentItem().text().split(" — ")[0] if widget.currentItem() else None
            widget.clear()
            for row in document[family]:
                label = row["id"] + " — " + (
                    row["scene"] if family != "crops" else
                    str(row["grow_days"]) + " jour(s)")
                widget.addItem(label)
                if selected == row["id"]:
                    widget.setCurrentRow(widget.count() - 1)
        self.seed.setValue(document["seed"])
        self.season_days.setValue(document["season_days"])
        self.weather.setChecked(document["weather"])
        self.undo_button.setEnabled(self.draft.can_undo)
        self.redo_button.setEnabled(self.draft.can_redo)

    def _settings(self):
        try:
            self.draft.settings(seed=self.seed.value(),
                                season_days=self.season_days.value(),
                                weather=self.weather.isChecked())
            self._refresh()
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)

    def _selection(self, family):
        item = self.lists[family].currentItem()
        if item is None:
            raise ValueError("Sélectionnez une ligne " + self.LABELS[family])
        identity = item.text().split(" — ")[0]
        return next(row for row in self.draft.document[family]
                    if row["id"] == identity)

    def _edit(self, family, *, selected=False):
        try:
            original = self._selection(family) if selected else None
        except (ValueError, StopIteration) as exc:
            self._show_error(exc)
            return
        dialog = FarmRecordEditor(family, self.draft, record=original, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.draft.upsert(
                family, dialog.record,
                original_id=original["id"] if original is not None else None)
            self.diagnostics.setText("Modification validée dans le brouillon.")
            self._refresh()
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)

    def _delete(self, family):
        try:
            original = self._selection(family)
            self.draft.remove(family, original["id"])
            self._refresh()
        except (ValueError, TypeError, KeyError, StopIteration) as exc:
            self._show_error(exc)

    def _undo(self):
        if self.draft.undo():
            self._refresh()

    def _redo(self):
        if self.draft.redo():
            self._refresh()

    def _edit_schedules(self):
        from drawtemp.studio.living_world_qt import LivingWorldDialog
        original = self.session.revision
        LivingWorldDialog(self.session, parent=self).exec()
        if self.session.revision != original:
            # A world calendar transaction invalidates our cached R1 revision.
            self.diagnostics.setText(
                "Horaires modifiés : fermer et rouvrir Farm Studio pour éviter "
                "d'écraser une révision concurrente.")

    def _preview(self):
        try:
            self.draft.initialize_clock = self.initialize_clock.isChecked()
            report = self.draft.preview().report
            sample = FarmingLife(
                self.draft.document, set(self.draft.scenes),
                set(self.draft.items)).view()
            self.diagnostics.setText(
                "Validé sans modifier le projet — "
                f"{report['plot_count']} parcelle(s), "
                f"{report['crop_count']} culture(s), "
                f"{report['animal_count']} animal(aux) ; "
                f"saison : {sample['season']}, météo : "
                f"{sample['weather'] or 'désactivée'}.")
            return report
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)
            return None

    def _apply(self):
        if self._preview() is None:
            return
        try:
            self.draft.apply()
            self.diagnostics.setText("Ferme appliquée au projet (Undo/Redo global).")
            self.accept()
        except (ValueError, TypeError, KeyError) as exc:
            self._show_error(exc)


__all__ = ["FarmStudioDialog", "FarmRecordEditor"]
