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

from PySide6.QtCore import QItemSelectionModel, QProcess, QSettings, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIntValidator, QKeySequence, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDockWidget,
    QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QScrollArea, QSplitter, QStackedWidget, QStyleFactory, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.workspace_model import FAMILY_LABELS, resources
from drawtemp.studio.inspector_model import (
    InspectorError, common_value, edit_properties, shared_specs, validate_draft,
)
from drawtemp.studio.resource_links import connections
from drawtemp.sdk.controlled_scripting import (
    StudioScriptError, read_script_manifest, install_script,
)
from drawtemp.studio.plugins import (
    StudioPluginError, StudioPluginRegistry, read_studio_manifest,
)
from drawtemp.studio.r18_navigation import (WORKSPACES, LABELS, EN, recent_projects, workspace_host)
from drawtemp.studio.r18_onboarding import (
    GUIDE_UI, STEP_IDS, journey_steps, next_step, normalize_completed, project_key,
)

log = logging.getLogger(__name__)
DEFAULT_SHORTCUTS = {
    "save": "Ctrl+S", "open": "Ctrl+O", "undo": "Ctrl+Z", "redo": "Ctrl+Shift+Z",
    "palette": "Ctrl+Shift+P", "guide": "Ctrl+Shift+G",
    "focus_resources": "Ctrl+1",
    "focus_inspector": "Ctrl+2", "new": "Ctrl+Shift+N",
    "new_project": "Ctrl+N", "new_template": "Ctrl+Alt+N",
    "playtest": "F5", "export": "Ctrl+Shift+E",
    "go_project": "Ctrl+Alt+1", "go_maps": "Ctrl+Alt+2",
    "go_construction": "Ctrl+Alt+3", "go_actors": "Ctrl+Alt+4",
    "go_database": "Ctrl+Alt+5", "go_events": "Ctrl+Alt+6",
    "go_campaigns": "Ctrl+Alt+7", "go_cinematics": "Ctrl+Alt+8",
    "go_analysis": "Ctrl+Alt+9", "go_publication": "Ctrl+Alt+0",
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
    """Recursive text/family/mission/reference filters, applied to stable keys."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.favorite_only = False
        self.favorites = set()
        self.family_filter = ""
        self.mission_filter = ""
        self.related_keys = None
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        identity = index.data(Qt.UserRole)
        if identity is None:
            return any(self.filterAcceptsRow(row, index)
                       for row in range(self.sourceModel().rowCount(index)))
        family, mission, identifier = identity.split("|", 2)
        if self.favorite_only and identity not in self.favorites:
            return False
        if self.family_filter and family != self.family_filter:
            return False
        if self.mission_filter and self.mission_filter not in (mission,
                                                               identifier if family == "maps" else ""):
            return False
        if self.related_keys is not None and (family, mission, identifier) not in self.related_keys:
            return False
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
        self.search.returnPressed.connect(
            lambda: self.run_item(self.listing.currentItem())
            if self.listing.currentItem() else None)
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
        self._onboarding_key = project_key(self.content_path)
        self._onboarding_done = set(normalize_completed(
            self.settings.value(self._onboarding_key + "/done", [])
            if self._onboarding_key else []))
        self._onboarding_hidden = self.settings.value(
            "onboarding/hidden", False, type=bool)
        self.last_revision = -1
        self._models = {}
        self._resource_by_key = {}
        self._selected = ()
        self.pages = {}
        self.commands = {}
        self.plugins = StudioPluginRegistry()
        self._plugin_docks = {}
        self._plugin_fields = {}
        self._active_workspace = "project"
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
        self.set_language(str(self.settings.value("language", "fr")))
        self._refresh_recent_menu()
        self._activate("project")

    def _make_home(self):
        page = QScrollArea()
        page.setObjectName("r18-home-scroll")
        page.setAccessibleName("Page Projet défilante")
        page.setWidgetResizable(True)
        self.home_scroll = page
        content = QWidget()
        panel = QVBoxLayout(content)
        title = QLabel("DrawTemp Studio 5.0")
        title.setObjectName("studio-heading")
        font = title.font()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        panel.addWidget(title)
        intro = QLabel(
            "Créez un projet et découvrez les ateliers sans modifier de fichiers JSON.")
        self.guide_intro = intro
        intro.setWordWrap(True)
        intro.setAccessibleName("Introduction au Studio DrawTemp")
        panel.addWidget(intro)
        self.guide_panel = QWidget()
        self.guide_panel.setObjectName("r18-guide-panel")
        self.guide_panel.setAccessibleName("Visite guidée du premier projet")
        guide_layout = QVBoxLayout(self.guide_panel)
        self.guide_title = QLabel("Premiers pas — projet → carte → personnages → sauvegarde → jeu")
        self.guide_title.setWordWrap(True)
        self.guide_title.setAccessibleName("Étapes de la visite guidée")
        guide_layout.addWidget(self.guide_title)
        self.guide_list = QListWidget()
        self.guide_list.setObjectName("r18-guide-steps")
        self.guide_list.setAccessibleName("Progression du premier projet")
        self.guide_list.setAccessibleDescription(
            "Les étapes sont validées après une action réussie, sans crédit fictif.")
        self.guide_list.setMinimumHeight(150)
        guide_layout.addWidget(self.guide_list)
        self.guide_hint = QLabel("")
        self.guide_hint.setWordWrap(True)
        self.guide_hint.setAccessibleName("Instruction de la prochaine étape")
        guide_layout.addWidget(self.guide_hint)
        actions = QHBoxLayout()
        self.guide_next_button = QPushButton("Démarrer ou continuer")
        self.guide_next_button.setObjectName("r18-guide-next")
        self.guide_next_button.setAccessibleName("Effectuer la prochaine étape")
        self.guide_next_button.clicked.connect(self.guide_next)
        actions.addWidget(self.guide_next_button)
        self.guide_hide_button = QPushButton("Masquer le guide")
        self.guide_hide_button.setObjectName("r18-guide-hide")
        self.guide_hide_button.setAccessibleName("Masquer le guide, réouverture dans Outils")
        self.guide_hide_button.clicked.connect(self.hide_guide)
        actions.addWidget(self.guide_hide_button)
        guide_layout.addLayout(actions)
        warning = QLabel(
            "Événements et Cinématiques : consultation possible ; "
            "édition complète depuis le shell encore à certifier.")
        self.guide_warning = warning
        warning.setWordWrap(True)
        warning.setAccessibleName("Limites actuelles des ateliers")
        guide_layout.addWidget(warning)
        panel.addWidget(self.guide_panel)
        for label, callback in (("Nouveau projet…", self.new_document),
                                ("Nouveau projet multi-genres…", self.new_project)):
            button = QPushButton(label)
            button.setAccessibleName(label)
            button.clicked.connect(callback)
            panel.addWidget(button)
        for group in (("Créer", ("profiles", "gameplay", "maps", "construction", "actors", "database", "events")),
                      ("Organiser", ("campaigns", "cinematics", "analysis", "publication"))):
            panel.addWidget(QLabel(group[0]))
            buttons = QGridLayout()
            for index, identifier in enumerate(group[1]):
                button = QPushButton(LABELS[identifier])
                button.setAccessibleName("Atelier " + LABELS[identifier])
                button.clicked.connect(lambda _checked=False, key=identifier:
                                       self.navigate(key))
                buttons.addWidget(button, index // 2, index % 2)
            panel.addLayout(buttons)
        panel.addStretch(1)
        page.setWidget(content)
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
        self.search.setPlaceholderText("Rechercher nom, ID ou mission…")
        self.search.setAccessibleName("Recherche de ressources")
        layout.addWidget(self.search)
        self.family_filter = QComboBox()
        self.family_filter.setAccessibleName("Famille de ressources")
        self.family_filter.addItem("Toutes les familles", "")
        for family, label in FAMILY_LABELS.items():
            self.family_filter.addItem(label, family)
        layout.addWidget(self.family_filter)
        self.mission_filter = QComboBox()
        self.mission_filter.setAccessibleName("Carte ou mission")
        self.mission_filter.addItem("Toutes les cartes", "")
        layout.addWidget(self.mission_filter)
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
        self.reference_filter = QComboBox()
        self.reference_filter.setAccessibleName("Relations de la sélection")
        self.reference_filter.addItems((
            "Toutes les relations", "Ressources qui la référencent",
            "Ressources qu'elle référence"))
        layout.addWidget(self.reference_filter)

        self.resource_model = QStandardItemModel(self)
        self.resource_model.setHorizontalHeaderLabels(["Ressources"])
        self.proxy = ResourceProxy(self)
        self.proxy.setSourceModel(self.resource_model)
        self.resource_view = QTreeView()
        self.resource_view.setModel(self.proxy)
        self.resource_view.setHeaderHidden(True)
        self.resource_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.resource_view.setAccessibleName("Explorateur du projet")
        self.resource_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.resource_view.customContextMenuRequested.connect(self.resource_context_menu)
        self.resource_view.selectionModel().selectionChanged.connect(
            lambda *_: self._update_selection())
        self.resource_view.doubleClicked.connect(self._open_selected_resource)
        layout.addWidget(self.resource_view, 1)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.filter.currentIndexChanged.connect(self._set_favorites_only)
        self.family_filter.currentIndexChanged.connect(self._update_resource_filters)
        self.mission_filter.currentIndexChanged.connect(self._update_resource_filters)
        self.reference_filter.currentIndexChanged.connect(self._reference_mode_changed)
        self.resource_dock = self._dock(
            "Explorateur", "r2-resource-dock", host, Qt.LeftDockWidgetArea)

    def _make_inspector_dock(self):
        host = QWidget()
        layout = QVBoxLayout(host)
        self.inspector_title = QLabel("Sélectionnez une ressource")
        layout.addWidget(self.inspector_title)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.name_edit = None
        self.property_widgets = {}
        self._property_error_labels = {}
        self._edited_fields = set()
        self._inspector_revision = self.session.revision
        self.pending_label = QLabel("")
        self.pending_label.setAccessibleName("État des modifications de l'inspecteur")
        layout.addWidget(self.pending_label)
        self.apply_button = QPushButton("Appliquer les propriétés")
        self.apply_button.clicked.connect(self.apply_selection)
        self.apply_button.setEnabled(False)
        layout.addWidget(self.apply_button)
        self.discard_button = QPushButton("Ignorer les modifications de l'inspecteur")
        self.discard_button.clicked.connect(self.discard_inspector_changes)
        self.discard_button.setEnabled(False)
        layout.addWidget(self.discard_button)
        self.inspector_error = QLabel("")
        self.inspector_error.setWordWrap(True)
        self.inspector_error.setAccessibleName("Erreur de validation des propriétés")
        layout.addWidget(self.inspector_error)
        self.references = QLabel("Aucune sélection")
        self.references.setWordWrap(True)
        self.references.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.references)
        layout.addWidget(QLabel("Références croisées — double-cliquer pour naviguer"))
        self.links = QListWidget()
        self.links.setAccessibleName("Références entrantes et sortantes")
        self.links.itemActivated.connect(self.follow_reference)
        self.links.itemDoubleClicked.connect(self.follow_reference)
        layout.addWidget(self.links, 1)
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
        self._action("new", "Nouveau projet…", self.new_document)
        self._action("new_project", "Nouveau projet multi-genres…", self.new_project)
        self._action("new_template", "Projet depuis un modèle rapide…", self.new_project_template)
        self._action("open", "Ouvrir un projet…", self.open_document)
        self._action("save", "Enregistrer le projet", self.save_document)
        self._action("save_as", "Enregistrer sous…", self.save_document_as)
        self._action("playtest", "Jouer / Playtest", self.playtest)
        self._action("export", "Exporter le Player…", self.export_player)
        self._action("preferences", "Préférences…", self.open_preferences)
        self._action("undo", "Annuler", self.undo)
        self._action("redo", "Rétablir", self.redo)
        self._action("palette", "Palette de commandes…", self.open_palette)
        self._action("guide", "Visite guidée du premier projet", self.open_guide)
        self._action("r30_creator", "Packs et revue des conflits…", self.open_creator_review)
        self._action("r31_logic", "Game Logic Studio R31…", self.open_logic_graph)
        self._action("focus_resources", "Rechercher les ressources",
                     lambda: self.search.setFocus())
        self._action("focus_inspector", "Inspecter la sélection",
                     lambda: (self.name_edit or self.resource_view).setFocus())
        for identifier in WORKSPACES:
            action = self._action(
                "go_" + identifier, "Atelier : " + LABELS[identifier],
                lambda _checked=False, key=identifier: self.navigate(key))
            action.setCheckable(True)

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("&Fichier")
        for key in ("new_project", "new", "new_template", "open"):
            file_menu.addAction(self.commands[key])
        self.recent_menu = file_menu.addMenu("Projets récents")
        self.recent_menu.aboutToShow.connect(self._refresh_recent_menu)
        for key in ("save", "save_as"):
            file_menu.addAction(self.commands[key])
        file_menu.addSeparator()
        for key in ("playtest", "export"):
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
        tools_menu.addAction(self.commands["r30_creator"])
        tools_menu.addAction(self.commands["r31_logic"])
        scripts_menu = tools_menu.addMenu("Hooks contrôlés")
        import_hooks = scripts_menu.addAction("Importer des hooks JSON…")
        import_hooks.triggered.connect(self._import_hooks_dialog)
        tools_menu.addAction(self.commands["preferences"])
        tools_menu.addAction(self.commands["guide"])
        plugin_menu = tools_menu.addMenu("Plugins Studio")
        load_plugin = plugin_menu.addAction("Charger un manifeste…")
        load_plugin.triggered.connect(self._load_plugin_dialog)
        disable_plugin = plugin_menu.addAction("Désactiver un plugin…")
        disable_plugin.triggered.connect(self._disable_plugin_dialog)
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
            preset = str(self.settings.value("window/preset", "editing"))
            self.layout_preset(preset if preset in ("editing", "analysis", "compact")
                               else "editing")

    def layout_preset(self, preset):
        if preset not in ("editing", "analysis", "compact"):
            raise ValueError("Unknown layout preset: " + str(preset))
        self.settings.setValue("window/preset", preset)
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
        self._update_guide()

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

    def open_creator_review(self):
        """One shared editor session; packs are always exported as new copies."""
        from drawtemp.studio.r30_creator_qt import R30CreatorDialog
        initial_revision = self.session.revision
        dialog = R30CreatorDialog(self.session, content_path=self.content_path, parent=self)
        dialog.exec()
        if self.session.revision != initial_revision:
            self.refresh()

    def open_logic_graph(self):
        """R31.B logic graphs share the Studio R1 owner, never a second project."""
        from drawtemp.studio.logic_graph_qt import LogicGraphDialog
        initial_revision = self.session.revision
        dialog = LogicGraphDialog(self.session, parent=self)
        dialog.updated.connect(self.refresh)
        dialog.exec()
        if self.session.revision != initial_revision:
            self.refresh()

    def _set_favorites_only(self, index):
        self.proxy.favorite_only = index == 1
        self.proxy.invalidateFilter()

    def _reference_mode_changed(self, _index):
        # Freeze anchor while displaying related resources; selecting another
        # result must not silently change the scope of the query.
        self._reference_anchor = tuple(self._selected)
        self._update_resource_filters()

    def _update_resource_filters(self, *_):
        self.proxy.family_filter = self.family_filter.currentData() or ""
        self.proxy.mission_filter = self.mission_filter.currentData() or ""
        mode = self.reference_filter.currentIndex()
        if mode:
            anchor = getattr(self, "_reference_anchor", ())
            direction = "incoming" if mode == 1 else "outgoing"
            rows = connections(self.session.snapshot(), anchor, direction)
            self.proxy.related_keys = {
                (edge.source.key if mode == 1 else edge.target.key)
                for edge in rows
            }
        else:
            self.proxy.related_keys = None
        self.proxy.invalidateFilter()
        self.resource_view.expandAll()

    @staticmethod
    def _identity(resource):
        return "|".join(resource.key)

    def _favorites(self):
        stored = self.settings.value("resources/favorites", [])
        if isinstance(stored, str):
            return {stored} if stored else set()
        return set(stored or [])

    def toggle_favorite(self):
        if not self._selected:
            return
        favorites = self._favorites()
        for resource in self._selected:
            key = self._identity(resource)
            if key in favorites:
                favorites.remove(key)
            else:
                favorites.add(key)
        self.settings.setValue("resources/favorites", sorted(favorites))
        self.proxy.favorites = favorites
        self.proxy.invalidateFilter()

    def resource_context_menu(self, point):
        index = self.resource_view.indexAt(point)
        if not index.isValid():
            return
        self.resource_view.setCurrentIndex(index)
        menu = QMenu(self.resource_view)
        menu.addAction("Ouvrir la ressource",
                       lambda: self._open_selected_resource(index))
        menu.addAction("Ajouter / retirer des favoris", self.toggle_favorite)
        menu.addSeparator()
        menu.addAction("Qui référence cette ressource ?",
                       lambda: self.reference_filter.setCurrentIndex(1))
        menu.addAction("Références utilisées",
                       lambda: self.reference_filter.setCurrentIndex(2))
        menu.exec(self.resource_view.viewport().mapToGlobal(point))

    def refresh(self):
        snapshot = self.session.snapshot()
        selected_keys = {r.key for r in self._selected}
        self._resource_by_key = {r.key: r for r in resources(snapshot)}
        selection = self.resource_view.selectionModel()
        selection.blockSignals(True)
        self.resource_model.clear()
        self.resource_model.setHorizontalHeaderLabels(["Ressources"])
        for family, title in FAMILY_LABELS.items():
            parent = QStandardItem(title)
            parent.setEditable(False)
            for resource in self._resource_by_key.values():
                if resource.family != family:
                    continue
                label = resource.title + " · " + resource.resource_id
                if resource.mission_id:
                    label += "  [" + resource.mission_id + "]"
                child = QStandardItem(label)
                child.setEditable(False)
                child.setData(self._identity(resource), Qt.UserRole)
                child.setToolTip(resource.resource_id)
                parent.appendRow(child)
            if parent.rowCount():
                self.resource_model.appendRow(parent)
        # Family, mission and favorite filters are UI preferences, not part of
        # GameProject. A project switch preserves the type filter, but clears an
        # invalid mission scope.
        mission = self.mission_filter.currentData() or ""
        self.mission_filter.blockSignals(True)
        self.mission_filter.clear()
        self.mission_filter.addItem("Toutes les cartes", "")
        for resource in self._resource_by_key.values():
            if resource.family == "maps":
                self.mission_filter.addItem(resource.title, resource.resource_id)
        pos = self.mission_filter.findData(mission)
        self.mission_filter.setCurrentIndex(max(0, pos))
        self.mission_filter.blockSignals(False)
        self.proxy.favorites = self._favorites()
        self._update_resource_filters()
        self._selected = tuple(r for k, r in self._resource_by_key.items()
                               if k in selected_keys)
        for row in range(self.resource_model.rowCount()):
            parent = self.resource_model.item(row)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                identity = child.data(Qt.UserRole)
                if identity and tuple(identity.split("|", 2)) in selected_keys:
                    mapped = self.proxy.mapFromSource(child.index())
                    if mapped.isValid():
                        selection.select(mapped, QItemSelectionModel.Select |
                                         QItemSelectionModel.Rows)
        selection.blockSignals(False)
        self.last_revision = snapshot.revision
        self._refresh_plugins(snapshot)
        for name in ("profiles", "gameplay"):
            if name in self._models:
                self._models[name].refresh()
        self._show_inspector()
        self._update_title()
        self.commands["undo"].setEnabled(snapshot.can_undo)
        self.commands["redo"].setEnabled(snapshot.can_redo)
        self._update_guide()

    def _refresh_if_changed(self):
        if self.last_revision != self.session.revision:
            if self._edited_fields:
                # A background revision must not silently overwrite an
                # uncommitted form. Keep it visible, but block stale commits.
                self.last_revision = self.session.revision
                self._validate_inspector_draft()
            else:
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
                key = tuple(identity.split("|", 2))
                if key in self._resource_by_key:
                    selected.append(self._resource_by_key[key])
        # An active relation filter retains its original selection even when
        # the anchor is itself hidden by the filtered result set.
        if selected:
            self._selected = tuple(selected)
        elif self.reference_filter.currentIndex() == 0:
            self._selected = ()
        self._show_inspector()

    def _mark_property_edit(self, key):
        self._edited_fields.add(key)
        self._validate_inspector_draft()

    def _validate_inspector_draft(self):
        for label in self._property_error_labels.values():
            label.clear()
        if not self._edited_fields:
            self.inspector_error.setText("")
            self.pending_label.setText("")
            self.apply_button.setEnabled(False)
            self.discard_button.setEnabled(False)
            return False
        self.discard_button.setEnabled(True)
        if self.session.revision != self._inspector_revision:
            self.inspector_error.setText(
                "Le projet a changé pendant la saisie. Ignorez les modifications "
                "de l'inspecteur puis recommencez sur les données actualisées.")
            self.pending_label.setText("Saisie obsolète — application bloquée")
            self.apply_button.setEnabled(False)
            return False
        updates, parsing_errors = {}, {}
        for key in sorted(self._edited_fields):
            widget, spec = self.property_widgets[key]
            try:
                updates[key] = self._field_value(widget, spec)
            except InspectorError as exc:
                parsing_errors[key] = str(exc)
        errors = dict(parsing_errors)
        if updates:
            try:
                _, invalid = validate_draft(
                    self.session.snapshot(), self._selected, updates)
                errors.update(invalid)
            except InspectorError as exc:
                self.inspector_error.setText(str(exc))
                self.apply_button.setEnabled(False)
                return False
        for key, message in errors.items():
            self._property_error_labels[key].setText(message)
            self.property_widgets[key][0].setToolTip(message)
        for key in self._edited_fields - set(errors):
            self.property_widgets[key][0].setToolTip("")
        self.pending_label.setText(
            str(len(self._edited_fields)) + " propriété(s) à appliquer "
            "sur " + str(len(self._selected)) + " ressource(s)")
        self.inspector_error.setText(next(iter(errors.values()), ""))
        self.apply_button.setEnabled(not errors)
        return not errors

    def discard_inspector_changes(self):
        """Explicitly discard only staged widgets; never undo R1 content."""
        self.refresh()

    def _show_inspector(self):
        chosen = self._selected
        snapshot = self.session.snapshot()
        self._inspector_revision = snapshot.revision
        self._edited_fields = set()
        self.property_widgets.clear()
        self._property_error_labels.clear()
        self.name_edit = None
        while self.form.rowCount():
            self.form.removeRow(0)
        self.inspector_error.setText("")
        self.apply_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.pending_label.setText("")
        self.inspector_title.setText(
            str(len(chosen)) + " ressource(s) sélectionnée(s)" if chosen else
            "Sélectionnez une ressource dans l'explorateur")
        self.links.clear()
        if not chosen:
            self.references.setText("Aucune sélection")
            return
        try:
            specs = shared_specs(snapshot, chosen)
            for spec in specs:
                value, mixed = common_value(snapshot, chosen, spec.key)
                if spec.kind == "int" and not mixed:
                    widget = QSpinBox()
                    widget.setRange(spec.minimum, spec.maximum)
                    widget.setValue(value)
                    widget.valueChanged.connect(
                        lambda _v, key=spec.key: self._mark_property_edit(key))
                elif spec.kind == "int":
                    widget = QLineEdit()
                    widget.setValidator(QIntValidator(spec.minimum, spec.maximum, widget))
                    widget.setPlaceholderText("Valeurs multiples — saisir un entier")
                    widget.textEdited.connect(
                        lambda _v, key=spec.key: self._mark_property_edit(key))
                elif spec.kind == "bool":
                    widget = QCheckBox()
                    widget.setTristate(mixed)
                    widget.setCheckState(Qt.PartiallyChecked if mixed else
                                         (Qt.Checked if value else Qt.Unchecked))
                    widget.stateChanged.connect(
                        lambda _v, key=spec.key: self._mark_property_edit(key))
                elif spec.kind == "multiline":
                    widget = QPlainTextEdit()
                    widget.setFixedHeight(100)
                    widget.setPlainText("" if mixed else value)
                    if mixed:
                        widget.setPlaceholderText("Valeurs multiples")
                    widget.textChanged.connect(
                        lambda key=spec.key: self._mark_property_edit(key))
                else:
                    widget = QLineEdit("" if mixed else value)
                    if mixed:
                        widget.setPlaceholderText("Valeurs multiples")
                    widget.textEdited.connect(
                        lambda _v, key=spec.key: self._mark_property_edit(key))
                widget.setAccessibleName(spec.label)
                holder = QWidget()
                holder_layout = QVBoxLayout(holder)
                holder_layout.setContentsMargins(0, 0, 0, 0)
                holder_layout.setSpacing(2)
                holder_layout.addWidget(widget)
                field_error = QLabel("")
                field_error.setWordWrap(True)
                field_error.setStyleSheet("color: #d35454")
                field_error.setAccessibleName(
                    "Erreur de validation : " + spec.label)
                holder_layout.addWidget(field_error)
                self.form.addRow(spec.label, holder)
                self.property_widgets[spec.key] = (widget, spec)
                self._property_error_labels[spec.key] = field_error
                if spec.key in ("name", "title") and self.name_edit is None:
                    self.name_edit = widget
            self.references.setText(
                "Identifiant(s) stable(s) : " +
                ", ".join(r.resource_id for r in chosen) +
                "\nLes identifiants et références ne sont pas modifiés par l'inspecteur.")
            for direction, title in (("incoming", "← Référencée par"),
                                     ("outgoing", "→ Référence")):
                for edge in connections(snapshot, chosen, direction):
                    other = edge.source if direction == "incoming" else edge.target
                    item = self._link_item(
                        title + " : " + other.title + " (" + other.family + ")",
                        other.key, edge.path)
                    self.links.addItem(item)
        except (InspectorError, ValueError) as exc:
            self.inspector_error.setText(str(exc))

    def _link_item(self, title, identity, path):
        from PySide6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, identity)
        item.setToolTip(path)
        return item

    def _field_value(self, widget, spec):
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            if widget.checkState() == Qt.PartiallyChecked:
                raise InspectorError(spec.label + " : choisir Oui ou Non")
            return widget.isChecked()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if spec.kind == "int":
            try:
                return int(widget.text().strip())
            except ValueError as exc:
                raise InspectorError(spec.label + " : entier attendu") from exc
        return widget.text()

    def apply_selection(self):
        if not self._validate_inspector_draft():
            return False
        try:
            updates = {key: self._field_value(*self.property_widgets[key])
                       for key in self._edited_fields}
            edit_properties(self.session, self._selected, updates,
                            expected_revision=self._inspector_revision)
            self.refresh()
            return True
        except (AuthoringError, InspectorError, ValueError) as exc:
            self.inspector_error.setText(str(exc))
            self.problems.addItem("Inspecteur : " + str(exc))
            self.statusBar().showMessage(str(exc))
            return False

    def follow_reference(self, item):
        identity = item.data(Qt.UserRole)
        if identity:
            self.focus_resource(tuple(identity))

    def focus_resource(self, identity):
        """Reveal one resource across all facets, then navigate precisely."""
        self.search.clear()
        self.reference_filter.setCurrentIndex(0)
        self.filter.setCurrentIndex(0)
        self.family_filter.setCurrentIndex(0)
        self.mission_filter.setCurrentIndex(0)
        for row in range(self.resource_model.rowCount()):
            parent = self.resource_model.item(row)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                if tuple(child.data(Qt.UserRole).split("|", 2)) == identity:
                    index = self.proxy.mapFromSource(child.index())
                    if index.isValid():
                        self.resource_view.selectionModel().setCurrentIndex(
                            index, QItemSelectionModel.ClearAndSelect |
                            QItemSelectionModel.Rows)
                        self.resource_view.scrollTo(index)
                        self.resource_view.setFocus()
                        return True
        return False

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
        elif destination == "actors":
            child = self._models.get("database")
            if child is not None:
                child.tree.setCurrentItem(child.tree.topLevelItem(1))
                child._reload_items(("actors", resource.resource_id, resource.mission_id))
        elif destination == "campaigns":
            child = self._models.get("campaigns")
            if child is not None:
                row = child.campaign.findData(resource.resource_id)
                if row >= 0:
                    child.campaign.setCurrentIndex(row)

    def navigate(self, identifier):
        host = workspace_host(identifier)
        if identifier == "actors" and "database" in self._models:
            database = self._models["database"]
            database.tree.setCurrentItem(database.tree.topLevelItem(1))
        if host not in self.pages:
            try:
                self._make_workspace(host)
            except Exception as exc:
                self.report_error(exc)
                return
        if identifier == "construction":
            self.pages["construction"] = self.pages["maps"]
        if identifier in ("maps", "construction"):
            # R6 shares the exact viewport and authoring session of R5.
            self._models["maps"].mode.setCurrentIndex(
                1 if identifier == "construction" else 0)
        self._activate(identifier)
        if identifier == "maps":
            self._guide_mark("map")
        elif identifier == "actors":
            self._guide_mark("actor")

    def _activate(self, identifier):
        self.workspace_tabs.setCurrentWidget(self.pages[identifier])
        self._active_workspace = identifier
        for name in WORKSPACES:
            self.commands["go_" + name].setChecked(name == identifier)
        self.statusBar().showMessage("Atelier : " + LABELS[identifier])

    def _make_workspace(self, identifier):
        if identifier in ("database", "actors") and "database" in self._models:
            child = self._models["database"]
            self.pages[identifier] = child
            self.pages["database"] = child
            if identifier == "actors":
                child.tree.setCurrentItem(child.tree.topLevelItem(1))
            return
        if identifier == "profiles":
            from drawtemp.studio.profile_editor_qt import ProfileEditorWidget
            child = ProfileEditorWidget(self.session)
            child.updated.connect(self.refresh)
        elif identifier == "gameplay":
            from drawtemp.studio.genre_rules_qt import GenreRulesWorkspace
            child = GenreRulesWorkspace(self.session)
            child.updated.connect(self.refresh)
        elif identifier == "maps":
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
        elif identifier == "publication":
            child = self._publication_page()
        else:
            child = self._overview(identifier)
        if identifier in ("profiles", "gameplay", "maps", "database", "campaigns"):
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

    def _publication_page(self):
        page = QWidget()
        panel = QVBoxLayout(page)
        panel.addWidget(QLabel("Publication du projet"))
        description = QLabel(
            "Le Player autonome est exporté par R15 avec validation des "
            "assets, licences et runtime natif. Aucun export n'est lancé "
            "sans contrôle explicite.")
        description.setWordWrap(True)
        panel.addWidget(description)
        play = QPushButton("Playtest du projet enregistré")
        play.clicked.connect(self.playtest)
        panel.addWidget(play)
        export = QPushButton("Vérifier et exporter le Player…")
        export.clicked.connect(self.export_player)
        panel.addWidget(export)
        panel.addStretch(1)
        return page

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
        if listing.count() == 0:
            empty = QLabel(
                "Aucune ressource dans cet atelier. "
                "Créez une ressource dans l’éditeur spécialisé, "
                "ou ouvrez un projet contenant déjà des données.")
            empty.setObjectName("r18-empty-workspace")
            empty.setWordWrap(True)
            empty.setAccessibleName("Aucune ressource dans cet atelier")
            layout.addWidget(empty)
        return page

    def apply_controlled_hooks(self, path, *, grants):
        """Opt-in import into native narrative effects; editor remains owner."""
        source = read_script_manifest(path)
        result = install_script(
            self.session, source, granted_permissions=grants,
            expected_revision=self.session.revision)
        self.refresh()
        self.problems.addItem("Hooks contrôlés importés : " + source["id"])
        return result

    def _import_hooks_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer hooks contrôlés", "", "JSON (*.json)")
        if not path:
            return
        try:
            source = read_script_manifest(path)
            approved = QMessageBox.question(
                self, "Permissions des hooks",
                source["id"] + "\n\nActions autorisées :\n" +
                "\n".join("• " + item for item in source["permissions"]) +
                "\n\nCes effets deviendront des données natives du GameProject "
                "(annulables avant sauvegarde). Autoriser ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if approved == QMessageBox.Yes:
                self.apply_controlled_hooks(path, grants=source["permissions"])
        except (StudioScriptError, AuthoringError, ValueError, OSError) as exc:
            self.report_error(exc)

    # R24.B: only the host creates widgets and commits edits. A plugin is
    # inert JSON; it never owns a QWidget, callback, model or Editor session.
    def install_plugin_manifest(self, path, *, grants):
        manifest = read_studio_manifest(path)
        plugin_id = manifest["id"]
        self.plugins.install(manifest)
        try:
            self.plugins.enable(plugin_id, grants=grants)
            self._mount_plugin(plugin_id)
            self._refresh_plugins(self.session.snapshot())
        except Exception as exc:
            self.plugins.quarantine(plugin_id, exc)
            self._unmount_plugin(plugin_id)
            raise
        return plugin_id

    def _mount_plugin(self, plugin_id):
        status = self.plugins.status(plugin_id)
        if not status["enabled"]:
            raise StudioPluginError("permission_denied", "Plugin is disabled")
        host = QWidget()
        layout = QVBoxLayout(host)
        contributions = self.plugins.definition(plugin_id)
        for panel in contributions["panels"]:
            heading = QLabel(panel["title"])
            heading.setTextFormat(Qt.PlainText)
            layout.addWidget(heading)
            description = QLabel(panel["description"])
            description.setTextFormat(Qt.PlainText)
            description.setWordWrap(True)
            layout.addWidget(description)
            for field in panel["fields"]:
                label = QLabel()
                label.setTextFormat(Qt.PlainText)
                label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                label.setAccessibleName("Plugin " + panel["id"] + " " + field)
                layout.addWidget(label)
                self._plugin_fields[(plugin_id, panel["id"], field)] = label
        for template in contributions["templates"]:
            button = QPushButton(template["label"])
            button.setAccessibleName("Plugin " + plugin_id + " " + template["id"])
            button.clicked.connect(
                lambda _checked=False, pid=plugin_id, tid=template["id"]:
                self._apply_plugin_template(pid, tid))
            layout.addWidget(button)
        layout.addStretch(1)
        dock = self._dock("Plugin : " + status["name"],
                          "r24-plugin-" + plugin_id, host, Qt.RightDockWidgetArea)
        self._plugin_docks[plugin_id] = dock
        dock.show()

    def _unmount_plugin(self, plugin_id):
        dock = self._plugin_docks.pop(plugin_id, None)
        if dock is not None:
            self.removeDockWidget(dock)
            dock.hide()
            dock.deleteLater()
        for key in tuple(self._plugin_fields):
            if key[0] == plugin_id:
                del self._plugin_fields[key]

    def _plugin_failure(self, plugin_id, exc):
        self.plugins.quarantine(plugin_id, exc)
        self._unmount_plugin(plugin_id)
        message = "Plugin " + plugin_id + " désactivé : " + str(exc)
        self.problems.addItem(message)
        self.statusBar().showMessage(message)
        log.warning("%s", message)

    def _refresh_plugins(self, snapshot):
        for plugin_id, dock in tuple(self._plugin_docks.items()):
            try:
                panels = self.plugins.definition(plugin_id)["panels"]
                for panel in panels:
                    state = self.plugins.panel_state(plugin_id, panel["id"], snapshot)
                    for field, value in state["fields"]:
                        label = self._plugin_fields[(plugin_id, panel["id"], field)]
                        label.setText(field + " : " + str(value))
            except Exception as exc:
                self._plugin_failure(plugin_id, exc)

    def _apply_plugin_template(self, plugin_id, template_id):
        try:
            self.plugins.apply_template(
                plugin_id, template_id, self.session,
                expected_revision=self.session.revision)
            self.refresh()
        except (StudioPluginError, AuthoringError, ValueError) as exc:
            message = "Plugin " + plugin_id + " : " + str(exc)
            self.problems.addItem(message)
            self.statusBar().showMessage(message)
        except Exception as exc:
            self._plugin_failure(plugin_id, exc)

    def _load_plugin_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Manifeste de plugin Studio", "", "JSON (*.json)")
        if not path:
            return
        try:
            manifest = read_studio_manifest(path)
            permissions = manifest["permissions"]
            accepted = QMessageBox.question(
                self, "Autorisations du plugin",
                manifest["name"] + "\n\nPermissions demandées :\n" +
                "\n".join("• " + permission for permission in permissions) +
                "\n\nAutoriser ce manifeste dans cette session Studio ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if accepted != QMessageBox.Yes:
                return
            self.install_plugin_manifest(path, grants=permissions)
        except (StudioPluginError, ValueError, OSError) as exc:
            self.report_error(exc)

    def _disable_plugin_dialog(self):
        active = [status for status in self.plugins.statuses() if status["enabled"]]
        if not active:
            self.statusBar().showMessage("Aucun plugin actif")
            return
        names = [status["id"] for status in active]
        selected, accepted = QInputDialog.getItem(
            self, "Plugins Studio", "Désactiver le plugin", names, 0, False)
        if accepted:
            self.plugins.disable(selected)
            self._unmount_plugin(selected)
            self.statusBar().showMessage("Plugin désactivé : " + selected)

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

    def _guide_switch_document(self, path, *, keep_visits=()):
        """Rebind stored guide evidence after a successful document switch."""
        self._onboarding_key = project_key(path)
        saved = normalize_completed(
            self.settings.value(self._onboarding_key + "/done", []))
        self._onboarding_done = set(saved) | set(keep_visits) | {"project"}
        self._persist_guide()
        self._update_guide()

    def _persist_guide(self):
        if self._onboarding_key:
            self.settings.setValue(
                self._onboarding_key + "/done",
                sorted(self._onboarding_done & set(STEP_IDS)))

    def _guide_mark(self, identifier):
        if not self.content_path or identifier not in STEP_IDS:
            return
        if identifier in self._onboarding_done:
            return
        # A navigation command is not evidence of an editable resource unless
        # a corresponding canonical map/actor actually exists.
        steps = journey_steps(
            self.session.snapshot(), self._onboarding_done,
            content_path=self.content_path)
        current = next(step for step in steps if step.identifier == identifier)
        if not current.available:
            self._update_guide()
            return
        self._onboarding_done.add(identifier)
        self._persist_guide()
        self._update_guide()

    def _update_guide(self):
        if not hasattr(self, "guide_list"):
            return
        self.guide_panel.setVisible(not self._onboarding_hidden)
        language = str(self.settings.value("language", "fr"))
        if language not in GUIDE_UI:
            language = "fr"
        ui = GUIDE_UI[language]
        self.guide_intro.setText(ui["intro"])
        self.guide_panel.setAccessibleName(ui["panel"])
        self.guide_list.setAccessibleName(ui["steps"])
        self.guide_hint.setAccessibleName(ui["hint"])
        self.guide_next_button.setAccessibleName(ui["next"])
        self.guide_hide_button.setText(ui["hide"])
        self.guide_warning.setText(ui["warning"])
        steps = journey_steps(
            self.session.snapshot(), self._onboarding_done,
            content_path=self.content_path, language=language)
        self.guide_list.clear()
        completed = sum(step.done for step in steps)
        for step in steps:
            prefix = "✓ " if step.done else "○ "
            self.guide_list.addItem(prefix + step.title)
            item = self.guide_list.item(self.guide_list.count() - 1)
            item.setToolTip(step.instructions + (
                "\n" + step.blocker if step.blocker else ""))
        self.guide_title.setText(ui["progress"].format(
            done=completed, total=len(steps)))
        upcoming = next_step(steps)
        if upcoming is None:
            self.guide_hint.setText(ui["complete"])
            self.guide_next_button.setEnabled(False)
            return
        self.guide_hint.setText(
            upcoming.instructions +
            ("\n" + upcoming.blocker if upcoming.blocker else ""))
        self.guide_next_button.setText(
            ui["new"] if upcoming.identifier == "project" else
            ui["workspace"] if upcoming.identifier in ("map", "actor") else
            ui["save"] if upcoming.identifier == "save" else ui["playtest"])
        # Project creation also remains possible when no file is yet open;
        # missing map/actor blockers require explicit resource creation.
        self.guide_next_button.setEnabled(
            upcoming.available or upcoming.identifier in ("map", "actor"))

    def guide_next(self):
        steps = journey_steps(
            self.session.snapshot(), self._onboarding_done,
            content_path=self.content_path)
        step = next_step(steps)
        if step is None:
            return
        actions = {
            "project": self.new_project,
            "map": lambda: self.navigate("maps"),
            "actor": lambda: self.navigate("actors"),
            "save": self.save_document,
            "playtest": self.playtest,
        }
        actions[step.identifier]()

    def open_guide(self):
        self._onboarding_hidden = False
        self.settings.setValue("onboarding/hidden", False)
        self.navigate("project")
        self._update_guide()
        target = (self.guide_next_button if self.guide_next_button.isEnabled()
                  else self.guide_list)
        self.home_scroll.ensureWidgetVisible(target)
        target.setFocus(Qt.ShortcutFocusReason)

    def hide_guide(self):
        self._onboarding_hidden = True
        self.settings.setValue("onboarding/hidden", True)
        self._update_guide()

    def _record_recent(self, path):
        items = recent_projects(self.settings.value("files/recent", []),
                                selected=path)
        self.settings.setValue("files/recent", items)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        paths = recent_projects(self.settings.value("files/recent", []))
        if not paths:
            item = self.recent_menu.addAction("Aucun projet récent")
            item.setEnabled(False)
        for path in paths:
            name = Path(path).name
            label = name + " — " + path
            if not Path(path).is_file():
                label += " (introuvable)"
            action = self.recent_menu.addAction(label)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, selected=path: self.open_path(selected))

    def _install_document(self, fresh, path):
        """Replace one canonical R1 session only after the new one is valid."""
        self.workspace_tabs.setCurrentWidget(self.pages["project"])
        old_pages = {page for name, page in self.pages.items() if name != "project"}
        self.pages = {"project": self.pages["project"]}
        for page in old_pages:
            self.workspace_tabs.removeWidget(page)
            page.setParent(None)
            page.deleteLater()
        self._models.clear()
        self._selected = ()
        self._reference_anchor = ()
        self.reference_filter.setCurrentIndex(0)
        self.session = fresh
        self.content_path = Path(path)
        self._activate("project")
        self.refresh()
        self._record_recent(path)
        # A loaded project is proof of a completed open/create action.
        self._guide_switch_document(path)

    def open_path(self, path):
        if not self._confirm_leave():
            return False
        try:
            fresh = AuthoringSession.open(path)
        except (AuthoringError, OSError, ValueError) as exc:
            self.report_error(exc)
            return False
        self._install_document(fresh, path)
        return True

    def create_project(self, kind, destination):
        if not self._confirm_leave():
            return False
        from drawtemp.export.templates import create_template
        try:
            created = create_template(kind, destination)
            fresh = AuthoringSession.open(created / "game.json")
        except (AuthoringError, OSError, ValueError) as exc:
            self.report_error(exc)
            return False
        self._install_document(fresh, created / "game.json")
        return True

    def new_project_template(self):
        from drawtemp.export.templates import TEMPLATES
        kind, accepted = QInputDialog.getItem(
            self, "Nouveau projet", "Modèle", list(TEMPLATES), 0, False)
        if not accepted:
            return
        parent = QFileDialog.getExistingDirectory(
            self, "Dossier parent du projet")
        if not parent:
            return
        name, accepted = QInputDialog.getText(
            self, "Nouveau projet", "Nom du dossier à créer", text="DrawTempProject")
        if not accepted:
            return
        name = name.strip()
        if name in ("", ".", "..") or Path(name).name != name or "\\" in name:
            self.report_error(ValueError("Nom de dossier invalide"))
            return
        self.create_project(kind, Path(parent) / name)

    def new_document(self):
        """R22: use the canonical CreatorDialog and shared R1 session."""
        from drawtemp.studio.r15_creator import CreatorDialog
        dialog = CreatorDialog(self)
        if dialog.exec() != QDialog.Accepted or dialog.created_content_path is None:
            return False
        return self.open_path(dialog.created_content_path)

    def new_project(self):
        """R28: guided multi-genre flow without a second Studio session."""
        from drawtemp.studio.genre_wizard_qt import GenreProjectWizard
        dialog = GenreProjectWizard(self)
        if dialog.exec() != QDialog.Accepted or dialog.created_content_path is None:
            return False
        return self.open_path(dialog.created_content_path)

    def save_document(self):
        try:
            if self.content_path is None:
                return self.save_document_as()
            self.session.save()
            self.refresh()
            self._record_recent(self.content_path)
            self._guide_mark("save")
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
            # The document identity becomes persistent only after both files
            # have been saved successfully. Preserve prior in-memory visits.
            previous_visits = self._onboarding_done & {"map", "actor"}
            self.content_path = Path(path)
            self._guide_switch_document(path, keep_visits=previous_visits)
            self.refresh()
            self._record_recent(path)
            self._guide_mark("save")
            return True
        except (AuthoringError, OSError) as exc:
            self.report_error(exc)
            return False

    def _saved_for_player(self):
        if self.content_path is None or self.session.snapshot().dirty:
            return self.save_document()
        return True

    def playtest(self):
        if not self._saved_for_player():
            return False
        try:
            started, _pid = QProcess.startDetached(
                sys.executable, ["-m", "drawtemp.player.qt_app",
                                 "--content", str(self.content_path)])
            if not started:
                raise OSError("Le processus Player Qt n'a pas démarré.")
        except (OSError, RuntimeError) as exc:
            self.report_error(exc)
            return False
        self.statusBar().showMessage("Player Qt lancé : " + str(self.content_path))
        # A successful Player launch against a clean, persisted pair proves
        # that the pair has been saved, even if it was opened from disk.
        self._guide_mark("save")
        self._guide_mark("playtest")
        return True

    def export_player(self):
        if not self._saved_for_player():
            return False
        from drawtemp.studio.r15_creator import CreatorDialog
        dialog = CreatorDialog(self)
        dialog.mode.setCurrentIndex(2)
        dialog.source.setText(str(self.content_path))
        dialog.exec()
        return True

    def open_preferences(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Préférences du Studio")
        form = QFormLayout(dialog)
        theme = QComboBox()
        theme.addItems(["dark", "light"])
        theme.setCurrentText(str(self.settings.value("theme", "dark")))
        form.addRow("Thème", theme)
        language = QComboBox()
        language.addItems(["fr", "en"])
        language.setCurrentText(str(self.settings.value("language", "fr")))
        form.addRow("Langue du shell", language)
        scale = QComboBox()
        scale.addItems(["90", "100", "115", "130"])
        scale.setCurrentText(str(self.settings.value("scale", 100)))
        form.addRow("Échelle (%)", scale)
        apply_button = QPushButton("Appliquer")
        apply_button.clicked.connect(dialog.accept)
        form.addRow(apply_button)
        if dialog.exec() == QDialog.Accepted:
            self.set_theme(theme.currentText())
            self.set_language(language.currentText())
            self.set_scale(int(scale.currentText()))

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
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir Content + GameProject", "", "Content JSON (*.json)")
        if path:
            return self.open_path(path)
        return False

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
        if args.content:
            window._record_recent(args.content)
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
