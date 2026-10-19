"""R30.C — Qt Widgets creator packs and semantic conflict review.

Pure-python controllers own all validation and transactions. This dialog does
not maintain a second Content/GameProject or write into the active game folder.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView,
)

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r30_creator_review import (
    MergeReviewController, PackReviewController,
)


def _short(value):
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return rendered if len(rendered) <= 140 else rendered[:137] + "..."


def _item(value, *, readonly=True):
    item = QTableWidgetItem(str(value))
    if readonly:
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    return item


def _default_name(path):
    name = re.sub(r"[^a-z0-9_-]", "-", Path(path).stem.lower()).strip("-")
    if not name or not name[0].isalpha():
        name = "asset-" + name
    return name[:64]


class R30CreatorDialog(QDialog):
    """Modal project-safe viewer: packs create new copies; merges stage Undo."""

    def __init__(self, session: AuthoringSession, *, content_path=None, parent=None):
        super().__init__(parent)
        self.setObjectName("r30-creator-dialog")
        self.setWindowTitle("DrawTemp Creator — Packs & révision sémantique (R30.C)")
        self.resize(1080, 720)
        self.session = session
        self.content_path = Path(content_path) if content_path else None
        self.pack_controller = (PackReviewController(self.content_path)
                                if self.content_path else None)
        self.merge_controller = MergeReviewController(self.session)
        self._pack_populating = False
        self._merge_choices = {}
        root = QVBoxLayout(self)
        info = QLabel("Pack : publication dans une NOUVELLE copie uniquement. "
                      "Fusion : session Studio partagée, enregistrement manuel.")
        info.setWordWrap(True)
        root.addWidget(info)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._build_pack_tab()
        self._build_merge_tab()
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.reject)
        root.addWidget(close_button)

    def _build_pack_tab(self):
        panel = QWidget()
        self.tabs.addTab(panel, "Packs de ressources")
        layout = QVBoxLayout(panel)
        row = QHBoxLayout()
        self.pack_path = QLineEdit()
        self.pack_path.setReadOnly(True)
        self.pack_path.setAccessibleName("Chemin du pack examiné")
        row.addWidget(self.pack_path)
        choose = QPushButton("Ouvrir pack ZIP…")
        choose.clicked.connect(self._choose_pack)
        row.addWidget(choose)
        layout.addLayout(row)
        self.pack_help = QLabel(
            "Les licences sont déclaratives et NON approuvées. "
            "Seuls les PNG et WAV/OGG peuvent être sélectionnés ; "
            "le projet source restera intact.")
        self.pack_help.setWordWrap(True)
        layout.addWidget(self.pack_help)
        self.pack_table = QTableWidget(0, 6)
        self.pack_table.setHorizontalHeaderLabels(
            ("Importer", "Ressource", "Type", "Identifiant local", "Licence", "Origine"))
        self.pack_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pack_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pack_table.setAccessibleName("Ressources disponibles dans le pack")
        self.pack_table.itemChanged.connect(self._invalidate_pack)
        layout.addWidget(self.pack_table)
        actions = QHBoxLayout()
        self.pack_preview_button = QPushButton("Prévisualiser la sélection")
        self.pack_preview_button.setEnabled(False)
        self.pack_preview_button.clicked.connect(self.preview_pack)
        actions.addWidget(self.pack_preview_button)
        self.pack_publish_button = QPushButton("Créer une copie avec les ressources…")
        self.pack_publish_button.setEnabled(False)
        self.pack_publish_button.clicked.connect(self._publish_dialog)
        actions.addWidget(self.pack_publish_button)
        layout.addLayout(actions)
        self.pack_status = QLabel("Ouvrir un pack pour vérifier les ressources.")
        self.pack_status.setWordWrap(True)
        self.pack_status.setAccessibleName("Diagnostics de l'import pack")
        layout.addWidget(self.pack_status)
        if self.pack_controller is None:
            choose.setEnabled(False)
            self.pack_status.setText("Enregistrez d'abord le projet Content/GameProject.")

    def _invalidate_pack(self, *_):
        if self._pack_populating:
            return
        if self.pack_controller:
            self.pack_controller.invalidate()
        self.pack_publish_button.setEnabled(False)
        self.pack_status.setText("Sélection modifiée — nouvelle prévisualisation requise.")

    def _choose_pack(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un pack de ressources", "",
            "Pack ZIP (*.zip);;Tous les fichiers (*)")
        if path:
            self.load_pack(path)

    def load_pack(self, path):
        self._invalidate_pack()
        self.pack_preview_button.setEnabled(False)
        self.pack_table.setRowCount(0)
        self.pack_path.setText("")
        try:
            rows = self.pack_controller.inspect(path)
        except (ValueError, OSError) as exc:
            self._error("Pack invalide", exc, self.pack_status)
            return False
        self._pack_populating = True
        try:
            self.pack_path.setText(str(path))
            self.pack_table.setRowCount(len(rows))
            for index, resource in enumerate(rows):
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                check.setCheckState(Qt.Unchecked)
                if not resource.kinds:
                    check.setFlags(Qt.NoItemFlags)
                self.pack_table.setItem(index, 0, check)
                self.pack_table.setItem(index, 1, _item(resource.path))
                types = QComboBox()
                types.addItems(resource.kinds)
                types.setEnabled(bool(resource.kinds))
                types.setAccessibleName("Type : " + resource.path)
                types.currentIndexChanged.connect(self._invalidate_pack)
                self.pack_table.setCellWidget(index, 2, types)
                name = QLineEdit(_default_name(resource.path))
                name.setMaxLength(64)
                name.setEnabled(bool(resource.kinds))
                name.setAccessibleName("Identifiant local : " + resource.path)
                name.textChanged.connect(self._invalidate_pack)
                self.pack_table.setCellWidget(index, 3, name)
                license_item = _item(resource.license)
                license_item.setToolTip("Licence déclarée ; droits NON vérifiés")
                self.pack_table.setItem(index, 4, license_item)
                origin = _item(resource.origin)
                origin.setToolTip(resource.origin)
                self.pack_table.setItem(index, 5, origin)
        finally:
            self._pack_populating = False
        self.pack_preview_button.setEnabled(any(row.kinds for row in rows))
        self.pack_status.setText(
            f"{len(rows)} fichiers contrôlés. Sélectionnez les ressources à importer.")
        return True

    def _selected_resources(self):
        choices = []
        for index in range(self.pack_table.rowCount()):
            checkbox = self.pack_table.item(index, 0)
            if checkbox and checkbox.flags() & Qt.ItemIsEnabled and checkbox.checkState() == Qt.Checked:
                choices.append({
                    "path": self.pack_table.item(index, 1).text(),
                    "kind": self.pack_table.cellWidget(index, 2).currentText(),
                    "name": self.pack_table.cellWidget(index, 3).text(),
                })
        return choices

    def preview_pack(self):
        self.pack_publish_button.setEnabled(False)
        try:
            preview = self.pack_controller.preview(self._selected_resources())
        except (ValueError, OSError) as exc:
            self._error("Prévisualisation refusée", exc, self.pack_status)
            return None
        self.pack_publish_button.setEnabled(True)
        unsaved = (" ATTENTION : les modifications non enregistrées dans le "
                   "Studio ne seront pas intégrées à la copie."
                   if self.session.snapshot().dirty else "")
        self.pack_status.setText(
            f"{preview.pack_id} {preview.pack_version} : "
            f"{len(preview.selections)} ressource(s) validée(s). "
            "Droits de publication NON vérifiés. Destination = nouveau projet." + unsaved)
        return preview

    def _publish_dialog(self):
        if not self.pack_publish_button.isEnabled():
            return
        target, ok = QInputDialog.getText(
            self, "Nouvelle copie du projet",
            "Répertoire inexistant (le projet original ne sera pas remplacé) :")
        if not ok or not target.strip():
            return
        confirm = QMessageBox.question(
            self, "Confirmer la copie",
            "Créer une NOUVELLE copie du jeu avec les ressources sélectionnées ?\n"
            "Aucune autorisation de redistribution n'est acquise.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.publish_pack(target.strip())

    def publish_pack(self, destination):
        # Also disabled after ANY selection change or failed preflight.
        if not self.pack_publish_button.isEnabled():
            return None
        try:
            output = self.pack_controller.publish(destination)
        except (ValueError, OSError) as exc:
            self.pack_publish_button.setEnabled(False)
            self._error("Import refusé", exc, self.pack_status)
            return None
        self.pack_publish_button.setEnabled(False)
        self.pack_status.setText(
            f"Copie créée : {output}. Droits toujours non vérifiés ; "
            "projet Studio original conservé.")
        return output

    def _build_merge_tab(self):
        panel = QWidget()
        self.tabs.addTab(panel, "Diff & conflits")
        layout = QVBoxLayout(panel)
        intro = QLabel(
            "Choisissez BASE commune et version ENTRANTE (deux paires Content/"
            "GameProject existantes). La version LOCALE est la session active. "
            "Aucune résolution automatique de conflit.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.base_path = QLineEdit()
        self.base_path.setReadOnly(True)
        self.base_path.setAccessibleName("Chemin de la version de base")
        self.incoming_path = QLineEdit()
        self.incoming_path.setReadOnly(True)
        self.incoming_path.setAccessibleName("Chemin du projet entrant")
        for title, field, callback in (
            ("Base", self.base_path, self._choose_base),
            ("Entrant", self.incoming_path, self._choose_incoming),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            row.addWidget(field)
            button = QPushButton("Parcourir…")
            button.clicked.connect(callback)
            row.addWidget(button)
            layout.addLayout(row)
        self.merge_table = QTableWidget(0, 6)
        self.merge_table.setHorizontalHeaderLabels(
            ("Source", "Chemin", "Avant", "Local", "Entrant", "Décision"))
        self.merge_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.merge_table.setAccessibleName("Changements et conflits sémantiques")
        layout.addWidget(self.merge_table)
        actions = QHBoxLayout()
        self.merge_compare_button = QPushButton("Comparer les versions")
        self.merge_compare_button.clicked.connect(self._compare)
        actions.addWidget(self.merge_compare_button)
        self.merge_apply_button = QPushButton("Appliquer dans la session…")
        self.merge_apply_button.setEnabled(False)
        self.merge_apply_button.clicked.connect(self._apply_merge_dialog)
        actions.addWidget(self.merge_apply_button)
        layout.addLayout(actions)
        self.merge_status = QLabel("Sélectionnez les paires de documents à comparer.")
        self.merge_status.setWordWrap(True)
        self.merge_status.setAccessibleName("Diagnostics de revue des conflits")
        layout.addWidget(self.merge_status)

    def _invalidate_merge(self):
        self.merge_controller.invalidate()
        self.merge_table.setRowCount(0)
        self._merge_choices.clear()
        self.merge_apply_button.setEnabled(False)
        self.merge_status.setText("Les sources ont changé : recommencez la comparaison.")

    def _choose_base(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Content de base", "", "Content JSON (*.json)")
        if path:
            self._invalidate_merge()
            self.base_path.setText(path)

    def _choose_incoming(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Content entrant", "", "Content JSON (*.json)")
        if path:
            self._invalidate_merge()
            self.incoming_path.setText(path)

    def _compare(self):
        return self.compare_paths(self.base_path.text(), self.incoming_path.text())

    def compare_paths(self, base_path, incoming_path):
        self._invalidate_merge()
        self.base_path.setText(str(base_path))
        self.incoming_path.setText(str(incoming_path))
        try:
            preview = self.merge_controller.compare(base_path, incoming_path)
        except (ValueError, OSError) as exc:
            self._error("Comparaison impossible", exc, self.merge_status)
            return None
        self._merge_choices = {}
        changes = [("Local", entry) for entry in preview.local_changes]
        changes += [("Entrant", entry) for entry in preview.incoming_changes]
        conflicts = list(preview.conflicts)
        self.merge_table.setRowCount(len(changes) + len(conflicts))
        for row, (source, change) in enumerate(changes):
            target_local = source == "Local"
            values = (source, change.path, _short(change.before),
                      _short(change.after) if target_local else "",
                      "" if target_local else _short(change.after), "")
            for column, value in enumerate(values):
                self.merge_table.setItem(row, column, _item(value))
        for offset, conflict in enumerate(conflicts):
            row = len(changes) + offset
            values = ("Conflit", conflict.path, _short(conflict.base),
                      _short(conflict.local), _short(conflict.incoming))
            for column, value in enumerate(values):
                self.merge_table.setItem(row, column, _item(value))
            select = QComboBox()
            select.addItem("Choisir…", None)
            select.addItem("Garder local", "local")
            select.addItem("Prendre entrant", "incoming")
            select.setAccessibleName("Résoudre : " + conflict.path)
            select.currentIndexChanged.connect(self._update_merge_apply)
            self.merge_table.setCellWidget(row, 5, select)
            self._merge_choices[conflict.path] = select
        self.merge_status.setText(
            f"{len(changes)} changement(s) recensé(s), "
            f"{len(conflicts)} conflit(s). "
            "Résolvez chaque conflit ; application en mémoire avec Undo.")
        self._update_merge_apply()
        return preview

    def _update_merge_apply(self, *_):
        complete = all(widget.currentData() in ("local", "incoming")
                       for widget in self._merge_choices.values())
        self.merge_apply_button.setEnabled(
            complete and self.merge_controller._review is not None and
            bool(self.merge_controller._review.local_changes or
                 self.merge_controller._review.incoming_changes))

    def _apply_merge_dialog(self):
        if not self.merge_apply_button.isEnabled():
            return
        if QMessageBox.question(
                self, "Confirmer la fusion",
                "Appliquer les changements à la session Studio ?\n"
                "Un Undo restera possible. L'enregistrement disque est séparé.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.apply_merge()

    def apply_merge(self):
        if not self.merge_apply_button.isEnabled():
            return None
        decisions = {path: widget.currentData()
                     for path, widget in self._merge_choices.items()}
        try:
            transition = self.merge_controller.apply(decisions)
        except (ValueError, OSError) as exc:
            self.merge_apply_button.setEnabled(False)
            self._error("Fusion refusée", exc, self.merge_status)
            return None
        self.merge_apply_button.setEnabled(False)
        self.merge_status.setText(
            f"Fusion intégrée à la révision {transition.snapshot.revision}. "
            "Utilisez Enregistrer dans le Studio pour la persister, "
            "ou Annuler (Undo) pour revenir.")
        return transition

    def _error(self, title, error, label):
        label.setText(str(error))
        QMessageBox.warning(self, title, str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(description="R30.C Creator review Qt Widgets")
    parser.add_argument("--content", type=Path, help="Canonical Content with GameProject")
    parser.add_argument("--smoke", action="store_true", help="Initialize Qt then quit")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("The Qt preview is qualified on Python 3.12")
    session = (AuthoringSession.open(args.content) if args.content else
               AuthoringSession.new(*reference_project()))
    app = QApplication.instance() or QApplication([sys.argv[0]])
    widget = R30CreatorDialog(session, content_path=args.content)
    widget.show()
    if args.smoke:
        QTimer.singleShot(150, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
