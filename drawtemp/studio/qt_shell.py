"""DrawTemp 5.0 R2 Qt Widgets Studio shell.

A single owner holds the canonical R1 AuthoringSession. Existing R5/R8/R10
windows can be hosted as workspaces; no Content/GameProject copy is introduced.
Qt is optional and is never imported by the game SDK.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from PySide6.QtCore import QSettings, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDockWidget, QFileDialog,
    QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QStackedWidget, QStyleFactory,
    QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.workspace_model import (
    FAMILY_LABELS, common_name, edit_names, editable_name, reference_hints,
    resources,
)

log = logging.getLogger(__name__)
WORKSPACES = ("project", "maps", "actors", "database", "events",
              "campaigns", "cinematics", "analysis")
LABELS = {
    "project": "Projet", "maps": "Carte", "actors": "Personnages",
    "database": "Base RPG", "events": "Événements", "campaigns": "Campagne",
    "cinematics": "Cinématiques", "analysis": "Analyse",
}
EN = {
    "project": "Project", "maps": "Map", "actors": "Characters",
    "database": "RPG Database", "events": "Events", "campaigns": "Campaign",
    "cinematics": "Cinematics", "analysis": "Analysis",
}
DEFAULT_SHORTCUTS = {
    "save": "Ctrl+S", "open": "Ctrl+O", "undo": "Ctrl+Z", "redo": "Ctrl+Shift+Z",
    "palette": "Ctrl+Shift+P", "focus_resources": "Ctrl+1",
    "focus_inspector": "Ctrl+2",
}


def apply_theme(app, name, scale=100):
    """Accessible Fusion palettes; no model or renderer mutation."""
    app.setStyle(QStyleFactory.create("Fusion"))
    dark = name == "dark"
    palette = QPalette()
    colors = {
        QPalette.Window: "#171c27" if dark else "#f5f7fb",
        QPalette.WindowText: "#f2f5fa" if dark else "#222939",
        QPalette.Base: "#222a39" if dark else "#ffffff",
        QPalette.AlternateBase: "#2b3547" if dark else "#ecf1f8",
        QPalette.Text: "#f2f5fa" if dark else "#222939",
        QPalette.Button: "#303a4d" if dark else "#e7edf7",
        QPalette.ButtonText: "#ffffff" if dark else "#222939",
        QPalette.Highlight: "#7baaff" if dark else "#245dc0",
        QPalette.HighlightedText: "#111827" if dark else "#ffffff",
        QPalette.ToolTipBase: "#2b3547" if dark else "#ffffff",
        QPalette.ToolTipText: "#ffffff" if dark else "#222939",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#a0a8b6"))
    app.setPalette(palette)
    font = QFont(app.font())
    font.setPointSizeF(max(8.0, min(18.0, 10.0 * scale / 100)))
    app.setFont(font)


class ResourceProxy(QSortFilterProxyModel):
    """Recursive search plus optional favorites, both UI-only filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.favorite_only = False
        self.favorites = set()
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        identity = index.data(Qt.UserRole)
        if identity is not None and self.favorite_only:
            if identity not in self.favorites:
                return False
        elif identity is None and self.favorite_only:
            return any(self.filterAcceptsRow(row, index)
                       for row in range(self.sourceModel().rowCount(index)))
        return super().filterAcceptsRow(source_row, source_parent)


