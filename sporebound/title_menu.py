"""Cinematic, keyboard-accessible Tk title menu for the standalone Player.

Presentation only. Campaign selection and save actions still use PlayerController;
no game or persistence state is duplicated here.
"""
from pathlib import Path


BACKGROUND = "#101827"
PANEL = "#172233"
GOLD = "#e3b970"
IVORY = "#f4ead7"
MUTED = "#c0ccda"


def has_save(player, campaign_id, slot, *, long_mode=False):
    """Detect a slot or recovery copy without parsing/migrating saved data."""
    path = (player.long_path_for(campaign_id, slot) if long_mode
            else player.path_for(campaign_id, slot))
    return path.exists() or path.with_name(path.name + ".bak").exists()


class TitleMenu:
    def __init__(self, app):
        self.app = app
        self.tk = app.tk
        self.scale = app.text_scale.get() / 100
        self.contrast = app.high_contrast.get()
        # Bundled Jeanne illustration; custom projects keep the vector fallback.
        self._backdrop_path = None
        self._backdrop_source = None
        self._backdrop_photo = None
        self._backdrop_size = None
        self._backdrop_native = None
        self._image_tk = None
        if any(campaign["id"] == "jeanne" for campaign in app.project.campaigns):
            candidates = (
                app.asset_root / "art" / "jeanne" / "jeanne_menu_backdrop.png",
                Path(__file__).resolve().parent / "content" / "art" /
                "jeanne" / "jeanne_menu_backdrop.png",
            )
            self._backdrop_path = next((path for path in candidates
                                         if path.is_file()), None)
            if self._backdrop_path is not None:
                try:
                    from PIL import Image, ImageTk
                    self._backdrop_source = Image.open(self._backdrop_path).convert("RGB")
                    self._image_tk = ImageTk
                except (ImportError, OSError, ValueError):
                    # No Pillow dependency: native Tk supports bundled PNGs.
                    try:
                        self._backdrop_native = self.tk.PhotoImage(
                            file=str(self._backdrop_path))
                    except self.tk.TclError:
                        self._backdrop_native = None
        self.portrait = None
        if any(campaign["id"] == "jeanne" for campaign in app.project.campaigns):
            image_path = app.asset_root / "art" / "jeanne" / "jeanne_portrait.png"
            if image_path.is_file():
                try:
                    self.portrait = self.tk.PhotoImage(file=str(image_path))
                except self.tk.TclError:
                    pass  # The vector title art remains usable without the PNG.
        self.canvas = self.tk.Canvas(app.view, bg=BACKGROUND, borderwidth=0,
                                     highlightthickness=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)
        self.windows = []
        self.overlay = None
        self.overlay_window = None
        self.overlay_shade = None
        self.status = None
        self._build_controls()
        self.canvas.bind("<Configure>",
                         lambda event: self.paint(event.width, event.height))
        self.paint(max(app.view.winfo_width(), 800),
                   max(app.view.winfo_height(), 560))
        self.canvas.after_idle(self._focus_default)

    def _focus_default(self):
        if self.canvas.winfo_exists() and self.overlay is None:
            (self.continue_button if self._saved() else self.new_button).focus_set()

    def _saved(self):
        return has_save(self.app.player, self.app.campaign_var.get(),
                        int(self.app.slot_var.get()),
                        long_mode=self.app.long_save_var.get())

    def _button(self, text, command, *, primary=False):
        button = self.tk.Button(
            self.canvas, text=text, command=lambda: self.app._safe(command),
            bg=GOLD if primary else PANEL,
            fg="#101827" if primary else IVORY,
            activebackground="#f4cf93" if primary else "#293d54",
            activeforeground="#101827" if primary else IVORY,
            disabledforeground="#768396",
            font=("Segoe UI", max(10, round(12 * self.scale)), "bold"),
            relief="flat", bd=0, cursor="hand2",
            highlightthickness=2, highlightbackground=GOLD if primary else "#334659",
            highlightcolor=GOLD, takefocus=True)
        identifier = self.canvas.create_window(0, 0, anchor="nw", window=button)
        self.windows.append((identifier, button))
        return button

    def _build_controls(self):
        self.continue_button = self._button("CONTINUER", self.app._load_game)
        self.new_button = self._button("NOUVELLE PARTIE", self.app._new_game, primary=True)
        self.load_button = self._button("CHARGER UNE PARTIE",
                                        lambda: self.open_selection(load=True))
        self.options_button = self._button("OPTIONS", self.app.options_screen)
        self.quit_button = self._button("QUITTER", self.app.close)
        self.choose_button = self._button("CHOISIR CAMPAGNE / EMPLACEMENT",
                                          self.open_selection)
        self.advanced_button = self._button("OUTILS AVANCÉS", self.open_advanced)

    def _campaign_label(self):
        campaign = self.app.project.campaign(self.app.campaign_var.get())
        return campaign["name"] if campaign is not None else self.app.campaign_var.get()

    def paint(self, width, height):
        if width < 2 or height < 2 or not self.canvas.winfo_exists():
            return
        c = self.canvas
        c.delete("art")
        panel_width = min(max(440, width * .48), 560)
        if self.contrast:
            c.create_rectangle(0, 0, width, height, fill="#000000",
                               outline="", tags="art")
        else:
            c.create_rectangle(0, 0, width, height, fill="#121d2c",
                               outline="", tags="art")
            if not self._paint_backdrop(panel_width, width, height):
                top = (13, 22, 38)
                bottom = (68, 48, 56)
                for band in range(80):
                    t = band / 79
                    rgb = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
                    colour = "#%02x%02x%02x" % rgb
                    y0 = height * band / 80
                    y1 = height * (band + 1) / 80 + 1
                    c.create_rectangle(0, y0, width, y1, fill=colour,
                                       outline="", tags="art")
                # Moonlit hills and a fortress: vector fallback, no asset downloads.
                cx, cy = width * .80, height * .31
                for radius, colour in ((125, "#413e4d"), (88, "#6e6471"),
                                       (55, "#b7a7a0"), (39, "#e9d6b3")):
                    c.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                  fill=colour, outline="", tags="art")
                c.create_polygon(0, height*.65, width*.22, height*.40,
                                 width*.45, height*.65, width*.66, height*.44,
                                 width, height*.64, width, height,
                                 0, height, fill="#263344", outline="", tags="art")
                c.create_polygon(0, height*.78, width*.21, height*.61,
                                 width*.48, height*.74, width*.76, height*.59,
                                 width, height*.73, width, height,
                                 0, height, fill="#172639", outline="", tags="art")
                self._castle(width*.76, height*.71, min(width*.29, 310),
                             min(height*.32, 235))
                c.create_polygon(0, height*.91, width*.35, height*.82,
                                 width*.68, height*.90, width, height*.81,
                                 width, height, 0, height,
                                 fill="#111e2b", outline="", tags="art")
                if self.portrait is not None:
                    px = panel_width + (width-panel_width)*.56
                    py = height*.46
                    half_w = self.portrait.width()/2
                    half_h = self.portrait.height()/2
                    c.create_rectangle(px-half_w-10, py-half_h-10,
                                       px+half_w+10, py+half_h+10,
                                       fill="#1b2937", outline=GOLD,
                                       width=2, tags="art")
                    c.create_image(px, py, image=self.portrait, tags="art")
            c.create_rectangle(0, 0, panel_width, height, fill=BACKGROUND,
                               outline="", tags="art")
            c.create_line(panel_width, 0, panel_width, height,
                          fill="#7c6955", width=2, tags="art")

        x = 46 if width >= 970 else 28
        top_y = 42 if height >= 720 else 23
        headline, sep, subtitle = self.app.project.title.partition(" — ")
        if not sep:
            headline, sep, subtitle = self.app.project.title.partition(" - ")
        if not sep:
            headline, subtitle = self.app.project.title, ""
        c.create_text(x, top_y, anchor="nw",
                      text=("CHAPITRE I  ·  LES CENDRES"
                            if getattr(self.app, "chapter_one", False)
                            else "UNE CHRONIQUE TACTIQUE"),
                      fill=GOLD, font=("Segoe UI", max(9, round(10*self.scale)), "bold"),
                      tags="art")
        c.create_line(x, top_y+28, panel_width-40, top_y+28,
                      fill="#9b7e50", width=1, tags="art")
        title_size = max(21, round((34 if width >= 970 else 27)*self.scale))
        c.create_text(x, top_y+43, anchor="nw", text=headline,
                      fill=IVORY, width=panel_width-x-20,
                      font=("Georgia", title_size, "bold"), tags="art")
        c.create_text(x, top_y+100, anchor="nw", text=subtitle.upper(),
                      fill=GOLD, width=panel_width-x-15,
                      font=("Georgia", max(13, round(17*self.scale)), "bold"),
                      tags="art")
        c.create_text(x, top_y+137, anchor="nw", text=self.app.project.subtitle,
                      fill=MUTED, width=panel_width-x-20,
                      font=("Segoe UI", max(9, round(10*self.scale))),
                      tags="art")
        menu_y = max(top_y + 181, height * .35)
        gap = 7 if height >= 680 else 5
        btn_height = (max(35, round(43*self.scale)) if height >= 680
                      else max(35, round(37*min(self.scale, 1.1))))
        btn_width = min(335, panel_width-x-30)
        for index, (identifier, _widget) in enumerate(self.windows[:5]):
            y = menu_y + index*(btn_height+gap)
            c.coords(identifier, x, y)
            c.itemconfigure(identifier, width=btn_width, height=btn_height)
        footer_y = menu_y + 5*(btn_height+gap) + 8
        c.create_text(x, footer_y, anchor="nw",
                      text=self._campaign_label()[:46],
                      fill=IVORY, width=btn_width,
                      font=("Segoe UI", max(9, round(10*self.scale))),
                      tags="art")
        c.create_text(x, footer_y+22, anchor="nw",
                      text="Emplacement " + self.app.slot_var.get() +
                           (" · Longue" if self.app.long_save_var.get() else "") +
                           (" · Sauvegarde trouvée" if self._saved() else " · Libre"),
                      fill="#a9cbbd" if self._saved() else MUTED,
                      font=("Segoe UI", max(9, round(9*self.scale))),
                      tags="art")
        for index, (identifier, _widget) in enumerate(self.windows[5:]):
            y = footer_y + 49 + index*35
            c.coords(identifier, x, y)
            c.itemconfigure(identifier, width=btn_width, height=29)
        self.continue_button.configure(state="normal" if self._saved() else "disabled")
        self.new_button.configure(
            bg=PANEL if self._saved() else GOLD,
            fg=IVORY if self._saved() else BACKGROUND)
        if not self.contrast:
            c.create_text(width-45, height-34, anchor="se",
                          text="DOMRÉMY  •  LE ROYAUME VOUS ATTEND",
                          fill="#e0c29b", width=width-panel_width-20,
                          font=("Georgia", max(10, round(12*self.scale)), "italic"),
                          tags="art")
        if self.overlay_shade is not None:
            c.coords(self.overlay_shade, 0, 0, width, height)
            c.tag_raise(self.overlay_shade)
        if self.overlay_window is not None:
            c.coords(self.overlay_window, width/2, height/2)
            c.tag_raise(self.overlay_window)

    def _paint_backdrop(self, panel_width, width, height):
        """Fill the scenic area without altering the live menu controls."""
        c = self.canvas
        available_width = max(1, round(width - panel_width))
        available_height = max(1, round(height))
        if self._backdrop_source is not None and self._image_tk is not None:
            size = (available_width, available_height)
            if size != self._backdrop_size:
                from PIL import Image, ImageOps
                picture = ImageOps.fit(
                    self._backdrop_source, size,
                    method=Image.Resampling.LANCZOS if hasattr(Image, "Resampling")
                    else Image.LANCZOS,
                    centering=(0.5, 0.47))
                self._backdrop_photo = self._image_tk.PhotoImage(
                    picture, master=self.app.root)
                self._backdrop_size = size
            c.create_image(panel_width, 0, anchor="nw",
                           image=self._backdrop_photo, tags="art")
            return True
        if self._backdrop_native is not None:
            c.create_image(panel_width + available_width/2,
                           available_height/2, anchor="center",
                           image=self._backdrop_native, tags="art")
            return True
        return False

    def _castle(self, x, y, w, h):
        c = self.canvas
        dark = "#0d1824"
        c.create_rectangle(x-w*.37, y-h*.52, x+w*.38, y,
                           fill=dark, outline="", tags="art")
        for pos, size in ((-.32, .38), (.27, .46), (0, .72)):
            xx = x + pos*w
            c.create_rectangle(xx-w*.12, y-size*h, xx+w*.12, y,
                               fill=dark, outline="", tags="art")
            c.create_polygon(xx-w*.17, y-size*h,
                             xx, y-(size+.28)*h, xx+w*.17, y-size*h,
                             fill="#111a24", outline="", tags="art")
        for dx in (-.30, -.12, .12, .30):
            c.create_rectangle(x+w*dx-w*.025, y-h*.40,
                               x+w*dx+w*.025, y-h*.32,
                               fill="#be9260", outline="", tags="art")
        c.create_arc(x-w*.10, y-h*.24, x+w*.10, y+h*.05,
                     start=0, extent=180, style="chord",
                     fill="#675245", outline="", tags="art")

    def _close_overlay(self):
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None
        if self.overlay_window is not None:
            self.canvas.delete(self.overlay_window)
            self.overlay_window = None
        if self.overlay_shade is not None:
            self.canvas.delete(self.overlay_shade)
            self.overlay_shade = None
        for identifier, _ in self.windows:
            self.canvas.itemconfigure(identifier, state="normal")
        self.paint(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._focus_default()

    def _open_overlay(self, heading, *, width=590):
        self._close_overlay()
        c = self.canvas
        for identifier, _ in self.windows:
            c.itemconfigure(identifier, state="hidden")
        self.overlay_shade = c.create_rectangle(
            0, 0, c.winfo_width(), c.winfo_height(),
            fill="#060a11", stipple="gray50")
        self.overlay = self.tk.Frame(c, bg=PANEL, padx=26, pady=20,
                                     highlightthickness=2,
                                     highlightbackground=GOLD)
        self.overlay_window = c.create_window(
            c.winfo_width()/2, c.winfo_height()/2, anchor="center",
            window=self.overlay, width=min(width, c.winfo_width()-35))
        head = self.tk.Frame(self.overlay, bg=PANEL)
        head.pack(fill="x", pady=(0, 17))
        self.tk.Label(head, text=heading, bg=PANEL, fg=IVORY,
                      font=("Georgia", round(19*self.scale), "bold")
                      ).pack(side="left")
        self.tk.Button(head, text="✕", command=self._close_overlay,
                       bg=PANEL, fg=IVORY, relief="flat",
                       activebackground="#354a5d",
                       activeforeground=IVORY, cursor="hand2").pack(side="right")
        return self.overlay

    def _panel_button(self, parent, label, action, *, primary=False):
        return self.tk.Button(
            parent, text=label, command=lambda: self.app._safe(action),
            bg=GOLD if primary else "#273b52",
            fg=BACKGROUND if primary else IVORY,
            activebackground="#f4cf93" if primary else "#39526b",
            activeforeground=BACKGROUND if primary else IVORY,
            relief="flat", bd=0, cursor="hand2", pady=9,
            font=("Segoe UI", max(10, round(11*self.scale)), "bold"),
            highlightthickness=1, highlightbackground="#667b8d",
            highlightcolor=GOLD, takefocus=True)

    def open_selection(self, load=False):
        from tkinter import ttk
        parent = self._open_overlay("Reprendre une aventure" if load
                                    else "Choisir une aventure")
        names = [entry["name"] for entry in self.app.project.campaigns]
        ids = [entry["id"] for entry in self.app.project.campaigns]
        selected_name = self.tk.StringVar(value=names[ids.index(
            self.app.campaign_var.get())])
        slot = self.tk.StringVar(value=self.app.slot_var.get())
        long_mode = self.tk.BooleanVar(value=self.app.long_save_var.get())

        def field(text):
            self.tk.Label(parent, text=text, bg=PANEL, fg=MUTED,
                          anchor="w", font=("Segoe UI", max(10, round(11*self.scale)))
                          ).pack(fill="x", pady=(8, 4))

        field("Campagne")
        choices = ttk.Combobox(parent, state="readonly", values=names,
                               textvariable=selected_name)
        choices.pack(fill="x", ipady=5)
        field("Emplacement")
        slots = ttk.Combobox(parent, state="readonly", textvariable=slot,
                             values=[str(i) for i in range(
                                 1, self.app.project.save_slots + 1)])
        slots.pack(fill="x", ipady=5)
        self.tk.Checkbutton(
            parent, text="Sessions longues (expérimental, emplacement séparé)",
            variable=long_mode, bg=PANEL, fg=MUTED,
            selectcolor=BACKGROUND, activebackground=PANEL,
            activeforeground=IVORY, anchor="w"
        ).pack(fill="x", pady=(14, 4))
        status = self.tk.Label(parent, bg=PANEL, fg=IVORY, anchor="w",
                               font=("Segoe UI", 10))
        status.pack(fill="x", pady=(7, 12))

        def selected():
            return ids[names.index(selected_name.get())], int(slot.get())

        def update_status(*_):
            cid, number = selected()
            status.configure(text=("● Partie enregistrée" if has_save(
                self.app.player, cid, number, long_mode=long_mode.get())
                                   else "○ Emplacement libre"))
            resume.configure(state=("normal" if has_save(
                self.app.player, cid, number, long_mode=long_mode.get())
                                    else "disabled"))

        def commit():
            cid, number = selected()
            self.app.campaign_var.set(cid)
            self.app.slot_var.set(str(number))
            self.app.long_save_var.set(long_mode.get())

        def run(action):
            commit()
            self._close_overlay()
            action()

        actions = self.tk.Frame(parent, bg=PANEL)
        actions.pack(fill="x", pady=(4, 4))
        resume = self._panel_button(actions, "CONTINUER", lambda: run(self.app._load_game),
                                     primary=load)
        resume.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self._panel_button(actions, "NOUVELLE PARTIE",
                           lambda: run(self.app._new_game),
                           primary=not load).pack(side="left", expand=True, fill="x")
        self._panel_button(parent, "CHOISIR SANS LANCER",
                           lambda: run(lambda: None)).pack(fill="x", pady=(6, 3))
        self._panel_button(parent, "GESTIONNAIRE DE SAUVEGARDES",
                           lambda: run(self.app.save_manager_screen)
                           ).pack(fill="x", pady=3)
        for variable in (selected_name, slot, long_mode):
            variable.trace_add("write", update_status)
        update_status()
        choices.focus_set()

    def open_advanced(self):
        parent = self._open_overlay("Outils avancés")
        self.tk.Label(
            parent, text="Maintenance des sauvegardes et scénarios de test.",
            bg=PANEL, fg=MUTED, anchor="w").pack(fill="x", pady=(0, 12))
        actions = [
            ("Gestionnaire de sauvegardes", self.app.save_manager_screen),
            ("Migrer une sauvegarde v1 vers v2", self.app._migrate_game),
            ("Copier v1/v2 vers une session longue", self.app._migrate_long_game),
        ]
        if self.app.project.sieges:
            actions.append(("Sièges créés dans le Studio",
                            self.app._authored_siege_menu))
        castle_example = (Path(__file__).resolve().parent.parent /
                          "examples" / "castle_vertical_slice.py")
        if castle_example.is_file():
            actions.append(("Campagne Château (démonstration)",
                            self.app._open_castle))
        for label, action in actions:
            self._panel_button(
                parent, label,
                lambda action=action: (self._close_overlay(), action())
            ).pack(fill="x", pady=4)
        self._panel_button(parent, "RETOUR AU MENU", self._close_overlay
                           ).pack(fill="x", pady=(12, 0))
        parent.focus_set()
