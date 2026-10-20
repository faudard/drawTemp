"""R58.B1: native Qt package audit, explicitly pinned install and safe removal.

UI/controller only; canonical R24.C install and R58.B1 removal own all writes.
No network, third-party code execution, silent license grant or automatic save.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from drawtemp.assets.packs import ResourcePackError, install_pack
from drawtemp.assets.package_ecosystem import (
    PackagePlanError, plan_package_install,
)
from drawtemp.studio.package_manager import (
    PackageManagerError, installed_package_usage,
    preview_package_removal, apply_package_removal,
)


class PackageManagerDialog(QDialog):
    """Uses the caller's AuthoringSession; never opens a second project."""

    def __init__(self, session, *, content_path=None, parent=None):
        super().__init__(parent)
        self.session = session
        path = Path(content_path) if content_path is not None else None
        self.project_root = path.parent if path and path.is_file() else None
        self.reports = ()
        self.setObjectName("r58-package-manager")
        self.setWindowTitle("Packages de ressources — R58")
        self.resize(830, 590)

        layout = QVBoxLayout(self)
        self.notice = QLabel(
            "Archives locales R24.C uniquement. Installation avec SHA-256 externe ; "
            "licences/signatures non certifiées. Les retraits conservent les fichiers "
            "pour permettre Annuler/Rétablir."
        )
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.status = QLabel()
        self.status.setObjectName("r58-package-status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("r58-package-table")
        self.table.setAccessibleName("Packages installés")
        self.table.setHorizontalHeaderLabels(["Package", "Version", "Fichiers", "État"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemSelectionChanged.connect(self._select)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setObjectName("r58-package-details")
        self.details.setAccessibleName("Prévisualisation des références et des droits")
        layout.addWidget(self.details)

        actions = QHBoxLayout()
        self.install_button = QPushButton("Installer un pack vérifié…")
        self.install_button.setObjectName("r58-install")
        self.install_button.clicked.connect(self.install_selected)
        actions.addWidget(self.install_button)
        self.remove_button = QPushButton("Retirer les références…")
        self.remove_button.setObjectName("r58-remove")
        self.remove_button.clicked.connect(self.remove_selected)
        actions.addWidget(self.remove_button)
        refresh_button = QPushButton("Actualiser")
        refresh_button.clicked.connect(self.refresh)
        actions.addWidget(refresh_button)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        self.reports = ()
        self.details.clear()
        self.remove_button.setEnabled(False)
        self.install_button.setEnabled(self.project_root is not None)
        if self.project_root is None:
            self.status.setText("Enregistrez le projet avant de gérer les packages.")
            return
        try:
            self.reports = installed_package_usage(self.session, self.project_root)
        except (PackageManagerError, ResourcePackError, ValueError, OSError) as exc:
            self.status.setText("Audit refusé : " + str(exc))
            self.install_button.setEnabled(False)
            return
        self.status.setText(
            str(len(self.reports)) + " package(s) • aucune opération automatique"
        )
        self.table.setRowCount(len(self.reports))
        for index, report in enumerate(self.reports):
            values = (
                report["id"], report["version"], str(len(report["files"])),
                "Retirable" if report["removable"] else "Utilisé / bloqué",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, report["id"])
                self.table.setItem(index, column, cell)
        if self.reports:
            self.table.selectRow(0)
            self._select()

    def _selected_report(self):
        row = self.table.currentRow()
        return self.reports[row] if 0 <= row < len(self.reports) else None

    def _select(self):
        report = self._selected_report()
        self.remove_button.setEnabled(bool(report and report["removable"]))
        if report is None:
            self.details.clear()
            return
        self.details.setPlainText(json.dumps({
            "id": report["id"], "version": report["version"],
            "asset_ids": report["asset_ids"], "files": report["files"],
            "used_by": report["used_by"],
            "blocked": not report["removable"],
            "on_remove": "Les fichiers physiques sont conservés pour Undo.",
            "rights_verified": False,
        }, ensure_ascii=False, indent=2, sort_keys=True))

    def _error(self, error):
        self.status.setText(str(error))
        QMessageBox.warning(self, "Package refusé", str(error))

    def install_selected(self):
        if self.project_root is None:
            return
        archive, _ = QFileDialog.getOpenFileName(
            self, "Choisir une archive R24.C", "",
            "Resource packs (*.rpack *.zip);;Archives (*.zip)")
        if not archive:
            return
        supplied, ok = QInputDialog.getText(
            self, "Empreinte indépendante",
            "SHA-256 de confiance (64 caractères hexadécimaux) :")
        if not ok or not supplied.strip():
            return
        try:
            initial_revision = self.session.revision
            from drawtemp.assets.packs import inspect_pack
            inspected = inspect_pack(archive)
            plan = plan_package_install(
                [archive], project_root=self.project_root,
                project=self.session.snapshot().to_dict()["project"],
                expected_sha256={inspected.manifest["id"]: supplied.strip()},
            )
            report = plan.to_dict()
            message = (
                "Package : " + report["packages"][0]["id"] + "\n" +
                "Version : " + report["packages"][0]["version"] + "\n" +
                "Fichiers : " + str(len(inspected.manifest["files"])) + "\n" +
                "SHA-256 : " + inspected.sha256 + "\n\n" +
                "Signatures et droits non certifiés. Les ressources seront "
                "ajoutées au Studio, sans sauvegarde automatique.\n\n"
                "Confirmer l'installation ?"
            )
            yes = QMessageBox.question(
                self, "Prévisualisation d'installation", message,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if yes != QMessageBox.Yes:
                return
            # R24.C checks fresh bytes, pinned dependency receipts, editor
            # revision, target collisions and native AssetRegistry again.
            install_pack(plan.packages[0].preview, self.session, self.project_root,
                         expected_revision=initial_revision)
            self.refresh()
        except (PackagePlanError, PackageManagerError, ResourcePackError,
                ValueError, OSError) as exc:
            self._error(exc)

    def remove_selected(self):
        report = self._selected_report()
        if report is None or self.project_root is None:
            return
        try:
            plan = preview_package_removal(
                self.session, self.project_root, report["id"],
                expected_revision=self.session.revision)
            message = (
                "Retirer " + plan.package_id + " (" + plan.version + ") du projet ?\n\n"
                + str(len(plan.asset_ids)) + " entrées du registre seront retirées.\n"
                + str(len(plan.files_retained)) +
                " fichiers resteront sur disque pour restaurer l'historique.\n\n"
                "Annuler/Rétablir restent possibles dans le Studio. "
                "La sauvegarde reste manuelle."
            )
            answer = QMessageBox.question(
                self, "Prévisualisation du retrait", message,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            apply_package_removal(plan, self.session, self.project_root)
            self.refresh()
        except (PackageManagerError, ResourcePackError, ValueError, OSError) as exc:
            self._error(exc)
