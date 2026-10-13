"""3.7.24A — graphical world-map authoring in the existing Game Studio.

Only GameProject.world is edited. Mission links and their unlock rules remain
in Content; the owner's StudioHistory owns undo/redo and save transactions.
"""
from copy import deepcopy
import json

from .game_project import GameProject
from .model import RuleError
from .world_map import (WORLD_THEMES, default_world, upsert_location,
                        remove_location, world_projection)
from .world_map_view import draw_world_map, pick_world_mission


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
            frame, width=880, height=500, background="#efe2c4",
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

    def refresh(self):
        project = self.owner.project
        if project is None:
            return
        content = self.owner._content()
        self.mission_box["values"] = list(content.missions)
        world = project.world
        if world:
            self.theme.set(world["theme"])
        sig = json.dumps((world, [(mid, m.name, m.next_missions)
                                 for mid, m in content.missions.items()],
                          self.selected.get()), sort_keys=True)
        if sig == self._signature:
            return
        self._projection = world_projection(world, content,
                                            available=tuple(content.missions))
        draw_world_map(self.canvas, self._projection, selected=self.selected.get())
        self._signature = sig

    def on_press(self, event):
        if not self._projection:
            return
        mid = pick_world_mission(self.canvas, self._projection, event)
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
