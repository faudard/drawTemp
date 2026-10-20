"""R74.B/C1 opt-in Qt review of logical graphs and bounded physical R27 maps.

The graphs are not spatial R5 plans. Only the separate R74.C1 action can
prepare three physical puzzle missions. Every canonical write requires
explicit confirmation; no operation saves files on disk implicitly.
"""
from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.procgen import ProcGenError
from .r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError, DungeonSuggestion,
    compare_dungeon_suggestions,
)
from .r74_physical_dungeons import (
    prepare_physical_dungeons, apply_physical_dungeons,
)


def _spin(name, low, high, initial):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(initial)
    widget.setAccessibleName(name)
    return widget


class R74DungeonAssistDialog(QDialog):
    """One explicitly approved R34 or R27 editor transaction, no disk writes."""

    def __init__(self, session, *, parent=None, library=None):
        super().__init__(parent)
        self.setObjectName("r74-assisted-dungeon-dialog")
        self.setWindowTitle("R74 • Assistant de donjons (opt-in)")
        self.resize(1130, 760)
        self.session = session
        self.controller = AssistedDungeonController(session, library=library)
        self.proposals = ()
        self.pinned = None
        self._applied_revision = None
        self._undone_revision = None
        self.physical_plan = None

        root = QVBoxLayout(self)
        warning = QLabel(
            "Variantes locales et déterministes, sans IA distante ni écriture "
            "automatique. Les variantes ci-dessous sont des graphes R34, "
            "pas des cartes R5. Le bouton 'Préparer 3 cartes R27' ajoute "
            "une preuve physique distincte, sans IA/combat ni export certifiés. "
            "Ajuster les paramètres régénère le donjon.")
        warning.setWordWrap(True)
        warning.setObjectName("r74-scope-warning")
        root.addWidget(warning)

        form = QFormLayout()
        controls = QHBoxLayout()
        self.seed_spin = _spin("R74 seed", 0, 2147483647, 74)
        self.rooms_spin = _spin("R74 rooms", 3, 32, 8)
        self.branches_spin = _spin("R74 branches", 0, 5, 2)
        self.count_spin = _spin("R74 variant count", 1, 5, 3)
        self.encounters_spin = _spin("R74 encounters", 0, 64, 2)
        self.loot_spin = _spin("R74 loot", 0, 64, 2)
        self.reward_spin = _spin("R74 meta reward", 0, 1000, 1)
        self.locked_box = QCheckBox("Clé requise avant l'objectif")
        self.locked_box.setChecked(True)
        self.biome_box = QComboBox()
        self.biome_box.setAccessibleName("R74 biome")
        biomes = sorted({b for p in self.controller.library.get("prefabs", ())
                         for b in p.get("biomes", ())})
        self.biome_box.addItems(biomes or ["ruins"])
        for text, widget in (
            ("Seed", self.seed_spin), ("Salles", self.rooms_spin),
            ("Branches", self.branches_spin), ("Variantes", self.count_spin),
            ("Rencontres", self.encounters_spin), ("Butin", self.loot_spin),
            ("Méta-récompense", self.reward_spin), ("Biome", self.biome_box),
        ):
            form.addRow(text, widget)
        form.addRow("", self.locked_box)
        self.physical_prefix = QLineEdit("r74")
        self.physical_prefix.setObjectName("r74-physical-prefix")
        self.physical_prefix.setAccessibleName("Préfixe des trois missions R27")
        self.physical_prefix.setMaxLength(12)
        form.addRow("Préfixe R27", self.physical_prefix)
        settings = QWidget()
        settings.setLayout(form)
        controls.addWidget(settings, 1)

        variants = QVBoxLayout()
        self.variant_table = QTableWidget(0, 5)
        self.variant_table.setObjectName("r74-variant-table")
        self.variant_table.setAccessibleName("Variantes R74 validées")
        self.variant_table.setHorizontalHeaderLabels(
            ["Seed", "Salles", "Branches", "Route", "Empreinte"])
        self.variant_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.variant_table.setSelectionMode(QTableWidget.SingleSelection)
        self.variant_table.setEditTriggers(QTableWidget.NoEditTriggers)
        variants.addWidget(self.variant_table, 2)
        self.diff_report = QPlainTextEdit()
        self.diff_report.setObjectName("r74-diff-report")
        self.diff_report.setAccessibleName("Différences entre donjons logiques")
        self.diff_report.setReadOnly(True)
        variants.addWidget(self.diff_report, 1)
        right = QWidget()
        right.setLayout(variants)
        controls.addWidget(right, 3)
        root.addLayout(controls, 2)

        charts = QHBoxLayout()
        for title, attr in (("Référence de comparaison", "reference_graph"),
                            ("Variante sélectionnée", "candidate_graph")):
            group = QGroupBox(title)
            column = QVBoxLayout(group)
            view = QGraphicsView()
            view.setObjectName("r74-" + attr.replace("_", "-"))
            view.setAccessibleName(title + " (graphe logique)")
            view.setScene(QGraphicsScene(view))
            column.addWidget(view)
            charts.addWidget(group)
            setattr(self, attr, view)
        root.addLayout(charts, 3)

        self.status = QLabel("Paramétrer les contraintes puis générer un aperçu.")
        self.status.setObjectName("r74-status")
        self.status.setAccessibleName("Statut de la génération R74")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Proposer des variantes")
        self.preview_button.setObjectName("r74-preview")
        self.pin_button = QPushButton("Garder comme référence")
        self.pin_button.setObjectName("r74-pin")
        self.pin_button.setEnabled(False)
        self.reject_button = QPushButton("Rejeter les propositions")
        self.reject_button.setObjectName("r74-reject")
        self.apply_button = QPushButton("Appliquer la sélection…")
        self.apply_button.setObjectName("r74-apply")
        self.apply_button.setEnabled(False)
        self.physical_preview_button = QPushButton("Préparer 3 cartes R27")
        self.physical_preview_button.setObjectName("r74-physical-preview")
        self.physical_preview_button.setEnabled(False)
        self.physical_apply_button = QPushButton("Créer les 3 cartes…")
        self.physical_apply_button.setObjectName("r74-physical-apply")
        self.physical_apply_button.setEnabled(False)
        self.undo_button = QPushButton("Annuler l'application")
        self.undo_button.setObjectName("r74-undo")
        self.undo_button.setEnabled(False)
        self.redo_button = QPushButton("Rétablir l'application")
        self.redo_button.setObjectName("r74-redo")
        self.redo_button.setEnabled(False)
        close_button = QPushButton("Fermer")
        for widget in (self.preview_button, self.pin_button, self.reject_button,
                       self.apply_button, self.physical_preview_button,
                       self.physical_apply_button, self.undo_button, self.redo_button,
                       close_button):
            actions.addWidget(widget)
        root.addLayout(actions)

        self.preview_button.clicked.connect(self.preview_generation)
        self.pin_button.clicked.connect(self.pin_selected)
        self.reject_button.clicked.connect(self.reject_proposals)
        self.apply_button.clicked.connect(self.apply_selected)
        self.physical_preview_button.clicked.connect(self.prepare_physical_generation)
        self.physical_apply_button.clicked.connect(self.apply_physical_generation)
        self.physical_prefix.textChanged.connect(self._invalidate_physical)
        self.undo_button.clicked.connect(self.undo_application)
        self.redo_button.clicked.connect(self.redo_application)
        close_button.clicked.connect(self.close)
        self.variant_table.itemSelectionChanged.connect(self._selection_changed)
        self.rooms_spin.valueChanged.connect(self._adjust_branch_limit)
        for widget in (self.seed_spin, self.rooms_spin, self.branches_spin,
                       self.count_spin, self.encounters_spin, self.loot_spin,
                       self.reward_spin):
            widget.valueChanged.connect(self.invalidate)
        self.biome_box.currentIndexChanged.connect(self.invalidate)
        self.locked_box.toggled.connect(self.invalidate)
        self._adjust_branch_limit()

    def _adjust_branch_limit(self, *_):
        self.branches_spin.setMaximum(min(5, self.rooms_spin.value() - 3))

    def _invalidate_physical(self, *_):
        self.physical_plan = None
        self.physical_apply_button.setEnabled(False)

    def _clear(self):
        self.proposals = ()
        self.controller.invalidate()
        self._invalidate_physical()
        self.physical_preview_button.setEnabled(False)
        self.variant_table.setRowCount(0)
        self.pin_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.candidate_graph.scene().clear()
        self.diff_report.clear()
        # An explicit comparison reference is kept until the author rejects it.
        self._draw(self.reference_graph, self.pinned)

    def invalidate(self, *_):
        self._clear()
        self.status.setText("Paramètres modifiés : régénérer avant toute application.")

    def preview_generation(self):
        self._clear()
        try:
            proposals = self.controller.preview_variants(
                seed=self.seed_spin.value(), biome=self.biome_box.currentText(),
                count=self.count_spin.value(), rooms=self.rooms_spin.value(),
                branches=self.branches_spin.value(),
                locked_goal=self.locked_box.isChecked(),
                encounter_budget=self.encounters_spin.value(),
                loot_budget=self.loot_spin.value(),
                meta_reward=self.reward_spin.value(),
            )
        except (DungeonAssistError, ProcGenError, AuthoringError,
                ValueError, OSError) as exc:
            self.status.setText("Génération refusée : " + str(exc))
            return ()
        self.proposals = proposals
        self.physical_preview_button.setEnabled(len(proposals) == 3)
        self.variant_table.setRowCount(len(proposals))
        for i, proposal in enumerate(proposals):
            fields = (str(proposal.seed), str(len(proposal.layout["rooms"])),
                      str(len(proposal.layout["locks"])),
                      str(len(proposal.layout["route"])),
                      proposal.topology_digest[:12])
            for j, value in enumerate(fields):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.variant_table.setItem(i, j, item)
        self.variant_table.selectRow(0)
        self.status.setText(
            f"{len(proposals)} solution(s) logiques distinctes, vérifiées R34. "
            "L'application attend une confirmation ; aucune écriture disque.")
        return proposals

    def _selected(self):
        row = self.variant_table.currentRow()
        if row < 0 or row >= len(self.proposals):
            return None
        return self.proposals[row]

    def _selection_changed(self):
        proposal = self._selected()
        self.apply_button.setEnabled(proposal is not None)
        self.pin_button.setEnabled(proposal is not None)
        self._draw(self.candidate_graph, proposal)
        self._draw(self.reference_graph, self.pinned or (
            self.proposals[0] if self.proposals else None))
        if proposal is None:
            self.diff_report.clear()
            return
        reference = self.pinned or self.proposals[0]
        self.diff_report.setPlainText(json.dumps(
            compare_dungeon_suggestions(reference, proposal),
            ensure_ascii=False, indent=2, sort_keys=True,
        ))

    def pin_selected(self):
        proposal = self._selected()
        if proposal is None:
            return None
        self.pinned = deepcopy(proposal)
        self._selection_changed()
        self.status.setText(
            "Référence épinglée localement. Modifier seed/salles/branches/ressources "
            "puis régénérer pour comparer ; le projet reste inchangé.")
        return self.pinned

    def reject_proposals(self):
        self._clear()
        self.pinned = None
        self.reference_graph.scene().clear()
        self.status.setText("Propositions refusées. Aucun contenu ni historique modifié.")

    def _draw(self, view, proposal):
        scene = view.scene()
        scene.clear()
        if proposal is None:
            return
        rooms = proposal.layout["rooms"]
        coords = {r["id"]: (20 + (i % 4) * 160, 20 + (i // 4) * 115)
                  for i, r in enumerate(rooms)}
        for room in rooms:
            a = room["id"]
            x, y = coords[a]
            for b in room["neighbors"]:
                if b > a and b in coords:
                    xx, yy = coords[b]
                    scene.addLine(x + 46, y + 27, xx + 46, yy + 27,
                                  QPen(QColor("#9a9a9a"), 2))
        palette = {
            "entry": "#79c3a4", "goal": "#f1c46b", "exit": "#96b8e2",
            "key": "#d4a3e1", "normal": "#c4c4c4",
        }
        for room in rooms:
            x, y = coords[room["id"]]
            scene.addEllipse(x, y, 92, 54, QPen(QColor("#333333")),
                             QBrush(QColor(palette.get(room["role"], "#c4c4c4"))))
            label = scene.addSimpleText(
                str(room["id"]) + " : " + room["role"])
            label.setBrush(QBrush(QColor("#171717")))
            label.setPos(x + 5, y + 15)
        scene.setSceneRect(scene.itemsBoundingRect())

    def prepare_physical_generation(self):
        """Dry-run three actual R27 missions; the live editor remains untouched."""
        self._invalidate_physical()
        if not self.physical_preview_button.isEnabled() or len(self.proposals) != 3:
            return None
        try:
            plan = prepare_physical_dungeons(
                self.controller, self.proposals,
                prefix=self.physical_prefix.text().strip())
        except (DungeonAssistError, ProcGenError, AuthoringError,
                ValueError, OSError) as exc:
            self.status.setText("Cartes physiques refusées : " + str(exc))
            return None
        self.physical_plan = plan
        self.physical_apply_button.setEnabled(True)
        self.diff_report.setPlainText(json.dumps(
            plan.to_dict(), ensure_ascii=False, indent=2))
        self.status.setText(
            "3 missions R27 et 3 témoins clé→porte→objectif préparés dans "
            "une session isolée. Aucun fichier ni projet actif modifié ; "
            "le graphe R34 complet n'est pas instancié.")
        return plan

    def apply_physical_generation(self):
        """Separate modal consent for a single, 3-mission R1 transaction."""
        if self.physical_plan is None or not self.physical_apply_button.isEnabled():
            return None
        decision = QMessageBox.question(
            self, "Confirmer les trois missions R74",
            "Ajouter 3 cartes R27, leurs clés/portes et une campagne au projet ? "
            "Une transaction annulable, sans sauvegarde disque. "
            "La preuve exclut IA/combat et export Player.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if decision != QMessageBox.Yes:
            self.status.setText("Création physique refusée. Aucun changement.")
            return None
        plan = self.physical_plan
        self._invalidate_physical()
        try:
            transition = apply_physical_dungeons(self.controller, plan)
        except (DungeonAssistError, ProcGenError, AuthoringError,
                ValueError, OSError) as exc:
            self._clear()
            self.status.setText("Création physique bloquée : " + str(exc))
            return None
        self._applied_revision = transition.snapshot.revision
        self._undone_revision = None
        self._clear()
        self.undo_button.setEnabled(transition.snapshot.can_undo)
        self.redo_button.setEnabled(False)
        self.status.setText(
            "Trois cartes R27 créées en une transaction. "
            "Save/reload Player et certification export restent à prouver.")
        return transition

    def apply_selected(self):
        proposal = self._selected()
        if proposal is None or not self.apply_button.isEnabled():
            return None
        # In particular, the default is No; tests must explicitly approve.
        choice = QMessageBox.question(
            self, "Confirmer R74",
            "Appliquer seulement la recette logique R34 sélectionnée ? "
            "Aucun donjon physique R5 ni export Player n'est créé. "
            "Un Undo est disponible et l'enregistrement reste manuel.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            self.status.setText("Application refusée : aucun changement.")
            return None
        try:
            transition = self.controller.apply(proposal)
        except (DungeonAssistError, ProcGenError, AuthoringError,
                ValueError, OSError) as exc:
            self._clear()
            self.status.setText("Application bloquée : " + str(exc))
            return None
        self._applied_revision = transition.snapshot.revision
        self._undone_revision = None
        self._clear()
        self.undo_button.setEnabled(transition.snapshot.can_undo)
        self.redo_button.setEnabled(False)
        self.status.setText(
            f"Recette R34 appliquée à la révision {transition.snapshot.revision}. "
            "Sauvegarder explicitement dans le Studio, ou Annuler.")
        return transition

    def undo_application(self):
        if (self._applied_revision != self.session.revision
                or not self.undo_button.isEnabled()):
            self.undo_button.setEnabled(False)
            self.status.setText("Annulation refusée : historique modifié ailleurs.")
            return None
        transition = self.session.undo()
        self._applied_revision = None
        self._undone_revision = transition.snapshot.revision
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(True)
        self._clear()
        self.status.setText("Application R74 annulée dans l'historique partagé.")
        return transition

    def redo_application(self):
        if (self._undone_revision != self.session.revision
                or not self.redo_button.isEnabled()):
            self.redo_button.setEnabled(False)
            self.status.setText("Rétablissement refusé : historique modifié ailleurs.")
            return None
        transition = self.session.redo()
        self._applied_revision = transition.snapshot.revision
        self._undone_revision = None
        self.redo_button.setEnabled(False)
        self.undo_button.setEnabled(transition.snapshot.can_undo)
        self._clear()
        self.status.setText("Application R74 rétablie dans l'historique partagé.")
        return transition