class CommandPalette(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Commandes • DrawTemp")
        self.resize(480, 420)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une commande…")
        self.search.setAccessibleName("Rechercher une commande")
        layout.addWidget(self.search)
        self.listing = QListWidget()
        self.listing.setAccessibleName("Commandes disponibles")
        layout.addWidget(self.listing)
        self.search.textChanged.connect(self.update_list)
        self.listing.itemActivated.connect(self.run_item)
        self.update_list("")
        self.search.setFocus()

    def update_list(self, query):
        self.listing.clear()
        for action in self.owner.commands.values():
            if action.isEnabled() and query.casefold() in action.text().casefold():
                self.listing.addItem(action.text())
                self.listing.item(self.listing.count() - 1).setData(
                    Qt.UserRole, action)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def run_item(self, item):
        action = item.data(Qt.UserRole)
        self.accept()
        action.trigger()


class StudioWindow(QMainWindow):
    def __init__(self, session=None, *, content_path=None, settings=None):
        super().__init__()
        self.session = session or AuthoringSession.new(*reference_project())
        self.content_path = Path(content_path) if content_path else None
        self.settings = settings or QSettings("DrawTemp", "Studio5")
        self.last_revision = -1
        self._models = {}
        self._resource_by_key = {}
        self._selected = ()
        self.pages = {}
        self.commands = {}
        self.setObjectName("drawtemp-r2-main")
        self.setWindowTitle("DrawTemp 5.0 • Studio")
        self.resize(1440, 900)
        apply_theme(QApplication.instance(),
                    self.settings.value("theme", "dark"),
                    int(self.settings.value("scale", 100)))
        self._build()
        self._restore_layout()
        self.refresh()
        self.watch = QTimer(self)
        self.watch.timeout.connect(self._refresh_if_changed)
        self.watch.start(300)

    def _build(self):
        self.workspace_tabs = QStackedWidget()
        self.workspace_tabs.setAccessibleName("Ateliers Studio")
        self.setCentralWidget(self.workspace_tabs)
        self._make_home()
        self._make_resource_dock()
        self._make_inspector_dock()
        self._make_problems_dock()
        self._build_commands()
        self._build_menus()
        self._activate("project")

    def _make_home(self):
        page = QWidget()
        panel = QVBoxLayout(page)
        title = QLabel("DrawTemp Studio 5.0")
        title.setObjectName("studio-heading")
        font = title.font()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        panel.addWidget(title)
        panel.addWidget(QLabel("Projet Jeanne • édition sans JSON • Content / GameProject partagés"))
        for group in (("Créer", ("maps", "actors", "database", "events")),
                      ("Organiser", ("campaigns", "cinematics", "analysis"))):
            panel.addWidget(QLabel(group[0]))
            buttons = QHBoxLayout()
            for identifier in group[1]:
                button = QPushButton(LABELS[identifier])
                button.setAccessibleName("Atelier " + LABELS[identifier])
                button.clicked.connect(lambda _checked=False, key=identifier:
                                       self.navigate(key))
                buttons.addWidget(button)
            panel.addLayout(buttons)
        panel.addStretch(1)
        self.workspace_tabs.addWidget(page)
        self.pages["project"] = page

    def _dock(self, title, name, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable |
                         QDockWidget.DockWidgetClosable)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _make_resource_dock(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Rechercher cartes, personnages, événements…")
        self.search.setAccessibleName("Recherche de ressources")
        layout.addWidget(self.search)
        row = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItems(("Toutes les ressources", "Favoris"))
        self.filter.setAccessibleName("Filtre des ressources")
        row.addWidget(self.filter)
        self.favorite_button = QPushButton("☆")
        self.favorite_button.setAccessibleName("Ajouter ou retirer des favoris")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        row.addWidget(self.favorite_button)
        layout.addLayout(row)
        self.resource_model = QStandardItemModel(self)
        self.resource_model.setHorizontalHeaderLabels(["Ressources"])
        self.proxy = ResourceProxy(self)
        self.proxy.setSourceModel(self.resource_model)
        self.resource_view = QTreeView()
        self.resource_view.setModel(self.proxy)
        self.resource_view.setHeaderHidden(True)
        self.resource_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.resource_view.setAccessibleName("Explorateur du projet")
        self.resource_view.selectionModel().selectionChanged.connect(
            lambda *_: self._update_selection())
        self.resource_view.doubleClicked.connect(self._open_selected_resource)
        layout.addWidget(self.resource_view, 1)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.filter.currentIndexChanged.connect(self._set_favorites_only)
        self.resource_dock = self._dock(
            "Explorateur", "r2-resource-dock", host, Qt.LeftDockWidgetArea)

    def _make_inspector_dock(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        self.inspector_title = QLabel("Sélectionnez une ressource")
        layout.addWidget(self.inspector_title)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.name_edit = QLineEdit()
        self.name_edit.setAccessibleName("Nom des ressources sélectionnées")
        self.form.addRow("Nom", self.name_edit)
        self.apply_button = QPushButton("Appliquer à la sélection")
        self.apply_button.clicked.connect(self.apply_selection)
        layout.addWidget(self.apply_button)
        self.references = QLabel("Aucune sélection")
        self.references.setWordWrap(True)
        self.references.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.references)
        layout.addStretch(1)
        self.inspector_dock = self._dock(
            "Inspecteur", "r2-inspector-dock", host, Qt.RightDockWidgetArea)

    def _make_problems_dock(self):
        self.problems = QListWidget()
        self.problems.setAccessibleName("Journal des diagnostics du Studio")
        self.problems_dock = self._dock(
            "Diagnostics", "r2-problems-dock", self.problems, Qt.BottomDockWidgetArea)

    def _action(self, key, label, callback):
        action = QAction(label, self)
        shortcut = self.settings.value("shortcuts/" + key, DEFAULT_SHORTCUTS.get(key, ""))
        if shortcut:
            action.setShortcut(QKeySequence(str(shortcut)))
            action.setShortcutContext(Qt.ApplicationShortcut)
        action.triggered.connect(callback)
        self.addAction(action)
        self.commands[key] = action
        return action

    def _build_commands(self):
        self._action("open", "Ouvrir un projet…", self.open_document)
        self._action("save", "Enregistrer le projet", self.save_document)
        self._action("save_as", "Enregistrer sous…", self.save_document_as)
        self._action("undo", "Annuler", self.undo)
        self._action("redo", "Rétablir", self.redo)
        self._action("palette", "Palette de commandes…", self.open_palette)
        self._action("focus_resources", "Rechercher les ressources",
                     lambda: self.search.setFocus())
        self._action("focus_inspector", "Inspecter la sélection",
                     lambda: self.name_edit.setFocus())
        for identifier in WORKSPACES:
            self._action("go_" + identifier, "Atelier : " + LABELS[identifier],
                         lambda _checked=False, key=identifier: self.navigate(key))

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("&Fichier")
        for key in ("open", "save", "save_as"):
            file_menu.addAction(self.commands[key])
        edit_menu = self.menuBar().addMenu("&Édition")
        for key in ("undo", "redo", "palette"):
            edit_menu.addAction(self.commands[key])
        view_menu = self.menuBar().addMenu("&Affichage")
        self.workspaces_menu = self.menuBar().addMenu("&Ateliers")
        for identifier in WORKSPACES:
            self.workspaces_menu.addAction(self.commands["go_" + identifier])
        for dock in (self.resource_dock, self.inspector_dock, self.problems_dock):
            view_menu.addAction(dock.toggleViewAction())
        for title, name in (("Disposition édition", "editing"),
                            ("Disposition analyse", "analysis"),
                            ("Disposition compacte", "compact")):
            action = view_menu.addAction(title)
            action.triggered.connect(lambda _=False, p=name: self.layout_preset(p))
        theme_menu = view_menu.addMenu("Thème")
        for title, key in (("Sombre", "dark"), ("Clair", "light")):
            action = theme_menu.addAction(title)
            action.triggered.connect(lambda _=False, value=key: self.set_theme(value))
        for scale in (90, 100, 115, 130):
            action = view_menu.addAction("Échelle UI : " + str(scale) + "%")
            action.triggered.connect(lambda _=False, size=scale: self.set_scale(size))
        tools_menu = self.menuBar().addMenu("&Outils")
        shortcuts = tools_menu.addAction("Configurer un raccourci…")
        shortcuts.triggered.connect(self.configure_shortcut)
        # Localization applies to global workspace labels; legacy editors
        # maintain their own FR labels while they are being migrated.
        locale_menu = tools_menu.addMenu("Langue")
        for lang in ("fr", "en"):
            action = locale_menu.addAction(lang.upper())
            action.triggered.connect(lambda _=False, code=lang: self.set_language(code))
        self.toolbar = QToolBar("Navigation", self)
        self.toolbar.setObjectName("r2-navigation-toolbar")
        self.addToolBar(self.toolbar)
        for identifier in WORKSPACES:
            self.toolbar.addAction(self.commands["go_" + identifier])

    def _restore_layout(self):
        geometry = self.settings.value("window/geometry")
        state = self.settings.value("window/docks")
        if geometry:
            self.restoreGeometry(geometry)
        if not (state and self.restoreState(state, 1)):
            self.layout_preset("editing")

    def layout_preset(self, preset):
        for dock in (self.resource_dock, self.inspector_dock, self.problems_dock):
            dock.setFloating(False)
        self.resource_dock.show()
        self.inspector_dock.setVisible(preset != "compact")
        self.problems_dock.setVisible(preset == "analysis")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.resource_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)

    def set_theme(self, theme):
        self.settings.setValue("theme", theme)
        apply_theme(QApplication.instance(), theme,
                    int(self.settings.value("scale", 100)))

    def set_scale(self, scale):
        self.settings.setValue("scale", scale)
        apply_theme(QApplication.instance(), self.settings.value("theme", "dark"), scale)

    def set_language(self, language):
        self.settings.setValue("language", language)
        labels = EN if language == "en" else LABELS
        for identifier in WORKSPACES:
            self.commands["go_" + identifier].setText("Workspace: " + labels[identifier]
                                                      if language == "en" else
                                                      "Atelier : " + labels[identifier])
        self.statusBar().showMessage("Langue du shell : " + language.upper())

    def configure_shortcut(self):
        keys = tuple(DEFAULT_SHORTCUTS)
        key, chosen = QInputDialog.getItem(
            self, "Raccourci", "Commande", list(keys), 0, False)
        if not chosen:
            return
        value, chosen = QInputDialog.getText(
            self, "Raccourci", "Séquence Qt (ex. Ctrl+Alt+O)",
            text=self.commands[key].shortcut().toString())
        if not chosen:
            return
        sequence = QKeySequence(value.strip())
        if sequence.isEmpty() or any(
            other != key and action.shortcut() == sequence
            for other, action in self.commands.items()
        ):
            QMessageBox.warning(self, "Raccourci", "Séquence vide ou déjà affectée.")
            return
        self.commands[key].setShortcut(sequence)
        self.settings.setValue("shortcuts/" + key, sequence.toString())

    def open_palette(self):
        CommandPalette(self).exec()

    def _set_favorites_only(self, index):
        self.proxy.favorite_only = index == 1
        self.proxy.invalidateFilter()

    @staticmethod
    def _identity(resource):
        return "|".join(resource.key)

    def _favorites(self):
        stored = self.settings.value("resources/favorites", [])
        if isinstance(stored, str):
            return {stored} if stored else set()
        return set(stored or [])

    def toggle_favorite(self):
        chosen = self._selected
        if not chosen:
            return
        favorites = self._favorites()
        for resource in chosen:
            key = self._identity(resource)
            if key in favorites:
                favorites.remove(key)
            else:
                favorites.add(key)
        self.settings.setValue("resources/favorites", sorted(favorites))
        self.proxy.favorites = favorites
        self.proxy.invalidateFilter()

    def refresh(self):
        snapshot = self.session.snapshot()
        selected_keys = {r.key for r in self._selected}
        self._resource_by_key = {r.key: r for r in resources(snapshot)}
        self.resource_model.clear()
        self.resource_model.setHorizontalHeaderLabels(["Ressources"])
        for family, title in FAMILY_LABELS.items():
            parent = QStandardItem(title)
            parent.setEditable(False)
            for resource in self._resource_by_key.values():
                if resource.family != family:
                    continue
                label = resource.title
                if resource.mission_id:
                    label += "  [" + resource.mission_id + "]"
                child = QStandardItem(label)
                child.setEditable(False)
                child.setData(self._identity(resource), Qt.UserRole)
                child.setToolTip(resource.resource_id)
                parent.appendRow(child)
            if parent.rowCount():
                self.resource_model.appendRow(parent)
        self.proxy.favorites = self._favorites()
        self.proxy.invalidateFilter()
        self.resource_view.expandAll()
        self._selected = tuple(r for k, r in self._resource_by_key.items()
                               if k in selected_keys)
        self.last_revision = snapshot.revision
        self._show_inspector()
        self._update_title()
        self.commands["undo"].setEnabled(snapshot.can_undo)
        self.commands["redo"].setEnabled(snapshot.can_redo)

    def _refresh_if_changed(self):
        if self.last_revision != self.session.revision:
            self.refresh()
            for name, child in self._models.items():
                try:
                    if name == "maps":
                        child.refresh_maps()
                    elif name == "database":
                        child._reload()
                    elif name == "campaigns":
                        child._refresh()
                except Exception as exc:
                    self.report_error(exc)

    def _update_title(self):
        state = self.session.snapshot()
        title = state.project.get("title", "DrawTemp")
        suffix = " • " + str(self.content_path) if self.content_path else " • Référence Jeanne"
        self.setWindowTitle(("* " if state.dirty else "") +
                            str(title) + " — DrawTemp Studio 5.0" + suffix)

    def _update_selection(self):
        selected = []
        for index in self.resource_view.selectionModel().selectedRows(0):
            identity = index.data(Qt.UserRole)
            if identity:
                parts = identity.split("|")
                key = (parts[0], parts[1], parts[2])
                if key in self._resource_by_key:
                    selected.append(self._resource_by_key[key])
        self._selected = tuple(selected)
        self._show_inspector()

    def _show_inspector(self):
        chosen = self._selected
        self.inspector_title.setText(
            str(len(chosen)) + " ressource(s) sélectionnée(s)" if chosen else
            "Sélectionnez une ressource dans l'explorateur")
        can_edit = editable_name(chosen)
        self.name_edit.setEnabled(can_edit)
        self.apply_button.setEnabled(can_edit)
        value, mixed = common_name(chosen)
        self.name_edit.setPlaceholderText("Valeurs multiples" if mixed else "Nom")
        self.name_edit.setText(value)
        if len(chosen) == 1:
            hints = reference_hints(self.session.snapshot(), chosen[0])
            self.references.setText("ID stable : " + chosen[0].resource_id +
                "\nRéférences indicatives :\n" +
                ("\n".join(hints) if hints else "Aucune référence connue"))
        else:
            self.references.setText("Modifications de nom atomiques (un Undo)."
                                    if can_edit else "Lecture seule / sélection mixte.")

    def apply_selection(self):
        try:
            edit_names(self.session, self._selected, self.name_edit.text())
            self.refresh()
        except (AuthoringError, ValueError) as exc:
            self.report_error(exc)

    def _open_selected_resource(self, _index):
        if not self._selected:
            return
        resource = self._selected[0]
        destination = {
            "maps": "maps", "actors": "actors", "objects": "maps",
            "events": "events", "campaigns": "campaigns",
            "scenes": "events", "cinematics": "cinematics",
        }.get(resource.family, "project")
        self.navigate(destination)
        if destination == "maps":
            child = self._models.get("maps")
            if child is not None:
                mid = resource.mission_id or resource.resource_id
                child.studio.select_map(mid)
                child.refresh_maps()

    def navigate(self, identifier):
        if identifier not in WORKSPACES:
            raise ValueError("Unknown workspace: " + identifier)
        if identifier not in self.pages:
            try:
                self._make_workspace(identifier)
            except Exception as exc:
                self.report_error(exc)
                return
        self._activate(identifier)

    def _activate(self, identifier):
        self.workspace_tabs.setCurrentWidget(self.pages[identifier])
        self.statusBar().showMessage("Atelier : " + LABELS[identifier])

    def _make_workspace(self, identifier):
        if identifier in ("database", "actors") and "database" in self._models:
            child = self._models["database"]
            self.pages[identifier] = child
            self.pages["database"] = child
            if identifier == "actors":
                child.tree.setCurrentItem(child.tree.topLevelItem(1))
            return
        if identifier == "maps":
            from drawtemp.studio.map_authoring import MapStudio
            from drawtemp.studio.map_editor import MapWindow
            child = MapWindow(MapStudio(self.session))
        elif identifier in ("database", "actors"):
            from drawtemp.studio.rpg_database_qt import DatabaseWindow
            child = self._models.get("database")
            if child is None:
                child = DatabaseWindow(self.session, path=self.content_path)
                self._models["database"] = child
            if identifier == "actors":
                child.tree.setCurrentItem(child.tree.topLevelItem(1))
        elif identifier == "campaigns":
            from drawtemp.sdk.campaign_studio import CampaignStudio
            from drawtemp.studio.campaign_window import CampaignWindow
            campaigns = self.session.snapshot().project.get("campaigns", [])
            if not campaigns:
                raise ValueError("Le projet ne contient pas de campagne")
            studio = CampaignStudio(self.session, campaigns[0]["id"])
            child = CampaignWindow(studio, source=self.content_path,
                                   opened=bool(self.content_path))
        else:
            child = self._overview(identifier)
        if identifier in ("maps", "database", "campaigns"):
            self._models[identifier] = child
            # Embedded editors must never swap the shared AuthoringSession:
            # opening/saving a project is a shell responsibility.
            for toolbar in child.findChildren(QToolBar):
                for action in toolbar.actions():
                    if action.text().lower().startswith(("ouvrir", "enregistrer")):
                        action.setEnabled(False)
            if identifier == "campaigns":
                for button in child.findChildren(QPushButton):
                    if button.text().lower().startswith(("enregistrer", "ouvrir")):
                        button.setEnabled(False)
        self.workspace_tabs.addWidget(child)
        self.pages[identifier] = child
        if identifier in ("database", "actors"):
            self.pages["database"] = child
            self.pages["actors"] = child

    def _overview(self, identifier):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(LABELS[identifier]))
        text = {
            "events": "Événements du projet • exploration (édition R9 à intégrer dans le shell)",
            "cinematics": "Cinématiques du projet • exploration (R11, édition partagée à certifier)",
            "analysis": "Analyse et ressources • diagnostics de la session canonique",
        }.get(identifier, "Atelier disponible prochainement")
        layout.addWidget(QLabel(text))
        listing = QListWidget()
        listing.setAccessibleName("Ressources : " + LABELS[identifier])
        family = {"events": "events", "cinematics": "cinematics"}.get(identifier)
        for item in resources(self.session.snapshot()):
            if family is None or item.family == family:
                listing.addItem(item.title + "  [" + item.resource_id + "]")
        layout.addWidget(listing)
        return page

    def report_error(self, error):
        log.warning("R2 Studio: %s", error)
        self.problems.addItem(str(error))
        self.statusBar().showMessage(str(error))
        QMessageBox.warning(self, "DrawTemp Studio", str(error))

    def undo(self):
        try:
            self.session.undo()
            self.refresh()
        except AuthoringError as exc:
            self.report_error(exc)

    def redo(self):
        try:
            self.session.redo()
            self.refresh()
        except AuthoringError as exc:
            self.report_error(exc)

    def save_document(self):
        try:
            if self.content_path is None:
                return self.save_document_as()
            self.session.save()
            self.refresh()
            return True
        except (AuthoringError, OSError) as exc:
            self.report_error(exc)
            return False

    def save_document_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer Content et GameProject",
            "jeanne.json", "Content JSON (*.json)")
        if not path:
            return False
        try:
            self.session.save_as(path)
            self.content_path = Path(path)
            self.refresh()
            return True
        except (AuthoringError, OSError) as exc:
            self.report_error(exc)
            return False

    def _confirm_leave(self):
        if not self.session.snapshot().dirty:
            return True
        choice = QMessageBox.warning(
            self, "Modifications non enregistrées",
            "Enregistrer le projet avant de quitter ?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel)
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            return self.save_document()
        return True

    def open_document(self):
        if not self._confirm_leave():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir Content + GameProject", "", "Content JSON (*.json)")
        if not path:
            return
        try:
            fresh = AuthoringSession.open(path)
        except (AuthoringError, OSError, ValueError) as exc:
            self.report_error(exc)
            return
        self.workspace_tabs.setCurrentWidget(self.pages["project"])
        old_pages = {page for name, page in self.pages.items() if name != "project"}
        self.pages = {"project": self.pages["project"]}
        for page in old_pages:
            self.workspace_tabs.removeWidget(page)
            page.setParent(None)
            page.deleteLater()
        self._models.clear()
        self._selected = ()
        self.session = fresh
        self.content_path = Path(path)
        self.refresh()

    def closeEvent(self, event):
        if not self._confirm_leave():
            event.ignore()
            return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/docks", self.saveState(1))
        self.settings.sync()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5.0 Qt 6 Studio (R2)")
    parser.add_argument("--content", type=Path, help="Existing paired Content + GameProject")
    parser.add_argument("--smoke", action="store_true", help="Start and quit after GUI initialization")
    parser.add_argument("--workspace", choices=WORKSPACES, default="project")
    parser.add_argument("--reset-layout", action="store_true")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("DrawTemp 5.0 Qt 6 is qualified on Python 3.12")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        if args.content:
            session = AuthoringSession.open(args.content)
        else:
            session = AuthoringSession.new(*reference_project())
        app = QApplication.instance() or QApplication([sys.argv[0]])
        settings = QSettings("DrawTemp", "Studio5")
        if args.reset_layout:
            settings.remove("window")
        window = StudioWindow(session, content_path=args.content, settings=settings)
        window.show()
        window.navigate(args.workspace)
        if args.smoke:
            QTimer.singleShot(180, app.quit)
        return app.exec()
    except Exception as exc:
        log.exception("Studio startup failed")
        print("DrawTemp Qt Studio: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
