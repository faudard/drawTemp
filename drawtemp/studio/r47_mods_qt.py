"""R47.B — host-owned Qt inspector for inert declarative mods.

No third-party callback is connected to a QWidget. Only the Studio can
choose files, consent to permissions and apply canonical authoring changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.modding import ModError, read_mod_manifest


class ModManagerDialog(QDialog):
    """One session-only inspector. Never persists grants or runs plugin code."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.registry = owner.mods
        self.setObjectName("r47-mod-manager")
        self.setWindowTitle("R47 • SDK et modules déclaratifs")
        self.resize(760, 550)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Extensions déclaratives sans code exécutable. "
            "Les droits d'assets doivent être vérifiés avant toute publication."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.PlainText)
        root.addWidget(intro)

        self.items = QListWidget()
        self.items.setObjectName("r47-mod-list")
        self.items.setAccessibleName("Modules déclaratifs installés")
        self.items.currentRowChanged.connect(self._update_details)
        root.addWidget(self.items)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setObjectName("r47-mod-details")
        self.details.setAccessibleName(
            "Inspecteur des versions, dépendances, permissions et provenance"
        )
        root.addWidget(self.details)

        actions = QHBoxLayout()
        self.install_button = QPushButton("Importer…")
        self.enable_button = QPushButton("Autoriser / activer")
        self.disable_button = QPushButton("Désactiver")
        self.apply_button = QPushButton("Prévisualiser / appliquer")
        self.remove_button = QPushButton("Retirer")
        for button in (self.install_button, self.enable_button, self.disable_button,
                       self.apply_button, self.remove_button):
            actions.addWidget(button)
        root.addLayout(actions)
        self.install_button.clicked.connect(self._import_clicked)
        self.enable_button.clicked.connect(self._enable_clicked)
        self.disable_button.clicked.connect(self._disable_clicked)
        self.apply_button.clicked.connect(self._apply_clicked)
        self.remove_button.clicked.connect(self._remove_clicked)

        self.notice = QLabel("")
        self.notice.setTextFormat(Qt.PlainText)
        self.notice.setWordWrap(True)
        self.notice.setAccessibleName("Statut des modules déclaratifs")
        root.addWidget(self.notice)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        root.addWidget(close)
        self.refresh()

    def _selected(self):
        item = self.items.currentItem()
        return item.data(Qt.UserRole) if item else None

    def refresh(self, preferred=None):
        selected = preferred if preferred is not None else self._selected()
        self.items.blockSignals(True)
        self.items.clear()
        selected_row = -1
        for state in self.registry.statuses():
            suffix = "actif" if state["enabled"] else "inactif"
            self.items.addItem(
                "{}  •  {}  •  {}".format(state["id"], state["version"], suffix)
            )
            row = self.items.count() - 1
            self.items.item(row).setData(Qt.UserRole, state["id"])
            if state["id"] == selected:
                selected_row = row
        self.items.blockSignals(False)
        if selected_row < 0 and self.items.count():
            selected_row = 0
        if selected_row >= 0:
            self.items.setCurrentRow(selected_row)
        self._update_details()
        return selected_row

    def _update_details(self, _row=None):
        mod_id = self._selected()
        active = mod_id is not None
        for button in (self.enable_button, self.disable_button, self.apply_button,
                       self.remove_button):
            button.setEnabled(active)
        if not active:
            self.details.setPlainText("Aucun module installé.")
            return
        status = self.registry.status(mod_id)
        doc = self.registry.manifest(mod_id)
        diff = sorted(set(status["required_permissions"]) - set(status["grants"]))
        self.details.setPlainText(
            "Identifiant : {}\nVersion : {}\nNamespace : {}\n"
            "SHA-256 du manifeste : {}\n\n"
            "Permissions requises : {}\nPermissions accordées : {}\n"
            "Permissions non accordées : {}\n\n"
            "Dépendances : {}\nPacks vérifiés à l'installation : {}\n\n"
            "Licence déclarée : {}\nOrigine : {}\nPreuve déclarée : {}\n"
            "Redistribution déclarée : {}\nDroits légalement validés : NON\n"
            "Exécution de code : NON\n"
            .format(
                status["id"], status["version"], status["namespace"],
                status["manifest_sha256"],
                ", ".join(status["required_permissions"]) or "(aucune)",
                ", ".join(status["grants"]) or "(aucune)",
                ", ".join(diff) or "(aucune)",
                json.dumps(doc["dependencies"], ensure_ascii=False),
                json.dumps(doc["resources"], ensure_ascii=False),
                doc["rights"]["license"], doc["rights"]["origin"],
                doc["rights"]["evidence"], doc["rights"]["redistributable"],
            )
        )
        self.enable_button.setEnabled(not status["enabled"])
        self.disable_button.setEnabled(status["enabled"])
        self.apply_button.setEnabled(
            status["enabled"] and
            "project.extensions.write" in status["grants"] and
            doc["extension"] is not None
        )

    def _confirm(self, title, message):
        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Question)
        prompt.setWindowTitle(title)
        prompt.setTextFormat(Qt.PlainText)
        prompt.setText(message)
        prompt.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        prompt.setDefaultButton(QMessageBox.No)
        return prompt.exec() == QMessageBox.Yes

    def _error(self, exc):
        reason = getattr(exc, "code", "error")
        message = "{} : {}".format(reason, exc)
        self.notice.setText(message)
        self.owner.problems.addItem("R47 : " + message)
        box = QMessageBox(self)
        box.setTextFormat(Qt.PlainText)
        box.setWindowTitle("R47 • Opération refusée")
        box.setIcon(QMessageBox.Warning)
        box.setText(message)
        box.exec()

    def install_descriptor(self, manifest, resource_paths=None):
        """Host-owned installation only: metadata starts disabled, no consent."""
        state = self.registry.install(manifest, resource_paths=resource_paths)
        self.notice.setText("Module vérifié et installé, permissions non accordées.")
        self.refresh(state["id"])
        return state

    def _import_clicked(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "Choisir un manifeste R47 (JSON)", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            manifest = read_mod_manifest(path)
            mapping = {}
            # Files are selected by the human, never resolved from manifest paths.
            for resource in manifest["resources"]:
                file_path, _filter = QFileDialog.getOpenFileName(
                    self,
                    "Pack ZIP requis : {} ({})".format(resource["id"], resource["version"]),
                    str(Path(path).parent), "ZIP (*.zip)"
                )
                if not file_path:
                    self.notice.setText("Import annulé : pack non sélectionné.")
                    return
                mapping[resource["id"]] = Path(file_path)
            self.install_descriptor(manifest, mapping)
        except (ModError, OSError, ValueError) as exc:
            self._error(exc)

    def _enable_clicked(self):
        mod_id = self._selected()
        if mod_id is None:
            return
        try:
            doc = self.registry.manifest(mod_id)
            permissions = doc["permissions"]
            message = (
                "Module : {}\nVersion : {}\nNamespace : {}\n\n"
                "Permissions actuellement accordées : {}\n"
                "Nouvelles permissions demandées : {}\n\n"
                "Origine déclarée : {}\nLicence : {}\n\n"
                "Autoriser explicitement ces capacités pour CETTE session Studio ?\n"
                "Aucune autorisation ne sera sauvegardée."
            ).format(
                doc["id"], doc["version"], doc["namespace"],
                ", ".join(self.registry.status(mod_id)["grants"]) or "(aucune)",
                ", ".join(permissions) or "(aucune)",
                doc["rights"]["origin"], doc["rights"]["license"]
            )
            if not self._confirm("Autorisation R47 • refus par défaut", message):
                self.notice.setText("Autorisation refusée ; le mod reste désactivé.")
                return
            self.registry.enable(mod_id, grants=permissions)
            self.notice.setText("Permissions accordées pour cette session uniquement.")
            self.refresh(mod_id)
        except (ModError, ValueError) as exc:
            self._error(exc)

    def _disable_clicked(self):
        mod_id = self._selected()
        if mod_id is None:
            return
        try:
            self.registry.disable(mod_id)
            self.notice.setText("Permissions révoquées : " + mod_id)
            self.refresh(mod_id)
        except ModError as exc:
            self._error(exc)

    def _apply_clicked(self):
        mod_id = self._selected()
        if mod_id is None:
            return
        try:
            revision = self.owner.session.revision
            # Canonical preview must validate the entire Content/GameProject pair.
            self.registry.preview_extension(mod_id, self.owner.session)
            doc = self.registry.manifest(mod_id)
            message = (
                "Révision du projet : {}\nNamespace : {}\n"
                "Données proposées (aucun autre namespace modifié) :\n\n{}\n\n"
                "Appliquer via AuthoringSession avec Undo/Redo ?"
            ).format(
                revision, doc["namespace"],
                json.dumps(doc["extension"], ensure_ascii=False, indent=2)
            )
            if not self._confirm("Prévisualisation transactionnelle R47", message):
                self.notice.setText("Prévisualisation annulée, projet inchangé.")
                return
            self.registry.apply_extension(
                mod_id, self.owner.session, expected_revision=revision
            )
            self.owner.refresh()
            self.notice.setText("Extension appliquée, annulation possible via Ctrl+Z.")
            self.refresh(mod_id)
        except (ModError, AuthoringError, ValueError) as exc:
            self._error(exc)

    def _remove_clicked(self):
        mod_id = self._selected()
        if mod_id is None:
            return
        if not self._confirm(
            "Retrait non destructif R47",
            "Retirer {} de cette session ?\n\n"
            "Aucune donnée, ressource ni fichier n'est supprimé.\n"
            "Le retrait sera refusé en présence de dépendances ou de données actives."
            .format(mod_id)
        ):
            return
        try:
            self.registry.uninstall(mod_id, project=self.owner.session.snapshot())
            self.notice.setText("Mod retiré sans suppression de données : " + mod_id)
            self.refresh()
        except (ModError, ValueError) as exc:
            self._error(exc)
