"""R38.2 Qt authoring panel for *existing* R6 group prefabs and variants.

No second prefab placement algorithm. All edits flow through the Studio's
canonical AuthoringSession, and inherited updates require a separate review.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from sporebound.group_prefabs import load_group_prefab, _validate_prefab
from sporebound.prefab_variants import (
    KIND, NAMESPACE, VERSION, prefab_digest, preview_place_variant,
    preview_register_variant, preview_update_variant,
)


class PrefabVariantsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.session = owner.session
        self._source = None
        self._pending = None
        self.setObjectName("r38-prefab-variants")
        self.setWindowTitle("R38.2 • Prefabs et variantes héritées")
        self.resize(670, 590)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Sélectionnez un prefab de groupes R6 v1. Les variantes modifient "
            "uniquement des propriétés typées ; la carte reste un Content canonique.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        browse = QPushButton("Charger un prefab de groupes v1…")
        browse.clicked.connect(self.browse_source)
        layout.addWidget(browse)
        self.source_label = QLabel("Aucun prefab sélectionné")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        form = QFormLayout()
        self.variant_id = QLineEdit()
        self.variant_id.setObjectName("r38-variant-id")
        self.variant_id.setAccessibleName("Identifiant de variante")
        form.addRow("ID de variante", self.variant_id)
        self.group_title = QLineEdit()
        self.group_title.setObjectName("r38-variant-group-name")
        self.group_title.setAccessibleName("Nom du groupe hérité")
        form.addRow("Nom du premier groupe", self.group_title)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        create = QPushButton("Enregistrer une nouvelle variante")
        create.clicked.connect(self.register)
        button_row.addWidget(create)
        update = QPushButton("Prévisualiser la mise à jour")
        update.clicked.connect(self.stage_update)
        button_row.addWidget(update)
        commit = QPushButton("Appliquer la mise à jour")
        commit.clicked.connect(self.apply_staged)
        button_row.addWidget(commit)
        layout.addLayout(button_row)

        self.variant_list = QListWidget()
        self.variant_list.setAccessibleName("Variantes enregistrées dans GameProject")
        self.variant_list.setMaximumHeight(105)
        self.variant_list.itemClicked.connect(
            lambda item: self._load_variant(item.text().split(" · ", 1)[0]))
        layout.addWidget(self.variant_list)

        placement = QFormLayout()
        self.mission = QComboBox()
        self.mission.setAccessibleName("Mission cible du prefab")
        placement.addRow("Carte cible", self.mission)
        coords = QHBoxLayout()
        self.anchor_x = QSpinBox()
        self.anchor_x.setRange(0, 4095)
        self.anchor_x.setAccessibleName("Colonne de placement")
        coords.addWidget(self.anchor_x)
        self.anchor_y = QSpinBox()
        self.anchor_y.setRange(0, 4095)
        self.anchor_y.setAccessibleName("Ligne de placement")
        coords.addWidget(self.anchor_y)
        placement.addRow("Position (X, Y)", coords)
        self.instance_id = QLineEdit()
        self.instance_id.setAccessibleName("Identifiant stable de l'instance")
        placement.addRow("ID d'instance", self.instance_id)
        layout.addLayout(placement)

        place = QPushButton("Placer une nouvelle instance (transaction Undo)")
        place.setObjectName("r38-place-prefab")
        place.clicked.connect(self.place)
        layout.addWidget(place)

        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setObjectName("r38-prefab-preview")
        self.diagnostics.setAccessibleName("Prévisualisation et diagnostic de variante")
        layout.addWidget(self.diagnostics, 1)

        finish = QPushButton("Fermer")
        finish.clicked.connect(self.accept)
        layout.addWidget(finish)
        self.refresh()

    def _record(self, text):
        self.diagnostics.setPlainText(text)

    def _fail(self, error):
        self._pending = None
        self._record("Opération refusée : " + str(error))
        return False

    def _catalog(self):
        snapshot = self.session.snapshot().to_dict()
        spec = snapshot["project"].get("extensions", {}).get(NAMESPACE, {})
        return spec.get("data", {"variants": [], "instances": []})

    def refresh(self):
        selected = self.variant_id.text()
        self.variant_list.clear()
        for row in self._catalog()["variants"]:
            count = sum(i["variant_id"] == row["id"] for i in
                        self._catalog()["instances"])
            self.variant_list.addItem(row["id"] + " · " + str(count) + " instances")
        self.mission.clear()
        for mission in self.session.snapshot().to_dict()["content"]["missions"]:
            self.mission.addItem(mission.get("name", mission["id"]), mission["id"])
        if selected:
            self.variant_id.setText(selected)

    def browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un prefab de groupes v1", "", "Prefab JSON (*.json)")
        if path:
            try:
                self.use_source(load_group_prefab(path))
            except (ValueError, OSError) as exc:
                self._fail(exc)

    def use_source(self, source):
        self._source = deepcopy(_validate_prefab(source))
        digest = prefab_digest(self._source)
        self._pending = None
        self.source_label.setText(self._source["name"] + " · SHA256 " + digest[:16])
        self.group_title.setText(self._source["groups"][0]["name"])
        self._record("Source validée. Les noms et identités métier restent ceux du prefab R6.")

    def _variant(self):
        if self._source is None:
            raise ValueError("Chargez d'abord un prefab de groupes R6")
        group = self._source["groups"][0]
        title = self.group_title.text().strip()
        if not title:
            raise ValueError("Le nom de groupe ne peut être vide")
        return {
            "kind": KIND, "version": VERSION,
            "id": self.variant_id.text().strip(),
            "base_sha256": prefab_digest(self._source),
            "overrides": [{"section": "groups", "id": group["id"],
                           "field": "name", "value": title}],
        }

    def _load_variant(self, variant_id):
        self.variant_id.setText(variant_id)
        row = next((r for r in self._catalog()["variants"] if r["id"] == variant_id),
                   None)
        if row is not None and self._source is not None:
            overrides = [p for p in row["overrides"] if p["section"] == "groups"
                         and p["id"] == self._source["groups"][0]["id"]
                         and p["field"] == "name"]
            if overrides:
                self.group_title.setText(overrides[0]["value"])

    def register(self):
        try:
            self._pending = None
            plan = preview_register_variant(self.session, self._source,
                                            self._variant())
            self.session.apply(plan)
            self.refresh()
            self._record("Variante enregistrée dans GameProject, "
                         "transaction Undo/Redo disponible.")
            return True
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return self._fail(exc)

    def place(self):
        try:
            self._pending = None
            plan = preview_place_variant(
                self.session, self._source, self.variant_id.text().strip(),
                self.mission.currentData(), (self.anchor_x.value(),
                                             self.anchor_y.value()),
                self.instance_id.text().strip())
            self.session.apply(plan)
            self.refresh()
            self.owner.refresh()
            self._record("Instance placée avec mapping des IDs et référence "
                         "de source. Modifications Content+GameProject atomiques.")
            return True
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return self._fail(exc)

    def stage_update(self):
        try:
            descriptor = self._variant()
            current = next(v for v in self._catalog()["variants"]
                           if v["id"] == descriptor["id"])
            plan = preview_update_variant(self.session, self._source, descriptor)
            impacted = [i["id"] for i in self._catalog()["instances"]
                        if i["variant_id"] == descriptor["id"]]
            self._pending = plan
            self._record(
                "PRÉVISUALISATION — aucune modification appliquée.\n"
                "Variante : " + descriptor["id"] + "\n"
                "Avant : " + str(current["overrides"]) + "\n"
                "Après : " + str(descriptor["overrides"]) + "\n"
                "Instances concernées : " + ", ".join(impacted) + "\n"
                "Les overrides propres aux instances sont conservés ; "
                "une modification locale non déclarée bloque le lot entier.\n"
                "Cliquez sur Appliquer la mise à jour pour confirmer.")
            return True
        except (ValueError, TypeError, KeyError, AttributeError, StopIteration) as exc:
            return self._fail(exc)

    def apply_staged(self):
        if self._pending is None:
            self._record("Aucune mise à jour prévisualisée à appliquer.")
            return False
        try:
            self.session.apply(self._pending)
            self._pending = None
            self.refresh()
            self.owner.refresh()
            self._record("Mise à jour confirmée. Une seule transaction Undo/Redo.")
            return True
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return self._fail(exc)
