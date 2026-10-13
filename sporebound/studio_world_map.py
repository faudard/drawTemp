"""3.7.24A — graphical world-map authoring in the existing Game Studio.

Only GameProject.world is edited. Mission links and their unlock rules remain
in Content; the owner's StudioHistory owns undo/redo and save transactions.
"""
from copy import deepcopy
import json

from .game_project import GameProject
from .model import RuleError
from .world_event_authoring import (
    closest_road, delete_road_event, events_on_road, preview_road_event,
    set_road_choice, upsert_road_event,
)
from .world_map import (WORLD_THEMES, default_world, upsert_location,
                        remove_location, world_projection)
from .world_map_view import draw_world_map, pick_world_mission
from .world_travel_lab import WorldTravelLab


class WorldMapStudio:
    def __init__(self, owner, notebook):
        self.owner, self.notebook = owner, notebook
        tk, ttk = owner.tk, owner.ttk
        self.tab = ttk.Frame(notebook)
        notebook.add(self.tab, text="Monde")
        ttk.Label(self.tab, text="Carte du monde — itinéraires de campagne",
                  font=("TkDefaultFont", 12, "bold")).pack(
                      anchor="w", padx=12, pady=(9, 2))
        ttk.Label(self.tab, text="Déplacer les lieux à la souris. "
                  "Les flèches reprennent uniquement les liens des missions ; "
                  "aucun déplacement sur la carte ne modifie les combats.",
                  wraplength=1000).pack(anchor="w", padx=12)

        toolbar = ttk.Frame(self.tab)
        toolbar.pack(fill="x", padx=10, pady=7)
        self.selected = tk.StringVar()
        self.region = tk.StringVar()
        self.theme = tk.StringVar(value="parchment")
        self.road = None
        self.event_selected = ""
        self.event_id = tk.StringVar(value="")
        self.event_scene = tk.StringVar(value="")
        self.event_step = tk.StringVar(value="4")
        self.event_choice = tk.StringVar(value="")
        self.event_action = tk.StringVar(value="continue")
        self.event_destination = tk.StringVar(value="")
        self.road_label = tk.StringVar(value="Cliquez sur une route de la carte.")
        self.lab = None
        self._lab_signature = None
        self.lab_campaign = tk.StringVar(value="")
        self.lab_start = tk.StringVar(value="")
        self.lab_destination = tk.StringVar(value="")
        self.lab_choice = tk.StringVar(value="")
        self.lab_author_mode = tk.BooleanVar(value=True)
        self.lab_status = tk.StringVar(value="Simulation isolée : aucune sauvegarde modifiée.")
        ttk.Button(toolbar, text="Créer la carte du monde",
                   command=lambda: owner._run(self.create_world)).pack(
                       side="left", padx=3)
        ttk.Label(toolbar, text="Mission").pack(side="left", padx=(12, 2))
        self.mission_box = ttk.Combobox(
            toolbar, textvariable=self.selected, state="readonly", width=22)
        self.mission_box.pack(side="left", padx=3)
        self.mission_box.bind("<<ComboboxSelected>>", self._selected)
        ttk.Button(toolbar, text="Placer",
                   command=lambda: owner._run(self.add_location)).pack(
                       side="left", padx=3)
        ttk.Button(toolbar, text="Retirer du monde",
                   command=lambda: owner._run(self.remove_selected)).pack(
                       side="left", padx=3)
        ttk.Label(toolbar, text="Ambiance").pack(side="left", padx=(12, 2))
        theme_box = ttk.Combobox(
            toolbar, textvariable=self.theme, values=WORLD_THEMES,
            state="readonly", width=12)
        theme_box.pack(side="left", padx=3)
        theme_box.bind("<<ComboboxSelected>>",
                       lambda _e: owner._run(self.set_theme))
        details = ttk.Frame(self.tab)
        details.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(details, text="Région").pack(side="left")
        ttk.Entry(details, textvariable=self.region, width=26).pack(
            side="left", padx=6)
        ttk.Button(details, text="Appliquer la région",
                   command=lambda: owner._run(self.set_region)).pack(side="left")
        self.status = tk.StringVar(value="Créer une carte ou ouvrir un projet possédant un monde.")
        ttk.Label(details, textvariable=self.status).pack(
            side="left", padx=14)

        frame = ttk.Frame(self.tab)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas = tk.Canvas(
            frame, width=680, height=500, background="#efe2c4",
            highlightthickness=0)
        xscroll = ttk.Scrollbar(frame, orient="horizontal",
                                command=self.canvas.xview)
        yscroll = ttk.Scrollbar(frame, orient="vertical",
                                command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set,
                              yscrollcommand=yscroll.set)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        # Compact inspector beside the *same* canvas; existing map dragging
        # and one cross-resource StudioHistory snapshot remain untouched.
        events = ttk.LabelFrame(frame, text="Rencontres et embranchements",
                                padding=7)
        events.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(8, 0))
        ttk.Label(events, textvariable=self.road_label,
                  wraplength=280).pack(anchor="w", pady=(0, 5))
        ttk.Label(events, text="Événements sur la route").pack(anchor="w")
        self.event_list = tk.Listbox(events, height=5, width=39,
                                     exportselection=False)
        self.event_list.pack(fill="x", pady=(1, 6))
        self.event_list.bind("<<ListboxSelect>>", self._select_event)
        form = ttk.Frame(events)
        form.pack(fill="x")
        for row, (label, var) in enumerate((
                ("ID", self.event_id), ("Scène", self.event_scene),
                ("Position (1-7)", self.event_step))):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 5), pady=2)
            if row == 1:
                self.event_scene_box = ttk.Combobox(
                    form, textvariable=var, state="readonly", width=21)
                widget = self.event_scene_box
                widget.bind("<<ComboboxSelected>>", self._scene_changed)
            elif row == 2:
                widget = ttk.Combobox(
                    form, textvariable=var, state="readonly", width=7,
                    values=[str(step) for step in range(1, 8)])
            else:
                widget = ttk.Entry(form, textvariable=var, width=23)
            widget.grid(row=row, column=1, sticky="ew", pady=2)
        form.columnconfigure(1, weight=1)
        actions = ttk.Frame(events)
        actions.pack(fill="x", pady=(5, 6))
        ttk.Button(actions, text="Nouveau", command=self.new_event).pack(
            side="left", padx=(0, 3))
        ttk.Button(actions, text="Enregistrer", command=lambda:
                   owner._run(self.save_event)).pack(side="left", padx=3)
        ttk.Button(actions, text="Supprimer", command=lambda:
                   owner._run(self.remove_event)).pack(side="left", padx=3)

        choices = ttk.LabelFrame(events, text="Décision → itinéraire", padding=5)
        choices.pack(fill="x")
        self.event_choice_box = ttk.Combobox(
            choices, textvariable=self.event_choice,
            state="readonly", width=30)
        self.event_choice_box.pack(fill="x", pady=(0, 3))
        self.event_choice_box.bind("<<ComboboxSelected>>", self._choice_changed)
        self.event_action_box = ttk.Combobox(
            choices, textvariable=self.event_action, state="readonly",
            values=("continue", "return", "destination"), width=30)
        self.event_action_box.pack(fill="x", pady=3)
        self.event_action_box.bind("<<ComboboxSelected>>", self._action_changed)
        self.event_destination_box = ttk.Combobox(
            choices, textvariable=self.event_destination,
            state="readonly", width=30)
        self.event_destination_box.pack(fill="x", pady=3)
        ttk.Button(choices, text="Appliquer cet embranchement",
                   command=lambda: owner._run(self.save_choice)).pack(
                       fill="x", pady=(3, 0))
        ttk.Button(events, text="Prévisualiser l'événement",
                   command=lambda: owner._run(self.preview_event)).pack(
                       fill="x", pady=(7, 3))
        ttk.Button(events, text="Ouvrir la scène narrative",
                   command=lambda: owner._run(self.open_story_scene)).pack(
                       fill="x", pady=(0, 3))
        self.event_preview = tk.Text(
            events, height=7, width=38, wrap="word", state="disabled")
        self.event_preview.pack(fill="both", expand=True)
        ttk.Label(events, text="Les scènes et leurs effets se créent dans "
                  "l'éditeur narratif existant.",
                  wraplength=280).pack(anchor="w", pady=(5, 0))
        lab_frame = ttk.LabelFrame(
            self.tab, text="Laboratoire de voyage · simulation sans sauvegarde", padding=7)
        lab_frame.pack(fill="x", padx=10, pady=(0, 8))
        lab_bar = ttk.Frame(lab_frame)
        lab_bar.pack(fill="x")
        for caption, variable, attr, width in (
                ("Campagne", self.lab_campaign, "lab_campaign_box", 17),
                ("Départ", self.lab_start, "lab_start_box", 19),
                ("Arrivée", self.lab_destination, "lab_destination_box", 19)):
            ttk.Label(lab_bar, text=caption).pack(side="left", padx=(5, 3))
            widget = ttk.Combobox(
                lab_bar, textvariable=variable, width=width, state="readonly")
            widget.pack(side="left", padx=(0, 5))
            setattr(self, attr, widget)
        ttk.Checkbutton(
            lab_frame, text="Mode auteur : accès provisoire aux lieux de l'itinéraire sélectionné",
            variable=self.lab_author_mode).pack(anchor="w", padx=5)
        lab_actions = ttk.Frame(lab_frame)
        lab_actions.pack(fill="x", pady=3)
        for label, action in (
                ("Initialiser", self.start_lab),
                ("Un pas", self.step_lab),
                ("Jusqu'au prochain événement", self.run_lab),
                ("Nouvelle destination", self.destination_lab),
                ("Réinitialiser", self.reset_lab)):
            ttk.Button(lab_actions, text=label,
                       command=lambda action=action:
                       owner._run(action)).pack(side="left", padx=3)
        ttk.Label(lab_actions, text="Choix").pack(side="left", padx=(8, 3))
        self.lab_choice_box = ttk.Combobox(
            lab_actions, textvariable=self.lab_choice,
            state="readonly", width=17)
        self.lab_choice_box.pack(side="left", padx=3)
        ttk.Button(lab_actions, text="Décider", command=lambda:
                   owner._run(self.choose_lab)).pack(side="left", padx=3)
        ttk.Label(lab_frame, textvariable=self.lab_status,
                  wraplength=1100).pack(anchor="w", padx=5)
        self.lab_log = tk.Text(
            lab_frame, height=4, wrap="word", state="disabled")
        self.lab_log.pack(fill="x", padx=5, pady=(3, 0))
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self._projection = None
        self._signature = None
        self._drag_mid = None
        self._drag_origin = None

    def show(self):
        self.notebook.select(self.tab)
        self.refresh()

    def _project(self):
        if self.owner.project is None:
            raise RuleError("No active GameProject")
        return self.owner.project

    def _commit(self, world):
        project = self._project()
        updated = project.to_dict()
        updated["world"] = world
        candidate = GameProject.from_dict(updated, self.owner._content())
        if candidate.to_dict() == project.to_dict():
            return
        self.owner.project = candidate
        self._signature = None
        self.refresh()

    def create_world(self):
        project = self._project()
        if project.world:
            raise RuleError("The world is already created")
        world = default_world(self.owner._content(), project.campaigns,
                              theme=self.theme.get())
        self._commit(world)
        self.status.set("Carte initialisée ; faire glisser les lieux pour les organiser.")

    def _node(self):
        mid = self.selected.get()
        return next((n for n in self._project().world.get("nodes", ())
                     if n["mission"] == mid), None)

    def _selected(self, _event=None):
        node = self._node()
        self.region.set(node["region"] if node else "")
        self._signature = None
        self.refresh()

    def add_location(self):
        project = self._project()
        if not project.world:
            raise RuleError("Créer d'abord une carte du monde")
        mid = self.selected.get()
        if mid not in self.owner._content().missions:
            raise RuleError("Choisir une mission existante")
        if self._node() is not None:
            raise RuleError("Ce lieu est déjà placé : le déplacer à la souris")
        world = upsert_location(
            project.world, self.owner._content(), project.campaigns,
            mid, (project.world["width"] // 2, project.world["height"] // 2))
        self._commit(world)
        self.status.set(mid + " ajouté au monde")

    def remove_selected(self):
        project = self._project()
        mid = self.selected.get()
        if self._node() is None:
            raise RuleError("Sélectionner un lieu placé")
        self._commit(remove_location(
            project.world, self.owner._content(), project.campaigns, mid))
        self.status.set(mid + " retiré de la carte (mission conservée)")

    def set_region(self):
        project = self._project()
        node = self._node()
        if node is None:
            raise RuleError("Choisir un lieu placé")
        self._commit(upsert_location(
            project.world, self.owner._content(), project.campaigns,
            node["mission"], (node["x"], node["y"]), region=self.region.get()))

    def set_theme(self):
        project = self._project()
        if not project.world:
            return
        updated = deepcopy(project.world)
        updated["theme"] = self.theme.get()
        self._commit(updated)



    def _model_signature(self):
        """Invalidate private previews when Studio content or story changes."""
        return json.dumps((self._project().to_dict(), self.owner.doc().data),
                          sort_keys=True)

    def _lab_is_fresh(self):
        if self.lab is None:
            raise RuleError("Initialiser le simulateur de voyage")
        if self._lab_signature != self._model_signature():
            self.reset_lab()
            raise RuleError("Studio modifié : réinitialiser la simulation")
        return self.lab

    def reset_lab(self):
        self.lab = None
        self._lab_signature = None
        self.lab_choice.set("")
        self.lab_choice_box["values"] = ()
        self.lab_status.set("Simulation arrêtée (les sauvegardes restent inchangées).")
        self._set_lab_log("")
        self.canvas.delete("world_lab_party")
        self.canvas.delete("world_lab_route")

    def start_lab(self):
        project = self._project()
        if not project.world:
            raise RuleError("Créer d'abord la carte du monde")
        campaign = self.lab_campaign.get()
        content = self.owner._content()
        candidate = WorldTravelLab(
            content, project, campaign,
            self.lab_start.get(), self.lab_destination.get(),
            author_mode=self.lab_author_mode.get())
        self.lab = candidate
        self._lab_signature = self._model_signature()
        self._render_lab()

    def _set_lab_log(self, report):
        self.lab_log.configure(state="normal")
        self.lab_log.delete("1.0", "end")
        self.lab_log.insert("1.0", report)
        self.lab_log.see("end")
        self.lab_log.configure(state="disabled")

    def _render_lab(self):
        self.canvas.delete("world_lab_party")
        self.canvas.delete("world_lab_route")
        if self.lab is None:
            return
        report = self.lab.snapshot()
        state = report["world"]
        coords = {row["mission"]: (row["x"], row["y"])
                  for row in self._project().world["nodes"]}
        if len(state["route"]) > 1:
            points = [value for mid in state["route"]
                      for value in coords[mid]]
            self.canvas.create_line(
                *points, fill="#247fb6", width=4, dash=(5, 5),
                tags=("world_lab_route",))
        px, py = state["position"]
        self.canvas.create_oval(
            px-10, py-28, px+10, py-8, fill="#32b1e2",
            outline="#183b56", width=3, tags=("world_lab_party",))
        scene = report["scene"]
        # Show the authored labels, not only opaque choice identifiers.
        options = [
            row["id"] + " — " + row["label"] for row in report["choices"]]
        self.lab_choice_box["values"] = options
        if self.lab_choice.get() not in options:
            self.lab_choice.set(options[0] if options else "")
        if scene is not None:
            message = "Dialogue : " + scene["title"]
            message += " | " + scene["text"][:160]
        elif state["traveling"]:
            message = "En route : " + " → ".join(state["route"])
        else:
            message = "Arrivé à : " + state["at"]
        self.lab_status.set(
            f'Simulation {report["mode"]} | {message} | Or : {report["gold"]}'
            " | Aucun fichier écrit")
        self._set_lab_log(
            "\n".join([*report["log"], "— Écarts par rapport au départ —",
                       *(report["changes"] or ["Aucune conséquence narrative."])]))

    def step_lab(self):
        self._lab_is_fresh().step()
        self._render_lab()

    def run_lab(self):
        self._lab_is_fresh().run_to_stop()
        self._render_lab()

    def choose_lab(self):
        selected = self.lab_choice.get().split(" — ", 1)[0]
        self._lab_is_fresh().choose(selected)
        self._render_lab()

    def destination_lab(self):
        self._lab_is_fresh().destination(self.lab_destination.get())
        self._render_lab()

    def _scene(self, scene_id):
        return next((scene for scene in self._project().story.get("scenes", [])
                     if scene["id"] == scene_id), None)

    def _event(self):
        return next((row for row in self._project().world.get("events", [])
                     if row["id"] == self.event_selected), None)

    def _select_road(self, source, target):
        if self.road != (source, target):
            self.road = (source, target)
            self.event_selected = ""
            self.event_id.set("")
            self.event_step.set("4")
            self._signature = None
        self.refresh()

    def new_event(self):
        self.event_selected = ""
        self.event_id.set("")
        self.event_step.set("4")
        self.event_action.set("continue")
        self.event_destination.set("")
        self.event_list.selection_clear(0, "end")
        self._scene_changed()

    def _select_event(self, _event=None):
        selection = self.event_list.curselection()
        if selection and self.road:
            items = events_on_road(self._project().world, *self.road)
            if selection[0] < len(items):
                self.event_selected = items[selection[0]]["id"]
                self._load_event()
                self._draw_event_markers()

    def _load_event(self):
        event = self._event()
        if event is None:
            return
        self.event_id.set(event["id"])
        self.event_scene.set(event["scene"])
        self.event_step.set(str(event.get("step", 4)))
        self._scene_changed()

    def _scene_changed(self, _event=None):
        scene = self._scene(self.event_scene.get())
        choice_ids = [choice["id"] for choice in scene["choices"]] if scene else []
        self.event_choice_box["values"] = choice_ids
        if self.event_choice.get() not in choice_ids:
            self.event_choice.set(choice_ids[0] if choice_ids else "")
        self._choice_changed()

    def _choice_changed(self, _event=None):
        event = self._event()
        action = (event.get("routes", {}).get(self.event_choice.get(),
                  {"kind": "continue"}) if event is not None and
                  event["scene"] == self.event_scene.get()
                  else {"kind": "continue"})
        self.event_action.set(action["kind"])
        self.event_destination.set(action.get("mission", ""))
        self._action_changed()

    def _action_changed(self, _event=None):
        self.event_destination_box.configure(
            state=("readonly" if self.event_action.get() == "destination"
                   else "disabled"))

    def save_event(self):
        require_world = self._project().world
        if not require_world or not self.road:
            raise RuleError("Sélectionner une route existante sur la carte")
        source, target = self.road
        event_id = self.event_id.get().strip()
        existing = self._event()
        if not self.event_selected and any(
                row["id"] == event_id
                for row in require_world.get("events", [])):
            raise RuleError("Identifiant déjà utilisé : sélectionner l'événement existant")
        updated = (deepcopy(existing) if existing else {})
        updated.update(id=event_id, scene=self.event_scene.get(),
                       step=int(self.event_step.get()),
                       **{"from": source, "to": target})
        if existing and existing["scene"] != updated["scene"]:
            updated.pop("routes", None)  # Different scene, different choice IDs.
        world = upsert_road_event(
            require_world, self.owner._content(),
            self._project().campaigns, self._project().story,
            updated, original_id=self.event_selected or event_id)
        self.event_selected = event_id
        self._commit(world)
        self.status.set("Événement enregistré : " + event_id)

    def remove_event(self):
        if not self.event_selected:
            raise RuleError("Sélectionner un événement à supprimer")
        world = delete_road_event(
            self._project().world, self.owner._content(),
            self._project().campaigns, self._project().story, self.event_selected)
        removed = self.event_selected
        self.event_selected = ""
        self.event_id.set("")
        self._commit(world)
        self.status.set("Événement supprimé : " + removed)

    def save_choice(self):
        if not self.event_selected:
            raise RuleError("Enregistrer d'abord la rencontre")
        world = set_road_choice(
            self._project().world, self.owner._content(),
            self._project().campaigns, self._project().story,
            self.event_selected, self.event_choice.get(),
            self.event_action.get(), self.event_destination.get())
        self._commit(world)
        self.status.set("Décision liée au trajet : " + self.event_choice.get())

    def preview_event(self):
        if not self.event_selected:
            raise RuleError("Sélectionner un événement existant")
        self._set_preview(preview_road_event(
            self._project().world, self._project().story, self.event_selected))

    def open_story_scene(self):
        scene = self.event_scene.get()
        if self._scene(scene) is None:
            raise RuleError("Sélectionner une scène narrative existante")
        self.owner.story_editor.select_graph_target(scene)

    def _set_preview(self, content):
        self.event_preview.configure(state="normal")
        self.event_preview.delete("1.0", "end")
        self.event_preview.insert("1.0", content)
        self.event_preview.configure(state="disabled")

    def _draw_event_markers(self):
        self.canvas.delete("world_road_event")
        world = self._project().world
        if not world:
            return
        positions = {node["mission"]: node for node in world["nodes"]}
        for event in world.get("events", []):
            a, b = positions[event["from"]], positions[event["to"]]
            fraction = event.get("step", 4) / 8
            x = a["x"] + (b["x"] - a["x"]) * fraction
            y = a["y"] + (b["y"] - a["y"]) * fraction
            selected = event["id"] == self.event_selected
            self.canvas.create_oval(
                x - 11, y - 11, x + 11, y + 11,
                fill="#d46b42" if selected else "#e1b453",
                outline="#442f29", width=2,
                tags=("world_road_event", "world_road_event_" + event["id"]))
            self.canvas.create_text(
                x, y - 1, text="!", fill="#232323",
                font=("TkDefaultFont", 12, "bold"),
                tags=("world_road_event", "world_road_event_" + event["id"]))

    def _pick_event(self, x, y):
        world = self._project().world
        if not world:
            return None
        positions = {node["mission"]: node for node in world["nodes"]}
        for event in reversed(world.get("events", [])):
            a, b = positions[event["from"]], positions[event["to"]]
            fraction = event.get("step", 4) / 8
            px = a["x"] + (b["x"] - a["x"]) * fraction
            py = a["y"] + (b["y"] - a["y"]) * fraction
            if (px - x) ** 2 + (py - y) ** 2 <= 14 ** 2:
                return event
        return None

    def refresh(self):
        project = self.owner.project
        if project is None:
            return
        # Most Map Editor selection/paint notifications do not change the
        # world. Derive a cheap signature from raw mission metadata *before*
        # constructing/validating an expensive complete Content snapshot.
        raw_missions = self.owner.doc().data["missions"]
        world = project.world
        sig = json.dumps((world, self.owner.project.story,
                          [(m["id"], m["name"],
                            m.get("next_missions", []))
                           for m in raw_missions],
                          self.selected.get(), self.road,
                          self.event_selected), sort_keys=True)
        if sig == self._signature:
            return
        if self.lab is not None and self._lab_signature != self._model_signature():
            self.reset_lab()
            self.lab_status.set("Projet ou carte modifiés : simulation invalidée.")
        content = self.owner._content()
        self.mission_box["values"] = list(content.missions)
        if world:
            self.theme.set(world["theme"])
        self._projection = world_projection(world, content,
                                            available=tuple(content.missions))
        draw_world_map(self.canvas, self._projection, selected=self.selected.get())
        self._draw_event_markers()
        story_scenes = [scene["id"]
                        for scene in project.story.get("scenes", [])]
        self.event_scene_box["values"] = story_scenes
        if self.event_scene.get() not in story_scenes:
            self.event_scene.set(story_scenes[0] if story_scenes else "")
        self.event_destination_box["values"] = [
            node["mission"] for node in world.get("nodes", [])
            if not self.road or node["mission"] not in self.road]
        campaigns = [item["id"] for item in project.campaigns]
        self.lab_campaign_box["values"] = campaigns
        if self.lab_campaign.get() not in campaigns:
            self.lab_campaign.set(campaigns[0] if campaigns else "")
        places = [node["mission"] for node in world.get("nodes", [])]
        self.lab_start_box["values"] = places
        self.lab_destination_box["values"] = places
        if self.lab_start.get() not in places:
            self.lab_start.set(project.campaigns[0]["start_mission"]
                               if project.campaigns[0]["start_mission"] in places
                               else places[0] if places else "")
        if self.lab_destination.get() not in places:
            self.lab_destination.set(next((mid for mid in places
                                           if mid != self.lab_start.get()), ""))
        self.road_label.set(
            f"Route : {self.road[0]} → {self.road[1]}" if self.road
            else "Cliquez sur une route de la carte.")
        self.event_list.delete(0, "end")
        if self.road:
            for event in events_on_road(world, *self.road):
                self.event_list.insert(
                    "end", f'{event["id"]} · {event["step"] if "step" in event else 4}/8 · {event["scene"]}')
                if event["id"] == self.event_selected:
                    self.event_list.selection_set(self.event_list.size() - 1)
            if self.event_selected and self._event() is None:
                self.event_selected = ""
        if self.event_selected:
            self._load_event()
        else:
            self._scene_changed()
        self._signature = sig
        self._render_lab()

    def on_press(self, event):
        if not self._projection:
            return
        mid = pick_world_mission(self.canvas, self._projection, event)
        if mid is None:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            encounter = self._pick_event(x, y)
            if encounter is not None:
                self._select_road(encounter["from"], encounter["to"])
                self.event_selected = encounter["id"]
                self._load_event()
                self._signature = None
                self.refresh()
            else:
                road = closest_road(self._project().world,
                                    self.owner._content(), (x, y))
                if road is not None:
                    self._select_road(*road)
        self._drag_mid = mid
        self._drag_origin = (self.canvas.canvasx(event.x),
                             self.canvas.canvasy(event.y))
        if mid is not None:
            self.selected.set(mid)
            self._selected()

    def on_motion(self, event):
        if self._drag_mid is None:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.canvas.delete("world_drag")
        self.canvas.create_oval(x-25, y-25, x+25, y+25,
                                fill="", outline="#e89d32", dash=(4, 3),
                                width=3, tags=("world_drag",))

    def on_release(self, event):
        mid, origin = self._drag_mid, self._drag_origin
        self._drag_mid, self._drag_origin = None, None
        self.canvas.delete("world_drag")
        if mid is None or origin is None:
            return
        x, y = int(round(self.canvas.canvasx(event.x))), int(round(
            self.canvas.canvasy(event.y)))
        if abs(x-origin[0]) + abs(y-origin[1]) < 5:
            return

        def commit_drag():
            project = self._project()
            node = self._node()
            if node is None or node["mission"] != mid:
                raise RuleError("World selection changed during drag")
            self._commit(upsert_location(
                project.world, self.owner._content(), project.campaigns,
                mid, (x, y)))
            self.status.set("Lieu déplacé : " + mid +
                            " (" + str(x) + ", " + str(y) + ") — Undo disponible")

        self.owner._run(commit_drag)
