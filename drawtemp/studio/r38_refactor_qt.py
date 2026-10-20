"""R38.3 Qt review/apply for mission-local typed identity refactoring."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from drawtemp.sdk.r38_refactor import (
    apply_rename_identity, preview_rename_identity,
)


class RefactorDialog(QDialog):
    """No writes before explicit apply; uses the originating R1 revision."""

    def __init__(self, owner, initial=None):
        super().__init__(owner)
        self.owner = owner
        self.session = owner.session
        self.review = None
        self.setObjectName("r38-typed-refactor")
        self.setWindowTitle("R38.3 • Renommer les références typées")
        self.resize(760, 580)
        layout = QVBoxLayout(self)
        explainer = QLabel(
            "Renommage transactionnel : objets et acteurs d'une mission. "
            "Les événements R9, graphes R31 et instances de prefab liées "
            "sont vérifiés et mis à jour sans modifier les autres missions.")
        explainer.setWordWrap(True)
        layout.addWidget(explainer)

        form = QFormLayout()
        self.family = QComboBox()
        self.family.setObjectName("r38-refactor-family")
        self.family.addItem("Objets", "objects")
        self.family.addItem("Personnages", "actors")
        form.addRow("Famille", self.family)
        self.mission = QComboBox()
        self.mission.setObjectName("r38-refactor-mission")
        form.addRow("Mission", self.mission)
        self.old_id = QComboBox()
        self.old_id.setObjectName("r38-refactor-original")
        self.old_id.setAccessibleName("Identifiant à renommer")
        form.addRow("Ressource", self.old_id)
        self.new_id = QLineEdit()
        self.new_id.setObjectName("r38-refactor-new")
        self.new_id.setAccessibleName("Nouvel identifiant")
        self.new_id.setPlaceholderText("nouvel_identifiant")
        form.addRow("Nouvel ID", self.new_id)
        layout.addLayout(form)

        self.impact = QPlainTextEdit()
        self.impact.setObjectName("r38-refactor-impact")
        self.impact.setReadOnly(True)
        self.impact.setAccessibleName("Prévisualisation des références modifiées")
        layout.addWidget(self.impact, 1)

        controls = QHBoxLayout()
        stage = QPushButton("Prévisualiser les impacts")
        stage.setObjectName("r38-refactor-preview")
        stage.clicked.connect(self.preview)
        controls.addWidget(stage)
        commit = QPushButton("Appliquer en une transaction")
        commit.setObjectName("r38-refactor-commit")
        commit.clicked.connect(self.apply)
        controls.addWidget(commit)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        controls.addWidget(close)
        layout.addLayout(controls)

        self.family.currentIndexChanged.connect(self._refresh_sources)
        self.mission.currentIndexChanged.connect(self._refresh_sources)
        self.old_id.currentIndexChanged.connect(self._invalidate)
        self.new_id.textChanged.connect(self._invalidate)
        self._refresh_missions()
        if isinstance(initial, (tuple, list)) and len(initial) == 3:
            family, mid, identifier = initial
            family_at = self.family.findData(family)
            mission_at = self.mission.findData(mid)
            if family_at >= 0 and mission_at >= 0:
                self.family.setCurrentIndex(family_at)
                self.mission.setCurrentIndex(mission_at)
                original_at = self.old_id.findData(identifier)
                if original_at >= 0:
                    self.old_id.setCurrentIndex(original_at)
                    self.new_id.setFocus()

    def _invalidate(self, *_args):
        self.review = None

    def _refresh_missions(self):
        self.mission.clear()
        for row in self.session.snapshot().to_dict()["content"]["missions"]:
            self.mission.addItem(row.get("name", row["id"]), row["id"])
        self._refresh_sources()

    def _refresh_sources(self, *_args):
        self._invalidate()
        self.old_id.clear()
        mid, family = self.mission.currentData(), self.family.currentData()
        for mission in self.session.snapshot().to_dict()["content"]["missions"]:
            if mission["id"] != mid:
                continue
            field = "objects" if family == "objects" else "units"
            for item in mission.get(field, ()):
                self.old_id.addItem(
                    item.get("name", item["id"]) + " · " + item["id"], item["id"])

    def preview(self):
        try:
            review = preview_rename_identity(
                self.session, self.family.currentData(),
                self.mission.currentData(), self.old_id.currentData(),
                self.new_id.text().strip())
            self.review = review
            lines = [
                "APERÇU — aucun changement appliqué",
                "Mission : " + review.mission_id,
                "Ressource : " + review.family + " / " + review.old_id +
                " → " + review.new_id,
                "Chemins concernés : " + str(review.change_count),
                "",
            ]
            lines += [
                change.path + "\n  " + change.before + " → " + change.after
                for change in review.changes[:150]
            ]
            if review.change_count > 150:
                lines.append("… " + str(review.change_count - 150) +
                             " chemins supplémentaires")
            lines.append("")
            lines.append("Appliquer confirme un seul Undo/Redo. Un aperçu "
                         "périmé ou une référence inconnue est refusé.")
            self.impact.setPlainText("\n".join(lines))
            return True
        except (ValueError, TypeError, KeyError) as exc:
            self.review = None
            self.impact.setPlainText("Prévisualisation refusée : " + str(exc))
            return False

    def apply(self):
        if self.review is None:
            self.impact.setPlainText("Prévisualisez les impacts avant application.")
            return False
        review = self.review
        try:
            apply_rename_identity(self.session, review)
            self.review = None
            self._refresh_missions()
            self.owner.refresh()
            self.impact.setPlainText(
                "Renommage appliqué : " + str(review.change_count) +
                " chemins suivis, une transaction Undo/Redo.")
            return True
        except (ValueError, TypeError, KeyError) as exc:
            self.review = None
            self.impact.setPlainText("Application refusée : " + str(exc))
            return False
