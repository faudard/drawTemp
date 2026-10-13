"""Desktop player for GameSession: campaign -> deployment -> combat -> results.

Uses Tk only at launch, and sends every player intent through PlayerController.
No game mechanics, AI rules, dice or persistence schemas live in this module.
"""
import json
import time
from pathlib import Path

from .audio_stage import AudioStage
from .exploration_view import draw_exploration, draw_story_backdrop
from .game_project import GameProject
from .model import Content, RuleError
from .player_controller import PlayerController
from .presentation import Camera, battle_frame, strategy_frame
from .siege import available_operations
from .tactical_actions import tactical_action_options, tactical_command
from .tactical_rpg3 import authored_rules_for_document
from .tk_renderer import CanvasRenderer
from .iso_battle_view import IsoBattleCanvas, anchored_iso_zoom
from .world_map import world_projection
from .world_map_view import draw_world_map, pick_world_mission
from .visual_motion import MotionDirector


class PlayerApplication:
    def __init__(self, content_path, project_path=None, profile_path=None):
        import tkinter as tk
        from tkinter import ttk, messagebox

        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        content_path = Path(content_path)
        project_path = (Path(project_path) if project_path is not None
                        else content_path.with_suffix(".game.json"))
        # Validate advanced formations/bosses with their opt-in rules from load.
        document = json.loads(content_path.read_text(encoding="utf-8"))
        content = Content.from_dict(document, rules=authored_rules_for_document(document))
        project = (GameProject.load(project_path, content) if project_path.is_file()
                   else GameProject.default(content))
        profile = (Path(profile_path) if profile_path is not None
                   else Path.home() / ".sporebound" / project_path.name)
        self.player = PlayerController(content, project, profile)
        self.project_path = project_path
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
        self.level_var = tk.IntVar(value=0)
        self.unit_var = tk.StringVar()
        self.facing_var = tk.StringVar(value="south")
        self.front_var = tk.StringVar()
        self.route_var = tk.StringVar(value="breach")
        self.doctrine_var = tk.StringVar(value="hold")
        self.logistics_dest_var = tk.StringVar()
        self.logistics_transfer_dest_var = tk.StringVar()
        self.logistics_actor_var = tk.StringVar(value="reserve_1")
        self.logistics_x_var = tk.StringVar(value="1")
        self.logistics_y_var = tk.StringVar(value="1")
        self.convoy_var = tk.StringVar()
        self.selection = (0, 0)
        self.iso_view_var = tk.BooleanVar(value=False)
        self.camera = Camera(52, 8, 8)
        self.motion = MotionDirector()
        self._motion_source = None
        self._motion_frame = None
        self._motion_job = None
        self.canvas = None
        self.renderer = None
        self.iso_renderer = None
        self.info = None
        self.cinematic = None
        # Presentation-only acknowledgements. Saved battles already contain
        # the authoritative fired trigger IDs and replay command log.
        self._seen_tactical_cinematics = {}
        self._typewriter_job = None
        self._stage_job = None
        self._explore_feedback = ""
        self._explore_scene_id = None
        self._audible_scene = None
        self._closing = False
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
        if self.cinematic is not None:
            self.cinematic.close()
            self.cinematic = None
        if self._typewriter_job is not None:
            self.root.after_cancel(self._typewriter_job)
            self._typewriter_job = None
        if self._stage_job is not None:
            self.root.after_cancel(self._stage_job)
            self._stage_job = None
        if self._motion_job is not None:
            self.root.after_cancel(self._motion_job)
            self._motion_job = None
        self._motion_frame = None
        for key in ("<Up>", "<Down>", "<Left>", "<Right>", "w", "a", "s", "d", "z", "q", "e"):
            self.root.unbind(key)
        if self.renderer:
            self.renderer.dispose()
            self.renderer = None
        if self.iso_renderer:
            self.iso_renderer.dispose()
            self.iso_renderer = None
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
        if not self._show_new_tactical_cinematics():
            self.show()

    def _show_new_tactical_cinematics(self):
        """Play only newly fired authored cues, never replay on a plain redraw."""
        from .cinematics import triggered_tactical_cinematics

        session = self.player.session
        battle = session.active_battle if session is not None else None
        if battle is None:
            return False
        previous = self._seen_tactical_cinematics.get(battle.battle_id, ())
        clips, observed = triggered_tactical_cinematics(
            self.project, battle, previous)
        self._seen_tactical_cinematics[battle.battle_id] = observed
        if not clips:
            return False
        self._play_cinematic_clips(clips, self.show)
        return True

    def _acknowledge_loaded_tactical_cinematics(self):
        """A reloaded save resumes combat, not already-fired movie sequences."""
        self._seen_tactical_cinematics.clear()
        session = self.player.session
        battle = session.active_battle if session is not None else None
        if battle is not None:
            self._seen_tactical_cinematics[battle.battle_id] = set(battle.fired)

    def title_screen(self):
        self._audible_scene = None
        self.audio.music_for("title")
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
        self._button(panel, "Migrer une sauvegarde v1", self._migrate_game).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=4)
        # The authored castle example is a repository demo, not packaged
        # core content. Show its entry only when that source is available.
        castle_example = Path(__file__).resolve().parent.parent / "examples" / "castle_vertical_slice.py"
        row = 5
        if self.project.sieges:
            self._button(panel, "Sièges créés dans le Studio", self._authored_siege_menu).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=4)
            row += 1
        if castle_example.is_file():
            self._button(panel, "Campagne Château (2.8)", self._open_castle).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=4)
            row += 1
        self._button(panel, "Options", self.options_screen).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4)
        self._button(panel, "Quitter", self.close).grid(
            row=row + 1, column=0, columnspan=2, sticky="ew", pady=4)

    def _authored_siege_menu(self):
        self._clear()
        self._heading("Sièges du Studio", "Jouer vos fronts, missions et événements personnalisés")
        selected = self.tk.StringVar(value=self.project.sieges[0]["id"])
        slot = self.tk.StringVar(value="1")
        frame = self.ttk.LabelFrame(self.view, text="Choisir le scénario et la sauvegarde",
                                    padding=18)
        frame.pack(fill="x", padx=100, pady=30)
        self.ttk.Combobox(frame, textvariable=selected, state="readonly",
                          values=[bp["id"] for bp in self.project.sieges],
                          width=28).pack(pady=8)
        self.ttk.Combobox(frame, textvariable=slot, state="readonly",
                          values=[str(i) for i in range(1, 10)], width=10).pack(pady=8)

        def launch_selected():
            from .studio_siege_player_app import launch
            from .tactical_rpg3 import authored_rules_for_document
            blueprint = next(bp for bp in self.project.sieges if bp["id"] == selected.get())
            content = self.player.content
            rules = authored_rules_for_document(content.to_dict())
            launch(content, blueprint, self.project, self.project_path,
                   int(slot.get()), rules=rules, master=self.root)

        self._button(frame, "Ouvrir ce siège", launch_selected).pack(
            fill="x", pady=8)
        self._button(frame, "Retour", self.title_screen).pack(
            fill="x", pady=5)

    def _open_castle(self):
        from examples.castle_vertical_slice import castle_content, castle_blueprint
        from .tactical_rpg3 import tactical_rpg_rules
        from .castle_player_app import launch as launch_castle
        save_path = self.player.profile.with_name(
            self.player.profile.stem + "_castle.json")
        return launch_castle(castle_content(), castle_blueprint(), save_path,
                             rules=tactical_rpg_rules(), master=self.root)

    def _new_game(self):
        cid, slot = self.campaign_var.get(), int(self.slot_var.get())
        path = self.player.path_for(cid, slot)
        exists = path.exists() or path.with_name(path.name + ".bak").exists()
        if exists and not self.messagebox.askyesno("Nouvelle partie",
                                                    "Recommencer cet emplacement ?"):
            return
        self.player.new_game(cid, slot, overwrite=exists)
        self._seen_tactical_cinematics.clear()
        self._cinematic_sequence("campaign_start", cid, self.show)

    def _load_game(self):
        self.player.load_game(self.campaign_var.get(), int(self.slot_var.get()))
        self._acknowledge_loaded_tactical_cinematics()
        status = self.player.last_load_status
        if status is not None and status.source == "backup":
            self.messagebox.showwarning(
                "Récupération de sauvegarde",
                "Le fichier principal est invalide. Une copie de secours a été "
                "chargée en mémoire, sans modifier les fichiers. "
                "Une partie de la progression récente peut manquer.")
        self.show()

    def _migrate_game(self):
        if not self.messagebox.askyesno(
                "Migration explicite",
                "Convertir la sauvegarde v1 sélectionnée vers le format v2 ? "
                "Une copie de l'original sera conservée en .bak. "
                "Les règles et les données du jeu ne seront pas converties."):
            return
        self.player.migrate_game(self.campaign_var.get(), int(self.slot_var.get()))
        self.messagebox.showinfo(
            "Migration terminée", "Sauvegarde v2 vérifiée. L'original v1 est conservé.")
        self._load_game()

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
        elif session.tactical_story_pending:
            # Story UI is modal over the current Battle, not a campaign screen.
            self._clear()
            self._heading("Décision pendant la bataille")
            self._narrative_scene(
                session.tactical_scene(), choices=session.tactical_choices(),
                on_choice=lambda cid: self._change(
                    lambda: self.player.choose_tactical_story_option(cid)))
        elif session.mode == "fronts":
            self.battle_screen()
        elif session.mode == "battle":
            self.battle_screen()
        else:
            self.campaign_screen()

    def _cinematic_sequence(self, kind, target, finished):
        """Play authored presentation beats without mutating the saved game."""
        from .cinematics import matching_cinematics
        from .cinematic_player import CinematicPlayback

        clips = matching_cinematics(self.project, kind, target)
        self._play_cinematic_clips(clips, finished)

    def _play_cinematic_clips(self, clips, finished):
        """Shared playback for campaign, mission, scene and tactical events."""
        from .cinematic_player import CinematicPlayback

        def next_clip(index=0):
            self.cinematic = None
            if index >= len(clips):
                finished()
                return
            self._clear()
            self.cinematic = CinematicPlayback(
                self.view, self.tk, self.ttk, clips[index],
                lambda: next_clip(index + 1), audio=self.audio,
                registry=self.registry, asset_root=self.asset_root)

        next_clip()

    def _start_mission_with_cinematic(self, mission_id):
        self._cinematic_sequence(
            "before_mission", mission_id,
            lambda: self._safe(lambda: self._change(
                lambda: self.player.start_mission(mission_id))))

    def _finish_mission_with_cinematic(self):
        battle = self.player.session.active_battle
        mission_id = battle.mission.id
        self.player.return_to_campaign()
        self._cinematic_sequence("after_mission", mission_id, self.show)

    def campaign_screen(self):
        session = self.player.session
        self._clear()
        self._heading(self.project.campaign(session.campaign_id)["name"],
                      "Or : " + str(session.progress.gold) +
                      "    Missions terminées : " + str(len(session.progress.completed)))
        # Visible roster: recruitment and equipment have actual tactical effects.
        if session.progress.heroes:
            roster = self.ttk.LabelFrame(self.view, text="Équipe et progression", padding=8)
            roster.pack(fill="x", padx=60, pady=(2, 8))
            for uid, hero in sorted(session.progress.heroes.items()):
                if uid.startswith("otage_") or uid == "refugie":
                    continue
                gear = ", ".join(hero.equipment.values()) or "sans équipement"
                self.ttk.Label(roster, text=f"{uid} · niveau {hero.level} · {hero.job} · {gear}").pack(anchor="w")
            bonds = [(key[6:], value) for key, value in sorted(session.progress.story_flags.items())
                     if key.startswith("trust_") and type(value) is int]
            if bonds:
                self.ttk.Label(roster, text="Relations : " +
                    ", ".join(f"{name} {value}" for name, value in bonds)).pack(anchor="w")
        scene = session.active_scene()
        if scene:
            self.audio.music_for(f'music_scene_{scene["id"]}', "campaign")
            if self._audible_scene != scene["id"]:
                self.audio.cue(f'scene_enter_{scene["id"]}')
                self._audible_scene = scene["id"]
            stage = session.exploration_state()
            if stage is not None and not stage["completed"]:
                self._exploration_screen(scene, stage)
            else:
                self._narrative_scene(scene)
        else:
            self._audible_scene = None
            self.audio.music_for("campaign")
            available = session.available_missions()
            if self.project.world:
                self._button(self.view, "Carte du monde",
                             self.world_screen).pack(fill="x", padx=80, pady=(3, 9))
            self.ttk.Label(self.view, text="Choisir une mission :").pack(anchor="w", pady=8)
            for mission_id in available:
                mission = self.player.content.missions[mission_id]
                self._button(self.view, mission.name + " — " + mission.objective,
                             lambda mid=mission_id: self._start_mission_with_cinematic(mid)).pack(
                                     fill="x", padx=80, pady=5)
            # Studio blueprints are distinct from ad-hoc multi-front battles.
            # Locked or duplicate-mission plans remain visible but not playable.
            sieges = self.player.available_sieges()
            if sieges:
                section = self.ttk.LabelFrame(
                    self.view, text="Sièges créés dans le Studio", padding=12)
                section.pack(fill="x", padx=80, pady=12)
                for siege in sieges:
                    if siege["ready"]:
                        self._button(
                            section, "Jouer le siège : " + siege["id"] +
                            " (" + str(siege["fronts"]) + " fronts)",
                            lambda sid=siege["id"]: self._change(
                                lambda: self.player.start_configured_siege(sid))).pack(
                                    fill="x", pady=3)
                    else:
                        detail = (", ".join(siege["locked"]) if siege["locked"] else
                                  "missions répétées ou autre rencontre active")
                        self.ttk.Label(
                            section, text=siege["id"] + " — bloqué : " + detail).pack(
                                anchor="w", pady=3)
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

    def world_screen(self):
        """Travel through the authored mission map; no alternate unlock rules."""
        session = self.player.session
        if session is None or not self.project.world:
            self.campaign_screen() if session is not None else self.title_screen()
            return
        # Active narrative decisions cannot be bypassed through world travel.
        if session.active_scene():
            self.campaign_screen()
            return
        projection = world_projection(
            self.project.world, self.player.content,
            available=session.available_missions(),
            completed=session.progress.completed)
        self._clear()
        self._heading("Carte du monde", "Destinations accessibles : vert • "
                      "terminées : bleu • verrouillées : gris")
        surface = self.ttk.Frame(self.view)
        surface.pack(fill="both", expand=True, padx=24, pady=8)
        surface.columnconfigure(0, weight=1)
        surface.rowconfigure(0, weight=1)
        canvas = self.tk.Canvas(surface, width=900, height=490,
                                highlightthickness=0)
        scrollbar_y = self.ttk.Scrollbar(surface, orient="vertical",
                                          command=canvas.yview)
        scrollbar_x = self.ttk.Scrollbar(surface, orient="horizontal",
                                          command=canvas.xview)
        canvas.configure(xscrollcommand=scrollbar_x.set,
                         yscrollcommand=scrollbar_y.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        draw_world_map(canvas, projection)
        label = self.tk.StringVar(value="Choisir un lieu sur la carte.")
        self.ttk.Label(self.view, textvariable=label).pack(anchor="w", padx=26)

        def choose(event):
            mid = pick_world_mission(canvas, projection, event)
            if mid is None:
                return
            location = next(node for node in projection["nodes"]
                            if node["mission"] == mid)
            label.set(location["label"] + " — " + location["status"])
            if location["status"] == "available":
                self._start_mission_with_cinematic(mid)

        canvas.bind("<Button-1>", lambda e: self._safe(lambda: choose(e)))
        footer = self.ttk.Frame(self.view)
        footer.pack(fill="x", pady=12)
        self._button(footer, "Retour à la campagne",
                     self.campaign_screen).pack(side="left", padx=12)
        self._button(footer, "Sauvegarder",
                     self.player.save).pack(side="left", padx=12)

    def _exploration_step(self, dx, dy):
        self._explore_feedback = ""
        self._change(lambda: self.player.explore_move(dx, dy))

    def _exploration_interact(self, point_id):
        def apply():
            result = self.player.explore_interact(point_id)
            self._explore_feedback = result["title"] + " — " + result["text"]
        self._change(apply)

    def _exploration_wait(self):
        self._explore_feedback = "Le temps passe. Les habitants continuent à se déplacer."
        self._change(self.player.explore_wait)

    def _exploration_actor(self, actor_id, action):
        def apply():
            result = self.player.explore_actor(actor_id, action)
            self._explore_feedback = result["title"] + " — " + result["text"]
        self._change(apply)

    def _exploration_screen(self, scene, stage):
        if self._explore_scene_id != scene["id"]:
            self._explore_feedback = ""
            self._explore_scene_id = scene["id"]
        subtitle = ("Le village brûle. Chaque déplacement compte : secourez les habitants !"
                    if stage["theme"] == "village" else
                    "Explorez les champs avant l'appel des voix.")
        self._heading(stage["title"], subtitle)
        area = self.ttk.Frame(self.view)
        area.pack(fill="both", expand=True)
        board = self.tk.Canvas(area, width=690, height=495,
                               highlightthickness=0, background="#314936")
        board.pack(side="left", padx=8, pady=6)
        draw_exploration(board, stage)
        def click(event):
            x, y = int((event.x - 42) // 58), int((event.y - 25) // 58)
            px, py = stage["position"]
            if abs(x - px) + abs(y - py) == 1:
                self._safe(lambda: self._exploration_step(x - px, y - py))
        board.bind("<Button-1>", click)
        sidebar = self.ttk.Frame(area, padding=10)
        sidebar.pack(side="left", fill="both", expand=True)
        self.ttk.Label(sidebar, text="Déplacement : flèches / ZQSD (WASD)",
                       wraplength=310).pack(anchor="w", pady=(4, 8))
        self.ttk.Label(sidebar, text="Cliquer une case voisine pour marcher.",
                       wraplength=310).pack(anchor="w", pady=(0, 5))
        if stage.get("actors"):
            self.ttk.Label(sidebar, text="Temps écoulé : " + str(stage["tick"]) +
                           " déplacements", wraplength=310).pack(anchor="w", pady=3)
            self._button(sidebar, "Attendre un déplacement",
                         self._exploration_wait).pack(anchor="w", pady=(2, 8))
        px, py = stage["position"]
        nearest = []
        for point in stage["interactions"]:
            distance = abs(point["pos"][0] - px) + abs(point["pos"][1] - py)
            info = (" ✓" if point["visited"] else "")
            self.ttk.Label(sidebar, text=point["title"] + info,
                           wraplength=270).pack(anchor="w", pady=(3, 0))
            if distance <= 1:
                nearest.append(point["id"])
                self._button(sidebar, "Examiner : " + point["title"],
                             lambda pid=point["id"]: self._exploration_interact(pid)).pack(
                                 anchor="w", fill="x", pady=(1, 5))
        nearest_actor = []
        for actor in stage.get("actors", []):
            description = actor["name"] + " — " + (
                "sauvé" if actor["status"] == "rescued" else
                "trop tard" if actor["status"] == "lost" else
                "à secourir (" + str(max(0, actor["deadline"] - stage["tick"])) +
                " pas)" if actor["kind"] == "civilian" else "témoin")
            self.ttk.Label(sidebar, text=description,
                           wraplength=310).pack(anchor="w", pady=(3, 0))
            distance = abs(actor["pos"][0] - px) + abs(actor["pos"][1] - py)
            if distance <= 1 and actor["status"] != "lost":
                nearest_actor.append(actor["id"])
                self._button(sidebar, "Parler à " + actor["name"],
                             lambda aid=actor["id"]: self._exploration_actor(
                                 aid, "talk")).pack(anchor="w", fill="x", pady=(1, 2))
                if actor["kind"] == "civilian" and actor["status"] == "active":
                    self._button(sidebar, "Secourir " + actor["name"],
                                 lambda aid=actor["id"]: self._exploration_actor(
                                     aid, "rescue")).pack(anchor="w", fill="x", pady=(1, 4))
        self.ttk.Label(sidebar, text=self._explore_feedback or
                       "Avancez vers un point d'intérêt ou un habitant.",
                       wraplength=300).pack(anchor="w", pady=9)
        moves = {"<Up>": (0, -1), "<Down>": (0, 1),
                 "<Left>": (-1, 0), "<Right>": (1, 0),
                 "w": (0, -1), "z": (0, -1), "a": (-1, 0),
                 "q": (-1, 0), "s": (0, 1), "d": (1, 0)}
        for key, delta in moves.items():
            self.root.bind(key, lambda event, vector=delta:
                           self._safe(lambda: self._exploration_step(*vector)))
        if nearest_actor:
            self.root.bind("e", lambda event: self._safe(
                lambda: self._exploration_actor(nearest_actor[0], "talk")))
        elif nearest:
            self.root.bind("e", lambda event: self._safe(
                lambda: self._exploration_interact(nearest[0])))

    def _narrative_scene(self, scene, *, choices=None, on_choice=None):
        panel = self.ttk.LabelFrame(self.view, text=scene["title"], padding=20)
        panel.pack(fill="both", expand=True, padx=60, pady=16)
        if scene["id"].startswith("sc_p0_"):
            art = self.tk.Canvas(panel, width=860, height=210, highlightthickness=0)
            art.pack(pady=4)
            def animate(frame=0):
                if not art.winfo_exists():
                    return
                draw_story_backdrop(art, scene["id"], frame)
                self._stage_job = self.root.after(170, animate, frame + 1)
            animate()
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
        if choices is None:
            choices = self.player.session.available_choices()
        if on_choice is None:
            on_choice = lambda cid: self._change(
                lambda: self.player.choose_story_option(cid))
        for choice in choices:
            self._button(panel, choice["label"],
                         lambda cid=choice["id"]: on_choice(cid)).pack(
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
        self._clear()
        if battle is None:
            self.strategy_screen()
            return
        self.audio.music_for(f"mission_{battle.mission.id}", "battle")
        self._heading(battle.mission.name,
                      "Tick " + str(battle.tick) + "    " +
                      ("Résultat : " + battle.result if battle.result else
                       "Déploiement" if battle.deploying else
                       "Unité active : " + (battle.active.name if battle.active else "?")))
        nav = self.ttk.Frame(self.view)
        nav.pack(fill="x", pady=4)
        if session.mode == "fronts":
            self._button(nav, "Timeline / Fronts", self.strategy_screen).pack(side="left", padx=4)
            if session.fronts.recovery_battles:
                self.ttk.Label(
                    nav, text="Reconquête tactique : " +
                    sorted(session.fronts.recovery_battles)[0]).pack(
                        side="left", padx=6)
        elif session.finalized:
            self._button(nav, "Résultats → Campagne",
                         self._finish_mission_with_cinematic).pack(
                             side="left", padx=4)
        self._button(nav, "Sauvegarder", self.player.save).pack(side="right", padx=4)
        self.ttk.Checkbutton(nav, text="Vue isométrique 2.5D",
                             variable=self.iso_view_var,
                             command=self._switch_projection).pack(side="right", padx=8)
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
                active_level = battle.unit_levels.get(battle.active.id, 0)
                if battle.mission.level_links:
                    if active_level:
                        options = ["level_move", "level_attack", "attack", "end"]
                    else:
                        options = (["move", "level_move", "level_attack",
                                    "attack", *battle.active.skills,
                                    "item:potion", "item:ether", "item:phoenix",
                                    *["object:" + obj["id"] for obj in battle.mission.objects],
                                    *available_operations(battle, battle.active)])
                        options += tactical_action_options(battle)
                        options += ["end"]
                else:
                    options = (["move", "attack", *battle.active.skills,
                                "item:potion", "item:ether", "item:phoenix",
                                *["object:" + obj["id"] for obj in battle.mission.objects],
                                *available_operations(battle, battle.active)])
                    options += tactical_action_options(battle)
                    options += ["end"]
            if options:
                if self.action_var.get() not in options:
                    self.action_var.set(options[0])
                self.ttk.Label(actions, text="Action").pack(side="left", padx=5)
                self.ttk.Combobox(actions, textvariable=self.action_var,
                                  values=options, state="readonly", width=23).pack(
                                      side="left", padx=7)
                if battle.mission.level_links:
                    self.ttk.Label(actions, text="Étage cible").pack(side="left")
                    self.ttk.Combobox(
                        actions, textvariable=self.level_var, state="readonly",
                        values=tuple(range(0, 1+max(
                            max(row["from"][0], row["to"][0])
                            for row in battle.mission.level_links))),
                        width=3).pack(side="left")
                self.ttk.Label(actions, text="Orientation").pack(side="left")
                self.ttk.Combobox(actions, textvariable=self.facing_var, state="readonly",
                                  values=["north", "south", "east", "west"],
                                  width=9).pack(side="left", padx=6)
                self._button(actions, "Exécuter", self._execute).pack(side="left", padx=5)
                if not battle.deploying:
                    self._button(actions, "Fin de tour", self._end).pack(side="left", padx=5)
        body = self.ttk.Frame(self.view)
        body.pack(fill="both", expand=True, pady=9)
        self.canvas = self.tk.Canvas(body, background="#172638", highlightthickness=0,
                                     takefocus=1)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.renderer = CanvasRenderer(self.canvas, registry=self.registry,
                                       asset_root=self.asset_root)
        self.iso_renderer = IsoBattleCanvas(self.canvas)
        self.canvas.bind("<Button-1>", self._select_cell)
        self.canvas.bind("<Return>", lambda _event: self._safe(self._execute))
        self.canvas.bind("<space>", lambda _event: self._safe(self._end))
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<Button-4>", lambda _: self._zoom_step(1))
        self.canvas.bind("<Button-5>", lambda _: self._zoom_step(-1))
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_drag)
        self.info = self.tk.Text(body, width=37, wrap="word", fg="#e9f2fc",
                                 bg="#182a40", relief="flat")
        self.info.pack(side="right", fill="y", padx=(9, 0))
        self._redraw()
        self.ttk.Label(self.view,
                       text="Carte : Entrée = exécuter • Espace = finir le tour | "
                            "Rouge = terrain, violet = incantation, orange = charge possible").pack(anchor="w")
        if not session.finalized:
            self._button(self.view, "Abandonner l'opération",
                         self._abandon).pack(anchor="e", pady=4)

    def _motion_tick(self):
        self._motion_job = None
        self._render_motion(time.monotonic() * 1000)

    def _render_motion(self, clock_ms):
        if self.renderer is None or self.canvas is None or self._motion_frame is None:
            return
        if self.iso_view_var.get() and self.iso_renderer is not None:
            # Same scene as Editor playtest. Use the engine snapshot for this
            # rendering gate; interpolated actor poses remain in 2D mode.
            battle = self.player.session.active_battle
            if battle is not None:
                self.iso_renderer.draw(
                    battle, self._motion_frame, self.camera,
                    poses=self.motion.poses(clock_ms))
            if self.motion.active(clock_ms) and self._motion_job is None:
                self._motion_job = self.root.after(60, self._motion_tick)
            return
        self.renderer.draw(
            self._motion_frame, self.camera, poses=self.motion.poses(clock_ms),
            elapsed_ms=self.motion.elapsed_ms(clock_ms), clock_ms=int(clock_ms))
        if (self.motion.active(clock_ms) or
                self.renderer.animates_when_idle(self._motion_frame)):
            if self._motion_job is None:
                self._motion_job = self.root.after(60, self._motion_tick)

    def _redraw(self):
        if self.canvas is None:
            return
        battle = self.player.session.active_battle
        skill = self.action_var.get()
        skill = skill if skill == "attack" or skill in (
            battle.active.skills if battle.active else ()) else None
        frame = battle_frame(battle, self.selection, skill)
        if battle is not self._motion_source:
            self.motion.reset()
            self._motion_source = battle
        clock_ms = time.monotonic() * 1000
        self.motion.observe(frame, clock_ms)
        self._motion_frame = frame
        self._render_motion(clock_ms)
        self.audio.observe(battle)
        rows = ["Case : " + str(self.selection), "", "Escouades"]
        if self.action_var.get() == 'level_attack' and battle.active is not None:
            try:
                rows.append('Tir vertical : ' + str(battle.vertical_forecast(
                    self.level_var.get(), self.selection)))
            except RuleError as exc:
                rows.append('Tir vertical indisponible : ' + str(exc))
        if battle.mission.level_links:
            rows.insert(1, "Étage actif : N" + str(
                battle.unit_levels.get(battle.active_id, 0) if battle.active_id else 0))
        rows.extend(u.name + " (" + u.team + ") : PV " + str(u.hp) + "/" +
                    str(u.max_hp) + " / MP " + str(u.mp) + "/" + str(u.max_mp)
                    for u in frame.actors)
        if frame.forecast:
            rows.extend(["", "Prévisions"])
            rows.extend(str(item) for item in frame.forecast)
        # Clarity: scheduled casts, armed reactions and hypothetical charges
        # are not equivalent to certain environmental damage.
        threats = {}
        for danger in frame.danger:
            threats.setdefault(danger["kind"], set()).add(tuple(danger["cell"]))
        labels = (("hazard", "Danger du terrain (certain)"),
                  ("cast", "Sort programmé"),
                  ("prepared", "Réaction armée"),
                  ("charge", "Charge possible (non garantie)"))
        rows.extend(["", "Menaces visibles"])
        rows.extend(f"{title} : {len(threats[kind])} cases"
                    for kind, title in labels if threats.get(kind))
        on_cell = [title for kind, title in labels
                   if tuple(self.selection) in threats.get(kind, set())]
        rows.append("Case sélectionnée : " +
                    (", ".join(on_cell) if on_cell else "aucune menace signalée"))
        rows.extend(["", "Prochaines activations (CT estimé)"])
        rows.extend(f"{entry['unit']} : " +
                    ("actif" if entry["active"] else
                     "bloqué" if entry["eta_ticks"] is None else
                     "t+" + str(entry["eta_ticks"])) for entry in frame.timeline)
        if frame.casts:
            rows.extend(["", "Incantations annoncées"])
            rows.extend(f"{cast['unit']} : {cast['skill']} dans {cast['remaining_ticks']} ticks"
                        for cast in frame.casts)
        if frame.charges:
            rows.extend(["", "Charges possibles (non garanties)"])
            rows.extend(f"{charge['unit']} → {charge['target']}" for charge in frame.charges)
        rows.extend(["", "Journal"])
        rows.extend(str(event) for event in frame.events[-15:])
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(rows))
        self.info.configure(state="disabled")

    def _switch_projection(self):
        # CanvasRenderer caches item IDs. Force a rebuild after swapping
        # the image-oriented and vector-oriented Canvas item sets.
        if self.renderer is not None:
            self.renderer.dispose()
        self._redraw()

    def _select_cell(self, event):
        self.canvas.focus_set()
        battle = self.player.session.active_battle
        if self.iso_view_var.get() and self.iso_renderer is not None:
            floor = (self.level_var.get() if self.action_var.get() in {'level_move', 'level_attack'}
                     else battle.unit_levels.get(battle.active_id, 0)
                     if battle.active_id else 0)
            cell = self.iso_renderer.hit_test(event.x, event.y, level=floor)
        else:
            cell = self.camera.screen_to_cell(event.x, event.y)
        if cell is not None and battle.board.contains(cell):
            self.selection = cell
            self._redraw()

    def _zoom(self, event):
        self._zoom_step(1 if event.delta > 0 else -1, (event.x, event.y))

    def _zoom_step(self, direction, anchor=(300, 200)):
        if self.iso_view_var.get() and self.iso_renderer is not None:
            battle = self.player.session.active_battle
            if battle is not None:
                self.camera = anchored_iso_zoom(
                    battle.board, self.camera, self.iso_renderer.viewport(),
                    direction, anchor)
        else:
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
        elif kind == "level_move":
            command = {"kind": "level_move", "level": self.level_var.get(),
                       "cell": list(self.selection)}
        elif kind == "level_attack":
            command = {"kind": "level_attack", "level": self.level_var.get(),
                       "cell": list(self.selection)}
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
        elif kind == "charge" or kind == "disengage" or kind.startswith(
                ("formation:", "prepare:", "relay:")):
            command = tactical_command(kind, self.selection)
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
        self.audio.music_for("battle")
        if session.mode != "fronts":
            self.show()
            return
        self._clear()
        frame = strategy_frame(session.fronts)
        self._heading("Siège : " + session.siege_id
                      if session.siege_id else "Commandement des fronts",
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
        if session.fronts.logistics is not None:
            self._logistics_panel(session.fronts)
        if session.fronts.campaign is not None:
            self._campaign_routes_panel(session.fronts)
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

    def _logistics_panel(self, fronts):
        """Display real convoy state and dispatch orders, never visual-only actors."""
        logistics = fronts.logistics
        panel = self.ttk.LabelFrame(self.view, text="Routes et ravitaillement", padding=8)
        panel.pack(fill="x", pady=7)
        state = logistics.state()
        supplies = state.get("supplies")
        summary = ("Réserves : " + str(state["reserves"]) +
                   "   Capacité : " + str(state["capacity"]) +
                   ("   Vivres : " + str(supplies) if supplies is not None else "") +
                   "   Escorts : " + str(state.get("escorts", 0)))
        self.ttk.Label(panel, text=summary).pack(anchor="w", pady=2)
        routes = state["routes"]
        self.ttk.Label(
            panel, text="Routes : " + (" ; ".join(
                r["from"] + " → " + r["to"] + " (" + str(r["turns"]) + " tours)"
                for r in routes) if routes else "aucune route configurée"),
            wraplength=1030).pack(anchor="w", pady=2)
        pending = state["in_transit"]
        self.ttk.Label(
            panel, text="Convois : " + (" ; ".join(
                row["id"] + " → " + row["to"] + " / arrivée T" +
                str(row["arrival"]) +
                (" [bloqué]" if row.get("stranded") else "")
                for row in pending) if pending else "aucun"),
            wraplength=1030).pack(anchor="w", pady=2)

        orders = self.ttk.Frame(panel)
        orders.pack(fill="x", pady=5)
        destinations = sorted({r["to"] for r in routes
                               if r["from"] == "reserve"})
        transfers = sorted({r["to"] for r in routes
                            if r["from"] == fronts.timeline.focused})
        if self.logistics_dest_var.get() not in destinations:
            self.logistics_dest_var.set(destinations[0] if destinations else "")
        if self.logistics_transfer_dest_var.get() not in transfers:
            self.logistics_transfer_dest_var.set(transfers[0] if transfers else "")
        self.ttk.Label(orders, text="Vers (réserves)").pack(side="left")
        self.ttk.Combobox(
            orders, textvariable=self.logistics_dest_var,
            values=destinations, width=14, state="readonly").pack(
                side="left", padx=4)
        for caption, variable, width in (
                ("Unité", self.logistics_actor_var, 13),
                ("X", self.logistics_x_var, 4),
                ("Y", self.logistics_y_var, 4)):
            self.ttk.Label(orders, text=caption).pack(side="left", padx=(5, 1))
            self.ttk.Entry(orders, textvariable=variable, width=width).pack(
                side="left")
        if destinations:
            self._button(orders, "Envoyer réserves", lambda: self._change(
                lambda: self.player.send_reserves(
                    self.logistics_dest_var.get(),
                    [{"id": self.logistics_actor_var.get(),
                      "name": self.logistics_actor_var.get(),
                      "team": "player",
                      "pos": [int(self.logistics_x_var.get()),
                              int(self.logistics_y_var.get())]}]))).pack(
                                  side="left", padx=4)
        if transfers:
            transfers_row = self.ttk.Frame(panel)
            transfers_row.pack(anchor="w", pady=3)
            self.ttk.Label(transfers_row, text="Vers (transfert)").pack(side="left")
            self.ttk.Combobox(
                transfers_row, textvariable=self.logistics_transfer_dest_var,
                values=transfers, width=14, state="readonly").pack(
                    side="left", padx=4)
            self._button(transfers_row, "Transférer unité", lambda: self._change(
                lambda: self.player.transfer_units(
                    self.logistics_transfer_dest_var.get(),
                    {self.logistics_actor_var.get():
                     [int(self.logistics_x_var.get()),
                      int(self.logistics_y_var.get())]}))).pack(
                          side="left", padx=4)
        if pending:
            convoy_ids = [r["id"] for r in pending]
            if self.convoy_var.get() not in convoy_ids:
                self.convoy_var.set(convoy_ids[0])
            convoy_actions = self.ttk.Frame(panel)
            convoy_actions.pack(anchor="w", pady=3)
            self.ttk.Label(convoy_actions, text="Convoi").pack(side="left")
            self.ttk.Combobox(
                convoy_actions, textvariable=self.convoy_var,
                values=convoy_ids, state="readonly", width=17).pack(
                    side="left", padx=5)
            self._button(convoy_actions, "Assigner escorte", lambda: self._change(
                lambda: self.player.escort_convoy(self.convoy_var.get()))).pack(
                    side="left", padx=4)
            self._button(convoy_actions, "Secourir (vivres)", lambda: self._change(
                lambda: self.player.rescue_convoy(self.convoy_var.get()))).pack(
                    side="left", padx=4)

    def _campaign_routes_panel(self, fronts):
        """Only genuine tactical results/events can unlock routes or treaties."""
        policy = fronts.campaign.state(fronts)
        panel = self.ttk.LabelFrame(self.view, text="Routes, accords et reconquête",
                                    padding=7)
        panel.pack(fill="x", pady=5)
        self.ttk.Label(panel, text=(
            "Finale : " + policy["final_front"] +
            "   | Statut : " + policy["status"] +
            "   | Accès : " + ("ouvert" if policy["unlocked"] else "verrouillé") +
            "   | Conditions : " + ", ".join(
                name + "=" + row["status"] +
                (" ✓" if row["accepted"] else " ✗")
                for name, row in policy["required"].items())),
            wraplength=1050).pack(anchor="w", pady=3)

        if fronts.route_policy is not None:
            routes = fronts.route_policy.routes
            if self.route_var.get() not in routes:
                self.route_var.set("breach")
            line = self.ttk.Frame(panel)
            line.pack(fill="x")
            self.ttk.Label(line, text="Approche").pack(side="left", padx=3)
            self.ttk.Combobox(
                line, textvariable=self.route_var, state="readonly",
                values=sorted(routes), width=16).pack(side="left", padx=4)
            self._button(line, "Engager itinéraire",
                         lambda: self._change(
                            lambda: self.player.select_route(
                                self.route_var.get()))).pack(side="left", padx=4)
            self.ttk.Label(
                line, text="Choix actuel : " + fronts.route_selected +
                (" (définitif)" if fronts.route_locked else ""),
                wraplength=400).pack(side="left", padx=5)
            current = routes[self.route_var.get()]
            self.ttk.Label(
                panel, text=("Coûts : " + str(current["supplies"]) + " vivres, " +
                            str(current["strength_loss"]) +
                            " soldats ; conditions : " +
                            str(current["required"])), wraplength=1050).pack(
                                anchor="w", pady=2)

        decisions = self.ttk.Frame(panel)
        decisions.pack(fill="x", pady=4)
        front = fronts.timeline.focused
        if fronts.recovery_battles:
            recovering = sorted(fronts.recovery_battles)[0]
            self._button(decisions, "Reprendre reconquête", self.battle_screen).pack(
                side="left", padx=4)
            self._button(
                decisions, "Abandonner reconquête", lambda: self._change(
                    lambda: self.player.abandon_recovery(recovering))).pack(
                        side="left", padx=4)
            return
        for category, label, action in (
            ("negotiation", "Négocier le passage", self.player.negotiate_front),
            ("partial", "Valider objectif partiel", self.player.partial_front),
            ("retreat", "Ordre de retraite", self.player.withdraw_front)):
            if front in fronts.campaign.spec[category] and (
                    fronts.timeline.fronts[front]["status"] == "active"):
                self._button(
                    decisions, label,
                    lambda selected=front, perform=action: self._change(
                        lambda: perform(selected))).pack(side="left", padx=4)
        chosen = self.front_var.get()
        if (fronts.route_policy is not None
                and chosen in fronts.route_policy.recovery
                and fronts.timeline.fronts[chosen]["status"] in
                ("defeat", "withdrawn")):
            self._button(
                decisions, "Reconquérir ce secteur", lambda: self._change(
                    lambda: self.player.start_recovery(
                        self.front_var.get()))).pack(side="left", padx=4)

    def close(self):
        # Multiple WM_DELETE/button callbacks must never double-close audio/Tk.
        if self._closing:
            return
        self._closing = True
        try:
            if self.player.session is not None:
                try:
                    self.player.save()
                except (RuleError, OSError, ValueError) as exc:
                    if not self.messagebox.askyesno(
                            "Sauvegarde impossible",
                            str(exc) + "\nQuitter malgré l'échec ?"):
                        self._closing = False
                        return
            self.audio.close()
            self.root.destroy()
        except Exception:
            self._closing = False
            raise

    def run(self):
        self.root.mainloop()


def launch(content_path, project_path=None, profile_path=None):
    PlayerApplication(content_path, project_path, profile_path).run()
