"""Interactive painterly RPG title screen, following the Jeanne menu art direction.

The scenery is presentation-only; saves and game actions remain exclusively in
PlayerController. All menu labels, buttons, hit targets and dialogs are live Tk.
"""
from datetime import datetime
from pathlib import Path

from .title_menu import BACKGROUND, GOLD, IVORY, MUTED, PANEL, TitleMenu
from .title_screen_settings import settings_for
from .title_screen_layout import CARD_KEYS, resolve_boxes


def title_geometry(width, height):
    """Return bounded rectangles for both 16:9 and minimum-size Tk windows."""
    width, height = max(800, int(width)), max(580, int(height))
    compact = width < 1070 or height < 680
    margin = 19 if compact else max(32, round(width * .035))
    # Leave room for readable command labels at typical desktop resolutions.
    menu_left = round(width * (.56 if compact else .58 if width < 1270 else .65))
    menu_width = width - menu_left - margin
    menu_top = round(height * (.245 if compact else .29))
    footer_height = 33 if compact else 40
    footer_top = height - footer_height - (15 if compact else 26)
    gap = 5 if compact else max(7, min(11, round(height * .011)))
    first_height = max(63, round(height * .117))
    if compact:
        first_height = min(first_height, 73)
    available = footer_top - menu_top - (7 if compact else 16)
    card_height = (available - first_height - 5 * gap) // 5
    card_height = max(43, card_height)
    cards = []
    y = menu_top
    for i in range(6):
        h = first_height if i == 0 else card_height
        cards.append((menu_left, y, menu_left + menu_width, y + h))
        y += h + gap
    box_x = 20 if compact else max(36, round(width * .024))
    # The original stage has a painted placard at the bottom-left.
    box_w = min(500, max(294, round(width * .36)))
    box_h = max(160, min(243, round(height * .267)))
    box_bottom = height - (54 if compact else 87)
    campaign = (box_x, box_bottom - box_h, box_x + box_w, box_bottom)
    return {
        "compact": compact,
        "menu_x": menu_left,
        "menu_width": menu_width,
        "menu_top": menu_top,
        "cards": cards,
        "campaign": campaign,
        "footer_y": footer_top,
        "footer_height": footer_height,
        "margin": margin,
    }


def render_title_background(source, width, height, menu_x, scenic_width, *,
                            centering=(0.49, 0.50)):
    """Pillow cover crop and smooth non-stippled fade, testable without Tk."""
    from PIL import Image, ImageDraw, ImageOps

    if min(width, height, scenic_width) <= 0:
        raise ValueError("title background dimensions must be positive")
    scenic_width = min(width, scenic_width)
    lanczos = (Image.Resampling.LANCZOS if hasattr(Image, "Resampling")
               else Image.LANCZOS)
    stage = ImageOps.fit(source, (scenic_width, height), method=lanczos,
                         centering=centering).convert("RGB")
    navy = (15, 27, 42)
    background = Image.new("RGB", (width, height), navy)
    background.paste(stage, (0, 0))
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    start = max(0, min(width, round(menu_x * .77)))
    end = max(start + 1, min(width, round(menu_x + 38)))
    for x in range(start, end):
        opacity = round(255 * (x - start) / max(1, end - start - 1))
        draw.line((x, 0, x, height), fill=opacity)
    if end < width:
        draw.rectangle((end, 0, width, height), fill=255)
    return Image.composite(Image.new("RGB", (width, height), navy),
                           background, mask)


class _ActionProxy:
    """Compatibility shim for older smoke tests that inspected ttk buttons."""

    def __init__(self, menu, name, text):
        self.menu, self.name, self.text = menu, name, text

    def __getitem__(self, key):
        if key == "text":
            return self.text
        if key == "state":
            return "disabled" if self.name == "continue" and not self.menu._saved() else "normal"
        raise KeyError(key)


