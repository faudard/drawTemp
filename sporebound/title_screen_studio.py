"""A dedicated, visual title-screen editor (no tactical-editor coupling).

Changes are authored in the existing GameProject manifest and participate in
Studio history, recovery and normal project saving. No Player actions execute in
the preview.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from shutil import copy2

from .game_project import GameProject
from .title_menu_cinematic import CinematicTitleMenu, title_geometry
from .title_screen_settings import (
    DEFAULTS, LABEL_KEYS, STRING_KEYS, LANGUAGES, NAMESPACE,
    ENGLISH_LABELS, ENGLISH_CAPTIONS, FRENCH_STRINGS, ENGLISH_STRINGS,
    display_text, extra_box, extension_for, settings_for,
)
from .title_screen_layout import ELEMENTS, CARD_KEYS, placement, relocate, resolve_boxes


class TitleScreenStudio:
    """Separate Title Screen tab: author presentation, preview, then apply."""

    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.tab = self.ttk.Frame(notebook)
        notebook.add(self.tab, text="Title Screen")
        self.tab.columnconfigure(1, weight=1)
        self.tab.columnconfigure(2, weight=0)
        self.tab.rowconfigure(0, weight=1)

        left = self.ttk.Frame(self.tab, width=305)
        left.grid(row=0, column=0, sticky="ns", padx=(7, 3), pady=7)
        left.grid_propagate(False)
        scroll = self.tk.Canvas(left, highlightthickness=0, width=284)
        bar = self.ttk.Scrollbar(left, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=bar.set)
        scroll.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        controls = self.ttk.Frame(scroll)
        window = scroll.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", lambda _e: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda e: scroll.itemconfigure(window, width=e.width))

        self.title = self.tk.StringVar()
        self.subtitle = self.tk.StringVar()
        self.background = self.tk.StringVar()
        self.image = self.tk.StringVar()
        self.accent = self.tk.StringVar()
        self.panel = self.tk.StringVar()
        self.text = self.tk.StringVar()
        self.show_campaign = self.tk.BooleanVar()
        self.labels = {key: self.tk.StringVar() for key in LABEL_KEYS}
        self._image_cache = None
        self._image_key = None
        self._photo = None
        self._positions = {}
        self._last_boxes = {}
        self._drag = None
        self._undo_moves = []
        self._redo_moves = []
        self._preview_transform = (0.0, 0.0, 1.0)
        self.selected = self.tk.StringVar(value="title")
        self.position_x = self.tk.StringVar()
        self.position_y = self.tk.StringVar()
        self.language = self.tk.StringVar(value="en")
        self._source_language = "en"
        self._base_title = ""
        self._base_subtitle = ""
        self._base_labels = {}
        self._base_captions = {}
        self._base_strings = {}
        self._translations = {}
        self._extras = []
        self._hidden = []
        self._syncing = False
        self._extra_photos = {}
        self.element_text = self.tk.StringVar()
        self.element_caption = self.tk.StringVar()
        self.element_third = self.tk.StringVar()
        self.element_fourth = self.tk.StringVar()
        self.element_color = self.tk.StringVar()
        self.element_size = self.tk.StringVar()
        self.element_width = self.tk.StringVar()
        self.element_height = self.tk.StringVar()

        self.ttk.Label(controls, text="Title Screen Editor",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=8, pady=(8, 3))
        self.ttk.Label(controls, text="Edit game UI · click elements in preview",
                       wraplength=264).pack(anchor="w", padx=8, pady=(0, 12))
        self.ttk.Label(controls, text="Language (preview / game)",
                       font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=8)
        self.ttk.Combobox(controls, textvariable=self.language,
                          state="readonly", values=LANGUAGES).pack(
                              fill="x", padx=8, pady=(3, 7))
        for caption, variable in (("Game title", self.title), ("Subtitle", self.subtitle)):
            self._entry(controls, caption, variable)

        self.ttk.Label(controls, text="Background", font=("TkDefaultFont", 10, "bold")
                       ).pack(anchor="w", padx=8, pady=(10, 2))
        self.ttk.Combobox(controls, textvariable=self.background, state="readonly",
                          values=("auto", "solid", "image")).pack(
                              fill="x", padx=8, pady=(1, 5))
        self.ttk.Label(controls, text="auto = packaged art; solid = no picture",
                       wraplength=264).pack(anchor="w", padx=8)
        self._entry(controls, "Relative image path (art/...)", self.image)
        self.ttk.Button(controls, text="Import background image…",
                        command=lambda: owner._run(self.import_image)).pack(
                            fill="x", padx=8, pady=(1, 8))

        self.ttk.Label(controls, text="Colors (#RRGGBB)",
                       font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        for caption, variable in (("Accent / border", self.accent),
                                  ("Card background", self.panel),
                                  ("Text", self.text)):
            self._entry(controls, caption, variable)
        self.ttk.Checkbutton(controls, text="Show current campaign card",
                             variable=self.show_campaign).pack(anchor="w", padx=8, pady=(5, 10))
        self.ttk.Label(controls, text="Action labels (current language)",
                       font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=8, pady=(5, 2))
        self.ttk.Label(controls, text="Actions and keyboard navigation remain connected.",
                       wraplength=264).pack(anchor="w", padx=8, pady=(0, 5))
        for (key, default, _caption, _icon) in CinematicTitleMenu.ACTIONS:
            self._entry(controls, key.title(), self.labels[key])

        self.ttk.Label(controls, text="Layout · drag objects in the preview",
                       font=("TkDefaultFont", 10, "bold")).pack(
                           anchor="w", padx=8, pady=(12, 2))
        self.ttk.Label(controls, text="Move: click and drag. Positions are relative "
                       "to the game window. Ctrl+Z/Ctrl+Y: undo/redo moves.",
                       wraplength=264).pack(anchor="w", padx=8, pady=(1, 7))
        self.element_selector = self.ttk.Combobox(
            controls, textvariable=self.selected, values=ELEMENTS, state="readonly")
        self.element_selector.pack(fill="x", padx=8, pady=4)
        self.selected.trace_add("write", lambda *_args: self._on_select())
        coords = self.ttk.Frame(controls)
        coords.pack(fill="x", padx=8, pady=4)
        self.ttk.Label(coords, text="X %").grid(row=0, column=0, sticky="w")
        self.ttk.Entry(coords, textvariable=self.position_x, width=9).grid(
            row=1, column=0, padx=(0, 8), sticky="ew")
        self.ttk.Label(coords, text="Y %").grid(row=0, column=1, sticky="w")
        self.ttk.Entry(coords, textvariable=self.position_y, width=9).grid(
            row=1, column=1, sticky="ew")
        coords.columnconfigure(0, weight=1)
        coords.columnconfigure(1, weight=1)
        self.ttk.Button(controls, text="Set position",
                        command=lambda: owner._run(self.set_position)).pack(
                            fill="x", padx=8, pady=2)
        self.ttk.Button(controls, text="Reset selected position",
                        command=self.reset_selected).pack(
                            fill="x", padx=8, pady=2)
        movement_buttons = self.ttk.Frame(controls)
        movement_buttons.pack(fill="x", padx=8, pady=7)
        self.ttk.Button(movement_buttons, text="Undo move",
                        command=self.undo_move).pack(side="left", padx=3)
        self.ttk.Button(movement_buttons, text="Redo move",
                        command=self.redo_move).pack(side="left", padx=3)

        buttons = self.ttk.Frame(controls)
        buttons.pack(fill="x", padx=8, pady=15)
        self.ttk.Button(buttons, text="Apply changes",
                        command=lambda: owner._run(self.apply)).pack(fill="x", pady=2)
        self.ttk.Button(buttons, text="Save project…",
                        command=lambda: owner._run(self.save)).pack(
                            fill="x", pady=2)
        self.ttk.Button(buttons, text="Restore defaults",
                        command=self.defaults).pack(fill="x", pady=2)
        self.ttk.Label(controls, text="Apply changes before saving. "
                       "Undo/Redo and recovery include these settings.",
                       wraplength=260).pack(anchor="w", padx=8, pady=(0, 18))

        preview_frame = self.ttk.Frame(self.tab)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 8), pady=7)
        preview_frame.rowconfigure(1, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.ttk.Label(preview_frame, text="Editable title scene · drag elements · no game actions in preview"
                       ).grid(row=0, column=0, sticky="w", pady=(3, 8))
        self.canvas = self.tk.Canvas(preview_frame, background="#101b2a",
                                     highlightthickness=1, highlightbackground="#788294")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.paint())
        self.canvas.bind("<ButtonPress-1>", self._pointer_down)
        self.canvas.bind("<B1-Motion>", self._pointer_move)
        self.canvas.bind("<ButtonRelease-1>", self._pointer_up)
        self.canvas.bind("<Escape>", self._cancel_drag)
        self.canvas.bind("<Control-z>", lambda _e: self.undo_move())
        self.canvas.bind("<Control-y>", lambda _e: self.redo_move())
        # A separate inspector stays visible while the original global
        # settings and game preview remain accessible.
        right = self.ttk.Frame(self.tab, width=270)
        right.grid(row=0, column=2, sticky="nsew", padx=(3, 8), pady=7)
        right.grid_propagate(False)
        self.ttk.Label(right, text="Elements / Inspector",
                       font=("TkDefaultFont", 12, "bold")).pack(
                           anchor="w", padx=7, pady=(7, 5))
        hierarchy = self.ttk.Frame(right)
        hierarchy.pack(fill="x", padx=7)
        self.element_list = self.tk.Listbox(hierarchy, height=8, exportselection=False)
        self.element_list.pack(side="left", fill="both", expand=True)
        bar = self.ttk.Scrollbar(hierarchy, orient="vertical",
                                 command=self.element_list.yview)
        bar.pack(side="right", fill="y")
        self.element_list.configure(yscrollcommand=bar.set)
        self.element_list.bind("<<ListboxSelect>>", self._list_selection)
        tools = self.ttk.Frame(right)
        tools.pack(fill="x", padx=7, pady=4)
        for caption, handler in (("+ Text", self.add_text),
                                 ("+ Image / logo", lambda: owner._run(self.add_image)),
                                 ("Delete / Hide", self.delete_selected),
                                 ("Show", self.show_selected)):
            self.ttk.Button(tools, text=caption,
                            command=handler).pack(fill="x", pady=2)
        property_container = self.ttk.Frame(right)
        property_container.pack(fill="both", expand=True, padx=2)
        property_canvas = self.tk.Canvas(property_container, highlightthickness=0,
                                         width=254, borderwidth=0)
        property_bar = self.ttk.Scrollbar(property_container, orient="vertical",
                                          command=property_canvas.yview)
        property_canvas.configure(yscrollcommand=property_bar.set)
        property_canvas.pack(side="left", fill="both", expand=True)
        property_bar.pack(side="right", fill="y")
        inspector = self.ttk.Frame(property_canvas)
        property_window = property_canvas.create_window(
            (0, 0), window=inspector, anchor="nw")
        inspector.bind("<Configure>", lambda _event: property_canvas.configure(
            scrollregion=property_canvas.bbox("all")))
        property_canvas.bind("<Configure>", lambda event:
            property_canvas.itemconfigure(property_window, width=event.width))
        self.ttk.Label(inspector, text="Selected element properties",
                       font=("TkDefaultFont", 10, "bold")).pack(
                           anchor="w", padx=7, pady=(10, 3))
        for caption, variable in (("Text / label", self.element_text),
                                  ("Description / subtitle", self.element_caption),
                                  ("Third label (footer Help)", self.element_third),
                                  ("Fourth label (footer brand)", self.element_fourth),
                                  ("Color (#RRGGBB)", self.element_color),
                                  ("Font size (extra text)", self.element_size),
                                  ("Width % (extras)", self.element_width),
                                  ("Height % (extras)", self.element_height)):
            self._entry(inspector, caption, variable)
        self.ttk.Button(inspector, text="Choose color…",
                        command=self.choose_color).pack(fill="x", padx=8, pady=2)
        self.ttk.Button(inspector, text="Apply selected properties",
                        command=lambda: owner._run(self.apply_selected)).pack(
                            fill="x", padx=8, pady=4)
        self.ttk.Button(inspector, text="Bring forward",
                        command=lambda: self.reorder_selected(1)).pack(
                            fill="x", padx=8, pady=2)
        self.ttk.Button(inspector, text="Send backward",
                        command=lambda: self.reorder_selected(-1)).pack(
                            fill="x", padx=8, pady=2)
        self.ttk.Label(inspector, text="Built-in buttons can be hidden; "
                       "their internal commands are never deleted. "
                       "New text and image elements can be removed.",
                       wraplength=250).pack(anchor="w", padx=8, pady=10)
        for var in (self.title, self.subtitle, self.background, self.image,
                    self.accent, self.panel, self.text, self.show_campaign,
                    *self.labels.values()):
            var.trace_add("write", lambda *_args: self.paint())
        self.language.trace_add("write", lambda *_args: self._show_locale())
        self.title.trace_add("write", lambda *_args: self._store_locale("title", "", self.title.get()))
        self.subtitle.trace_add("write", lambda *_args: self._store_locale("subtitle", "", self.subtitle.get()))
        for key in LABEL_KEYS:
            self.labels[key].trace_add("write", lambda *_args, k=key:
                self._store_locale("labels", k, self.labels[k].get()))

    def _entry(self, parent, caption, variable):
        self.ttk.Label(parent, text=caption).pack(anchor="w", padx=8, pady=(4, 1))
        self.ttk.Entry(parent, textvariable=variable).pack(fill="x", padx=8, pady=(0, 5))

    def _draft_settings(self):
        return dict(source_language=self._source_language,
                    labels=self._base_labels, captions=self._base_captions,
                    strings=self._base_strings, translations=self._translations)

    def _store_locale(self, group, key, value):
        if self._syncing:
            return
        language = self.language.get()
        if language == self._source_language:
            if group == "title":
                self._base_title = value
            elif group == "subtitle":
                self._base_subtitle = value
            else:
                target = {"labels": self._base_labels,
                          "captions": self._base_captions,
                          "strings": self._base_strings}.get(group)
                if target is not None:
                    target[key] = value
        else:
            entry = self._translations.setdefault(language, {})
            if group in ("title", "subtitle"):
                entry[group] = value
            else:
                entry.setdefault(group, {})[key] = value

    def _translated(self, group, key, fallback):
        return display_text(self._draft_settings(), self.language.get(),
                            group, key, fallback)

    def _show_locale(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            self.title.set(self._translated("title", "", self._base_title))
            self.subtitle.set(self._translated("subtitle", "", self._base_subtitle))
            defaults = {row[0]: row[1] for row in CinematicTitleMenu.ACTIONS}
            for key in LABEL_KEYS:
                self.labels[key].set(self._translated("labels", key, defaults[key]))
        finally:
            self._syncing = False
        self._sync_inspector()
        self.paint()

    def _extra_for(self, key):
        if not key.startswith("extra:"):
            return None
        return next((item for item in self._extras
                     if item["id"] == key.split(":", 1)[1]), None)

    def _refresh_elements(self):
        selected = self.selected.get()
        choices = list(ELEMENTS) + ["extra:" + e["id"] for e in self._extras]
        self.element_selector.configure(values=choices)
        self.element_list.delete(0, "end")
        for key in choices:
            label = key + ("  [hidden]" if key in self._hidden else "")
            self.element_list.insert("end", label)
        if selected not in choices:
            selected = "title"
            self.selected.set(selected)
        self.element_list.selection_clear(0, "end")
        self.element_list.selection_set(choices.index(selected))
        self.element_list.see(choices.index(selected))

    def _list_selection(self, _event=None):
        if self.element_list.curselection():
            choices = list(ELEMENTS) + ["extra:" + e["id"] for e in self._extras]
            index = self.element_list.curselection()[0]
            if index < len(choices) and self.selected.get() != choices[index]:
                self.selected.set(choices[index])

    def _on_select(self):
        self._refresh_elements()
        self._sync_selected_position()
        self._sync_inspector()
        self.paint()

    def _sync_inspector(self):
        if not hasattr(self, "element_text"):
            return
        key = self.selected.get()
        item = self._extra_for(key)
        actions = {("campaign_action" if row[0] == "campaign" else row[0]): row
                   for row in CinematicTitleMenu.ACTIONS}
        value, subvalue, third, fourth = "", "", "", ""
        color = self.text.get() or DEFAULTS["text"]
        size, width, height = "", "", ""
        if key == "title":
            value = self.title.get()
        elif key == "subtitle":
            value = self.subtitle.get()
            color = self.accent.get()
        elif key == "logo":
            value = self._translated("strings", "logo", "⚜")
            color = self.accent.get()
        elif key in actions:
            action, _name, caption, _icon = actions[key]
            value = self.labels[action].get()
            subvalue = self._translated("captions", action, caption)
        elif key == "campaign":
            value = self._translated("strings", "campaign_heading",
                                     FRENCH_STRINGS["campaign_heading"])
            subvalue = self._translated("strings", "campaign_change",
                                        FRENCH_STRINGS["campaign_change"])
        elif key == "footer":
            value = self._translated("strings", "advanced",
                                     FRENCH_STRINGS["advanced"])
            subvalue = self._translated("strings", "credits",
                                        FRENCH_STRINGS["credits"])
            third = self._translated("strings", "help", FRENCH_STRINGS["help"])
            fourth = self._translated("strings", "footer_brand",
                                       FRENCH_STRINGS["footer_brand"])
        elif item is not None:
            value = self._translated("extras", item["id"], item["text"])
            color = item["color"]
            size = str(item["size"])
            width = "%.1f" % (item["width"] * 100)
            height = "%.1f" % (item["height"] * 100)
        self._syncing = True
        try:
            for variable, content in (
                (self.element_text, value), (self.element_caption, subvalue),
                (self.element_third, third), (self.element_fourth, fourth),
                (self.element_color, color), (self.element_size, size),
                (self.element_width, width), (self.element_height, height)):
                variable.set(content)
        finally:
            self._syncing = False

    def _import_asset(self):
        from tkinter import filedialog
        name = filedialog.askopenfilename(
            title="Import title-screen image or logo",
            filetypes=[("Pictures", "*.png *.jpg *.jpeg")])
        if not name:
            return ""
        source = Path(name)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("Only PNG and JPEG assets are supported")
        if source.suffix.lower() != ".png":
            try:
                import PIL  # noqa: F401
            except ImportError as exc:
                raise ValueError("JPEG assets require Pillow; use PNG instead") from exc
        destination_dir = self.owner.project_path.parent / "art" / "title_screen"
        destination_dir.mkdir(parents=True, exist_ok=True)
        digest = sha256(source.read_bytes()).hexdigest()[:16]
        destination = destination_dir / (digest + source.suffix.lower())
        if source.resolve() != destination.resolve() and not destination.exists():
            copy2(source, destination)
        return destination.relative_to(self.owner.project_path.parent).as_posix()

    def _new_extra(self, kind, image=""):
        used = {item["id"] for item in self._extras}
        index = 1
        while kind + str(index) in used:
            index += 1
        self._remember_move()
        item = dict(id=kind + str(index), kind=kind,
                    text="Your text" if kind == "text" else "",
                    image=image, color=self.text.get() or DEFAULTS["text"],
                    size=32, x=0.15, y=0.15, width=0.32, height=0.10)
        self._extras.append(item)
        self.selected.set("extra:" + item["id"])
        self._refresh_elements()
        self.paint()

    def add_text(self):
        self._new_extra("text")

    def add_image(self):
        image = self._import_asset()
        if image:
            self._new_extra("image", image=image)

    def delete_selected(self):
        key = self.selected.get()
        if key.startswith("extra:"):
            self._remember_move()
            self._extras = [item for item in self._extras
                            if "extra:" + item["id"] != key]
            for translation in self._translations.values():
                translation.get("extras", {}).pop(key.split(":", 1)[1], None)
            self.selected.set("title")
        elif key in ELEMENTS and key not in self._hidden:
            self._remember_move()
            self._hidden.append(key)
        self._refresh_elements()
        self.paint()

    def show_selected(self):
        key = self.selected.get()
        if key in self._hidden:
            self._remember_move()
            self._hidden.remove(key)
            self._refresh_elements()
            self.paint()

    def choose_color(self):
        from tkinter import colorchooser
        selection = colorchooser.askcolor(
            color=self.element_color.get(), title="Element color")
        if selection[1]:
            self.element_color.set(selection[1])

    def apply_selected(self):
        key = self.selected.get()
        item = self._extra_for(key)
        value = self.element_text.get()
        subtitle = self.element_caption.get()
        color = self.element_color.get()
        if not self._valid_color(color, ""):
            raise ValueError("Color must use #RRGGBB")
        actions = {("campaign_action" if row[0] == "campaign" else row[0]): row
                   for row in CinematicTitleMenu.ACTIONS}
        if item is not None:
            size = int(self.element_size.get())
            width = float(self.element_width.get()) / 100
            height = float(self.element_height.get()) / 100
            if not (8 <= size <= 120 and 0 < width <= 1 and 0 < height <= 1):
                raise ValueError("Extra dimensions/size are outside allowed limits")
            self._remember_move()
            item["size"], item["width"], item["height"] = size, width, height
            item["color"] = color
            if item["kind"] == "text":
                if self.language.get() == self._source_language:
                    item["text"] = value
                else:
                    self._translations.setdefault(self.language.get(), {}).setdefault(
                        "extras", {})[item["id"]] = value
        elif key == "title":
            self.title.set(value)
            self.text.set(color)
        elif key == "subtitle":
            self.subtitle.set(value)
            self.accent.set(color)
        elif key == "logo":
            self._store_locale("strings", "logo", value)
            self.accent.set(color)
        elif key in actions:
            action = actions[key][0]
            self.labels[action].set(value)
            self._store_locale("captions", action, subtitle)
            self.text.set(color)
        elif key == "campaign":
            self._store_locale("strings", "campaign_heading", value)
            self._store_locale("strings", "campaign_change", subtitle)
            self.text.set(color)
        elif key == "footer":
            self._store_locale("strings", "advanced", value)
            self._store_locale("strings", "credits", subtitle)
            self._store_locale("strings", "help", self.element_third.get())
            self._store_locale("strings", "footer_brand",
                               self.element_fourth.get())
            self.text.set(color)
        if item is not None:
            item["x"] = min(item["x"], 1 - item["width"])
            item["y"] = min(item["y"], 1 - item["height"])
        self.paint()

    def reorder_selected(self, step):
        item = self._extra_for(self.selected.get())
        if item is None:
            return
        index = self._extras.index(item)
        target = min(max(0, index + step), len(self._extras) - 1)
        if target != index:
            self._remember_move()
            self._extras.insert(target, self._extras.pop(index))
            self._refresh_elements()
            self.paint()

    def load(self):
        if self.owner.project is None:
            return
        settings = settings_for(self.owner.project)
        self._syncing = True
        try:
            self._source_language = (settings["source_language"]
                                     or self.owner.project.options.get("language", "fr"))
            self._base_title = self.owner.project.title
            self._base_subtitle = self.owner.project.subtitle
            self._base_labels = deepcopy(settings["labels"])
            self._base_captions = deepcopy(settings["captions"])
            self._base_strings = deepcopy(settings["strings"])
            self._translations = deepcopy(settings["translations"])
            self._extras = deepcopy(settings["extras"])
            self._hidden = list(settings["hidden"])
            self._positions = deepcopy(settings["positions"])
            self._undo_moves.clear()
            self._redo_moves.clear()
            self._extra_photos.clear()
            self._drag = None
            self.language.set(self.owner.project.options.get("language", "fr"))
            for field in ("background", "image", "accent", "panel",
                          "text", "show_campaign"):
                getattr(self, field).set(settings[field])
        finally:
            self._syncing = False
        self._show_locale()
        self._refresh_elements()
        self._sync_selected_position()

    def defaults(self):
        self._remember_move()
        self._positions = {}
        self._extras = []
        self._hidden = []
        self._translations = {}
        self._base_labels = {}
        self._base_captions = {}
        self._base_strings = {}
        self._extra_photos.clear()
        for key in ("background", "image", "accent", "panel",
                    "text", "show_campaign"):
            getattr(self, key).set(deepcopy(DEFAULTS[key]))
        self._show_locale()
        self._refresh_elements()

    def _settings(self):
        defaults = {row[0]: row[1] for row in CinematicTitleMenu.ACTIONS}
        captions = {row[0]: row[2] for row in CinematicTitleMenu.ACTIONS}
        labels = {key: value for key, value in self._base_labels.items()
                  if value != defaults[key]}
        changed_captions = {key: value for key, value in self._base_captions.items()
                            if value != captions[key]}
        strings = {key: value for key, value in self._base_strings.items()
                   if value != FRENCH_STRINGS.get(key, "")}
        edited = dict(background=self.background.get(), image=self.image.get(),
                      accent=self.accent.get(), panel=self.panel.get(),
                      text=self.text.get(), show_campaign=self.show_campaign.get(),
                      labels=labels, positions=deepcopy(self._positions),
                      captions=changed_captions, strings=strings,
                      hidden=list(self._hidden), extras=deepcopy(self._extras),
                      translations=deepcopy(self._translations),
                      source_language="")
        if any(edited[key] != DEFAULTS[key] for key in DEFAULTS):
            edited["source_language"] = self._source_language
        return edited

    def pending(self):
        if self.owner.project is None:
            return False
        current = settings_for(self.owner.project)
        edited = self._settings()
        return (self._base_title != self.owner.project.title
                or self._base_subtitle != self.owner.project.subtitle
                or self.language.get() != self.owner.project.options.get("language", "fr")
                or any(edited[key] != current[key] for key in DEFAULTS))

    def _snapshot(self):
        return (deepcopy(self._positions), deepcopy(self._extras),
                list(self._hidden))

    def _restore_snapshot(self, state):
        self._positions, self._extras, self._hidden = deepcopy(state)
        self._refresh_elements()
        self.paint()
        self._sync_selected_position()
        self._sync_inspector()

    def _remember_move(self):
        self._undo_moves.append(self._snapshot())
        if len(self._undo_moves) > 50:
            self._undo_moves.pop(0)
        self._redo_moves.clear()

    def undo_move(self):
        if self._undo_moves:
            self._redo_moves.append(self._snapshot())
            self._restore_snapshot(self._undo_moves.pop())

    def redo_move(self):
        if self._redo_moves:
            self._undo_moves.append(self._snapshot())
            self._restore_snapshot(self._redo_moves.pop())

    def reset_selected(self):
        key = self.selected.get()
        item = self._extra_for(key)
        if item is not None:
            self._remember_move()
            item["x"], item["y"] = 0.15, 0.15
        elif key in self._positions:
            self._remember_move()
            self._positions.pop(key)
        self.paint()
        self._sync_selected_position()

    def _sync_selected_position(self):
        key = self.selected.get()
        box = self._last_boxes.get(key)
        if box:
            self.position_x.set("%.2f" % (box[0] / 11.6))
            self.position_y.set("%.2f" % (box[1] / 8.2))
        else:
            self.position_x.set("")
            self.position_y.set("")

    def set_position(self):
        x, y = float(self.position_x.get()), float(self.position_y.get())
        if not (0 <= x <= 100 and 0 <= y <= 100):
            raise ValueError("Coordinates must be between 0 and 100 percent")
        key = self.selected.get()
        if key not in self._last_boxes:
            raise ValueError("Select a visible title-screen element")
        proposed = relocate(self._last_boxes[key], x * 11.6, y * 8.2, 1160, 820)
        item = self._extra_for(key)
        self._remember_move()
        if item is not None:
            item["x"], item["y"] = proposed[0] / 1160, proposed[1] / 820
        else:
            self._positions[key] = placement(proposed, 1160, 820)
        self.paint()
        self._sync_selected_position()

    def _pointer_coords(self, event):
        ox, oy, scale = self._preview_transform
        return ((event.x - ox) / scale, (event.y - oy) / scale)

    def _pointer_down(self, event):
        self.canvas.focus_set()
        x, y = self._pointer_coords(event)
        choices = list(ELEMENTS) + ["extra:" + e["id"] for e in self._extras]
        for key in reversed(choices):
            if key in self._hidden or (
                    key == "campaign" and not self.show_campaign.get()):
                continue
            bounds = self._last_boxes.get(key)
            if bounds and bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]:
                self.selected.set(key)
                self._drag = (key, x, y, bounds, self._snapshot())
                self.canvas.configure(cursor="fleur")
                self.paint()
                return
        self._drag = None

    def _pointer_move(self, event):
        if self._drag is None:
            return
        key, start_x, start_y, original, _initial = self._drag
        x, y = self._pointer_coords(event)
        moved = relocate(original, original[0] + x - start_x,
                         original[1] + y - start_y, 1160, 820)
        item = self._extra_for(key)
        if item is not None:
            item["x"], item["y"] = placement(moved, 1160, 820)
        else:
            self._positions[key] = placement(moved, 1160, 820)
        self.paint()
        self._sync_selected_position()

    def _pointer_up(self, _event):
        if self._drag is not None:
            initial = self._drag[4]
            if self._snapshot() != initial:
                self._undo_moves.append(initial)
                if len(self._undo_moves) > 50:
                    self._undo_moves.pop(0)
                self._redo_moves.clear()
        self._drag = None
        self.canvas.configure(cursor="")
        self.paint()

    def _cancel_drag(self, _event=None):
        if self._drag is not None:
            state = self._drag[4]
            self._drag = None
            self.canvas.configure(cursor="")
            self._restore_snapshot(state)

    def apply(self):
        data = deepcopy(self.owner.project.to_dict())
        data["title"] = self._base_title
        data["subtitle"] = self._base_subtitle
        data["options"]["language"] = self.language.get()
        appearance = self._settings()
        if appearance == DEFAULTS:
            data.setdefault("extensions", {}).pop(NAMESPACE, None)
        else:
            data.setdefault("extensions", {})[NAMESPACE] = extension_for(appearance)
        new_project = GameProject.from_dict(data, self.owner._content())
        self.owner.project = new_project
        self.owner.title.set(new_project.title)
        self.owner.subtitle.set(new_project.subtitle)
        self.owner.project_status.config(
            text="Title Screen applied. Save the game project to persist changes.")
        self.owner.refresh()

    def save(self):
        self.apply()
        self.owner.save_project()

    def import_image(self):
        from tkinter import filedialog
        name = filedialog.askopenfilename(
            title="Import title screen background",
            filetypes=[("Pictures", "*.png *.jpg *.jpeg"), ("All files", "*.*")])
        if not name:
            return
        source = Path(name)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("Only PNG and JPEG backgrounds are supported")
        if source.suffix.lower() != ".png":
            try:
                import PIL  # noqa: F401
            except ImportError as exc:
                raise ValueError("JPEG backgrounds require Pillow; use PNG instead") from exc
        destination_dir = self.owner.project_path.parent / "art" / "title_screen"
        destination_dir.mkdir(parents=True, exist_ok=True)
        digest = sha256(source.read_bytes()).hexdigest()[:16]
        destination = destination_dir / (digest + source.suffix.lower())
        if source.resolve() != destination.resolve() and not destination.exists():
            copy2(source, destination)
        self.image.set(destination.relative_to(self.owner.project_path.parent).as_posix())
        self.background.set("image")

    @staticmethod
    def _valid_color(candidate, fallback):
        return (candidate if len(candidate) == 7 and candidate.startswith("#")
                and all(c in "0123456789abcdefABCDEF" for c in candidate[1:])
                else fallback)

    def _background_photo(self, canvas_w, canvas_h):
        mode = self.background.get()
        if mode == "solid":
            return None
        if mode == "image":
            path = self.image.get()
            if not path.startswith("art/") or ".." in Path(path).parts:
                return None
            root = self.owner.project_path.parent.resolve()
            candidate = (root / path).resolve()
            if not candidate.is_relative_to(root):
                return None
        elif any(c["id"] == "jeanne" for c in self.owner.project.campaigns):
            candidate = (Path(__file__).resolve().parent / "content" / "art" /
                         "jeanne" / "jeanne_menu_stage.jpg")
        else:
            return None
        if not candidate.is_file():
            return None
        key = (str(candidate), canvas_w, canvas_h)
        if key == self._image_key:
            return self._photo
        self._image_key = key
        self._photo = None
        try:
            from PIL import Image, ImageOps, ImageTk
            with Image.open(candidate) as file:
                photo = ImageOps.fit(file.convert("RGB"), (canvas_w, canvas_h),
                    method=Image.Resampling.LANCZOS if hasattr(Image, "Resampling")
                    else Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(photo, master=self.canvas)
        except (ImportError, OSError, ValueError):
            if candidate.suffix.lower() == ".png":
                try:
                    self._photo = self.tk.PhotoImage(file=str(candidate), master=self.canvas)
                except self.tk.TclError:
                    pass
        return self._photo

    def _preview_overlay_image(self, path, width, height):
        root = self.owner.project_path.parent.resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        width, height = max(1, round(width)), max(1, round(height))
        key = (str(candidate), width, height, candidate.stat().st_mtime_ns)
        if key in self._extra_photos:
            return self._extra_photos[key]
        try:
            from PIL import Image, ImageTk
            with Image.open(candidate) as handle:
                resampling = (Image.Resampling.LANCZOS if hasattr(Image, "Resampling")
                              else Image.LANCZOS)
                result = ImageTk.PhotoImage(handle.convert("RGBA").resize(
                    (width, height), resampling), master=self.canvas)
        except (ImportError, OSError, ValueError):
            if candidate.suffix.lower() != ".png":
                return None
            try:
                source = self.tk.PhotoImage(file=str(candidate), master=self.canvas)
                factor = max(1, round(max(source.width() / width,
                                          source.height() / height)))
                result = source.subsample(factor)
            except self.tk.TclError:
                return None
        self._extra_photos[key] = result
        if len(self._extra_photos) > 64:
            self._extra_photos = {key: result}
        return result

    def paint(self):
        """Draw in the same logical 1160x820 coordinate system as the Player.

        Letterbox instead of distorting the preview. Every draggable hit region
        is resolved with the exact same geometry helper as the real Player.
        """
        if self.owner.project is None or not self.canvas.winfo_exists():
            return
        canvas = self.canvas
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 20 or h < 20:
            return
        scale = min(w / 1160.0, h / 820.0)
        ox, oy = (w - 1160 * scale) / 2, (h - 820 * scale) / 2
        self._preview_transform = (ox, oy, scale)
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, h, fill="#090f19", outline="")
        def xy(x, y):
            return ox + x * scale, oy + y * scale
        def rect(x0, y0, x1, y1, **kwargs):
            ax, ay = xy(x0, y0)
            bx, by = xy(x1, y1)
            return canvas.create_rectangle(ax, ay, bx, by, **kwargs)
        def label(x, y, value, size, color, *, anchor="center",
                  bold=True, width=None, **kwargs):
            options = dict(text=value, fill=color, anchor=anchor,
                           font=("Georgia", max(7, round(size * scale)),
                                 "bold" if bold else "normal"))
            if width is not None:
                options["width"] = width * scale
            options.update(kwargs)
            return canvas.create_text(*xy(x, y), **options)

        accent = self._valid_color(self.accent.get(), DEFAULTS["accent"])
        panel = self._valid_color(self.panel.get(), DEFAULTS["panel"])
        foreground = self._valid_color(self.text.get(), DEFAULTS["text"])
        legacy = title_geometry(1160, 820)
        boxes = resolve_boxes(1160, 820, legacy, self._positions)
        for item in self._extras:
            boxes["extra:" + item["id"]] = extra_box(item, 1160, 820)
        self._last_boxes = boxes
        rect(0, 0, 1160, 820, fill="#101b2a", outline="")
        scenic_width = 1160 * .73
        photo = self._background_photo(max(1, round(scenic_width * scale)),
                                        max(1, round(820 * scale)))
        if photo is not None:
            canvas.create_image(*xy(0, 0), image=photo, anchor="nw")
        # Match the Player's fixed right-hand stage, independent of card moves.
        rect(legacy["menu_x"] - 8, 0, 1160, 820,
             fill="#101b2a", outline="")
        name, sep, sub = self.title.get().partition(" — ")
        if not sep:
            name, sep, sub = self.title.get().partition(" - ")
        if not sep:
            name, sub = self.title.get(), ""
        logo = boxes["logo"]
        title = boxes["title"]
        subtitle = boxes["subtitle"]
        if "logo" not in self._hidden:
            label((logo[0]+logo[2])/2, logo[1],
                  self._translated("strings", "logo", "⚜"), 24,
                  accent, anchor="n")
        if "title" not in self._hidden:
            label((title[0]+title[2])/2, title[1], name or "Game Title", 39,
                  foreground, anchor="n", width=title[2]-title[0])
        if "subtitle" not in self._hidden:
            label((subtitle[0]+subtitle[2])/2, subtitle[1],
                  self.subtitle.get().upper()
                  if (self.pending() or self._settings()["source_language"])
                  else (sub or self.subtitle.get()).upper(),
                  12, accent, anchor="n", width=subtitle[2]-subtitle[0])

        for key, default, description, _icon in CinematicTitleMenu.ACTIONS:
            item_key = "campaign_action" if key == "campaign" else key
            if item_key in self._hidden:
                continue
            x0, y0, x1, y1 = boxes[item_key]
            description = self._translated("captions", key, description)
            ch = y1-y0
            rect(x0, y0, x1, y1, fill=panel, outline=accent)
            icon_w = min(93, max(63, round(legacy["menu_width"] * .19)))
            rect(x0+1, y0+1, x0+icon_w, y1-1,
                 fill="#203249", outline="")
            label(x0+icon_w/2, (y0+y1)/2, "✦", 18, accent)
            tx = x0+icon_w+13
            label(tx, y0+ch*.34, self.labels[key].get() or default, 20,
                  foreground, anchor="w", width=x1-tx-29)
            label(tx, y0+ch*.71, description, 10, "#c0ccda",
                  anchor="w", bold=False, width=x1-tx-29)
            label(x1-15, (y0+y1)/2, "›", 19, accent)

        if self.show_campaign.get() and "campaign" not in self._hidden:
            x0, y0, x1, y1 = boxes["campaign"]
            rect(x0, y0, x1, y1, fill="#101b2a", outline=accent)
            label(x0+15, y0+14,
                  self._translated("strings", "campaign_heading", "Current campaign"), 12,
                  accent, anchor="nw")
            campaign = self.owner.project.campaigns[0]
            label(x0+15, y0+70, campaign["name"], 14, foreground,
                  anchor="nw", width=x1-x0-30)
            label(x0+15, y1-42, "⇆  " + self._translated(
                "strings", "campaign_change", "Change campaign"), 11,
                  foreground, anchor="nw")

        if "footer" not in self._hidden:
            fx0, fy0, fx1, fy1 = boxes["footer"]
            fw = fx1-fx0
            gap = 9
            widths = (fw*.48, fw*.245, fw*.275)
            for idx, (cw, caption_key) in enumerate(zip(
                    widths, ("advanced", "credits", "help"))):
                x0 = fx0 + sum(widths[:idx]) + gap * idx
                x1 = x0 + cw - (gap if idx == 2 else 0)
                rect(x0, fy0, x1, fy1, fill="#101a29", outline=accent)
                label((x0+x1)/2, (fy0+fy1)/2,
                      self._translated("strings", caption_key,
                                       ENGLISH_STRINGS[caption_key]),
                      11, foreground)
            rect(0, 789, 152, 820, fill="#101b2a", outline="")
            label(25, 796,
                  self._translated("strings", "footer_brand", "DrawTemp · Player"),
                  10, "#b8becc", anchor="nw", bold=False)
        for item in self._extras:
            x0, y0, x1, y1 = boxes["extra:" + item["id"]]
            if item["kind"] == "text":
                label(x0, y0, self._translated("extras", item["id"], item["text"]),
                      item["size"], item["color"], anchor="nw",
                      width=x1-x0)
            else:
                photo = self._preview_overlay_image(
                    item["image"], (x1-x0)*scale, (y1-y0)*scale)
                if photo is not None:
                    canvas.create_image(*xy(x0, y0), image=photo, anchor="nw")

        selected = self.selected.get()
        if (selected in boxes and selected not in self._hidden
                and not (selected == "campaign" and not self.show_campaign.get())):
            x0, y0, x1, y1 = boxes[selected]
            rect(x0, y0, x1, y1, fill="", outline="#5bc8ff",
                 dash=(5, 3), width=2)
            rect(x0-4, y0-4, x0+4, y0+4, fill="#5bc8ff",
                 outline="#101b2a", width=1)
        self._sync_selected_position()
