"""Visual cinematic authoring: multi-track timeline, property inspector and preview."""
from copy import deepcopy

from .cinematics import (KINDS, TRIGGERS, EASINGS, EXPRESSIONS, SHOT_TRANSITIONS,
                         cinematic_template, event_template, matching_cinematics)
from .event_cinematic_qa import audit_event_cinematic_path
from .audio_timeline import mix_at
from .cinematic_authoring4 import (
    add_motion_keyframe, update_motion_keyframe, remove_motion_keyframe,
    move_event, resize_event, clone_event)
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
        self._key_handles = []
        self.selected_key_ms = None
        self._clip_ids = []
        self._event_ids = []
        self.vars = {name: self.tk.StringVar(value=default) for name, default in {
            "cid": "cinematic_1", "name": "Nouvelle cinématique",
            "trigger": "campaign_start", "target": "", "length": "8000",
            "eid": "event_1", "kind": "dialogue", "start": "0",
            "duration": "1800", "subject": "Jeanne", "text": "Notre histoire commence...",
            "bus": "sfx", "volume": "100", "volume_to": "100",
            "easing": "linear", "shot": "", "transition": "cut",
            "portrait": "", "expression": "neutral", "pace": "0", "fadein": "0",
            "fadeout": "0", "duck": "40", "color": "#243c56", "x0": "0.15", "y0": "0.65",
            "x1": "0.65", "y1": "0.65", "zoom0": "1", "zoom1": "1",
            "key_time": "500", "key_x": "0.5", "key_y": "0.5",
            "key_zoom": "1", "copy_id": "event_copy",
        }.items()}
        self.qa_status = self.tk.StringVar(value="")
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
        self._button(title, "QA événement → choix", self.audit_path)
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
                                (3, "Cible (campagne / mission / événement)", "target"),
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
        # Contextual tabs replace the long all-properties-at-once column.
        common = ttk.Frame(middle)
        common.pack(fill="x", padx=4, pady=3)
        for row, (label, key, values) in enumerate((
                ("ID", "eid", None), ("Type", "kind", KINDS),
                ("Début (ms)", "start", None), ("Durée (ms)", "duration", None))):
            self._field(common, row, label, key, values)
        self.inspector_tabs = ttk.Notebook(middle)
        self.inspector_tabs.pack(fill="x", padx=4, pady=3)
        motion = ttk.Frame(self.inspector_tabs)
        dialogue = ttk.Frame(self.inspector_tabs)
        audio = ttk.Frame(self.inspector_tabs)
        self.inspector_tabs.add(motion, text="Animation / caméra")
        self.inspector_tabs.add(dialogue, text="Dialogue / portrait")
        self.inspector_tabs.add(audio, text="Son / musique")
        for row, (label, key, choices) in enumerate((
                ("Acteur", "subject", None), ("Couleur", "color", None),
                ("Départ X", "x0", None), ("Départ Y", "y0", None),
                ("Arrivée X", "x1", None), ("Arrivée Y", "y1", None),
                ("Zoom départ", "zoom0", None), ("Zoom arrivée", "zoom1", None),
                ("Easing", "easing", EASINGS), ("Plan", "shot", None),
                ("Transition", "transition", SHOT_TRANSITIONS))):
            self._field(motion, row, label, key, choices)
        keys = ttk.LabelFrame(motion, text="Keyframes (acteur / caméra)")
        keys.grid(row=11, column=0, columnspan=2, sticky="ew", pady=4)
        self.key_list = self.tk.Listbox(keys, height=3, exportselection=False)
        self.key_list.pack(fill="x", padx=4, pady=2)
        self.key_list.bind("<<ListboxSelect>>", self._select_key)
        key_form = ttk.Frame(keys)
        key_form.pack(fill="x")
        for row, (label, key) in enumerate((
                ("Temps relatif (ms)", "key_time"), ("Position X", "key_x"),
                ("Position Y", "key_y"), ("Zoom", "key_zoom"))):
            self._field(key_form, row, label, key)
        key_buttons = ttk.Frame(keys)
        key_buttons.pack(fill="x")
        self._button(key_buttons, "Ajouter au curseur", self.add_key)
        self._button(key_buttons, "Modifier key", self.update_key)
        self._button(key_buttons, "Supprimer key", self.delete_key)
        for row, (label, key, choices) in enumerate((
                ("Intervenant", "subject", None), ("Texte", "text", None),
                ("Portrait", "portrait", None),
                ("Expression", "expression", EXPRESSIONS),
                ("Caractères/s (0=direct)", "pace", None))):
            self._field(dialogue, row, label, key, choices)
        for row, (label, key, choices) in enumerate((
                ("Son", "subject", None),
                ("Bus", "bus", ("music", "ambience", "voice", "sfx")),
                ("Volume initial (%)", "volume", None),
                ("Volume final (%)", "volume_to", None),
                ("Fondu entrée (ms)", "fadein", None),
                ("Fondu sortie (ms)", "fadeout", None),
                ("Ducking voix (%)", "duck", None))):
            self._field(audio, row, label, key, choices)
        ttk.Checkbutton(audio, text="Répéter la piste",
                        variable=self.audio_loop).grid(
                            row=7, column=0, columnspan=2, sticky="w", padx=4)
        buttons = ttk.Frame(middle)
        buttons.pack(fill="x")
        self._button(buttons, "Ajouter événement", self.add_event)
        self._button(buttons, "Appliquer événement", self.update_event)
        self._button(buttons, "Dupliquer", self.duplicate_event)
        self._button(buttons, "Supprimer événement", self.delete_event)
        self._button(buttons, "Ajuster durée", self.resize_selected)
        ttk.Label(middle, textvariable=self.qa_status, wraplength=460).pack(
            fill="x", padx=5, pady=3)
        side = ttk.LabelFrame(main, text="Aperçu instantané")
        side.pack(side="right", fill="both", expand=True, padx=4)
        self.preview_canvas = self.tk.Canvas(side, height=290, width=370,
                                             background="#101a2b", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.preview_canvas.bind("<Configure>", lambda _: self._preview())
        self.preview_scale = ttk.Scale(side, from_=0, to=8000,
                                       variable=self.cursor,
                                       command=lambda _: self._preview())
        self.preview_scale.pack(fill="x", padx=8, pady=4)
        controls = ttk.Frame(side)
        controls.pack(fill="x")
        self._button(controls, "Lecture complète", self.preview)
        self._button(controls, "Début", lambda: self.cursor.set(0))
        ttk.Label(side, text="Plans, portraits, interpolations et mixage au curseur.",
                  wraplength=340).pack(fill="x", padx=7, pady=5)
        self.audio_canvas = self.tk.Canvas(side, width=360, height=96,
                                           background="#111c2a",
                                           highlightthickness=0)
        self.audio_canvas.pack(fill="x", padx=4, pady=4)
        self.audio_caption = self.tk.StringVar(value="Audio : sélectionner une séquence")
        ttk.Label(side, textvariable=self.audio_caption).pack(
            fill="x", padx=6, pady=2)
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
        self.timeline.bind("<B1-Motion>", self._drag_motion)
        self.timeline.bind("<Escape>", lambda _: self.cancel_drag())

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
        if hasattr(self.owner, "capture_history"):
            self.owner.capture_history()
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
                   [f"{mission['id']}/{event['id']}"
                    for mission in self.owner.doc().data["missions"]
                    for event in mission.get("triggers", [])]
                   if kind == "tactical_event" else
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
        self.vars["easing"].set(event.get("easing", "linear"))
        self.vars["shot"].set(event.get("shot", ""))
        self.vars["transition"].set(event.get("transition", "cut"))
        self.vars["portrait"].set(event.get("portrait", ""))
        self.vars["expression"].set(event.get("expression", "neutral"))
        self.vars["pace"].set(str(event.get("chars_per_second", 0)))
        self.vars["bus"].set(event.get("bus", "sfx"))
        self.vars["volume"].set(str(event.get("volume", 100)))
        self.vars["volume_to"].set(str(event.get("volume_to", event.get("volume", 100))))
        self.vars["fadein"].set(str(event.get("fade_in_ms", 0)))
        self.vars["fadeout"].set(str(event.get("fade_out_ms", 0)))
        self.vars["duck"].set(str(event.get("duck_percent", 40)))
        self.audio_loop.set(event.get("loop", False))
        self._refresh_keys()

    def _refresh_keys(self):
        self.key_list.delete(0, "end")
        event = next((e for e in self._clip()["events"]
                      if e["id"] == self.event_id), None)
        if event is None or event["kind"] not in ("actor", "camera"):
            self.selected_key_ms = None
            return
        keys = event.get("keyframes", [])
        if self.selected_key_ms not in [key["at_ms"] for key in keys]:
            self.selected_key_ms = None
        for index, key in enumerate(keys):
            label = (f"{key['at_ms']:>5} ms  ({key['pos'][0]:.2f}, "
                     f"{key['pos'][1]:.2f})" +
                     (f" zoom {key['zoom']:.2f}" if "zoom" in key else ""))
            self.key_list.insert("end", label)
            if key["at_ms"] == self.selected_key_ms:
                self.key_list.selection_set(index)

    def _select_key(self, _event=None):
        if self._refreshing or not self.key_list.curselection():
            return
        keys = self._event().get("keyframes", [])
        index = self.key_list.curselection()[0]
        if index >= len(keys):
            return
        key = keys[index]
        self.selected_key_ms = key["at_ms"]
        for name, value in (("key_time", key["at_ms"]),
                            ("key_x", key["pos"][0]), ("key_y", key["pos"][1]),
                            ("key_zoom", key.get("zoom", 1))):
            self.vars[name].set(str(value))
        self.cursor.set(self._event()["start_ms"] + self.selected_key_ms)
        self._timeline()

    def _spec(self):
        v = lambda name: self.vars[name].get().strip()
        kind = v("kind")
        event = event_template(kind, v("eid"), int(v("start")), int(v("duration")))
        if kind == "actor":
            event.update(actor=v("subject"), easing=v("easing"),
                         **{"from": [float(v("x0")), float(v("y0"))],
                            "to": [float(v("x1")), float(v("y1"))]})
        elif kind == "camera":
            event.update({"from": [float(v("x0")), float(v("y0"))],
                          "to": [float(v("x1")), float(v("y1"))],
                          "zoom_from": float(v("zoom0")), "zoom_to": float(v("zoom1")),
                          "easing": v("easing"), "transition": v("transition")})
            if v("shot"):
                event["shot"] = v("shot")
        elif kind == "dialogue":
            event.update(speaker=v("subject"), text=v("text"),
                         expression=v("expression"),
                         chars_per_second=int(v("pace")))
            if v("portrait"):
                event["portrait"] = v("portrait")
        elif kind in ("fade", "background"):
            event["color"] = v("color")
            if kind == "fade":
                event["easing"] = v("easing")
        elif kind == "sound":
            bus = v("bus")
            event.update(cue=v("subject"), bus=bus,
                         volume=int(v("volume")),
                         volume_to=int(v("volume_to")),
                         fade_in_ms=int(v("fadein")),
                         fade_out_ms=int(v("fadeout")),
                         loop=self.audio_loop.get())
            if bus == "voice":
                event["duck_percent"] = int(v("duck"))
        if kind in ("actor", "camera") and self.event_id == event["id"]:
            old = next((e for e in self._clip()["events"]
                        if e["id"] == self.event_id), None)
            if old is not None and old["kind"] == kind and old.get("keyframes"):
                event["keyframes"] = deepcopy(old["keyframes"])
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

    def _update_selected_event(self, replacement):
        cid, eid = self.clip_id, self.event_id
        def commit(data):
            events = next(c for c in data["cinematics"]
                          if c["id"] == cid)["events"]
            events[next(i for i, e in enumerate(events)
                        if e["id"] == eid)] = replacement
        self._apply(commit)

    def add_key(self):
        event = self._event()
        local = int(round(self.cursor.get())) - event["start_ms"]
        if not 0 < local < event["duration_ms"]:
            local = int(self.vars["key_time"].get())
        replacement = add_motion_keyframe(event, local)
        self.selected_key_ms = local
        self._update_selected_event(replacement)

    def update_key(self):
        event = self._event()
        require(self.selected_key_ms is not None, "Sélectionner une keyframe")
        at = int(self.vars["key_time"].get())
        pos = [float(self.vars["key_x"].get()), float(self.vars["key_y"].get())]
        zoom = (float(self.vars["key_zoom"].get())
                if event["kind"] == "camera" else None)
        replacement = update_motion_keyframe(
            event, self.selected_key_ms, at_ms=at, pos=pos, zoom=zoom)
        self.selected_key_ms = at
        self._update_selected_event(replacement)

    def delete_key(self):
        require(self.selected_key_ms is not None, "Sélectionner une keyframe")
        result = remove_motion_keyframe(self._event(), self.selected_key_ms)
        self.selected_key_ms = None
        self._update_selected_event(result)

    def duplicate_event(self):
        event, clip = self._event(), self._clip()
        ids = {row["id"] for row in clip["events"]}
        root = event["id"][:56] + "_copy"
        eid = root
        counter = 2
        while eid in ids:
            eid = f"{root[:55]}{counter}"
            counter += 1
        start = min(event["start_ms"] + 100,
                    clip["duration_ms"] - event["duration_ms"])
        copy = clone_event(event, eid, start, clip["duration_ms"])
        cid = self.clip_id
        self._apply(lambda data: next(c for c in data["cinematics"]
                                      if c["id"] == cid)["events"].append(copy))
        self.event_id = eid
        self.selected_key_ms = None
        self.refresh()

    def resize_selected(self):
        event = self._event()
        replacement = resize_event(event, int(self.vars["duration"].get()),
                                   self._clip()["duration_ms"])
        self._update_selected_event(replacement)

    def audit_path(self):
        """Authoring certification; choices are still executed by StoryBook."""
        clip = self._clip()
        require(clip["trigger"]["kind"] == "scene",
                "Le contrôle R7.16 attend une cinématique liée à une scène")
        scene_id = clip["trigger"]["target"]
        story = self._project().story
        for kind, field in (("tactical_event", "during_tactical_event"),
                            ("strategic_event", "after_strategic_event")):
            for source, linked in story.get(field, {}).items():
                if linked != scene_id:
                    continue
                scene = next(s for s in story["scenes"] if s["id"] == scene_id)
                choice = next((c for c in scene["choices"]
                               if c.get("effects") or c.get("tactical_effects")
                               or c.get("next_scene")), None)
                require(choice is not None, "La scène ne possède pas de conséquence")
                report = audit_event_cinematic_path(
                    self._project(), self.owner._content(), source_kind=kind,
                    source_id=source, choice_id=choice["id"])
                self.qa_status.set(
                    f"R7.16 ✓ {report.source_id} → {report.scene_id} → "
                    f"{', '.join(report.cinematic_ids)} → {report.choice_id} "
                    f"(SHA {report.timeline_sha256[:12]})")
                return report
        raise RuleError("Aucun événement lié à cette scène : ouvrir le Story Studio")

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
            self.preview_scale.configure(to=clip["duration_ms"])
            self.cursor.set(min(self.cursor.get(), clip["duration_ms"]))
            if self.event_id in self._event_ids:
                self._load_event()
        self._refreshing = False
        self._timeline()
        self._preview()

    def _timeline(self):
        """Lane-based storyboard with keyframe handles and a live playhead."""
        canvas = self.timeline
        canvas.delete("all")
        self._positions, self._key_handles = [], []
        if self._project() is None:
            return
        clip = next((c for c in self._project().cinematics
                     if c["id"] == self.clip_id), None)
        if clip is None:
            return
        duration = clip["duration_ms"]
        width = max(460, canvas.winfo_width())
        origin, span = 112, width - 128
        lanes = [
            ("background", "Décor"), ("camera", "Caméra"),
            ("actor", "Acteurs"), ("dialogue", "Dialogues"),
            ("fade", "Fondus"), ("music", "Musique"),
            ("ambience", "Ambiance"), ("voice", "Voix"),
            ("sfx", "Effets"),
        ]
        rows = {kind: 31 + i * 32 for i, (kind, _) in enumerate(lanes)}
        height = 42 + 32 * len(lanes)
        canvas.configure(scrollregion=(0, 0, width, height))
        for lane, name in lanes:
            y = rows[lane]
            canvas.create_line(0, y+23, width, y+23, fill="#344660")
            canvas.create_text(5, y+10, anchor="w", text=name,
                               fill="#cbd9e6")
        for index in range(6):
            x = origin + span * index / 5
            canvas.create_line(x, 16, x, height, fill="#344660")
            canvas.create_text(x, 14, text=f"{duration*index/5000:.1f}s",
                               anchor="s", fill="#a9bcd2")
        colors = {"background": "#506d93", "actor": "#c2a06e",
                  "camera": "#78b99b", "dialogue": "#9b8ad0",
                  "fade": "#da8b8b", "music": "#3fbd9c",
                  "ambience": "#65a1d3", "voice": "#e4b75e",
                  "sfx": "#b48fca"}
        for event in sorted(clip["events"],
                            key=lambda e: (e["start_ms"], e["id"])):
            lane = (event.get("bus", "sfx") if event["kind"] == "sound"
                    else event["kind"])
            y = rows[lane]
            x0 = origin + span * event["start_ms"] / duration
            x1 = origin + span * (event["start_ms"]+event["duration_ms"]) / duration
            canvas.create_rectangle(x0, y, max(x0+5, x1), y+21,
                                    fill=colors[lane],
                                    outline="#ffffff"
                                    if event["id"] == self.event_id else "")
            canvas.create_text(x0+4, y+10, anchor="w",
                               text=event["id"][:22], fill="#081626")
            self._positions.append((x0, x1, y, y+21, event["id"]))
            for key in event.get("keyframes", ()):
                kx = origin + span * (event["start_ms"]+key["at_ms"]) / duration
                ky = y + 11
                canvas.create_polygon(kx, ky-7, kx+6, ky, kx, ky+7,
                                      kx-6, ky,
                                      fill=("#fef08a" if event["id"] == self.event_id
                                            and key["at_ms"] == self.selected_key_ms
                                            else "#ffffff"),
                                      outline="#172535")
                self._key_handles.append((kx, ky, event["id"], key["at_ms"]))
        playhead = origin + span * self.cursor.get() / duration
        canvas.create_line(playhead, 18, playhead, height,
                           fill="#f5ead5", width=2)
        canvas.focus_set()

    def _press(self, event):
        canvas_y = self.timeline.canvasy(event.y)
        self._drag = None
        # Keyframe handles take priority over their containing clip.
        for kx, ky, eid, at in reversed(self._key_handles):
            if abs(event.x-kx) <= 8 and abs(canvas_y-ky) <= 9:
                self._drag = ("key", event.x, eid, at)
                self.event_id, self.selected_key_ms = eid, at
                self.refresh()
                self._select_key()
                return
        for x0, x1, y0, y1, eid in reversed(self._positions):
            if x0 <= event.x <= max(x0+5, x1) and y0 <= canvas_y <= y1:
                self._drag = ("event", event.x, eid, None)
                self.event_id = eid
                self.selected_key_ms = None
                self.refresh()
                return
        self._drag = ("seek", event.x, None, None)

    def _drag_motion(self, event):
        if self._drag is None:
            return
        kind, start_x, eid, old_key = self._drag
        self.timeline.delete("drag-preview")
        if kind == "seek":
            return
        dx = event.x - start_x
        row = next((pos for pos in self._positions if pos[4] == eid), None)
        if row is None:
            return
        if kind == "event":
            x0, x1, y0, y1, _ = row
            self.timeline.create_rectangle(x0+dx, y0, x1+dx, y1,
                                           outline="#ffffff", width=2,
                                           dash=(3, 2), tags="drag-preview")
        else:
            handle = next(((x, y) for x, y, event_id, at
                           in self._key_handles
                           if event_id == eid and at == old_key), None)
            if handle:
                x, y = handle
                self.timeline.create_polygon(x+dx, y-8, x+dx+7, y,
                                             x+dx, y+8, x+dx-7, y,
                                             outline="#ffffff", fill="",
                                             tags="drag-preview")

    def cancel_drag(self):
        self._drag = None
        self.timeline.delete("drag-preview")

    def _release(self, event):
        if self._drag is None:
            return
        kind, initial_x, eid, old_key = self._drag
        self.cancel_drag()
        clip = self._clip()
        width = max(460, self.timeline.winfo_width()) - 128
        offset_ms = (event.x-initial_x) * clip["duration_ms"] / width
        if kind == "seek":
            ms = (event.x-112) * clip["duration_ms"] / width
            self.cursor.set(max(0, min(clip["duration_ms"], ms)))
        elif abs(event.x-initial_x) > 5:
            current = next(e for e in clip["events"] if e["id"] == eid)
            if kind == "key":
                local = max(1, min(current["duration_ms"]-1,
                                  round(old_key+offset_ms)))
                if local != old_key:
                    replacement = update_motion_keyframe(
                        current, old_key, at_ms=local)
                    self.selected_key_ms = local
                    self.owner._run(lambda: self._update_selected_event(replacement))
            else:
                new_start = max(0, min(
                    clip["duration_ms"]-current["duration_ms"],
                    round((current["start_ms"]+offset_ms)/100)*100))
                if new_start != current["start_ms"]:
                    replacement = move_event(current, new_start,
                                             clip["duration_ms"])
                    self.owner._run(lambda: self._update_selected_event(replacement))
        self._timeline()
        self._preview()

    def _draw_audio(self, clip):
        canvas = self.audio_canvas
        canvas.delete("all")
        width = max(320, canvas.winfo_width())
        span = width - 90
        buses = (("music", "#3fbd9c"), ("ambience", "#65a1d3"),
                 ("voice", "#e4b75e"), ("sfx", "#b48fca"))
        for i, (bus, color) in enumerate(buses):
            y = 12 + i*21
            canvas.create_text(3, y, anchor="w", text=bus, fill="#d7e5f0")
            canvas.create_line(78, y+5, width-4, y+5, fill="#344660")
            coords = []
            for j in range(61):
                ms = round(clip["duration_ms"]*j/60)
                level = min(1., sum(track.level for track in mix_at(clip, ms)
                                   if track.bus == bus))
                coords.extend([78+span*j/60, y+5-level*13])
            canvas.create_line(*coords, fill=color, width=2)
        now = max(0, min(clip["duration_ms"], round(self.cursor.get())))
        levels = {track.bus: track.level for track in mix_at(clip, now)}
        self.audio_caption.set(
            "Mixage à %.2fs : %s" % (
                now/1000, " · ".join(
                    f"{bus} {levels.get(bus, 0):.0%}" for bus, _ in buses)))
        canvas.create_line(78+span*now/clip["duration_ms"], 0,
                           78+span*now/clip["duration_ms"], 96,
                           fill="#ffffff", dash=(2, 2))

    def _preview(self):
        if self._project() is None:
            return
        clip = next((c for c in self._project().cinematics if c["id"] == self.clip_id), None)
        if clip:
            draw_frame(self.preview_canvas, clip, self.cursor.get(),
                       self.preview_renderer)
            self._timeline()
            self._draw_audio(clip)

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