class CinematicTitleMenu(TitleMenu):
    """Code-rendered menu matching the approved 3-column cinematic mock-up."""

    ACTIONS = (
        ("continue", "Continuer", "Reprendre la dernière partie", "shield"),
        ("new", "Nouvelle partie", "Commencer une nouvelle aventure", "book"),
        ("load", "Charger une partie", "Choisir une sauvegarde existante", "scroll"),
        ("campaign", "Campagnes", "Choisir une campagne", "map"),
        ("options", "Options", "Graphismes, audio, commandes…", "gear"),
        ("quit", "Quitter", "Quitter le jeu", "door"),
    )

    def __init__(self, app):
        self._appearance = settings_for(app.project)
        self._accent = GOLD if app.high_contrast.get() else self._appearance["accent"]
        self._text_color = IVORY if app.high_contrast.get() else self._appearance["text"]
        self._panel_color = self._appearance["panel"]
        self._stage_path = None
        self._stage_source = None
        self._stage_photo = None
        self._stage_size = None
        self._thumb_photo = None
        self._selection_index = 0
        self._hitboxes = {}
        super().__init__(app)
        self.canvas.bind("<Up>", lambda _: self._move_selection(-1))
        self.canvas.bind("<Down>", lambda _: self._move_selection(1))
        self.canvas.bind("<Return>", lambda _: self._activate_selected())
        self.canvas.bind("<KP_Enter>", lambda _: self._activate_selected())
        self.canvas.bind("<space>", lambda _: self._activate_selected())
        self.canvas.bind("<Home>", lambda _: self._select_first())
        self.canvas.bind("<End>", lambda _: self._select_last())
        self.canvas.bind("<FocusIn>", lambda _: self._repaint())
        self.canvas.bind("<FocusOut>", lambda _: self._repaint())

    def _build_controls(self):
        # Keep the compatibility attributes used by the existing Player GUI
        # checks; no plain Tk buttons appear in the main painted menu.
        self.windows = []
        self.continue_button = _ActionProxy(self, "continue", "CONTINUER")
        self.new_button = _ActionProxy(self, "new", "NOUVELLE PARTIE")
        self.load_button = _ActionProxy(self, "load", "CHARGER UNE PARTIE")
        self.options_button = _ActionProxy(self, "options", "OPTIONS")
        self.quit_button = _ActionProxy(self, "quit", "QUITTER")
        self.choose_button = _ActionProxy(self, "choose", "CAMPAGNES")
        self.advanced_button = _ActionProxy(self, "advanced", "OUTILS AVANCÉS")
        self._commands = {
            "continue": self.app._load_game,
            "new": self.app._new_game,
            "load": lambda: self.open_selection(load=True),
            "campaign": self.open_selection,
            "options": self.app.options_screen,
            "quit": self.app.request_close,
            "choose": self.open_selection,
            "advanced": self.open_advanced,
            "credits": self.open_credits,
            "help": self.open_help,
        }

    def _focus_default(self):
        if self.canvas.winfo_exists() and self.overlay is None:
            self._selection_index = 0 if self._saved() else 1
            self.canvas.focus_set()
            self._repaint()

    def _repaint(self):
        if self.canvas.winfo_exists() and self.overlay is None:
            self.paint(self.canvas.winfo_width(), self.canvas.winfo_height())

    def _move_selection(self, amount):
        self._selection_index = (self._selection_index + amount) % len(self.ACTIONS)
        if not self._saved() and self._selection_index == 0:
            self._selection_index = 1 if amount > 0 else len(self.ACTIONS) - 1
        self._repaint()
        return "break"

    def _select_first(self):
        self._selection_index = 0 if self._saved() else 1
        self._repaint()
        return "break"

    def _select_last(self):
        self._selection_index = len(self.ACTIONS) - 1
        self._repaint()
        return "break"

    def _activate_selected(self):
        self._execute(self.ACTIONS[self._selection_index][0])
        return "break"

    def _execute(self, key):
        if key == "continue" and not self._saved():
            return
        return self.app._safe(self._commands[key])

    def _region(self, tag, rect, *, key):
        """Register a whole visible card as a single pointer hit target."""
        self._hitboxes[key] = tuple(rect)
        self.canvas.tag_bind(tag, "<Button-1>", lambda _, action=key: self._execute(action))
        self.canvas.tag_bind(tag, "<Enter>", lambda _: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _: self.canvas.configure(cursor=""))

    def _load_stage(self):
        if self._stage_source is not None:
            return True
        if self._stage_path is False:
            return False
        mode = self._appearance["background"]
        # The trimmed PNG permanently cuts off Jeanne's head. The original
        # stage art keeps her face and armor visible, and is the preferred
        # automatic Jeanne background when Pillow is available.
        if mode == "auto" and any(c["id"] == "jeanne" for c in self.app.project.campaigns):
            stage_path = (Path(__file__).resolve().parent / "content" / "art" /
                          "jeanne" / "jeanne_menu_stage.jpg")
            if stage_path.is_file():
                try:
                    from PIL import Image
                    self._stage_source = Image.open(stage_path).convert("RGB")
                    self._stage_path = stage_path
                    return True
                except (ImportError, OSError, ValueError):
                    pass
        if mode == "auto" and self._backdrop_source is not None:
            self._stage_source = self._backdrop_source
            self._stage_path = self._backdrop_path
            return True
        if mode == "image":
            root = self.app.asset_root.resolve()
            artwork = (root / self._appearance["image"]).resolve()
            if not artwork.is_relative_to(root):
                self._stage_path = False
                return False
        else:
            self._stage_path = False
            return False
        if not artwork.is_file():
            self._stage_path = False
            return False
        try:
            from PIL import Image
            self._stage_source = Image.open(artwork).convert("RGB")
            self._stage_path = artwork
            return True
        except (ImportError, OSError, ValueError):
            self._stage_path = False
            return False

    def _paint_stage(self, width, height, layout):
        c = self.canvas
        c.create_rectangle(0, 0, width, height,
                           fill="#000000" if self.contrast else "#101b2a",
                           outline="", tags="art")
        if self.contrast or self._appearance["background"] == "solid":
            return

        scenic_width = min(width, round(width *
                           (.73 if not layout["compact"] else .69)))
        if self._load_stage():
            key = (width, height, layout["menu_x"], scenic_width)
            if key != self._stage_size:
                try:
                    from PIL import ImageTk
                    backdrop = render_title_background(
                        self._stage_source, width, height,
                        layout["menu_x"], scenic_width,
                        centering=((0.16, 0.50) if self._stage_path is not None
                                   and self._stage_path.name == "jeanne_menu_stage.jpg"
                                   else (0.49, 0.50)))
                    self._stage_photo = ImageTk.PhotoImage(
                        backdrop, master=self.app.root)
                    self._stage_size = key
                except (ImportError, OSError, ValueError, self.tk.TclError):
                    # Failed artwork / absent Pillow: always use clean vectors.
                    self._stage_photo = None
                    self._stage_size = None
                    self._stage_source = None
                    self._stage_path = False
            if self._stage_photo is not None:
                c.create_image(0, 0, anchor="nw",
                               image=self._stage_photo, tags="art")
                return

        # Deterministic vector scenery, never pixelated Tk bitmap scaling.
        for i in range(45):
            y = height * i / 45
            c.create_rectangle(
                0, y, scenic_width, y + height / 45 + 1,
                fill="#%02x%02x%02x" % (24 + i // 5, 35 + i // 5, 53 + i // 6),
                outline="", tags="art")
        self._castle(scenic_width * .74, height * .67,
                     scenic_width * .48, height * .34)
        c.create_rectangle(layout["menu_x"] - 8, 0, width, height,
                           fill="#0f1c2b", outline="", tags="art")

    def _font(self, family, size, weight=None):
        p = max(9, round(size * min(self.scale, 1.4)))
        return (family, p, weight) if weight else (family, p)

    def _draw_header(self, layout, height, boxes):
        c = self.canvas
        lx0, ly0, lx1, _ = boxes["logo"]
        tx0, ty0, tx1, _ = boxes["title"]
        sx0, sy0, sx1, _ = boxes["subtitle"]
        header_width = tx1 - tx0
        name, sep, sub = self.app.project.title.partition(" — ")
        if not sep:
            name, sep, sub = self.app.project.title.partition(" - ")
        if not sep:
            name, sub = self.app.project.title, ""
        title_size = min(56, max(23, round(layout["menu_width"] * .095)))
        if layout["compact"]:
            title_size = min(title_size, 31)
        c.create_text((lx0+lx1)/2, ly0, anchor="n", text="⚜",
                      fill=self._accent, font=self._font("Georgia", 24 if not layout["compact"] else 15),
                      tags="art")
        c.create_text((tx0+tx1)/2, ty0,
                      text=name, anchor="n", width=header_width,
                      fill=self._text_color if not self.contrast else "white",
                      font=("Georgia", title_size, "bold"), tags="art")
        c.create_text((sx0+sx1)/2, sy0,
                      text=sub.upper() if sub else self.app.project.subtitle.upper(),
                      anchor="n", width=sx1-sx0, fill=self._accent,
                      font=self._font("Georgia", 12 if not layout["compact"] else 9),
                      tags="art")

    def _icon(self, kind, cx, cy, size, tag):
        """Vector pictograms—no fonts, images or external icon dependencies."""
        c = self.canvas
        k = max(7, size)
        kw = dict(fill="", outline=self._accent, width=2, tags=("art", tag))
        if kind == "shield":
            c.create_polygon(cx-k*.6, cy-k*.65, cx+k*.6, cy-k*.65,
                             cx+k*.55, cy+k*.15, cx, cy+k*.83,
                             cx-k*.55, cy+k*.15, **kw)
            c.create_text(cx, cy-1, text="⚜", fill=self._accent,
                          font=self._font("Georgia", max(9, k*.85)), tags=("art",tag))
        elif kind == "book":
            c.create_rectangle(cx-k*.77, cy-k*.58, cx, cy+k*.63, **kw)
            c.create_rectangle(cx, cy-k*.58, cx+k*.77, cy+k*.63, **kw)
            c.create_line(cx,cy-k*.58,cx,cy+k*.63,fill=self._accent,width=2,tags=("art",tag))
        elif kind == "scroll":
            c.create_rectangle(cx-k*.55, cy-k*.66, cx+k*.55, cy+k*.55, **kw)
            for d in (-.25, 0, .25):
                c.create_line(cx-k*.33,cy+k*d,cx+k*.34,cy+k*d,fill=self._accent,tags=("art",tag))
        elif kind == "map":
            c.create_polygon(cx-k*.85,cy-k*.55,cx-k*.28,cy-k*.75,
                             cx+k*.30,cy-k*.45,cx+k*.85,cy-k*.7,
                             cx+k*.85,cy+k*.55,cx+k*.3,cy+k*.75,
                             cx-k*.28,cy+k*.46,cx-k*.85,cy+k*.7,**kw)
            c.create_line(cx-k*.28,cy-k*.75,cx-k*.28,cy+k*.46,fill=self._accent,tags=("art",tag))
        elif kind == "gear":
            c.create_oval(cx-k*.68, cy-k*.68, cx+k*.68, cy+k*.68, **kw)
            c.create_oval(cx-k*.18,cy-k*.18,cx+k*.18,cy+k*.18,**kw)
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                c.create_line(cx+dx*k*.65,cy+dy*k*.65,cx+dx*k*.95,cy+dy*k*.95,
                              fill=self._accent,width=3,tags=("art",tag))
        elif kind == "door":
            c.create_rectangle(cx-k*.55,cy-k*.78,cx+k*.5,cy+k*.78,**kw)
            c.create_oval(cx+k*.16,cy, cx+k*.25,cy+k*.1,
                          fill=self._accent,outline=self._accent,tags=("art",tag))
        else:
            c.create_text(cx,cy,text="✦",fill=self._accent,
                          font=self._font("Georgia",15),tags=("art",tag))

    def _draw_cards(self, layout):
        c = self.canvas
        has_save = self._saved()
        self._hitboxes = {}
        for index, ((key,label,subtitle,icon), rect) in enumerate(zip(self.ACTIONS,layout["cards"])):
            label = self._appearance["labels"].get(key) or self.app._t("tk.title." + key)
            x0,y0,x1,y1=rect
            h = y1-y0
            tag="title_card_"+key
            disabled = key=="continue" and not has_save
            focused = index==self._selection_index and self.canvas.focus_get() == self.canvas
            c.create_rectangle(x0,y0,x1,y1,fill=self._panel_color if not focused else "#1c324d",
                               outline=self._accent if focused else "#b18a51",
                               width=3 if focused else 1, tags=("art",tag))
            icon_width = min(78, max(54, round(layout["menu_width"] * .16)))
            c.create_rectangle(x0+1,y0+1,x0+icon_width,y1-1,
                               fill="#203249",outline="",tags=("art",tag))
            self._icon(icon,x0+icon_width/2,y0+h/2,min(h*.29,26),tag)
            tx=x0+icon_width+13
            title_size=max(10,min(round((18 if layout["compact"] else 21)*self.scale),
                                  round(h*.30)))
            title_item = c.create_text(
                tx, y0+h*.33, text=label, anchor="w",
                fill=self._text_color if not disabled else "#94a1ae",
                font=("Georgia", title_size, "bold"), tags=("art",tag))
            # Keep both default and authored labels inside the active card.
            right_limit = x1 - 29
            bounds = c.bbox(title_item)
            while bounds is not None and bounds[2] > right_limit and title_size > 10:
                title_size -= 1
                c.itemconfigure(title_item, font=("Georgia",title_size,"bold"))
                bounds = c.bbox(title_item)
            if bounds is not None and bounds[2] > right_limit:
                short = label
                while len(short) > 1 and c.bbox(title_item)[2] > right_limit:
                    short = short[:-1]
                    c.itemconfigure(title_item,text=short.rstrip()+"…")
            sub = (self.app._t("tk.title.no_save") if disabled else
                   self._resume_caption() if key=="continue"
                   else self.app._t("tk.title." + key + ".detail"))
            c.create_text(tx,y0+h*.71,text=sub,anchor="w",
                          fill=MUTED if not disabled else "#7f8894",
                          width=max(80,x1-tx-32),
                          font=self._font("Segoe UI",9 if layout["compact"] else 12),
                          tags=("art",tag))
            c.create_text(x1-15,y0+h/2, text="›", anchor="center",
                          fill=self._accent if not disabled else "#6e7784",
                          font=self._font("Georgia",19), tags=("art",tag))
            self._region(tag,rect,key=key)

    def _resume_caption(self):
        path = (self.app.player.long_path_for(self.app.campaign_var.get(),int(self.app.slot_var.get()))
                if self.app.long_save_var.get() else
                self.app.player.path_for(self.app.campaign_var.get(),int(self.app.slot_var.get())))
        existing = path if path.is_file() else path.with_name(path.name+".bak")
        if not existing.is_file():
            return "Aucune sauvegarde"
        try:
            date = datetime.fromtimestamp(existing.stat().st_mtime).strftime("%d/%m/%Y")
        except (ValueError,OSError,OverflowError):
            date = ""
        return "Emplacement %s%s" % (self.app.slot_var.get(), " · "+date if date else "")

    def _draw_campaign(self, layout):
        c=self.canvas
        x0,y0,x1,y1=layout["campaign"]
        w,h=x1-x0,y1-y0
        c.create_rectangle(x0,y0,x1,y1,fill="#101b2a",outline="#af884f",width=1,tags="art")
        c.create_text(x0+15,y0+14,anchor="nw",text="Campagne actuelle",fill="#f0d3a0",
                      font=self._font("Georgia",11 if layout["compact"] else 13),tags="art")
        thumb_size=max(58,min(116,round(h*.48)))
        thumb_x, thumb_y = x0+15,y0+41
        if not layout["compact"] and self._backdrop_source is not None:
            if self._thumb_photo is None:
                from PIL import Image,ImageOps,ImageTk
                pic=ImageOps.fit(self._backdrop_source,(thumb_size,thumb_size),
                                  method=Image.Resampling.LANCZOS if hasattr(Image,"Resampling") else Image.LANCZOS)
                self._thumb_photo=ImageTk.PhotoImage(pic,master=self.app.root)
            c.create_image(thumb_x,thumb_y,anchor="nw",image=self._thumb_photo,tags="art")
        else:
            c.create_rectangle(thumb_x,thumb_y,thumb_x+thumb_size,thumb_y+thumb_size,
                               fill="#293e54",outline=self._accent,tags="art")
            self._castle(thumb_x+thumb_size*.5,thumb_y+thumb_size*.86,
                         thumb_size*.7,thumb_size*.58)
        offset = thumb_size+10
        camp = self.app.project.campaign(self.app.campaign_var.get())
        name=camp["name"] if camp is not None else self.app.project.title
        description=(camp.get("description") if camp is not None else None) or self.app.project.subtitle
        if (camp is not None and camp["id"] == "jeanne"
                and "org.drawtemp.titlescreen" not in self.app.project.extensions):
            # Preserve the original Jeanne card until the title screen is authored.
            name = "Les Cendres du Royaume"
            description = "Un royaume en guerre, des choix qui changeront son destin."
        c.create_text(thumb_x+offset,thumb_y+6,anchor="nw",text=name,
                      fill=self._text_color,width=max(80,w-offset-25),
                      font=self._font("Georgia",11 if layout["compact"] else 13),tags="art")
        if not layout["compact"]:
            c.create_text(thumb_x+offset,thumb_y+38,anchor="nw",text=description,
                          fill=MUTED,width=max(80,w-offset-25),
                          font=self._font("Segoe UI",11),tags="art")
        by1=y1-12
        by0=by1-(30 if layout["compact"] else 39)
        bx0=x0+15
        bx1=min(x1-16,bx0+max(176, w*.59))
        tag="title_campaign_change"
        c.create_rectangle(bx0,by0,bx1,by1,fill="#132236",outline=self._accent,
                           width=1,tags=("art",tag))
        c.create_text((bx0+bx1)/2,(by0+by1)/2,text="⇆  " + self.app._t("tk.title.change_campaign"),
                      fill=self._text_color,font=self._font("Georgia",10),tags=("art",tag))
        self._region(tag,(bx0,by0,bx1,by1),key="choose")

    def _draw_footer(self,layout,width,height):
        c=self.canvas
        x=layout.get("footer_x", layout["menu_x"])
        w=layout.get("footer_width", layout["menu_width"])
        y=layout["footer_y"]
        h=layout["footer_height"]
        gap=6 if layout["compact"] else 9
        available_width = max(0, w - 2*gap)
        widths=(available_width*.48,available_width*.245,available_width*.275)
        labels=(("advanced","⚒  " + self.app._t("tk.title.advanced" if not layout["compact"] else "tk.title.advanced_compact")),
                ("credits","♙  " + self.app._t("tk.title.credits")),("help","?  " + self.app._t("tk.title.help")))
        for i,((key,label),cw) in enumerate(zip(labels,widths)):
            xx=x+sum(widths[:i])+gap*i
            xx1=xx+cw
            tag="title_footer_"+key
            c.create_rectangle(xx,y,xx1,y+h,fill="#101a29",outline="#b18a51",tags=("art",tag))
            c.create_text((xx+xx1)/2,y+h/2,text=label,fill=self._text_color,
                          font=self._font("Georgia",9 if layout["compact"] else 12),
                          tags=("art",tag))
            self._region(tag,(xx,y,xx1,y+h),key=key)
        c.create_rectangle(0,height-31,152,height,fill="#101b2a",outline="",tags="art")
        c.create_text(25,height-22,anchor="nw",text="DrawTemp · Player",fill="#b8becc",
                      font=self._font("Segoe UI",9),tags="art")

    def paint(self,width,height):
        if width < 2 or height < 2 or not self.canvas.winfo_exists():
            return
        layout=title_geometry(width,height)
        boxes=resolve_boxes(width, height, layout, self._appearance["positions"])
        custom = dict(layout)
        custom["cards"] = [boxes[key] for key in CARD_KEYS]
        custom["campaign"] = boxes["campaign"]
        custom["footer_x"] = boxes["footer"][0]
        custom["footer_y"] = boxes["footer"][1]
        custom["footer_width"] = boxes["footer"][2] - boxes["footer"][0]
        custom["footer_height"] = boxes["footer"][3] - boxes["footer"][1]
        c=self.canvas
        c.delete("art")
        self._paint_stage(width,height,layout)
        self._draw_header(layout,height,boxes)
        self._draw_cards(custom)
        if self._appearance["show_campaign"]:
            self._draw_campaign(custom)
        self._draw_footer(custom,width,height)
        if self.overlay_shade is not None:
            c.coords(self.overlay_shade,0,0,width,height)
            c.tag_raise(self.overlay_shade)
        if self.overlay_window is not None:
            c.coords(self.overlay_window,width/2,height/2)
            c.tag_raise(self.overlay_window)

    def open_credits(self):
        parent=self._open_overlay(self.app._t("tk.title.credits"))
        self.tk.Label(parent,text="Jeanne d’Arc — Les Cendres du Royaume\n"
                    "Jeu de rôle tactique développé avec DrawTemp.\n"
                    "Illustrations et univers créés pour le projet.",
                    bg=PANEL,fg=self._text_color,justify="left",font=self._font("Georgia",12),
                    wraplength=500).pack(fill="x",pady=16)
        self._panel_button(parent,self.app._t("tk.title.back"),self._close_overlay).pack(fill="x",pady=8)

    def open_help(self):
        parent=self._open_overlay(self.app._t("tk.title.help"))
        info=("Cliquez sur une entrée du menu ou utilisez les flèches ↑/↓ puis Entrée.\n\n"
              "Continuer : charge l'emplacement sélectionné.\n"
              "Nouvelle partie : démarre une aventure ; confirmation si nécessaire.\n"
              "Charger / Campagnes : choisir campagne et emplacement.\n"
              "Options : affichage, audio et raccourcis personnalisables.\n"
              "Échap : fermer ce panneau.")
        self.tk.Label(parent,text=info,bg=PANEL,fg=self._text_color,justify="left",
                      wraplength=495,font=self._font("Segoe UI",11)).pack(fill="x",pady=12)
        self._panel_button(parent,self.app._t("tk.title.back"),self._close_overlay).pack(fill="x",pady=8)