"""Graphical Player for *any* validated Siege Studio blueprint (2.8.2).

Uses the 2.8.1 tactical Canvas unchanged; all bespoke logic is presentation
and all user intents are delegated to authored_siege_player controller.
"""
from pathlib import Path

from .authored_siege_player import AuthoredSiegeController
from .castle_player_app import CastlePlayerApplication
from .presentation import strategy_frame


class StudioSiegePlayerApplication(CastlePlayerApplication):
    def __init__(self, content, blueprint, project, project_path, slot=1,
                 *, rules=None, master=None, controller=None):
        self.authored_project = project
        self.intro_seen = False
        managed = controller or AuthoredSiegeController(
            content, blueprint, project_path, slot, rules=rules)
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

    def _authored_scene(self, scene_id):
        return next((scene for scene in self.authored_project.story.get("scenes", [])
                     if scene["id"] == scene_id), None)

    def show(self):
        if self.controller.session is not None and not self.intro_seen:
            campaign_id = self.controller.blueprint["campaign_id"]
            entry_id = self.authored_project.story.get("entry_scenes", {}).get(campaign_id)
            if entry_id and not self.controller.session.fronts.history:
                scene = self._authored_scene(entry_id)
                if scene is not None:
                    self._scene_screen(scene, self._acknowledge_intro, "Entrer en bataille")
                    return
            self.intro_seen = True
        super().show()

    def _acknowledge_intro(self):
        self.intro_seen = True
        self.show()

    def _scene_screen(self, scene, on_continue, button_text):
        self._clear()
        self._heading(scene["title"], scene["speaker"])
        text = self.tk.Text(self.view, wrap="word", height=16,
                            fg="#e9f2fc", bg="#182a40", relief="flat")
        text.pack(fill="both", expand=True, pady=12, padx=12)
        text.insert("1.0", scene["text"])
        text.configure(state="disabled")
        self._button(self.view, button_text, on_continue).pack(pady=12)
        self.ttk.Label(self.view, text="Transition narrative : aperçu de la scène "
                       "du Studio. Les choix narratifs et leurs effets sont "
                       "jouables dans la campagne principale, pas dans ce mode siège.",
                       style="Castle.TLabel", wraplength=1050).pack(anchor="w")
        self._footer()

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
        self._clear()
        game = self.controller.session
        self._heading("Siège terminé — " + game.ending,
                      "Épilogue déterminé par les résultats tactiques et la politique du siège.")
        fronts = game.fronts
        final = (fronts.campaign.final if fronts.campaign is not None
                 else next(iter(self.controller.blueprint["fronts"])))
        mission = fronts.missions[final]
        scene_id = self.authored_project.story.get("after_mission", {}).get(mission)
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
