"""Workspace navigation for the Tk Studio.

Presentation only: all editors remain in the canonical Notebook, so direct
notebook.select() calls, history, validation and gameplay keep working.
"""
from __future__ import annotations

import unicodedata


SECTIONS = (
    "Carte & monde",
    "Contenu",
    "Événements",
    "Campagne",
    "Présentation",
    "Analyse",
    "Projet",
    "Autres",
)


def _fold(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def section_for(title):
    """Classify an existing editor title without changing its identity."""
    name = _fold(title)
    if name == "carte et combat" or name.startswith("monde"):
        return "Carte & monde"
    if name.startswith(("personnages", "bibliotheque d'acte")):
        return "Contenu"
    if any(term in name for term in (
        "evenement", "scenario", "dialogue", "narratif", "condition",
        "variable",
    )):
        return "Événements"
    if any(term in name for term in (
        "campagne", "mission", "siege", "jeu, campagnes",
    )):
        return "Campagne"
    if any(term in name for term in ("cinemati", "musique", "audio", "son &")):
        return "Présentation"
    if any(term in name for term in (
        "battle lab", "battle la", "balance", "playtest",
    )):
        return "Analyse"
    if any(term in name for term in ("espace projet", "donnees json")):
        return "Projet"
    return "Autres"


class StudioNavigation:
    """Compact category bar and view switcher for the existing Tk Notebook.

    Hidden visual tab labels are optional and reversible; tab identities,
    selection events, and all cross-editor links stay unchanged.
    """

    def __init__(self, parent, notebook, tools, map_tab, tk, ttk):
        self.notebook = notebook
        self.tools = tools
        self.map_tab = str(map_tab)
        self.tk, self.ttk = tk, ttk
        self.section = tk.StringVar(value="Carte & monde")
        self.view = tk.StringVar()
        self.show_tabs = tk.BooleanVar(value=False)
        self.history = {}
        self.group_tabs = {}
        self.buttons = {}
        self.compact_choice = tk.StringVar(value="Carte & monde")
        self._compact = None

        shell = ttk.Frame(parent, padding=(6, 5, 6, 3))
        shell.pack(fill="x")
        sections = ttk.Frame(shell)
        sections.pack(side="left", fill="x", expand=True)
        self.sections = sections
        for category in SECTIONS:
            widget = ttk.Radiobutton(
                sections, text=category, value=category,
                variable=self.section, style="Toolbutton",
                command=lambda value=category: self.choose_section(value),
            )
            widget.pack(side="left", padx=(0, 3))
            self.buttons[category] = widget
        self.compact_box = ttk.Combobox(
            sections, textvariable=self.compact_choice,
            values=SECTIONS, state="readonly", width=21)
        self.compact_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.choose_section(self.compact_choice.get()))

        chooser = ttk.Frame(shell)
        chooser.pack(side="right", padx=(10, 0))
        ttk.Label(chooser, text="Vue").pack(side="left", padx=(0, 5))
        self.view_box = ttk.Combobox(
            chooser, textvariable=self.view, state="readonly", width=27
        )
        self.view_box.pack(side="left")
        self.view_box.bind("<<ComboboxSelected>>", self.choose_view)
        ttk.Checkbutton(
            chooser, text="Onglets", variable=self.show_tabs,
            command=self.toggle_tabs,
        ).pack(side="left", padx=(10, 0))

        style = ttk.Style()
        # A Notebook remains the only owner of the editor frames. The empty
        # tab layout removes the unreadable row of dozens of truncated labels.
        # Users can restore native tabs with the explicit "Onglets" option.
        try:
            style.layout("Studio.TNotebook.Tab", [])
            self.toggle_tabs()
        except tk.TclError:
            # On unsupported platform themes the native tabs remain usable.
            self.show_tabs.set(True)
            self.notebook.configure(style="TNotebook")
        self.rebuild()
        notebook.bind("<<NotebookTabChanged>>", self.sync, add="+")
        self.sync()
        shell.bind("<Configure>", self._adapt, add="+")

    def _adapt(self, event):
        """One category selector at narrow widths; editor tabs stay mounted."""
        compact = event.width < 1280
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            for button in self.buttons.values():
                button.pack_forget()
            self.compact_box.pack(side="left", padx=(0, 5))
        else:
            self.compact_box.pack_forget()
            for category in SECTIONS:
                self.buttons[category].pack(side="left", padx=(0, 3))

    def toggle_tabs(self):
        self.notebook.configure(
            style="TNotebook" if self.show_tabs.get() else "Studio.TNotebook"
        )

    def rebuild(self):
        groups = {name: [] for name in SECTIONS}
        for tab in self.notebook.tabs():
            title = self.notebook.tab(tab, "text")
            groups[section_for(title)].append((title, tab))
        self.group_tabs = groups
        for name, button in self.buttons.items():
            if groups[name]:
                button.state(["!disabled"])
            else:
                button.state(["disabled"])

    def choose_section(self, name):
        options = self.group_tabs.get(name, ())
        if not options:
            return
        remembered = self.history.get(name)
        tab = next((tab for _, tab in options if tab == remembered),
                   options[0][1])
        self.notebook.select(tab)
        self.sync()

    def choose_view(self, _event=None):
        name = self.view.get()
        for title, tab in self.group_tabs.get(self.section.get(), ()):
            if title == name:
                self.notebook.select(tab)
                return

    def sync(self, _event=None):
        # An editor may register an additional page after shell creation.
        if sum(map(len, self.group_tabs.values())) != len(self.notebook.tabs()):
            self.rebuild()
        # External navigation (Workspace, Problems, shortcut, restore_layout,
        # or a specialised editor) is reflected in this bar.
        selected = self.notebook.select()
        if not selected:
            return
        title = self.notebook.tab(selected, "text")
        group = section_for(title)
        self.history[group] = selected
        self.section.set(group)
        self.view_box.configure(
            values=[label for label, _ in self.group_tabs.get(group, ())]
        )
        self.view.set(title)
        self.compact_choice.set(group)
        if selected == self.map_tab:
            if not self.tools.winfo_manager():
                self.tools.pack(fill="x", padx=6, pady=(0, 3),
                                before=self.notebook)
        elif self.tools.winfo_manager():
            self.tools.pack_forget()
