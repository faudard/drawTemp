"""Graphical Player for *any* validated Siege Studio blueprint (2.8.2).

Uses the 2.8.1 tactical Canvas unchanged; all bespoke logic is presentation
and all user intents are delegated to authored_siege_player controller.
"""
from pathlib import Path

from .audio_stage import AudioStage
from .tk_renderer import CanvasRenderer
from .authored_siege_player import AuthoredSiegeController
from .castle_player_app import CastlePlayerApplication
from .presentation import strategy_frame


class StudioSiegePlayerApplication(CastlePlayerApplication):
    def __init__(self, content, blueprint, project, project_path, slot=1,
                 *, rules=None, master=None, controller=None):
        self.authored_project = project
        self._narrative_job = None
        self.presentation_registry = project.asset_registry()
        self.presentation_asset_root = Path(project_path).parent
        self.narrative_audio = AudioStage(
            self.presentation_registry, self.presentation_asset_root,
            effects_volume=project.options["effects_volume"],
            music_volume=project.options["music_volume"])
        managed = controller or AuthoredSiegeController(
            content, blueprint, project_path, slot, rules=rules,
            project=project)
        super().__init__(content, blueprint, managed.save_path, rules=rules,
                         master=master, controller=managed)
        self.root.title(project.title + " — " + blueprint["id"])
        self.root.geometry("1200x850")
        if managed.session is not None:
            self.show()

    def title_screen(self):
        self._clear()
        title = self.authored_project.title
        self._heading(title + " — Siège : " + self.controller.blueprint["id"],
                      "Carte, personnages, événements et siège issus du Studio ; "
                      "sauvegardes isolées par siège et emplacement.")
        box = self.ttk.LabelFrame(self.view, text="Campagne du Studio", padding=18)
        box.pack(fill="x", padx=65, pady=22)
        self.ttk.Label(box, text="Emplacement " + str(self.controller.slot)
                       + " : " + str(self.controller.save_path),
                       wraplength=960).pack(anchor="w", pady=8)
        self._button(box, "Nouvelle partie", self._new_game).pack(
            fill="x", pady=6)
        if self.controller.save_path.exists():
            self._button(box, "Reprendre sauvegarde", lambda: self._change(
                self.controller.continue_game)).pack(fill="x", pady=6)
        if self.controller.session is not None:
            self._button(box, "Retour à la bataille", self.show).pack(
                fill="x", pady=6)
        self._button(box, "Fermer", self.close).pack(fill="x", pady=6)

    def _clear(self):
        if self._narrative_job is not None:
            self.root.after_cancel(self._narrative_job)
            self._narrative_job = None
        super()._clear()

    def show(self):
        if self.controller.session is not None:
            scene = self.controller.active_scene()
            if scene is not None:
                self._scene_screen(scene)
                return
        super().show()

    def _scene_screen(self, scene):
        """Interactive narrative gate; StoryBook owns all conditions/effects."""
        self._clear()
        self.narrative_audio.music_for("scene_" + scene["id"],
                                      "speaker_" + scene["speaker"], "dialogue")
        self.narrative_audio.cue("scene_open")
        self._heading(scene["title"], "Scène interactive — " +
                      (scene["speaker"] or "Narration"))
        panel = self.ttk.LabelFrame(self.view, text=scene["speaker"] or "Narrateur",
                                    padding=18)
        panel.pack(fill="both", expand=True, padx=50, pady=10)
        picture = CanvasRenderer(
            panel, registry=self.presentation_registry,
            asset_root=self.presentation_asset_root).image(
                "portrait", scene["speaker"])
        if picture is not None:
            portrait = self.ttk.Label(panel, image=picture)
            portrait.image = picture
            portrait.pack(anchor="w", pady=8)
        elif scene["speaker"]:
            self.ttk.Label(panel, text=scene["speaker"][:2].upper(),
                           font=("TkDefaultFont", 28, "bold")).pack(
                               anchor="w", pady=8)
        dialogue = self.tk.Label(panel, text="", anchor="nw", justify="left",
                                 fg="#e9f2fc", bg="#101a2b", wraplength=900,
                                 font=("TkDefaultFont", 13))
        dialogue.pack(fill="x", pady=12)
        message = scene["text"]

        def reveal(count=0):
            if not dialogue.winfo_exists():
                return
            dialogue.configure(text=message[:count])
            if count < len(message):
                self._narrative_job = self.root.after(
                    12, reveal, min(count + 4, len(message)))
            else:
                self._narrative_job = None

        reveal()
        def skip_text():
            if self._narrative_job is not None:
                self.root.after_cancel(self._narrative_job)
                self._narrative_job = None
            dialogue.configure(text=message)

        self._button(panel, "Afficher tout le dialogue", skip_text).pack(
            anchor="w", pady=6)
        choices = self.controller.available_choices()
        for choice in choices:
            self._button(panel, choice["label"], lambda cid=choice["id"]:
                         self._change(lambda:
                             self.controller.choose_story_option(cid))).pack(
                                 fill="x", padx=18, pady=5)
        if not choices:
            self.ttk.Label(panel, text="Aucun choix disponible. Corriger les "
                           "conditions dans le Studio.",
                           style="Castle.TLabel").pack(anchor="w", pady=9)
        self.ttk.Label(panel, text="Or : " +
                       str(self.controller.story.progress.gold) +
                       "   |   Drapeaux : " +
                       str(self.controller.story.progress.story_flags),
                       style="Castle.TLabel").pack(anchor="w", pady=12)
        self._footer()

    def close(self):
        try:
            super().close()
        finally:
            # The audio stage is presentation-only and optional.
            if not self.root.winfo_exists():
                self.narrative_audio.close()

    def _current_battle(self):
        return self.controller.current_battle()

    def strategy_screen(self):
        self.page = "strategy"
        self._clear()
        controller = self.controller
        fronts = controller.session.fronts
        frame = strategy_frame(fronts)
        status = (fronts.campaign.state(fronts)["status"] if fronts.campaign
                  else "fronts libres")
        heading = f"Tour {frame.turn} | Secteur actif : {frame.focused} | Situation : {status}"
        if fronts.logistics is not None:
            heading += " | Escortes : " + str(fronts.logistics.escorts)
            if fronts.logistics.supplies is not None:
                heading += " | Provisions : " + str(fronts.logistics.supplies["player"])
        self._heading("Commandement — " + controller.blueprint["id"], heading)

        side = controller.active_encounter()
        if side:
            row = self.ttk.Frame(self.view)
            row.pack(fill="x", pady=7)
            self.ttk.Label(row, text=f"Mission annexe en cours : {side[0]} / {side[1]}",
                           style="Castle.TLabel").pack(side="left", padx=8)
            self._button(row, "Reprendre combat", self.battle_screen).pack(
                side="left", padx=5)
            self._button(row, "Abandonner mission", lambda: self._change(
                controller.abandon_side)).pack(side="left", padx=5)

        commands = self.ttk.Frame(self.view)
        commands.pack(fill="x", pady=6)
        self._button(commands, "Jouer sur la carte", self.battle_screen).pack(
            side="left", padx=4)
        self._button(commands, "Avancer la timeline", lambda: self._change(
            controller.advance)).pack(side="left", padx=4)
        self._button(commands, "Changer de front", lambda: self._change(
            lambda: controller.switch(self.front_var.get()),
            page="battle")).pack(side="left", padx=4)
        self._button(commands, "Doctrine", lambda: self._change(
            lambda: controller.doctrine(self.front_var.get(),
                                       self.doctrine_var.get()))).pack(
                                           side="left", padx=4)
        self.ttk.Combobox(commands, state="readonly", textvariable=self.doctrine_var,
                          values=("hold", "assault", "delay", "retreat"), width=10).pack(
                              side="left", padx=4)
        self.front_var.set(frame.focused)
        names = list(controller.blueprint["fronts"])
        front_table = self.ttk.Treeview(
            self.view, columns=("mission", "status", "allies", "enemies"),
            show="tree headings", height=min(8, max(2, len(names))))
        for col, title, width in (
                ("#0", "Front", 150), ("mission", "Mission", 240),
                ("status", "Résultat", 150), ("allies", "Alliés", 85),
                ("enemies", "Opposition", 90)):
            front_table.heading(col, text=title)
            front_table.column(col, width=width, anchor="center")
        for front in frame.fronts:
            front_table.insert("", "end", iid=front.id, text=front.id,
                               values=(controller.blueprint["fronts"][front.id],
                                       front.status, front.strength, front.opposition))
        front_table.selection_set(frame.focused)
        front_table.bind("<<TreeviewSelect>>",
                         lambda _: self.front_var.set(front_table.selection()[0])
                         if front_table.selection() else None)
        front_table.pack(fill="x", pady=6)

        if fronts.campaign is not None:
            choices = self.ttk.Frame(self.view)
            choices.pack(fill="x", pady=5)
            for name, action in (("Négocier", controller.negotiate),
                                 ("Objectif partiel", controller.partial),
                                 ("Retraite", lambda: controller.withdraw(
                                     self.front_var.get()))):
                self._button(choices, name, lambda fn=action: self._change(fn)
                             ).pack(side="left", padx=3)
            if fronts.route_policy is not None:
                routes = sorted(fronts.route_policy.routes)
                if self.route_var.get() not in routes:
                    self.route_var.set(routes[0])
                self.ttk.Combobox(choices, state="readonly",
                                  textvariable=self.route_var, values=routes,
                                  width=12).pack(side="left", padx=5)
                self._button(choices, "Choisir route", lambda: self._change(
                    lambda: controller.route(self.route_var.get()))
                             ).pack(side="left", padx=3)
                self._button(choices, "Reprise tactique", lambda: self._change(
                    lambda: controller.recover(self.front_var.get()),
                    page="battle")).pack(side="left", padx=3)

        if fronts.logistics is not None:
            convoy_frame = self.ttk.LabelFrame(self.view, text="Convois et missions annexes")
            convoy_frame.pack(fill="x", pady=6)
            left = self.ttk.Frame(convoy_frame)
            left.pack(fill="x")
            convoy_ids = [c["id"] for c in fronts.logistics.in_transit]
            convoy_ids += [cid for cid in fronts.pursuit_targets if cid not in convoy_ids]
            convoy_ids = sorted(set(convoy_ids))
            if not hasattr(self, "convoy_var"):
                self.convoy_var = self.tk.StringVar()
            if self.convoy_var.get() not in convoy_ids:
                self.convoy_var.set(convoy_ids[0] if convoy_ids else "")
            self.ttk.Combobox(left, textvariable=self.convoy_var,
                              state="readonly", values=convoy_ids,
                              width=17).pack(side="left", padx=6, pady=5)
            for title, fn in (
                ("Escorte", controller.escort), ("Sauvetage tactique", controller.rescue),
                ("Butin partiel", controller.salvage),
                ("Négocier cargaison", controller.negotiate_convoy),
                ("Poursuivre", controller.pursue)):
                self._button(left, title, lambda f=fn: self._change(
                    lambda: f(self.convoy_var.get()),
                    page="battle" if f in (controller.rescue, controller.pursue)
                    else "strategy")).pack(side="left", padx=3)
            dispatch = self.ttk.Frame(convoy_frame)
            dispatch.pack(fill="x", pady=5)
            if not hasattr(self, "destination_var"):
                self.destination_var = self.tk.StringVar(value=frame.focused)
                self.transfer_unit_var = self.tk.StringVar()
                self.transfer_x_var = self.tk.StringVar(value="1")
                self.transfer_y_var = self.tk.StringVar(value="1")
            self.ttk.Label(dispatch, text="Transférer combattant :",
                           style="Castle.TLabel").pack(side="left", padx=4)
            active_players = [u.id for u in fronts.active.units
                              if u.team == "player" and u.alive]
            if self.transfer_unit_var.get() not in active_players:
                self.transfer_unit_var.set(active_players[0] if active_players else "")
            self.ttk.Combobox(dispatch, textvariable=self.transfer_unit_var,
                              values=active_players, state="readonly", width=15).pack(
                                  side="left", padx=4)
            self.ttk.Combobox(dispatch, textvariable=self.destination_var,
                              values=list(fronts.missions), state="readonly", width=13).pack(
                                  side="left", padx=4)
            for name, variable in (("X", self.transfer_x_var),
                                   ("Y", self.transfer_y_var)):
                self.ttk.Label(dispatch, text=name,
                               style="Castle.TLabel").pack(side="left")
                self.ttk.Entry(dispatch, textvariable=variable, width=3).pack(
                    side="left", padx=3)
            self._button(dispatch, "Expédier le convoi", lambda: self._change(
                lambda: controller.transfer(
                    self.destination_var.get(), self.transfer_unit_var.get(),
                    [int(self.transfer_x_var.get()), int(self.transfer_y_var.get())]))
                         ).pack(side="left", padx=4)
            if convoy_ids:
                details = [f"{c['id']}: {c['from']} → {c['to']} / "
                           + ("intercepté" if c.get("stranded") else "en route")
                           for c in fronts.logistics.in_transit]
                self.ttk.Label(convoy_frame, text="   |   ".join(details),
                               wraplength=1100).pack(anchor="w", pady=3)

        if fronts.campaign is not None:
            self.ttk.Label(self.view, text="Accès au final : " +
                           str(fronts.campaign.state(fronts)["required"]),
                           style="Castle.TLabel", wraplength=1120).pack(
                               anchor="w", pady=5)
        events = self.tk.Text(self.view, height=7, wrap="word",
                              fg="#e9f2fc", bg="#182a40", relief="flat")
        events.pack(fill="both", expand=True, pady=8)
        events.insert("1.0", "\n".join(
            str(e) for e in frame.events[-15:]))
        events.configure(state="disabled")
        self._footer()

    def epilogue_screen(self):
        self.narrative_audio.music_for("ending_" +
                                      str(self.controller.session.ending), "epilogue")
        self._clear()
        game = self.controller.session
        self._heading("Siège terminé — " + game.ending,
                      "Épilogue déterminé par les résultats tactiques et la politique du siège.")
        fronts = game.fronts
        final = (fronts.campaign.final if fronts.campaign is not None
                 else next(iter(self.controller.blueprint["fronts"])))
        mission = fronts.missions[final]
        # StoryBook.after_mission is an after-*victory* hook. Defeat never
        # borrows a victorious epilogue or fires any story choice effects.
        scene_id = (self.authored_project.story.get("after_mission", {}).get(mission)
                    if game.ending == "victory" else None)
        scene = self._authored_scene(scene_id) if scene_id else None
        if scene is not None:
            self.ttk.Label(self.view, text=scene["title"] + " — " + scene["speaker"],
                           style="Castle.TLabel",
                           font=("TkDefaultFont", 15, "bold")).pack(anchor="w", pady=7)
            narrative = self.tk.Text(self.view, height=7, wrap="word",
                                     fg="#e9f2fc", bg="#182a40", relief="flat")
            narrative.pack(fill="x", pady=5)
            narrative.insert("1.0", scene["text"])
            narrative.configure(state="disabled")
        log = self.tk.Text(self.view, height=12, wrap="word",
                           fg="#e9f2fc", bg="#182a40", relief="flat")
        log.pack(fill="both", expand=True, pady=10)
        log.insert("1.0", "\n".join(
            f"{name}: {row['status']}" for name, row
            in sorted(fronts.timeline.fronts.items())))
        log.configure(state="disabled")
        self._footer()


def launch(content, blueprint, project, project_path, slot=1, *,
           rules=None, master=None, controller=None):
    app = StudioSiegePlayerApplication(
        content, blueprint, project, project_path, slot,
        rules=rules, master=master, controller=controller)
    if master is None:
        app.run()
    return app
