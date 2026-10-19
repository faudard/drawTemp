"""R38.1 Qt global search; the read-only index never owns authoring state."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .r38_global_search import GlobalSearchIndex


LABELS = {
    "project": "Projet", "maps": "Cartes", "actors": "Acteurs",
    "objects": "Objets", "events": "Événements", "campaigns": "Campagnes",
    "scenes": "Dialogues", "cinematics": "Cinématiques",
    "assets": "Assets", "quests": "Quêtes R35", "factions": "Factions R35",
    "logic_graphs": "Graphes R31",
    "graph_nodes": "Nœuds R31",
}


class GlobalSearchDialog(QDialog):
    """Revision-scoped search and usages; no file reads, writes or background jobs."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.index = GlobalSearchIndex(owner.session.snapshot())
        self._hits = ()
        self.setObjectName("r38-global-search")
        self.setWindowTitle("R38 • Recherche globale et utilisations")
        self.resize(760, 610)
        layout = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setObjectName("r38-query")
        self.query.setAccessibleName("Recherche globale dans le projet")
        self.query.setPlaceholderText("Nom, identifiant, chemin, catégorie, carte…")
        self.query.setClearButtonEnabled(True)
        layout.addWidget(self.query)

        filters = QHBoxLayout()
        self.family = QComboBox()
        self.family.setAccessibleName("Filtrer par famille")
        self.family.addItem("Toutes les familles", "")
        for key, label in LABELS.items():
            self.family.addItem(label, key)
        filters.addWidget(self.family)
        self.mission = QComboBox()
        self.mission.setAccessibleName("Filtrer par mission")
        self.mission.addItem("Toutes les missions", "")
        for entry in self.index.entries:
            if entry.family == "maps":
                self.mission.addItem(entry.title, entry.resource_id)
        filters.addWidget(self.mission)
        layout.addLayout(filters)

        self.count = QLabel()
        self.count.setAccessibleName("Nombre de résultats")
        layout.addWidget(self.count)
        self.results = QListWidget()
        self.results.setObjectName("r38-results")
        self.results.setAccessibleName("Résultats de recherche globale")
        layout.addWidget(self.results, 2)
        self.details = QPlainTextEdit()
        self.details.setObjectName("r38-usages")
        self.details.setAccessibleName("Détails et utilisations typées")
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)

        controls = QHBoxLayout()
        self.open_button = QPushButton("Sélectionner dans l'explorateur")
        self.open_button.setObjectName("r38-open")
        self.open_button.clicked.connect(self.open_selection)
        controls.addWidget(self.open_button)
        dismiss = QPushButton("Fermer")
        dismiss.clicked.connect(self.reject)
        controls.addWidget(dismiss)
        layout.addLayout(controls)

        self.query.textChanged.connect(self.refresh_results)
        self.family.currentIndexChanged.connect(self.refresh_results)
        self.mission.currentIndexChanged.connect(self.refresh_results)
        self.results.currentRowChanged.connect(self.show_details)
        self.results.itemActivated.connect(self.open_selection)
        self.refresh_results()
        self.query.setFocus()

    def refresh_results(self, *_args):
        selected = self.family.currentData()
        self._hits = self.index.search(
            self.query.text(), families=(selected,) if selected else (),
            mission_id=self.mission.currentData() or "")
        self.results.clear()
        for hit in self._hits:
            label = LABELS.get(hit.family, hit.family)
            scope = " · " + hit.mission_id if hit.mission_id else ""
            self.results.addItem(label + scope + " — " + hit.title +
                                 " [" + hit.resource_id + "]")
        self.count.setText(str(len(self._hits)) + " résultats (maximum 200)")
        if self._hits:
            self.results.setCurrentRow(0)
        else:
            self.details.setPlainText("Aucun résultat")
            self.open_button.setEnabled(False)

    def show_details(self, index):
        if not 0 <= index < len(self._hits):
            self.details.clear()
            self.open_button.setEnabled(False)
            return
        hit = self._hits[index]
        incoming = self.index.references(hit.key, "incoming")
        outgoing = self.index.references(hit.key, "outgoing")
        lines = [hit.title, hit.details, hit.path, "",
                 "Utilisé par (" + str(len(incoming)) + ") :"]
        for edge in incoming[:80]:
            source = self.index.by_key[edge.source]
            lines.append("• " + source.title + " [" + source.family + "] : " +
                         edge.field + " — " + edge.path)
        if len(incoming) > 80:
            lines.append("… " + str(len(incoming) - 80) + " autres usages")
        lines.extend(("", "Utilise (" + str(len(outgoing)) + ") :"))
        for edge in outgoing[:80]:
            target = self.index.by_key[edge.target]
            lines.append("• " + target.title + " [" + target.family + "] : " +
                         edge.field + " — " + edge.path)
        if len(outgoing) > 80:
            lines.append("… " + str(len(outgoing) - 80) + " autres usages")
        self.details.setPlainText("\n".join(lines))
        self.open_button.setEnabled(hit.navigate is not None or
                                    hit.family in ("logic_graphs", "graph_nodes"))
        self.open_button.setText(
            "Ouvrir Game Logic Studio" if hit.family in ("logic_graphs", "graph_nodes")
            else "Sélectionner dans l'explorateur")

    def open_selection(self, *_args):
        row = self.results.currentRow()
        if not 0 <= row < len(self._hits):
            return
        hit = self._hits[row]
        # Fail closed after concurrent edits: never navigate an obsolete ID.
        if self.owner.session.revision != self.index.revision:
            self.index = GlobalSearchIndex(self.owner.session.snapshot())
            self.refresh_results()
            self.details.setPlainText(
                "Le projet a changé : index recalculé. Re-sélectionnez une ressource.")
            return
        if hit.navigate is not None:
            self.accept()
            self.owner.resource_dock.show()
            self.owner.focus_resource(hit.navigate)
        elif hit.family in ("logic_graphs", "graph_nodes"):
            self.accept()
            self.owner.open_logic_graph()
