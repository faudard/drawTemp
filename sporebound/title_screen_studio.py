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
from .title_screen_layout import ELEMENTS, CARD_KEYS, placement, relocate, resolve_boxes


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
        self._positions = {}
        self._last_boxes = {}
        self._drag = None
        self._undo_moves = []
        self._redo_moves = []
        self._preview_transform = (0.0, 0.0, 1.0)
        self.selected = self.tk.StringVar(value="title")
        self.position_x = self.tk.StringVar()
        self.position_y = self.tk.StringVar()

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

        self.ttk.Label(controls, text="Layout · drag objects in the preview",
                       font=("TkDefaultFont", 10, "bold")).pack(
                           anchor="w", padx=8, pady=(12, 2))
        self.ttk.Label(controls, text="Move: click and drag. Positions are relative "
                       "to the game window. Ctrl+Z/Ctrl+Y: undo/redo moves.",
                       wraplength=264).pack(anchor="w", padx=8, pady=(1, 7))
        self.ttk.Combobox(controls, textvariable=self.selected,
                          values=ELEMENTS, state="readonly").pack(
                              fill="x", padx=8, pady=4)
        self.selected.trace_add("write", lambda *_args: self._sync_selected_position())
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
        self.ttk.Label(preview_frame, text="Live preview — presentation only (not Playtest)"
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
        self._positions = deepcopy(settings["positions"])
        self._undo_moves.clear()
        self._redo_moves.clear()
        self._drag = None
        self.title.set(self.owner.project.title)
        self.subtitle.set(self.owner.project.subtitle)
        for field in ("background", "image", "accent", "panel", "text", "show_campaign"):
            getattr(self, field).set(settings[field])
        defaults = dict((row[0], row[1]) for row in CinematicTitleMenu.ACTIONS)
        for key in LABEL_KEYS:
            self.labels[key].set(settings["labels"].get(key, defaults[key]))
        self.paint()
        self._sync_selected_position()

    def defaults(self):
        self._remember_move()
        self._positions = {}
        for key in ("background", "image", "accent", "panel", "text", "show_campaign"):
            getattr(self, key).set(deepcopy(DEFAULTS[key]))
        for key, label, _caption, _icon in CinematicTitleMenu.ACTIONS:
            self.labels[key].set(label)
        self.paint()
        self._sync_selected_position()

    def _settings(self):
        defaults = {row[0]: row[1] for row in CinematicTitleMenu.ACTIONS}
        labels = {key: var.get() for key, var in self.labels.items()
                  if var.get() != defaults[key]}
        return dict(background=self.background.get(), image=self.image.get(),
                    accent=self.accent.get(), panel=self.panel.get(),
                    text=self.text.get(), show_campaign=self.show_campaign.get(),
                    labels=labels, positions=deepcopy(self._positions))

    def pending(self):
        if self.owner.project is None:
            return False
        current = settings_for(self.owner.project)
        edited = self._settings()
        return (self.title.get() != self.owner.project.title
                or self.subtitle.get() != self.owner.project.subtitle
                or any(edited[key] != current[key] for key in DEFAULTS))

    def _remember_move(self):
        self._undo_moves.append(deepcopy(self._positions))
        if len(self._undo_moves) > 50:
            self._undo_moves.pop(0)
        self._redo_moves.clear()

    def undo_move(self):
        if self._undo_moves:
            self._redo_moves.append(deepcopy(self._positions))
            self._positions = self._undo_moves.pop()
            self.paint()
            self._sync_selected_position()

    def redo_move(self):
        if self._redo_moves:
            self._undo_moves.append(deepcopy(self._positions))
            self._positions = self._redo_moves.pop()
            self.paint()
            self._sync_selected_position()

    def reset_selected(self):
        key = self.selected.get()
        if key in self._positions:
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
            raise ValueError("Select a title-screen element")
        proposed = relocate(self._last_boxes[key], x * 11.6, y * 8.2, 1160, 820)
        new_position = placement(proposed, 1160, 820)
        if self._positions.get(key) != new_position:
            self._remember_move()
            self._positions[key] = new_position
        self.paint()
        self._sync_selected_position()

    def _pointer_coords(self, event):
        ox, oy, scale = self._preview_transform
        return ((event.x - ox) / scale, (event.y - oy) / scale)

    def _pointer_down(self, event):
        self.canvas.focus_set()
        x, y = self._pointer_coords(event)
        # Test in reverse draw order; prefer individual cards over their surround.
        for key in reversed(ELEMENTS):
            if key == "campaign" and not self.show_campaign.get():
                continue
            bounds = self._last_boxes.get(key)
            if bounds and bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]:
                self.selected.set(key)
                self._drag = (key, x, y, bounds, deepcopy(self._positions))
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
        self._positions[key] = placement(moved, 1160, 820)
        self.paint()
        self._sync_selected_position()

    def _pointer_up(self, _event):
        if self._drag is not None:
            _, _, _, _, initial = self._drag
            if self._positions != initial:
                self._undo_moves.append(initial)
                if len(self._undo_moves) > 50:
                    self._undo_moves.pop(0)
                self._redo_moves.clear()
        self._drag = None
        self.canvas.configure(cursor="")
        self.paint()

    def _cancel_drag(self, _event=None):
        if self._drag is not None:
            self._positions = self._drag[4]
            self._drag = None
            self.canvas.configure(cursor="")
            self.paint()
            self._sync_selected_position()

    def apply(self):
        data = deepcopy(self.owner.project.to_dict())
        data["title"] = self.title.get()
        data["subtitle"] = self.subtitle.get()
        appearance = self._settings()
        if appearance == DEFAULTS:
            # Removing an explicit override restores Jeanne's exact legacy menu.
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
        label((logo[0]+logo[2])/2, logo[1], "⚜", 24,
              accent, anchor="n")
        label((title[0]+title[2])/2, title[1], name or "Game Title", 39,
              foreground, anchor="n", width=title[2]-title[0])
        label((subtitle[0]+subtitle[2])/2, subtitle[1],
              (sub or self.subtitle.get()).upper(), 12, accent,
              anchor="n", width=subtitle[2]-subtitle[0])

        for key, default, description, _icon in CinematicTitleMenu.ACTIONS:
            x0, y0, x1, y1 = boxes[
                "campaign_action" if key == "campaign" else key]
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

        if self.show_campaign.get():
            x0, y0, x1, y1 = boxes["campaign"]
            rect(x0, y0, x1, y1, fill="#101b2a", outline=accent)
            label(x0+15, y0+14, "Current campaign", 12,
                  accent, anchor="nw")
            campaign = self.owner.project.campaigns[0]
            label(x0+15, y0+70, campaign["name"], 14, foreground,
                  anchor="nw", width=x1-x0-30)
            label(x0+15, y1-42, "⇆  Change campaign", 11,
                  foreground, anchor="nw")

        fx0, fy0, fx1, fy1 = boxes["footer"]
        fw = fx1-fx0
        gap = 9
        widths = (fw*.48, fw*.245, fw*.275)
        captions = ("Advanced tools", "Credits", "Help")
        for idx, (cw, caption) in enumerate(zip(widths, captions)):
            x0 = fx0 + sum(widths[:idx]) + gap * idx
            x1 = x0 + cw - (gap if idx == 2 else 0)
            rect(x0, fy0, x1, fy1, fill="#101a29", outline=accent)
            label((x0+x1)/2, (fy0+fy1)/2, caption, 11, foreground)
        rect(0, 789, 152, 820, fill="#101b2a", outline="")
        label(25, 796, "DrawTemp · Player", 10, "#b8becc",
              anchor="nw", bold=False)

        selected = self.selected.get()
        if selected in boxes and not (selected == "campaign" and not self.show_campaign.get()):
            x0, y0, x1, y1 = boxes[selected]
            rect(x0, y0, x1, y1, fill="", outline="#5bc8ff",
                 dash=(5, 3), width=2)
            rect(x0-4, y0-4, x0+4, y0+4, fill="#5bc8ff",
                 outline="#101b2a", width=1)
        self._sync_selected_position()
