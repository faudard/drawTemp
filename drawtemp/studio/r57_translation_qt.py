"""R57.B first Translation Studio surface: project-owned sidecar, no R1 mutations."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from drawtemp.localization import (
    Catalog, LocalizationError, file_revision, seeded_for_project, sidecar_path,
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
        project = thaw(session.snapshot().project)
        old = Catalog.load(self.path) if self.base_revision else None
        self.catalog, self.drift = seeded_for_project(project, old)
        self.drafts = {}
        self._selected_key = None
        self.setWindowTitle("R57 • Translation Studio")
        self.resize(850, 600)
        layout = QVBoxLayout(self)
        self.help = QLabel(
            "Traductions séparées du projet et du replay. "
            "Aucun texte n'est exporté ni enregistré avant Enregistrer.")
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
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Diagnostic de traduction")
        layout.addWidget(self.status)
        actions = QHBoxLayout()
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
            value = self.drafts.get((key, lang), entry["translations"].get(lang, ""))
            self.text.setPlainText(value if isinstance(value, str) else str(value))
            self.text.setReadOnly(not editable)
            self.save_button.setEnabled(editable)
            # Pseudo preview is non-editable and protects placeholders.
            try:
                preview = self.catalog.render(
                    key, lang if not editable else "qps-ploc")
            except LocalizationError:
                preview = "Aperçu indisponible (paramètres requis)"
            self.preview.setText(preview)
        else:
            self.key_label.setText("Aucune clé")
            self.context.clear()
            self.text.clear()
            self.preview.clear()
            self.save_button.setEnabled(False)
        self.text.blockSignals(False)
        issue_count = len(self.catalog.audit(
            "en" if self.catalog.data["source_language"] == "fr" else "fr"))
        self.status.setText(
            f"{issue_count} entrée(s) incomplète(s) ou trop longue(s). " +
            (("Sources modifiées : " + ", ".join(self.drift) +
              ". Réconcilier le texte source avant publication.")
             if self.drift else "Aucune dérive des sources du projet."))

    def remember_draft(self):
        lang = self.current_language()
        if self._selected_key and lang in ("fr", "en"):
            self.drafts[(self._selected_key, lang)] = self.text.toPlainText()

    def save(self):
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
