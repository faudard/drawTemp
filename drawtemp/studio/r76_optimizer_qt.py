"""R76.B1 Optimizer Studio — inspect and approve a separate derived preview.

The canonical GameProject and R1 editor history are not changed. This UI
makes no GPU, artistic golden or release certification claims.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sporebound.assets import AssetRegistry

from drawtemp.assets.optimizer import (
    OptimizerError, plan_optimization, publish_derived_assets, undo_derived_assets,
)


class OptimizerDialog(QDialog):
    """Read-only before explicit approval; undo touches only created artifacts."""

    def __init__(self, session, content_path, parent=None):
        super().__init__(parent)
        self.setObjectName("r76-optimizer-studio")
        self.setWindowTitle("R76.B — Optimizer Studio (aperçus non certifiés)")
        self.resize(1050, 680)
        self.session = session
        self.initial_revision = session.revision
        self.content_path = Path(content_path).resolve(strict=True)
        if not self.content_path.is_file() or session.snapshot().dirty:
            raise OptimizerError("Save the canonical project before opening Optimizer Studio")
        self.root = self.content_path.parent
        snapshot = session.snapshot().to_dict()
        self.registry = AssetRegistry(snapshot["project"].get("assets") or None)
        self.plan = None
        self.published = None

        layout = QVBoxLayout(self)
        warning = QLabel(
            "Prévisualisation locale de déduplication byte-identique. "
            "Aucun asset original ni sauvegarde modifié. "
            "Les aperçus ne valent pas approbation artistique, licence ou certification GPU."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.overview = QLabel()
        self.overview.setObjectName("r76-optimizer-summary")
        self.overview.setAccessibleName("Coûts et économies du projet")
        layout.addWidget(self.overview)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("r76-proposals")
        self.table.setAccessibleName("Propositions de déduplication sans perte")
        self.table.setHorizontalHeaderLabels(
            ["Fichier redondant", "Fichier canonique", "Octets", "SHA-256"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        previews = QHBoxLayout()
        self.before = QLabel("AVANT")
        self.before.setObjectName("r76-before-preview")
        self.after = QLabel("APRÈS")
        self.after.setObjectName("r76-after-preview")
        for label in (self.before, self.after):
            label.setFixedHeight(220)
            label.setMinimumWidth(280)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setAccessibleName(
                "Aperçu source" if label is self.before else "Aperçu identique réutilisé")
            previews.addWidget(label)
        layout.addLayout(previews)
        self.comparison = QLabel("Sélectionner une proposition")
        self.comparison.setWordWrap(True)
        self.comparison.setAccessibleName("Comparaison déterministe avant après")
        layout.addWidget(self.comparison)

        output_row = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setObjectName("r76-output")
        self.output.setAccessibleName("Destination du nouveau dossier dérivé")
        self.output.setPlaceholderText("Dossier neuf en dehors du projet")
        browse = QPushButton("Choisir le dossier parent…")
        browse.clicked.connect(self.choose_output)
        output_row.addWidget(self.output, 1)
        output_row.addWidget(browse)
        layout.addLayout(output_row)

        self.approve = QCheckBox(
            "J'approuve la création d'une copie dérivée non distribuable ; "
            "aucune écriture dans le projet original")
        self.approve.setObjectName("r76-explicit-approval")
        layout.addWidget(self.approve)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Recalculer l'audit")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)
        self.apply_button = QPushButton("Créer le dossier dérivé")
        self.apply_button.setObjectName("r76-approve")
        self.apply_button.clicked.connect(self.apply)
        controls.addWidget(self.apply_button)
        self.undo_button = QPushButton("Annuler le dossier dérivé créé")
        self.undo_button.setObjectName("r76-undo-derived")
        self.undo_button.clicked.connect(self.undo_derived)
        controls.addWidget(self.undo_button)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        controls.addWidget(close)
        layout.addLayout(controls)
        self.table.currentCellChanged.connect(self.show_comparison)
        self.approve.toggled.connect(self._buttons)
        self.output.textChanged.connect(self._buttons)
        self.refresh()

    def _check_revision(self):
        if self.session.revision != self.initial_revision or self.session.snapshot().dirty:
            raise OptimizerError("Studio session changed; close and reopen the optimizer")

    def _buttons(self, *_args):
        self.apply_button.setEnabled(
            self.plan is not None and bool(self.plan["proposals"])
            and self.approve.isChecked() and bool(self.output.text().strip())
            and self.published is None)
        self.undo_button.setEnabled(self.published is not None)

    def refresh(self):
        if self.published is not None:
            self.overview.setText(
                "Une copie dérivée est déjà créée. Annulez-la avant de recalculer.")
            return False
        try:
            self._check_revision()
            self.plan = plan_optimization(self.registry, self.root)
            cost = self.plan["cost"]
            self.overview.setText(
                f"Fichiers physiques : {len(self.plan['input_asset_fingerprints'])} · "
                f"Source : {cost['source_bytes']:,} o · "
                f"Copie dérivée : {cost['derived_bytes']:,} o · "
                f"Économie mesurée sur assets : {cost['bytes_saved']:,} o")
            self.table.setRowCount(len(self.plan["proposals"]))
            for row, item in enumerate(self.plan["proposals"]):
                for col, text in enumerate((
                        item["source_path"], item["canonical_path"],
                        str(item["bytes_saved_in_derived_assets"]), item["sha256"])):
                    self.table.setItem(row, col, QTableWidgetItem(text))
            if self.table.rowCount():
                self.table.selectRow(0)
                self.show_comparison(0)
            else:
                self.comparison.setText("Aucun doublon physique compatible.")
                self.before.clear()
                self.after.clear()
            self._buttons()
            return True
        except (OptimizerError, ValueError, OSError) as exc:
            self.plan = None
            self.table.setRowCount(0)
            self.overview.setText("Audit refusé : " + str(exc))
            self._buttons()
            return False

    def show_comparison(self, row, *_args):
        if self.plan is None or not 0 <= row < len(self.plan["proposals"]):
            return
        item = self.plan["proposals"][row]
        before_path = self.root / item["source_path"]
        after_path = self.root / item["canonical_path"]
        # Both paths have the same byte hash in the frozen audit. Re-validate
        # that assertion before the UI claims equivalence.
        try:
            from drawtemp.assets.optimization_audit import _file_fingerprint
            before_hash, before_size, _ = _file_fingerprint(before_path)
            after_hash, after_size, _ = _file_fingerprint(after_path)
            if (before_hash, before_size) != (after_hash, after_size) or (
                    before_hash != item["sha256"]):
                raise OptimizerError("Source changed since audit")
        except (OSError, ValueError) as exc:
            self.before.clear()
            self.after.clear()
            self.comparison.setText("Comparaison refusée : " + str(exc))
            return
        for label, path in ((self.before, before_path), (self.after, after_path)):
            image = QPixmap(str(path))
            if image.isNull():
                label.setText("Audio / PNG non décodé")
            else:
                label.setPixmap(image.scaled(
                    280, 210, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
        self.comparison.setText(
            "Octets et SHA identiques · " + item["source_path"] + " → " +
            item["canonical_path"] + " · aucun golden artistique approuvé")

    def choose_output(self):
        parent = QFileDialog.getExistingDirectory(self, "Parent de l'artefact R76")
        if parent:
            self.output.setText(str(Path(parent) / "r76b-derived-assets"))

    def apply(self):
        if self.plan is None or not self.approve.isChecked():
            self.overview.setText("Aperçu et approbation explicite requis.")
            return False
        try:
            self._check_revision()
            self.published = publish_derived_assets(
                self.registry, self.root, self.plan,
                Path(self.output.text().strip()), approved=True)
            self.overview.setText(
                "Copie atomique créée : " + self.published["directory"] +
                "\nNon distribuable : certification, droits dérivés et gameplay non prouvés.")
            self._buttons()
            return True
        except (OptimizerError, ValueError, OSError) as exc:
            self.overview.setText("Création refusée : " + str(exc))
            return False

    def undo_derived(self):
        if self.published is None:
            return False
        if QMessageBox.question(
                self, "Annuler la copie dérivée",
                "Supprimer uniquement les fichiers dérivés R76 vérifiés ? "
                "Le projet source reste intact.") != QMessageBox.StandardButton.Yes:
            return False
        try:
            undo_derived_assets(
                Path(self.published["directory"]),
                expected_receipt_sha256=self.published["receipt_sha256"])
            self.published = None
            self.approve.setChecked(False)
            self.overview.setText(
                "Copie dérivée annulée. Aucun fichier du projet original modifié.")
            self._buttons()
            return True
        except (OptimizerError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Annulation refusée", str(exc))
            return False
