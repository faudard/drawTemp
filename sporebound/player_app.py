"""Desktop player for GameSession: campaign -> deployment -> combat -> results.

Uses Tk only at launch, and sends every player intent through PlayerController.
No game mechanics, AI rules, dice or persistence schemas live in this module.
"""
from pathlib import Path

from .audio_stage import AudioStage
from .game_project import GameProject
from .model import Content, RuleError
from .player_controller import PlayerController
from .presentation import Camera, battle_frame, strategy_frame
from .siege import available_operations
from .tk_renderer import CanvasRenderer


class PlayerApplication:
    def __init__(self, content_path, project_path=None, profile_path=None):
        import tkinter as tk
        from tkinter import ttk, messagebox

        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        content_path = Path(content_path)
        project_path = (Path(project_path) if project_path is not None
                        else content_path.with_suffix(".game.json"))
        content = Content.load(content_path)
        project = (GameProject.load(project_path, content) if project_path.is_file()
                   else GameProject.default(content))
        profile = (Path(profile_path) if profile_path is not None
                   else Path.home() / ".sporebound" / project_path.name)
        self.player = PlayerController(content, project, profile)
        self.project = project
        self.registry = project.asset_registry()
        self.asset_root = project_path.parent
        self.audio = AudioStage(self.registry, self.asset_root,
                                effects_volume=project.options["effects_volume"],
                                music_volume=project.options["music_volume"])
        self.root = tk.Tk()
        self.root.title(project.title)
        self.root.geometry("1160x820")
        self.root.minsize(800, 580)
        self.root.configure(background="#101a2b")
        self.root.attributes("-fullscreen", project.options["fullscreen"])
        self._style()
        self.view = ttk.Frame(self.root, padding=18)
        self.view.pack(fill="both", expand=True)
        self.campaign_var = tk.StringVar(value=project.campaigns[0]["id"])
        self.slot_var = tk.StringVar(value="1")
        self.action_var = tk.StringVar(value="move")
        self.unit_var = tk.StringVar()
        self.facing_var = tk.StringVar(value="south")
        self.front_var = tk.StringVar()
        self.doctrine_var = tk.StringVar(value="hold")
        self.selection = (0, 0)
        self.camera = Camera(52, 8, 8)
        self.canvas = None
        self.renderer = None
        self.info = None
        self._typewriter_job = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda event: self.root.attributes("-fullscreen", False))
        self.title_screen()

    def _style(self):
        style = self.ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#101a2b", foreground="#e8f0fa",
                        font=("TkDefaultFont", 11))
        style.configure("TFrame", background="#101a2b")
        style.configure("TLabel", background="#101a2b", foreground="#e8f0fa")
        style.configure("TButton", padding=8, background="#304862", foreground="#ffffff")
        style.map("TButton", background=[("active", "#43668a")])
        style.configure("TCombobox", fieldbackground="#f5f7fb", foreground="#152438")
        style.configure("TLabelframe", background="#101a2b", foreground="#e8f0fa")
        style.configure("TLabelframe.Label", background="#101a2b", foreground="#e8f0fa")

    def _clear(self):
        if self._typewriter_job is not None:
            self.root.after_cancel(self._typewriter_job)
            self._typewriter_job = None
        if self.renderer:
            self.renderer.dispose()
            self.renderer = None
        for child in self.view.winfo_children():
            child.destroy()
        self.canvas = None
        self.info = None

    def _heading(self, text, subtitle=""):
        self.ttk.Label(self.view, text=text, font=("TkDefaultFont", 24, "bold")).pack(
            anchor="w", pady=(4, 12))
        if subtitle:
            self.ttk.Label(self.view, text=subtitle).pack(anchor="w", pady=(0, 12))

    def _button(self, parent, text, action, **kwargs):
        return self.ttk.Button(parent, text=text, command=lambda: self._safe(action),
                               **kwargs)

    def _safe(self, action):
        try:
            return action()
        except (RuleError, ValueError, TypeError, OSError, KeyError,
                IndexError, StopIteration) as exc:
            self.messagebox.showerror("Action refusée", str(exc))
            return None

    def _change(self, action):
        action()
        self.show()

    def title_screen(self):
        self.audio.music("title")
        self._clear()
        self._heading(self.project.title, self.project.subtitle)
        panel = self.ttk.LabelFrame(self.view, text="Nouvelle aventure / reprendre", padding=18)
        panel.pack(anchor="center", fill="x", padx=160, pady=30)
        self.ttk.Label(panel, text="Campagne").grid(row=0, column=0, sticky="w", pady=9)
        self.ttk.Combobox(panel, textvariable=self.campaign_var, state="readonly",
                          values=[c["id"] for c in self.project.campaigns],
                          width=26).grid(row=0, column=1, padx=15)
        self.ttk.Label(panel, text="Emplacement").grid(row=1, column=0, sticky="w", pady=9)
        self.ttk.Combobox(panel, textvariable=self.slot_var, state="readonly",
                          values=[str(i) for i in range(1, self.project.save_slots + 1)],
                          width=26).grid(row=1, column=1, padx=15)
        self._button(panel, "Nouvelle partie", self._new_game).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(20, 4))
        self._button(panel, "Continuer", self._load_game).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=4)
        self._button(panel, "Options", self.options_screen).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=4)
        self._button(panel, "Quitter", self.close).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=4)

    def _new_game(self):
        cid, slot = self.campaign_var.get(), int(self.slot_var.get())
        path = self.player.path_for(cid, slot)
        exists = path.exists() or path.with_name(path.name + ".bak").exists()
        if exists and not self.messagebox.askyesno("Nouvelle partie",
                                                    "Recommencer cet emplacement ?"):
            return
        self.player.new_game(cid, slot, overwrite=exists)
        self.show()

    def _load_game(self):
        self.player.load_game(self.campaign_var.get(), int(self.slot_var.get()))
        self.show()

    def options_screen(self):
        self._clear()
        self._heading("Options")
        self.ttk.Label(self.view, text="Audio optionnel : installer pygame-ce et déclarer des sounds dans le projet.").pack(
            anchor="w", pady=10)
        effects = self.tk.IntVar(value=int(self.audio.effects_volume * 100))
        music = self.tk.IntVar(value=int(self.audio.music_volume * 100))
        for name, variable in (("Effets", effects), ("Musique", music)):
            self.ttk.Label(self.view, text=name).pack(anchor="w", pady=(8, 0))
            self.ttk.Scale(self.view, from_=0, to=100, variable=variable).pack(
                fill="x", padx=24, pady=(2, 12))
        full = self.tk.BooleanVar(value=bool(self.root.attributes("-fullscreen")))
        self.ttk.Checkbutton(self.view, text="Plein écran", variable=full).pack(
            anchor="w", pady=10)
        def apply():
            self.audio.effects_volume = effects.get() / 100
            self.audio.music_volume = music.get() / 100
            self.root.attributes("-fullscreen", full.get())
            self.title_screen()
        self._button(self.view, "Appliquer", apply).pack(anchor="w", pady=12)
        self._button(self.view, "Retour", self.title_screen).pack(anchor="w")

    def show(self):
        session = self.player.session
        if session is None:
            self.title_screen()
        elif session.mode == "fronts":
            self.battle_screen()
        elif session.mode == "battle":
            self.battle_screen()
        else:
            self.campaign_screen()

    def campaign_screen(self):
        session = self.player.session
        self.audio.music("campaign")
        self._clear()
        self._heading(self.project.campaign(session.campaign_id)["name"],
                      "Or : " + str(session.progress.gold) +
                      "    Missions terminées : " + str(len(session.progress.completed)))
        scene = session.active_scene()
        if scene:
            self._narrative_scene(scene)
        else:
            available = session.available_missions()
            self.ttk.Label(self.view, text="Choisir une mission :").pack(anchor="w", pady=8)
            for mission_id in available:
                mission = self.player.content.missions[mission_id]
                self._button(self.view, mission.name + " — " + mission.objective,
                             lambda mid=mission_id: self._change(
                                 lambda: self.player.start_mission(mid))).pack(
                                     fill="x", padx=80, pady=5)
            if len(available) >= 2:
                self._button(self.view, "Commandement multi-fronts",
                             lambda: self.front_setup(available)).pack(pady=16)
            if not available:
                self.ttk.Label(self.view,
                               text="Campagne terminée : aucun objectif disponible.").pack(pady=20)
        footer = self.ttk.Frame(self.view)
        footer.pack(side="bottom", fill="x", pady=12)
        self._button(footer, "Sauvegarder", self.player.save).pack(side="left", padx=6)
        self._button(footer, "Menu principal", self.title_screen).pack(side="left", padx=6)

    def _narrative_scene(self, scene):
        panel = self.ttk.LabelFrame(self.view, text=scene["title"], padding=20)
        panel.pack(fill="both", expand=True, padx=60, pady=16)
        portrait = CanvasRenderer(panel, registry=self.registry, asset_root=self.asset_root).image(
            "portrait", scene["speaker"])
        # PhotoImage needs a widget master; keep a Python reference while showing scene.
        if portrait is not None:
            label = self.ttk.Label(panel, image=portrait)
            label.image = portrait
            label.pack(pady=6)
        if scene["speaker"]:
            self.ttk.Label(panel, text=scene["speaker"],
                           font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=6)
        text = self.tk.Label(panel, text="", fg="#f2f0d9", bg="#101a2b",
                             justify="left", wraplength=820, font=("TkDefaultFont", 12))
        text.pack(anchor="w", pady=15)
        # Typewriter effect is visual only: no changes to narrative state.
        message = scene["text"]
        def reveal(n=0):
            if not text.winfo_exists():
                return
            text.configure(text=message[:n])
            if n < len(message):
                self._typewriter_job = self.root.after(8, reveal, min(n + 4, len(message)))
            else:
                self._typewriter_job = None
        reveal()
        for choice in self.player.session.available_choices():
            self._button(panel, choice["label"],
                         lambda cid=choice["id"]: self._change(
                             lambda: self.player.choose_story_option(cid))).pack(
                                 fill="x", padx=30, pady=4)

    def front_setup(self, available):
        self._clear()
        self._heading("Préparer une opération multi-fronts",
                      "Choisir deux secteurs pour une timeline stratégique commune.")
        choices = [(mid, self.tk.BooleanVar(value=i < 2))
                   for i, mid in enumerate(available)]
        for mid, variable in choices:
            self.ttk.Checkbutton(self.view,
                                 text=self.player.content.missions[mid].name,
                                 variable=variable).pack(anchor="w", pady=6)
        def start():
            selected = [mid for mid, variable in choices if variable.get()]
            if len(selected) < 2:
                raise RuleError("Sélectionner au moins deux missions")
            self._change(lambda: self.player.start_fronts(
                {mid: mid for mid in selected}, selected[0]))
        self._button(self.view, "Déployer plusieurs fronts", start).pack(pady=18)
        self._button(self.view, "Retour", self.campaign_screen).pack()

    def battle_screen(self):
        session = self.player.session
        battle = session.active_battle
        self.audio.music("battle")
        self._clear()
        if battle is None:
            self.strategy_screen()
            return
        self._heading(battle.mission.name,
                      "Tick " + str(battle.tick) + "    " +
                      ("Résultat : " + battle.result if battle.result else
                       "Déploiement" if battle.deploying else
                       "Unité active : " + (battle.active.name if battle.active else "?")))
        nav = self.ttk.Frame(self.view)
        nav.pack(fill="x", pady=4)
        if session.mode == "fronts":
            self._button(nav, "Timeline / Fronts", self.strategy_screen).pack(side="left", padx=4)
        elif session.finalized:
            self._button(nav, "Résultats → Campagne",
                         lambda: self._change(self.player.return_to_campaign)).pack(
                             side="left", padx=4)
        self._button(nav, "Sauvegarder", self.player.save).pack(side="right", padx=4)
        if not session.finalized and not battle.result:
            actions = self.ttk.Frame(self.view)
            actions.pack(fill="x", pady=9)
            if battle.deploying:
                options = ["deploy", "start_battle"]
                players = [u.id for u in battle.units if u.team == "player" and u.alive]
                if self.unit_var.get() not in players:
                    self.unit_var.set(players[0] if players else "")
                self.ttk.Label(actions, text="Héros").pack(side="left")
                self.ttk.Combobox(actions, textvariable=self.unit_var,
                                  values=players, state="readonly", width=11).pack(
                                      side="left", padx=5)
            elif battle.active is None:
                options = []
            elif battle.active.team == "enemy":
                options = []
                self._button(actions, "Jouer l'activation IA",
                             lambda: self._change(self.player.ai_turn)).pack(side="left")
            else:
                options = (["move", "attack", *battle.active.skills,
                            "item:potion", "item:ether", "item:phoenix",
                            *["object:" + obj["id"] for obj in battle.mission.objects],
                            *available_operations(battle, battle.active)])
                options += ["end"]
            if options:
                if self.action_var.get() not in options:
                    self.action_var.set(options[0])
                self.ttk.Label(actions, text="Action").pack(side="left", padx=5)
                self.ttk.Combobox(actions, textvariable=self.action_var,
                                  values=options, state="readonly", width=23).pack(
                                      side="left", padx=7)
                self.ttk.Label(actions, text="Orientation").pack(side="left")
                self.ttk.Combobox(actions, textvariable=self.facing_var, state="readonly",
                                  values=["north", "south", "east", "west"],
                                  width=9).pack(side="left", padx=6)
                self._button(actions, "Exécuter", self._execute).pack(side="left", padx=5)
                if not battle.deploying:
                    self._button(actions, "Fin de tour", self._end).pack(side="left", padx=5)
        body = self.ttk.Frame(self.view)
        body.pack(fill="both", expand=True, pady=9)
        self.canvas = self.tk.Canvas(body, background="#172638", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.renderer = CanvasRenderer(self.canvas, registry=self.registry,
                                       asset_root=self.asset_root)
        self.canvas.bind("<Button-1>", self._select_cell)
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<Button-4>", lambda _: self._zoom_step(1))
        self.canvas.bind("<Button-5>", lambda _: self._zoom_step(-1))
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_drag)
        self.info = self.tk.Text(body, width=37, wrap="word", fg="#e9f2fc",
                                 bg="#182a40", relief="flat")
        self.info.pack(side="right", fill="y", padx=(9, 0))
        self._redraw()
        if not session.finalized:
            self._button(self.view, "Abandonner l'opération",
                         self._abandon).pack(anchor="e", pady=4)

    def _redraw(self):
        if self.canvas is None:
            return
        battle = self.player.session.active_battle
        skill = self.action_var.get()
        skill = skill if skill == "attack" or skill in (
            battle.active.skills if battle.active else ()) else None
        frame = battle_frame(battle, self.selection, skill)
        self.renderer.draw(frame, self.camera)
        self.audio.observe(battle)
        rows = ["Case : " + str(self.selection), "", "Escouades"]
        rows.extend(u.name + " (" + u.team + ") : PV " + str(u.hp) + "/" +
                    str(u.max_hp) + " / MP " + str(u.mp) + "/" + str(u.max_mp)
                    for u in frame.actors)
        if frame.forecast:
            rows.extend(["", "Prévisions"])
            rows.extend(str(item) for item in frame.forecast)
        rows.extend(["", "Journal"])
        rows.extend(str(event) for event in frame.events[-15:])
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(rows))
        self.info.configure(state="disabled")

    def _select_cell(self, event):
        battle = self.player.session.active_battle
        cell = self.camera.screen_to_cell(event.x, event.y)
        if battle.board.contains(cell):
            self.selection = cell
            self._redraw()

    def _zoom(self, event):
        self._zoom_step(1 if event.delta > 0 else -1, (event.x, event.y))

    def _zoom_step(self, direction, anchor=(300, 200)):
        self.camera = self.camera.zoomed(direction, anchor)
        self._redraw()

    def _pan_start(self, event):
        self._pan_point = (event.x, event.y)

    def _pan_drag(self, event):
        before = getattr(self, "_pan_point", (event.x, event.y))
        self.camera = self.camera.panned(event.x - before[0], event.y - before[1])
        self._pan_point = (event.x, event.y)
        self._redraw()

    def _facing(self):
        return {"north": [0, -1], "south": [0, 1],
                "east": [1, 0], "west": [-1, 0]}[self.facing_var.get()]

    def _execute(self):
        kind = self.action_var.get()
        if kind == "start_battle":
            command = {"kind": "start_battle"}
        elif kind == "deploy":
            command = {"kind": "deploy", "unit": self.unit_var.get(),
                       "cell": list(self.selection), "facing": self._facing()}
        elif kind == "move":
            command = {"kind": "move", "cell": list(self.selection)}
        elif kind == "end":
            command = {"kind": "end", "facing": self._facing()}
        elif kind.startswith("item:"):
            command = {"kind": "item", "item": kind[5:], "cell": list(self.selection)}
        elif kind.startswith("object:"):
            command = {"kind": "interact", "object": kind[7:]}
        elif kind.startswith("siege-attack:"):
            command = {"kind": "siege_attack", "object": kind[len("siege-attack:"):]}
        elif kind.startswith("repair-siege:"):
            command = {"kind": "repair_siege", "object": kind[len("repair-siege:"):]}
        else:
            command = {"kind": "act", "skill": kind, "cell": list(self.selection)}
        self._change(lambda: self.player.execute(command))

    def _end(self):
        self._change(lambda: self.player.execute(
            {"kind": "end", "facing": self._facing()}))

    def _abandon(self):
        if self.messagebox.askyesno("Abandonner",
                                    "Perdre la progression tactique de cette opération ?"):
            self._change(self.player.abandon_encounter)

    def strategy_screen(self):
        session = self.player.session
        if session.mode != "fronts":
            self.show()
            return
        self._clear()
        frame = strategy_frame(session.fronts)
        self._heading("Commandement des fronts",
                      "Tour stratégique " + str(frame.turn) +
                      "    Front actif : " + frame.focused)
        tree = self.ttk.Treeview(self.view,
                                 columns=("mission", "doctrine", "ally", "enemy", "state"),
                                 show="headings", selectmode="browse", height=9)
        for key, label in [("mission", "Mission"), ("doctrine", "Doctrine"),
                           ("ally", "Alliés"), ("enemy", "Ennemis"), ("state", "État")]:
            tree.heading(key, text=label)
            tree.column(key, width=150, anchor="center")
        for front in frame.fronts:
            tree.insert("", "end", iid=front.id,
                        values=(front.mission, front.doctrine, front.strength,
                                front.opposition, front.status))
        tree.selection_set(frame.focused)
        tree.pack(fill="both", expand=True, pady=10)
        self.front_var.set(frame.focused)
        def select(_event=None):
            selection = tree.selection()
            if selection:
                self.front_var.set(selection[0])
        tree.bind("<<TreeviewSelect>>", select)
        controls = self.ttk.Frame(self.view)
        controls.pack(fill="x", pady=12)
        self.ttk.Label(controls, text="Doctrine").pack(side="left")
        self.ttk.Combobox(controls, textvariable=self.doctrine_var,
                          values=("hold", "assault", "delay", "retreat"),
                          state="readonly", width=11).pack(side="left", padx=8)
        self._button(controls, "Appliquer", lambda: self._change(
            lambda: self.player.set_doctrine(self.front_var.get(),
                                            self.doctrine_var.get()))).pack(side="left", padx=4)
        self._button(controls, "Changer de front", lambda: self._change(
            lambda: self.player.switch_front(self.front_var.get()))).pack(side="left", padx=4)
        self._button(controls, "Avancer la timeline", lambda: self._change(
            self.player.advance_fronts)).pack(side="left", padx=4)
        self._button(controls, "Jouer le secteur", self.battle_screen).pack(
            side="left", padx=4)
        log = self.tk.Text(self.view, height=9, fg="#e9f2fc", bg="#182a40",
                           wrap="word", relief="flat")
        log.pack(fill="both", expand=True, pady=8)
        log.insert("1.0", "\n".join(str(event) for event in frame.events[-25:]))
        log.configure(state="disabled")
        footer = self.ttk.Frame(self.view)
        footer.pack(fill="x")
        self._button(footer, "Sauvegarder", self.player.save).pack(side="left", padx=6)
        self._button(footer, "Quitter l'opération", self._abandon).pack(side="right", padx=6)
        if all(f.status != "active" for f in frame.fronts):
            self._button(footer, "Résultats → Campagne", lambda: self._change(
                self.player.return_to_campaign)).pack(side="right", padx=6)

    def close(self):
        if self.player.session is not None:
            try:
                self.player.save()
            except (RuleError, OSError, ValueError) as exc:
                if not self.messagebox.askyesno(
                        "Sauvegarde impossible",
                        str(exc) + "\nQuitter malgré l'échec ?"):
                    return
        self.audio.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def launch(content_path, project_path=None, profile_path=None):
    PlayerApplication(content_path, project_path, profile_path).run()
