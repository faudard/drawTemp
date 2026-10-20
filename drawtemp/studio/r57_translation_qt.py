"""R57.B first Translation Studio surface: project-owned sidecar, no R1 mutations."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from drawtemp.localization import (
    Catalog, LocalizationError, file_revision, rebase_project_sources, seeded_for_project, sidecar_path,
)
from drawtemp.sdk.simulation import thaw


class TranslationStudioDialog(QDialog):
    """Keyboard-first editing with explicit save and external-change protection."""

    def __init__(self, session, content_path, parent=None):
        super().__init__(parent)
        if content_path is None:
            raise LocalizationError("Save the project before editing translations")
        self.path = sidecar_path(content_path)
        self.base_revision = file_revision(self.path)
        snapshot = session.snapshot()
        if snapshot.dirty:
            raise LocalizationError("Enregistrez le projet avant les traductions.")
        self.session = session
        self.source_revision = snapshot.revision
        self.project = thaw(snapshot.project)
        old = Catalog.load(self.path) if self.base_revision else None
        self.catalog, self.drift = seeded_for_project(self.project, old)
        self.drafts = {}
        self._selected_key = None
        self.setWindowTitle("R57 • Translation Studio")
        self.resize(850, 600)
        layout = QVBoxLayout(self)
        self.help = QLabel(
            "Traductions séparées du projet et du replay. "
            "Aucun texte n'est exporté ni enregistré avant Enregistrer. "
            "Ctrl+F : rechercher · Ctrl+L : clés · Ctrl+E : traduction · Ctrl+S : sauvegarder.")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        top = QHBoxLayout()
        top.addWidget(QLabel("Langue cible"))
        self.language = QComboBox()
        self.language.setAccessibleName("Choisir la langue cible")
        target = "en" if self.catalog.data["source_language"] == "fr" else "fr"
        self.language.addItem("English" if target == "en" else "Français", target)
        self.language.addItem("Pseudo (accents)", "qps-ploc")
        self.language.addItem("Pseudo (RTL)", "qps-plocm")
        self.language.currentIndexChanged.connect(self.refresh_list)
        top.addWidget(self.language)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Chercher une clé, source ou contexte…")
        self.search.setAccessibleName("Rechercher une traduction")
        self.search.textChanged.connect(self.refresh_list)
        top.addWidget(self.search, 1)
        layout.addLayout(top)
        splitter = QSplitter()
        self.keys = QListWidget()
        self.keys.setAccessibleName("Clés de localisation")
        self.keys.currentItemChanged.connect(self.show_key)
        splitter.addWidget(self.keys)
        editor = QWidget()
        panel = QVBoxLayout(editor)
        self.key_label = QLabel("Sélectionnez une clé")
        self.key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        panel.addWidget(self.key_label)
        panel.addWidget(QLabel("Contexte et texte source"))
        self.context = QPlainTextEdit()
        self.context.setReadOnly(True)
        self.context.setAccessibleName("Contexte et texte source")
        panel.addWidget(self.context, 1)
        self.plural_label = QLabel("Forme plurielle à traduire")
        panel.addWidget(self.plural_label)
        self.plural_form = QComboBox()
        self.plural_form.setAccessibleName("Choisir la forme plurielle à traduire")
        self.plural_form.addItem("Un élément (one)", "one")
        self.plural_form.addItem("Plusieurs éléments (other)", "other")
        self.plural_form.currentIndexChanged.connect(self.show_selected_form)
        panel.addWidget(self.plural_form)
        self.plural_label.setVisible(False)
        self.plural_form.setVisible(False)
        panel.addWidget(QLabel("Traduction"))
        self.text = QPlainTextEdit()
        self.text.setAccessibleName("Éditer la traduction sélectionnée")
        self.text.textChanged.connect(self.remember_draft)
        panel.addWidget(self.text, 1)
        panel.addWidget(QLabel("Prévisualisation pseudo-localisée"))
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        panel.addWidget(self.preview)
        splitter.addWidget(editor)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        # Explicit mnemonic navigation, independent of native mouse devices.
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.search.setFocus)
        self.list_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.list_shortcut.activated.connect(self.keys.setFocus)
        self.edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.edit_shortcut.activated.connect(self.text.setFocus)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Diagnostic de traduction")
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.rebase_button = QPushButton("Réconcilier les sources…")
        self.rebase_button.setAccessibleName("Actualiser les textes sources modifiés")
        self.rebase_button.clicked.connect(self.reconcile_sources)
        actions.addWidget(self.rebase_button)
        self.save_button = QPushButton("Enregistrer les traductions")
        self.save_button.setShortcut("Ctrl+S")
        self.save_button.clicked.connect(self.save)
        actions.addWidget(self.save_button)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh_list()

    def current_language(self):
        return self.language.currentData()

    def refresh_list(self, *_):
        current = self._selected_key
        query = self.search.text().casefold()
        self.keys.blockSignals(True)
        self.keys.clear()
        for key, entry in sorted(self.catalog.data["entries"].items()):
            if query not in (key + " " + str(entry["source"]) +
                             " " + entry["context"]).casefold():
                continue
            self.keys.addItem(key)
        self.keys.blockSignals(False)
        rows = self.keys.findItems(current, Qt.MatchExactly) if current else []
        self.keys.setCurrentItem(rows[0] if rows else (
            self.keys.item(0) if self.keys.count() else None))
        self.show_key(self.keys.currentItem())

    def show_key(self, current, *_):
        self._selected_key = current.text() if current else None
        key = self._selected_key
        self.text.blockSignals(True)
        if key:
            entry = self.catalog.data["entries"][key]
            self.key_label.setText(key)
            self.context.setPlainText(entry["context"] + "\n\n" +
                                      str(entry["source"]))
            lang = self.current_language()
            editable = lang in ("fr", "en")
            source = entry["source"]
            plural = isinstance(source, dict)
            self.plural_label.setVisible(plural)
            self.plural_form.setVisible(plural)
            value = self.drafts.get((key, lang), entry["translations"].get(lang, ""))
            if plural:
                # Each form stays a structured one/other pair. Converting it
                # to str(dict) would corrupt the translation upon saving.
                value = value.get(self.plural_form.currentData(), "") if isinstance(value, dict) else ""
            self.text.setPlainText(value)
            self.text.setReadOnly(not editable)
            self.save_button.setEnabled(editable)
            # Pseudo preview is non-editable and protects placeholders.
            try:
                preview = self.catalog.render(
                    key, lang if not editable else "qps-ploc",
                    count=(1 if self.plural_form.currentData() == "one" else 2) if plural else None)
            except LocalizationError:
                preview = "Aperçu indisponible (paramètres requis)"
            self.preview.setText(preview)
        else:
            self.key_label.setText("Aucune clé")
            self.plural_label.setVisible(False)
            self.plural_form.setVisible(False)
            self.context.clear()
            self.text.clear()
            self.preview.clear()
            self.save_button.setEnabled(False)
        self.text.blockSignals(False)
        issue_count = len(self.catalog.audit(
            "en" if self.catalog.data["source_language"] == "fr" else "fr"))
        self.rebase_button.setEnabled(bool(self.drift))
        self.status.setText(
            f"{issue_count} entrée(s) incomplète(s) ou trop longue(s). " +
            (("Sources modifiées : " + ", ".join(self.drift) +
              ". Réconcilier le texte source avant publication.")
             if self.drift else "Aucune dérive des sources du projet."))

    def show_selected_form(self, *_):
        # Existing edits are saved on textChanged, even when the user changes
        # the singular/plural selector without leaving the keyboard.
        self.show_key(self.keys.currentItem())

    def remember_draft(self):
        lang = self.current_language()
        if self._selected_key and lang in ("fr", "en"):
            draft_key = (self._selected_key, lang)
            source = self.catalog.data["entries"][self._selected_key]["source"]
            if isinstance(source, dict):
                # Unsupplied target forms explicitly fall back to the source.
                existing = self.drafts.get(
                    draft_key,
                    self.catalog.data["entries"][self._selected_key]
                    ["translations"].get(lang, {"one": "", "other": ""}))
                existing = dict(existing) if isinstance(existing, dict) else {
                    "one": "", "other": ""}
                existing[self.plural_form.currentData()] = self.text.toPlainText()
                self.drafts[draft_key] = existing
            else:
                self.drafts[draft_key] = self.text.toPlainText()

    def reconcile_sources(self):
        if not self.drift:
            return
        answer = QMessageBox.question(
            self, "Réconcilier les sources",
            "Les traductions des clés suivantes seront effacées car leurs textes "
            "sources ont changé : " + ", ".join(self.drift) +
            "\nLes traductions des autres clés seront préservées. Continuer ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            self.catalog, _ = rebase_project_sources(self.project, self.catalog)
        except LocalizationError as exc:
            QMessageBox.warning(self, "Réconciliation refusée", str(exc))
            return
        changed = set(self.drift)
        self.drafts = {key: value for key, value in self.drafts.items()
                       if key[0] not in changed}
        self.drift = ()
        self.refresh_list()

    def save(self):
        # The project is authoritative: reopening is mandatory after an edit
        # made in another Studio panel, even when no catalog file was changed.
        snapshot = self.session.snapshot()
        if snapshot.dirty or snapshot.revision != self.source_revision:
            QMessageBox.warning(
                self, "Projet modifié",
                "Le projet a changé depuis l'ouverture de Translation Studio. "
                "Enregistrez le projet puis rouvrez l'atelier.")
            return
        if self.drift:
            QMessageBox.warning(
                self, "Sources modifiées",
                "Le projet ne correspond plus aux textes de référence : " +
                ", ".join(self.drift))
            return
        try:
            candidate = self.catalog
            for (key, lang), value in sorted(self.drafts.items()):
                candidate = candidate.with_translation(key, lang, value)
            self.base_revision = candidate.save(
                self.path, expected_revision=self.base_revision)
            self.catalog = candidate
            self.drafts.clear()
        except (LocalizationError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Traductions non enregistrées", str(exc))
            return
        self.show_key(self.keys.currentItem())
        self.status.setText("Traductions enregistrées : " + str(self.path))


def open_translation_studio(window):
    if window.content_path is None:
        QMessageBox.warning(window, "Translation Studio",
                            "Enregistrez d'abord votre projet.")
        return
    try:
        dialog = TranslationStudioDialog(
            window.session, window.content_path, parent=window)
    except (LocalizationError, OSError, ValueError) as exc:
        QMessageBox.warning(window, "Translation Studio", str(exc))
        return
    dialog.exec()
