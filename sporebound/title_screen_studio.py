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
from .title_screen_settings import DEFAULTS, LABEL_KEYS, NAMESPACE, extension_for, settings_for


class TitleScreenStudio:
    """Separate Title Screen tab: author presentation, preview, then apply."""

    def __init__(self, owner, notebook):
        self.owner = owner
        self.tk, self.ttk = owner.tk, owner.ttk
        self.tab = self.ttk.Frame(notebook)
        notebook.add(self.tab, text="Title Screen")
        self.tab.columnconfigure(1, weight=1)
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

        self.ttk.Label(controls, text="Title Screen Editor",
                       font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=8, pady=(8, 3))
        self.ttk.Label(controls, text="Visual preview · project presentation only",
                       wraplength=264).pack(anchor="w", padx=8, pady=(0, 12))
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
        self.ttk.Label(controls, text="Action labels",
                       font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=8, pady=(5, 2))
        self.ttk.Label(controls, text="Actions and keyboard navigation remain connected.",
                       wraplength=264).pack(anchor="w", padx=8, pady=(0, 5))
        for (key, default, _caption, _icon) in CinematicTitleMenu.ACTIONS:
            self._entry(controls, key.title(), self.labels[key])

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
        self.ttk.Label(preview_frame, text="Live preview — presentation only (not Playtest)"
                       ).grid(row=0, column=0, sticky="w", pady=(3, 8))
        self.canvas = self.tk.Canvas(preview_frame, background="#101b2a",
                                     highlightthickness=1, highlightbackground="#788294")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self.paint())
        for var in (self.title, self.subtitle, self.background, self.image,
                    self.accent, self.panel, self.text, self.show_campaign,
                    *self.labels.values()):
            var.trace_add("write", lambda *_args: self.paint())

    def _entry(self, parent, caption, variable):
        self.ttk.Label(parent, text=caption).pack(anchor="w", padx=8, pady=(4, 1))
        self.ttk.Entry(parent, textvariable=variable).pack(fill="x", padx=8, pady=(0, 5))

    def load(self):
        if self.owner.project is None:
            return
        settings = settings_for(self.owner.project)
        self.title.set(self.owner.project.title)
        self.subtitle.set(self.owner.project.subtitle)
        for field in ("background", "image", "accent", "panel", "text", "show_campaign"):
            getattr(self, field).set(settings[field])
        defaults = dict((row[0], row[1]) for row in CinematicTitleMenu.ACTIONS)
        for key in LABEL_KEYS:
            self.labels[key].set(settings["labels"].get(key, defaults[key]))
        self.paint()

    def defaults(self):
        for key in ("background", "image", "accent", "panel", "text", "show_campaign"):
            getattr(self, key).set(deepcopy(DEFAULTS[key]))
        for key, label, _caption, _icon in CinematicTitleMenu.ACTIONS:
            self.labels[key].set(label)

    def _settings(self):
        defaults = {row[0]: row[1] for row in CinematicTitleMenu.ACTIONS}
        labels = {key: var.get() for key, var in self.labels.items()
                  if var.get() != defaults[key]}
        return dict(background=self.background.get(), image=self.image.get(),
                    accent=self.accent.get(), panel=self.panel.get(),
                    text=self.text.get(), show_campaign=self.show_campaign.get(),
                    labels=labels)

    def pending(self):
        if self.owner.project is None:
            return False
        current = settings_for(self.owner.project)
        edited = self._settings()
        return (self.title.get() != self.owner.project.title
                or self.subtitle.get() != self.owner.project.subtitle
                or any(edited[key] != current[key] for key in DEFAULTS))

    def apply(self):
        data = deepcopy(self.owner.project.to_dict())
        data["title"] = self.title.get()
        data["subtitle"] = self.subtitle.get()
        data.setdefault("extensions", {})[NAMESPACE] = extension_for(self._settings())
        new_project = GameProject.from_dict(data, self.owner._content())
        self.owner.project = new_project
        self.owner.title.set(new_project.title)
        self.owner.subtitle.set(new_project.subtitle)
        self.owner.project_status.config(
            text="Title Screen applied. Save the game project to persist changes.")
        self.owner.refresh()

    def save(self):
        # Saving directly from this tab must include edits not yet applied.
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

    def paint(self):
        if self.owner.project is None or not self.canvas.winfo_exists():
            return
        canvas = self.canvas
        w, h = max(canvas.winfo_width(), 2), max(canvas.winfo_height(), 2)
        if w < 20 or h < 20:
            return
        canvas.delete("all")
        sx, sy = w / 1160, h / 820
        def rect(x0, y0, x1, y1, **kwargs):
            return canvas.create_rectangle(x0*sx, y0*sy, x1*sx, y1*sy, **kwargs)
        def label(x, y, value, size, color, **kwargs):
            return canvas.create_text(x*sx, y*sy, text=value,
                                      fill=color, font=("Georgia", max(8, int(size*min(sx,sy))), "bold"),
                                      **kwargs)

        accent = self._valid_color(self.accent.get(), DEFAULTS["accent"])
        panel = self._valid_color(self.panel.get(), DEFAULTS["panel"])
        foreground = self._valid_color(self.text.get(), DEFAULTS["text"])
        rect(0, 0, 1160, 820, fill="#101b2a", outline="")
        photo = self._background_photo(max(1, int(w*.72)), h)
        if photo is not None:
            canvas.create_image(0, 0, image=photo, anchor="nw")
        layout = title_geometry(1160, 820)
        rect(layout["menu_x"]-8, 0, 1160, 820, fill="#101b2a", outline="")
        label(935, 75, "⚜", 25, accent, anchor="center")
        label(935, 120, self.title.get() or "Game Title", 31, foreground,
              anchor="center", width=400*sx, justify="center")
        label(935, 196, self.subtitle.get(), 13, accent,
              anchor="center", width=390*sx, justify="center")
        for (key, default, caption, _icon), (x0, y0, x1, y1) in zip(
                CinematicTitleMenu.ACTIONS, layout["cards"]):
            rect(x0, y0, x1, y1, fill=panel, outline=accent, width=1)
            rect(x0+2, y0+2, x0+77, y1-2, fill="#203249", outline="")
            label(x0+39, (y0+y1)/2, "✦", 18, accent, anchor="center")
            label(x0+95, y0+(y1-y0)*.36, self.labels[key].get() or default,
                  17, foreground, anchor="w", width=(x1-x0-114)*sx)
            label(x0+95, y0+(y1-y0)*.73, caption, 9, "#c0ccda",
                  anchor="w", width=(x1-x0-114)*sx)
        if self.show_campaign.get():
            x0,y0,x1,y1 = layout["campaign"]
            rect(x0,y0,x1,y1,fill="#101b2a",outline=accent)
            label(x0+15,y0+25,"Current campaign",14,accent,anchor="w")
            campaign = self.owner.project.campaigns[0]
            label(x0+15,y0+77,campaign["name"],15,foreground,anchor="w",
                  width=(x1-x0-25)*sx)
        rect(layout["menu_x"], layout["footer_y"], 1135, 794,
             fill=panel, outline=accent)
        label(915, 767, "Advanced tools       Credits       Help", 12,
              foreground, anchor="center", width=430*sx)
