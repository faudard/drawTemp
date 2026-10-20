"""R38.4 Qt read-only Creator preflight panel for the active R1 snapshot."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QVBoxLayout,
)

from drawtemp.sdk.r38_preflight import inspect_project


class PreflightDialog(QDialog):
    """Never saves, exports or modifies the authoring pair."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.session = owner.session
        self.report = None
        self.asset_root = (str(Path(owner.content_path).parent)
                           if getattr(owner, "content_path", None) else None)
        self.setObjectName("r38-project-preflight")
        self.setWindowTitle("R38.4 • Preflight du projet")
        self.resize(810, 570)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Vérification du projet courant sans sauvegarde : règles Content/"
            "GameProject, références, graphes R31, assets et droits. "
            "Ce rapport ne certifie pas une release.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.root_label = QLabel(self._root_text())
        self.root_label.setWordWrap(True)
        controls.addWidget(self.root_label, 1)
        choose = QPushButton("Dossier des assets…")
        choose.clicked.connect(self.choose_root)
        controls.addWidget(choose)
        layout.addLayout(controls)

        self.rights = QCheckBox("Exiger les preuves de droits de redistribution")
        self.rights.setObjectName("r38-preflight-rights")
        self.rights.toggled.connect(self.refresh)
        layout.addWidget(self.rights)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("r38-preflight-status")
        self.summary.setAccessibleName("Statut et périmètre du précontrôle")
        layout.addWidget(self.summary)

        self.issues = QListWidget()
        self.issues.setObjectName("r38-preflight-issues")
        self.issues.setAccessibleName("Erreurs et avertissements de validation")
        layout.addWidget(self.issues, 1)

        footer = QHBoxLayout()
        verify = QPushButton("Réanalyser le projet")
        verify.setObjectName("r38-preflight-refresh")
        verify.clicked.connect(self.refresh)
        footer.addWidget(verify)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)

        self.refresh()

    def _root_text(self):
        return ("Assets : " + self.asset_root if self.asset_root
                else "Assets : aucun dossier choisi (contrôle disque impossible)")

    def choose_root(self):
        root = QFileDialog.getExistingDirectory(
            self, "Choisir la racine des assets du projet",
            self.asset_root or "")
        if root:
            self.asset_root = root
            self.root_label.setText(self._root_text())
            self.refresh()

    def refresh(self, *_args):
        try:
            report = inspect_project(
                self.session.snapshot(), asset_root=self.asset_root,
                require_licenses=self.rights.isChecked())
        except (ValueError, TypeError, KeyError, OSError) as exc:
            self.report = None
            self.summary.setText("Preflight impossible : " + str(exc))
            self.issues.clear()
            return
        self.report = report
        self.issues.clear()
        for issue in report["issues"]:
            label = ("ERREUR" if issue["severity"] == "error" else "AVERTISSEMENT")
            item = label + " [" + issue["code"] + "] " + issue["message"]
            self.issues.addItem(item)
            self.issues.item(self.issues.count() - 1).setToolTip(issue["path"])
        revision = report["revision"]
        flags = [
            "règles : " + ("OK" if report["passed"] else "ÉCHEC"),
            "prévisualisation : " +
            ("possible" if report["ready_for_preview"] else "bloquée"),
            "fichiers : " +
            ("vérifiés" if report["asset_integrity_verified"] else "non vérifiés"),
            "droits : " +
            ("attestés techniquement" if report["rights_verified"] else "non attestés"),
            "erreurs : " + str(len(report["errors"])),
            "avertissements : " + str(len(report["warnings"])),
        ]
        status = "Révision " + str(revision) + " · " + " · ".join(flags)
        if not report["complete"]:
            status += "\nAudit incomplet : le résultat ne peut pas être déclaré conforme."
        self.summary.setText(status + "\nAucune certification Player/release délivrée.")
