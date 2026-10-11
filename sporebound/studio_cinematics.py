"""Visual cinematic authoring: multi-track timeline, property inspector and preview."""
from copy import deepcopy

from .cinematics import (KINDS, TRIGGERS, cinematic_template, event_template,
                         matching_cinematics)
from .cinematic_player import CinematicPlayback, draw_frame
from .tk_renderer import CanvasRenderer
from .game_project import GameProject
from .model import RuleError, require


class CinematicStudio:
    def __init__(self, owner, notebook):
        self.owner, self.tk, self.ttk = owner, owner.tk, owner.ttk
        self.clip_id = ""
        self.event_id = ""
        self.undo_stack = []
        self.redo_stack = []
        self._refreshing = False
        self._drag = None
        self._positions = []
        self._clip_ids = []
        self._event_ids = []
        self.vars = {name: self.tk.StringVar(value=default) for name, default in {
            "cid": "cinematic_1", "name": "Nouvelle cinématique",
            "trigger": "campaign_start", "target": "", "length": "8000",
            "eid": "event_1", "kind": "dialogue", "start": "0",
            "duration": "1800", "subject": "Jeanne", "text": "Notre histoire commence...",
            "bus": "sfx", "volume": "100", "fadein": "0",
            "fadeout": "0", "duck": "40", "color": "#243c56", "x0": "0.15", "y0": "0.65",
            "x1": "0.65", "y1": "0.65", "zoom0": "1", "zoom1": "1",
        }.items()}
        self.audio_loop = self.tk.BooleanVar(value=False)
        self.cursor = self.tk.DoubleVar(value=0)
        self.preview_renderer = None
        self._build(notebook)

    def _field(self, parent, row, label, key, choices=None):
        self.ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
        var = self.vars[key]
        if choices is None:
            control = self.ttk.Entry(parent, textvariable=var, width=23)
        else:
            control = self.ttk.Combobox(parent, values=choices, textvariable=var,
                                         state="readonly", width=22)
        control.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        parent.columnconfigure(1, weight=1)
        return control

    def _button(self, parent, label, action):
        self.ttk.Button(parent, text=label,
                        command=lambda: self.owner._run(action)).pack(
                            side="left", padx=3, pady=3)

    def _build(self, notebook):
        ttk = self.ttk
        root = ttk.Frame(notebook)
        notebook.add(root, text="Cinématiques")
        self.tab = root
        title = ttk.Frame(root)
        title.pack(fill="x", padx=8, pady=4)
        ttk.Label(title, text="Cinématique — storyboard et timeline",
                  font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self._button(title, "Annuler cinématique", self.undo)
        self._button(title, "Rétablir cinématique", self.redo)
        self._button(title, "Enregistrer projet", self.owner.save_project)
        self._button(title, "Exemple Jeanne", self.example)
        self._button(title, "Bande-son Jeanne", self.example_soundtrack)
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8)
        left = ttk.LabelFrame(main, text="Séquences")
        left.pack(side="left", fill="y", padx=4)
        self.clips = self.tk.Listbox(left, width=24, height=9, exportselection=False)
        self.clips.pack(fill="x", padx=5, pady=5)
        self.clips.bind("<<ListboxSelect>>", self._on_clip)
        clip_form = ttk.Frame(left)
        clip_form.pack(fill="x", padx=4, pady=4)
        for row, label, key in ((0, "ID", "cid"), (1, "Nom", "name"),
                                (2, "Déclenchement", "trigger"),
                                (3, "Campagne / mission", "target"),
                                (4, "Durée (ms)", "length")):
            if key == "trigger":
                self.trigger_box = self._field(clip_form, row, label, key, TRIGGERS)
                self.trigger_box.bind("<<ComboboxSelected>>", self._trigger_change)
            elif key == "target":
                self.target_box = self._field(clip_form, row, label, key, [])
            else:
                self._field(clip_form, row, label, key)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        self._button(buttons, "Créer séquence", self.create_clip)
        self._button(buttons, "Appliquer séquence", self.update_clip)
        self._button(buttons, "Supprimer séquence", self.delete_clip)

        middle = ttk.LabelFrame(main, text="Pistes / événements")
        middle.pack(side="left", fill="both", expand=True, padx=4)
        self.events = self.tk.Listbox(middle, height=9, exportselection=False)
        self.events.pack(fill="x", padx=5, pady=5)
        self.events.bind("<<ListboxSelect>>", self._on_event)
        form = ttk.Frame(middle)
        form.pack(fill="x")
        fields = [
            ("Événement ID", "eid", None),
            ("Type", "kind", KINDS),
            ("Début (ms)", "start", None),
            ("Durée (ms)", "duration", None),
            ("Acteur / voix / son", "subject", None),
            ("Texte du dialogue", "text", None),
            ("Couleur #RRGGBB", "color", None),
            ("Départ X", "x0", None),
            ("Départ Y", "y0", None),
            ("Arrivée X", "x1", None),
            ("Arrivée Y", "y1", None),
            ("Zoom départ", "zoom0", None),
            ("Zoom arrivée", "zoom1", None),
        ]
        for row, (label, key, choices) in enumerate(fields):
            self._field(form, row, label, key, choices)
        audio = ttk.LabelFrame(middle, text="Pistes audio — événements sound")
        audio.pack(fill="x", padx=4, pady=3)
        audio_fields = (
            (0, 0, "Bus", "bus", ("music", "ambience", "voice", "sfx")),
            (0, 2, "Volume (%)", "volume", None),
            (1, 0, "Fondu entrée (ms)", "fadein", None),
            (1, 2, "Fondu sortie (ms)", "fadeout", None),
            (2, 0, "Ducking voix (%)", "duck", None),
        )
        for row, col, label, key, choices in audio_fields:
            ttk.Label(audio, text=label).grid(
                row=row, column=col, sticky="w", padx=3, pady=2)
            if choices is None:
                control = ttk.Entry(audio, textvariable=self.vars[key], width=12)
            else:
                control = ttk.Combobox(audio, state="readonly",
                                       textvariable=self.vars[key],
                                       values=choices, width=12)
            control.grid(row=row, column=col+1, sticky="ew", padx=3, pady=2)
        ttk.Checkbutton(audio, text="Répéter la piste", variable=self.audio_loop).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=3)
        audio.columnconfigure(1, weight=1)
        audio.columnconfigure(3, weight=1)
        buttons = ttk.Frame(middle)
        buttons.pack(fill="x")
        self._button(buttons, "Ajouter événement", self.add_event)
        self._button(buttons, "Appliquer événement", self.update_event)
        self._button(buttons, "Supprimer événement", self.delete_event)
        side = ttk.LabelFrame(main, text="Aperçu instantané")
        side.pack(side="right", fill="both", expand=True, padx=4)
        self.preview_canvas = self.tk.Canvas(side, height=290, width=370,
                                             background="#101a2b", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview_canvas.bind("<Configure>", lambda _: self._preview())
        ttk.Scale(side, from_=0, to=8000, variable=self.cursor,
                  command=lambda _: self._preview()).pack(fill="x", padx=8, pady=4)
        controls = ttk.Frame(side)
        controls.pack(fill="x")
        self._button(controls, "Lecture complète", self.preview)
        self._button(controls, "Début", lambda: self.cursor.set(0))
        ttk.Label(side, text="Événements temporels, caméra interpolée, dialogue et fondus.",
                  wraplength=340).pack(fill="x", padx=7, pady=5)
        timeline = ttk.LabelFrame(root, text="Timeline — cliquer pour parcourir, glisser pour déplacer")
        timeline.pack(fill="x", padx=12, pady=7)
        self.timeline = self.tk.Canvas(timeline, height=175, background="#152237",
                                       highlightthickness=0)
        self.timeline.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(timeline, orient="vertical",
                                  command=self.timeline.yview)
        scrollbar.pack(side="right", fill="y")
        self.timeline.configure(yscrollcommand=scrollbar.set)
        self.timeline.bind("<MouseWheel>", lambda e: self.timeline.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        self.timeline.bind("<Button-4>", lambda _: self.timeline.yview_scroll(-1, "units"))
        self.timeline.bind("<Button-5>", lambda _: self.timeline.yview_scroll(1, "units"))
        self.timeline.bind("<Configure>", lambda _: self._timeline())
        self.timeline.bind("<ButtonPress-1>", self._press)
        self.timeline.bind("<ButtonRelease-1>", self._release)

    def _project(self):
        return self.owner.project

    def _clip(self):
        clip = next((c for c in self._project().cinematics if c["id"] == self.clip_id), None)
        if clip is None:
            raise RuleError("Sélectionner une cinématique")
        return clip

    def _event(self):
        event = next((e for e in self._clip()["events"] if e["id"] == self.event_id), None)
        if event is None:
            raise RuleError("Sélectionner un événement")
        return event

    def _apply(self, mutate):
        before = self._project().to_dict()
        updated = deepcopy(before)
        mutate(updated)
        candidate = GameProject.from_dict(updated, self.owner._content())
        self.undo_stack.append(before)
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        self.owner.project = candidate
        self.owner.project_status.config(
            text="Cinématique modifiée — enregistrer le projet de jeu.")
        self.refresh()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._project().to_dict())
        self.owner.project = GameProject.from_dict(
            self.undo_stack.pop(), self.owner._content())
        self.refresh()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._project().to_dict())
        self.owner.project = GameProject.from_dict(
            self.redo_stack.pop(), self.owner._content())
        self.refresh()

    def reset_project(self):
        if self.preview_renderer is not None:
            self.preview_renderer.dispose()
        self.preview_renderer = CanvasRenderer(
            self.preview_canvas, registry=self.owner.project.asset_registry(),
            asset_root=self.owner.project_path.parent)
        self.clip_id = self.event_id = ""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.refresh()

    def _trigger_change(self, _event=None):
        kind = self.vars["trigger"].get()
        if self._project() is None:
            return
        targets = ([c["id"] for c in self._project().campaigns]
                   if kind == "campaign_start" else
                   [s["id"] for s in self._project().story.get("scenes", [])]
                   if kind == "scene" else
                   [m["id"] for m in self.owner.doc().data["missions"]])
        self.target_box["values"] = targets
        if self.vars["target"].get() not in targets:
            self.vars["target"].set(targets[0] if targets else "")

    def _on_clip(self, _event=None):
        if self._refreshing or not self.clips.curselection():
            return
        self.clip_id = self._clip_ids[self.clips.curselection()[0]]
        self.event_id = ""
        self.refresh()

    def _on_event(self, _event=None):
        if self._refreshing or not self.events.curselection():
            return
        self.event_id = self._event_ids[self.events.curselection()[0]]
        self._load_event()
        self._timeline()
        self.cursor.set(self._event()["start_ms"])
        self._preview()

    def _load_event(self):
        event = self._event()
        for key, field in (("eid", "id"), ("kind", "kind"),
                           ("start", "start_ms"), ("duration", "duration_ms")):
            self.vars[key].set(str(event[field]))
        kind = event["kind"]
        self.vars["subject"].set(event.get("actor", event.get("speaker", event.get("cue", ""))))
        self.vars["text"].set(event.get("text", ""))
        self.vars["color"].set(event.get("color", "#243c56"))
        for key, index, field in (("x0", 0, "from"), ("y0", 1, "from"),
                                  ("x1", 0, "to"), ("y1", 1, "to")):
            self.vars[key].set(str(event.get(field, [0., 0.])[index]))
        self.vars["zoom0"].set(str(event.get("zoom_from", 1)))
        self.vars["zoom1"].set(str(event.get("zoom_to", 1)))
        self.vars["bus"].set(event.get("bus", "sfx"))
        self.vars["volume"].set(str(event.get("volume", 100)))
        self.vars["fadein"].set(str(event.get("fade_in_ms", 0)))
        self.vars["fadeout"].set(str(event.get("fade_out_ms", 0)))
        self.vars["duck"].set(str(event.get("duck_percent", 40)))
        self.audio_loop.set(event.get("loop", False))

    def _spec(self):
        v = lambda name: self.vars[name].get().strip()
        kind = v("kind")
        event = event_template(kind, v("eid"), int(v("start")), int(v("duration")))
        if kind == "actor":
            event.update(actor=v("subject"),
                         **{"from": [float(v("x0")), float(v("y0"))],
                            "to": [float(v("x1")), float(v("y1"))]})
        elif kind == "camera":
            event.update({"from": [float(v("x0")), float(v("y0"))],
                          "to": [float(v("x1")), float(v("y1"))],
                          "zoom_from": float(v("zoom0")), "zoom_to": float(v("zoom1"))})
        elif kind == "dialogue":
            event.update(speaker=v("subject"), text=v("text"))
        elif kind in ("fade", "background"):
            event["color"] = v("color")
        elif kind == "sound":
            bus = v("bus")
            event.update(cue=v("subject"), bus=bus,
                         volume=int(v("volume")),
                         fade_in_ms=int(v("fadein")),
                         fade_out_ms=int(v("fadeout")),
                         loop=self.audio_loop.get())
            if bus == "voice":
                event["duck_percent"] = int(v("duck"))
        return event

    def create_clip(self):
        v = self.vars
        clip = cinematic_template(v["cid"].get().strip(), v["name"].get().strip(),
                                  v["trigger"].get(), v["target"].get())
        clip["duration_ms"] = int(v["length"].get())
        self._apply(lambda data: data.setdefault("cinematics", []).append(clip))
        self.clip_id, self.event_id = clip["id"], ""
        self.refresh()

    def update_clip(self):
        cid = self.clip_id
        v = self.vars
        def edit(data):
            clip = next(c for c in data["cinematics"] if c["id"] == cid)
            clip.update(name=v["name"].get(), duration_ms=int(v["length"].get()),
                        trigger={"kind": v["trigger"].get(), "target": v["target"].get()})
        self._apply(edit)

    def delete_clip(self):
        cid = self.clip_id
        self._clip()
        self._apply(lambda data: data.update(cinematics=[
            c for c in data["cinematics"] if c["id"] != cid]))
        self.clip_id = self.event_id = ""
        self.refresh()

    def add_event(self):
        eid = self.vars["eid"].get().strip()
        event = self._spec()
        cid = self.clip_id
        self._clip()
        self._apply(lambda data: next(c for c in data["cinematics"]
                                     if c["id"] == cid)["events"].append(event))
        self.event_id = eid
        self.refresh()

    def update_event(self):
        self._event()
        eid, cid = self.event_id, self.clip_id
        spec = self._spec()
        require(spec["id"] == eid, "Event ID cannot change; delete and recreate")
        def edit(data):
            events = next(c for c in data["cinematics"] if c["id"] == cid)["events"]
            index = next(i for i, e in enumerate(events) if e["id"] == eid)
            events[index] = spec
        self._apply(edit)

    def delete_event(self):
        self._event()
        cid, eid = self.clip_id, self.event_id
        def edit(data):
            clip = next(c for c in data["cinematics"] if c["id"] == cid)
            clip["events"] = [e for e in clip["events"] if e["id"] != eid]
        self._apply(edit)
        self.event_id = ""
        self.refresh()

    def example(self):
        from .cinematics import event_template
        cid = "jeanne_prologue"
        target = self.owner.project.campaigns[0]["id"]
        example = cinematic_template(cid, "Jeanne — la vision et le village en feu",
                                     "campaign_start", target)
        example["duration_ms"] = 10000
        bg = event_template("background", "champs", 0, 10000)
        actor = event_template("actor", "jeanne_walk", 0, 8200)
        dialogue = event_template("dialogue", "vision", 1500, 4400)
        dialogue.update(speaker="Une voix", text="Jeanne, ton destin est devant toi.")
        cam = event_template("camera", "camera_pan", 0, 7000)
        cam["to"] = [0.12, -0.04]
        fade = event_template("fade", "fumee", 8200, 1800)
        example["events"] = [bg, actor, dialogue, cam, fade]
        self._apply(lambda data: data.setdefault("cinematics", []).append(example))
        self.clip_id, self.event_id = cid, ""
        self.refresh()

    def example_soundtrack(self):
        """Add authored sound beats to Jeanne's sample; users bind audio files later."""
        cid = "jeanne_prologue"
        clip = next((c for c in self._project().cinematics if c["id"] == cid), None)
        require(clip is not None, "Créer d'abord « Exemple Jeanne »")
        spec = (
            ("jeanne_music", "jeanne_theme", "music", 0, 10000, True, 1400, 1900),
            ("jeanne_fields", "jeanne_wind", "ambience", 0, 8200, True, 800, 1200),
            ("jeanne_voice", "jeanne_vision", "voice", 1500, 4400, False, 250, 550),
            ("jeanne_fire", "jeanne_fire", "ambience", 8000, 2000, True, 400, 600),
        )
        existing = {e["id"] for e in clip["events"]}
        require(not (existing & {item[0] for item in spec}),
                "La bande-son Jeanne existe déjà")
        events = []
        for eid, cue, bus, start, duration, loop, fade_in, fade_out in spec:
            event = event_template("sound", eid, start, duration)
            event.update(cue=cue, bus=bus, loop=loop, volume=85,
                         fade_in_ms=fade_in, fade_out_ms=fade_out)
            if bus == "voice":
                event["duck_percent"] = 30
            events.append(event)
        self._apply(lambda data: next(c for c in data["cinematics"]
                                      if c["id"] == cid)["events"].extend(events))
        self.clip_id = cid
        self.refresh()

    def refresh(self):
        if self._project() is None:
            return
        self._refreshing = True
        clips = self._project().cinematics
        self._clip_ids = [c["id"] for c in clips]
        self.clips.delete(0, "end")
        for i, clip in enumerate(clips):
            self.clips.insert("end", clip["id"] + " — " + clip["name"])
            if clip["id"] == self.clip_id:
                self.clips.selection_set(i)
        clip = next((c for c in clips if c["id"] == self.clip_id), None)
        if clip:
            for key, val in (("cid", clip["id"]), ("name", clip["name"]),
                             ("trigger", clip["trigger"]["kind"]),
                             ("target", clip["trigger"]["target"]),
                             ("length", clip["duration_ms"])):
                self.vars[key].set(str(val))
        self._trigger_change()
        self.events.delete(0, "end")
        events = sorted(clip["events"], key=lambda e: (e["start_ms"], e["id"])) if clip else []
        self._event_ids = [e["id"] for e in events]
        for i, event in enumerate(events):
            display_kind = (f"son:{event.get('bus', 'sfx')}"
                            if event["kind"] == "sound" else event["kind"])
            self.events.insert("end", f"{event['start_ms']:>6}  {display_kind} — {event['id']}")
            if event["id"] == self.event_id:
                self.events.selection_set(i)
        if clip:
            self.cursor.set(min(self.cursor.get(), clip["duration_ms"]))
            if self.event_id in self._event_ids:
                self._load_event()
        self._refreshing = False
        self._timeline()
        self._preview()

    def _timeline(self):
        canvas = self.timeline
        canvas.delete("all")
        self._positions = []
        if self._project() is None:
            return
        clip = next((c for c in self._project().cinematics if c["id"] == self.clip_id), None)
        if clip is None:
            return
        width = max(400, canvas.winfo_width())
        duration = clip["duration_ms"]
        height = max(175, 26 * len(clip["events"]) + 48)
        canvas.configure(scrollregion=(0, 0, width, height))
        for index in range(6):
            x = 80 + (width - 100) * index / 5
            canvas.create_line(x, 10, x, height, fill="#344660")
            canvas.create_text(x, 8, text=f"{duration * index / 5000:.1f}s",
                               anchor="s", fill="#a9bcd2")
        colors = {"background": "#506d93", "actor": "#c2a06e", "camera": "#78b99b",
                  "dialogue": "#9b8ad0", "fade": "#da8b8b", "sound": "#66bace"}
        buses = {"music": "#3fbd9c", "ambience": "#65a1d3",
                 "voice": "#e4b75e", "sfx": "#b48fca"}
        for i, event in enumerate(sorted(clip["events"], key=lambda e: (e["start_ms"], e["id"]))):
            y = 26 + i * 26
            x0 = 80 + (width - 100) * event["start_ms"] / duration
            x1 = 80 + (width - 100) * (event["start_ms"] + event["duration_ms"]) / duration
            canvas.create_rectangle(x0, y, max(x0+5, x1), y+20,
                                    fill=(buses.get(event.get("bus", "sfx"), "#66bace")
                                          if event["kind"] == "sound"
                                          else colors[event["kind"]]),
                                    outline="white" if event["id"] == self.event_id else "")
            label = (f"{event.get('bus', 'sfx')}:{event['id']}"
                     if event["kind"] == "sound" else event["id"])
            canvas.create_text(x0+3, y+10, anchor="w", text=label[:20],
                               fill="#081626")
            self._positions.append((x0, x1, y, y+20, event["id"]))
        playhead = 80 + (width - 100) * self.cursor.get() / duration
        canvas.create_line(playhead, 16, playhead, height, fill="#f5ead5", width=2)

    def _press(self, event):
        y = self.timeline.canvasy(event.y)
        self._drag = (event.x, y, None)
        for x0, x1, y0, y1, eid in self._positions:
            if x0 <= event.x <= max(x0+5, x1) and y0 <= y <= y1:
                self._drag = (event.x, y, eid)
                self.event_id = eid
                self.refresh()
                break

    def _release(self, event):
        if not self._drag:
            return
        x0, _, eid = self._drag
        self._drag = None
        clip = self._clip()
        width = max(400, self.timeline.winfo_width()) - 100
        if eid and abs(event.x - x0) > 5:
            current = next(e for e in clip["events"] if e["id"] == eid)
            new_start = int(round((current["start_ms"] +
                                   (event.x - x0) * clip["duration_ms"] / width) / 100) * 100)
            new_start = max(0, min(clip["duration_ms"] - current["duration_ms"], new_start))
            cid = self.clip_id
            def edit(data):
                events = next(c for c in data["cinematics"] if c["id"] == cid)["events"]
                next(e for e in events if e["id"] == eid)["start_ms"] = new_start
            self._apply(edit)
        else:
            ms = (event.x - 80) * clip["duration_ms"] / width
            self.cursor.set(max(0, min(clip["duration_ms"], ms)))
        self._timeline()
        self._preview()

    def _preview(self):
        if self._project() is None:
            return
        clip = next((c for c in self._project().cinematics if c["id"] == self.clip_id), None)
        if clip:
            draw_frame(self.preview_canvas, clip, self.cursor.get(),
                       self.preview_renderer)
            self._timeline()

    def preview(self):
        clip = deepcopy(self._clip())
        window = self.tk.Toplevel(self.tab)
        window.title("Aperçu cinématique — " + clip["name"])
        window.geometry("820x530")
        playback = CinematicPlayback(
            window, self.tk, self.ttk, clip, window.destroy,
            registry=self.owner.project.asset_registry(),
            asset_root=self.owner.project_path.parent)
        window.protocol("WM_DELETE_WINDOW", lambda: (playback.close(), window.destroy()))
