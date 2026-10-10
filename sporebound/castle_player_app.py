"""Tk castle player (2.8.1): preparation, tactical map, strategy and epilogue.

Shares battle_frame, strategy_frame and CanvasRenderer with the ordinary Player.
Only CastlePlayerController can mutate the replay-validated campaign.
"""
from pathlib import Path

from .castle_player_controller import CastlePlayerController
from .model import RuleError
from .presentation import Camera, battle_frame, strategy_frame
from .siege import available_operations
from .tk_renderer import CanvasRenderer


class CastlePlayerApplication:
    def __init__(self, content, blueprint, save_path, *, rules, master=None):
        import tkinter as tk
        from tkinter import ttk, messagebox

        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.controller = CastlePlayerController(content, blueprint, save_path, rules=rules)
        self.root = tk.Toplevel(master) if master is not None else tk.Tk()
        self.root.title("Sporebound — Siège du château 2.8")
        self.root.geometry("1170x820")
        self.root.minsize(860, 580)
        self.root.configure(background="#101a2b")
        style = ttk.Style(self.root)
        style.configure("Castle.TFrame", background="#101a2b")
        style.configure("Castle.TLabel", background="#101a2b", foreground="#e9f2fc")
        style.configure("Castle.TLabelframe", background="#101a2b")
        style.configure("Castle.TLabelframe.Label", foreground="#e9f2fc", background="#101a2b")
        self.view = ttk.Frame(self.root, style="Castle.TFrame", padding=15)
        self.view.pack(fill="both", expand=True)
        self.page = "strategy"
        self.front_var = tk.StringVar()
        self.doctrine_var = tk.StringVar(value="hold")
        self.route_var = tk.StringVar(value="breach")
        self.approach_var = tk.StringVar(value="ram")
        self.hero_var = tk.StringVar(value="captain")
        self.job_var = tk.StringVar(value="brave")
        self.item_var = tk.StringVar()
        self.unit_var = tk.StringVar()
        self.action_var = tk.StringVar(value="move")
        self.selection = (0, 0)
        self.facing_var = tk.StringVar(value="south")
        self.camera = Camera(49, 18, 16)
        self.canvas = None
        self.renderer = None
        self.info = None
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.title_screen()

    def _clear(self):
        if self.renderer is not None:
            self.renderer.dispose()
            self.renderer = None
        for child in self.view.winfo_children():
            child.destroy()
        self.canvas = None
        self.info = None

    def _heading(self, title, subtitle=""):
        self.ttk.Label(self.view, text=title, style="Castle.TLabel",
                       font=("TkDefaultFont", 23, "bold")).pack(anchor="w", pady=(1, 9))
        if subtitle:
            self.ttk.Label(self.view, text=subtitle, style="Castle.TLabel",
                           wraplength=1050).pack(anchor="w", pady=(0, 12))

    def _button(self, parent, label, fn):
        return self.ttk.Button(parent, text=label, command=lambda: self._safe(fn))

    def _safe(self, callback):
        try:
            return callback()
        except (RuleError, ValueError, TypeError, OSError,
                KeyError, IndexError, StopIteration) as error:
            self.messagebox.showerror("Action refusée", str(error), parent=self.root)

    def _change(self, callback, *, page=None):
        callback()
        if page is not None:
            self.page = page
        self.show()

    def title_screen(self):
        self._clear()
        self._heading("L'assaut du château",
                      "Une campagne tactique complète — 5 approches, fronts simultanés, diplomatie et boss à phases")
        panel = self.ttk.LabelFrame(self.view, text="Campagne 2.8", padding=20)
        panel.pack(fill="x", padx=65, pady=20)
        self.ttk.Label(panel, text="Sauvegarde : " + str(self.controller.save_path),
                       wraplength=880).pack(anchor="w", pady=(5, 15))
        self._button(panel, "Nouvelle campagne", self._new_game).pack(fill="x", pady=6)
        if self.controller.save_path.exists():
            self._button(panel, "Continuer la campagne", lambda: self._change(
                self.controller.continue_game)).pack(fill="x", pady=6)
        self._button(panel, "Quitter", self.close).pack(fill="x", pady=6)

    def _new_game(self):
        existing = self.controller.save_path.exists()
        if existing and not self.messagebox.askyesno(
                "Remplacer la sauvegarde",
                "Une partie existe déjà. Voulez-vous l'écraser ?", parent=self.root):
            return
        self._change(lambda: self.controller.new_game(overwrite=existing))

    def show(self):
        game = self.controller.session
        if game is None:
            self.title_screen()
        elif game.ending is not None:
            self.epilogue_screen()
        elif game.fronts is None:
            self.preparation_screen()
        elif self.page == "battle":
            self.battle_screen()
        else:
            self.strategy_screen()

    def _footer(self):
        footer = self.ttk.Frame(self.view)
        footer.pack(side="bottom", fill="x", pady=(9, 0))
        self._button(footer, "Sauvegarder", self.controller.save).pack(side="left", padx=5)
        self._button(footer, "Menu", self.title_screen).pack(side="left", padx=5)
        self._button(footer, "Fermer", self.close).pack(side="right", padx=5)

    def preparation_screen(self):
        self._clear()
        game = self.controller.session
        state = game.state()
        self._heading("Préparation de l'assaut",
                      f"Trésor : {state['gold']} pièces — Sélectionner les héros, classes et équipements avant le déploiement")
        panel = self.ttk.LabelFrame(self.view, text="Escouade", padding=12)
        panel.pack(fill="x", pady=5)
        members = [(uid, self.tk.BooleanVar(value=uid in game.squad))
                   for uid in game.squad_ids]
        for uid, var in members:
            self.ttk.Checkbutton(panel, text=uid, variable=var).pack(side="left", padx=14)
        self._button(panel, "Valider l'escouade", lambda: self._change(
            lambda: self.controller.select_squad(
                [uid for uid, var in members if var.get()]))).pack(side="right")

        setup = self.ttk.LabelFrame(self.view, text="Classes & équipement", padding=12)
        setup.pack(fill="x", pady=8)
        self.ttk.Label(setup, text="Héros").grid(row=0, column=0, sticky="w")
        self.ttk.Combobox(setup, textvariable=self.hero_var, state="readonly",
                          values=game.squad_ids, width=18).grid(row=0, column=1, padx=7)
        self.ttk.Label(setup, text="Classe").grid(row=0, column=2, sticky="w")
        self.ttk.Combobox(setup, textvariable=self.job_var, state="readonly",
                          values=sorted(game.content.jobs), width=22).grid(row=0, column=3, padx=7)
        self._button(setup, "Choisir la classe", lambda: self._change(
            lambda: self.controller.set_job(self.hero_var.get(),
                                           self.job_var.get()))).grid(row=0, column=4, padx=8)
        items = list(sorted(game.content.equipment))
        if items and self.item_var.get() not in items:
            self.item_var.set(items[0])
        self.ttk.Label(setup, text="Équipement").grid(row=1, column=0, sticky="w", pady=14)
        self.ttk.Combobox(setup, textvariable=self.item_var, state="readonly",
                          values=items, width=23).grid(row=1, column=1, columnspan=2)
        self._button(setup, "Acheter", lambda: self._change(
            lambda: self.controller.buy(self.item_var.get()))).grid(row=1, column=3, padx=8)
        self._button(setup, "Équiper", lambda: self._change(
            lambda: self.controller.equip(self.hero_var.get(), self.item_var.get()))
                     ).grid(row=1, column=4, padx=8)
        self.ttk.Label(self.view, style="Castle.TLabel",
                       text="Sac : " + str(state["inventory"])).pack(anchor="w", pady=6)
        for uid, info in state["heroes"].items():
            self.ttk.Label(self.view, style="Castle.TLabel",
                           text=f"{uid} — {info['job']} — {info['equipment']}"
                           ).pack(anchor="w", pady=3)

        approach = self.ttk.LabelFrame(self.view, text="Plan d'approche", padding=15)
        approach.pack(fill="x", pady=16)
        descriptions = {
            "ram": "Bélier, porte et défenseurs",
            "infiltration": "Grappin, remparts et herse",
            "tunnels": "Souterrains : victoire tactique nécessaire",
            "negotiation": "Ravitaillement et preuve diplomatique",
            "direct": "Assaut coûteux en provisions et combattants",
        }
        self.ttk.Combobox(approach, textvariable=self.approach_var, state="readonly",
                          values=tuple(descriptions), width=22).pack(side="left", padx=5)
        self.ttk.Label(approach, textvariable=self.approach_var).pack_forget()
        self._button(approach, "Déployer et commencer", lambda: self._change(
            lambda: self.controller.start(self.approach_var.get()),
            page="battle")).pack(side="left", padx=20)
        self.ttk.Label(self.view, style="Castle.TLabel",
                       text="Les autres fronts restent accessibles après le départ. "
                            "Une négociation nécessite une action tactique authentifiée.").pack(
                                anchor="w", pady=3)
        self._footer()

    def strategy_screen(self):
        self.page = "strategy"
        self._clear()
        game = self.controller.session
        state = game.state()
        front_state = strategy_frame(game.fronts)
        self._heading("Commandement — Siège du château",
                      f"Tour stratégique : {front_state.turn}   |   Approche : {game.approach}"
                      f"   |   Provisions : {state['supplies']['player']}"
                      f"   |   Trône : {state['campaign']['status']}")
        nav = self.ttk.Frame(self.view)
        nav.pack(fill="x", pady=6)
        self._button(nav, "Carte tactique", self.battle_screen).pack(side="left", padx=5)
        self._button(nav, "Avancer la timeline", lambda: self._change(
            self.controller.advance)).pack(side="left", padx=5)
        self._button(nav, "Abandonner la campagne", self._concede).pack(side="right", padx=5)
        columns = ("mission", "status", "doctrine", "strength", "opposition")
        tree = self.ttk.Treeview(self.view, columns=columns, show="headings", height=7)
        for name, width in zip(columns, (220, 115, 105, 85, 95)):
            tree.heading(name, text=name.title())
            tree.column(name, width=width, anchor="center")
        for front in front_state.fronts:
            tree.insert("", "end", iid=front.id,
                        values=(front.id, front.status, front.doctrine,
                                front.strength, front.opposition))
        self.front_var.set(front_state.focused)
        tree.selection_set(front_state.focused)
        tree.bind("<<TreeviewSelect>>",
                  lambda _: self.front_var.set(tree.selection()[0])
                  if tree.selection() else None)
        tree.pack(fill="x", expand=False, pady=8)

        commands = self.ttk.Frame(self.view)
        commands.pack(fill="x", pady=8)
        self._button(commands, "Changer de front", lambda: self._change(
            lambda: self.controller.switch(self.front_var.get()),
            page="battle")).pack(side="left", padx=4)
        self.ttk.Combobox(commands, state="readonly", textvariable=self.doctrine_var,
                          values=("hold", "assault", "delay", "retreat"),
                          width=11).pack(side="left", padx=5)
        self._button(commands, "Doctrine", lambda: self._change(
            lambda: self.controller.doctrine(self.front_var.get(),
                                            self.doctrine_var.get()))).pack(side="left", padx=4)
        self.ttk.Combobox(commands, state="readonly", textvariable=self.route_var,
                          values=("breach", "tunnels", "direct"), width=10).pack(
                              side="left", padx=5)
        self._button(commands, "Route alternative", lambda: self._change(
            lambda: self.controller.route(self.route_var.get()))).pack(side="left", padx=4)

        diplomacy = self.ttk.Frame(self.view)
        diplomacy.pack(fill="x", pady=8)
        self._button(diplomacy, "Négocier la porte", lambda: self._change(
            self.controller.negotiate)).pack(side="left", padx=5)
        self._button(diplomacy, "Victoire partielle dans la cour",
                     lambda: self._change(self.controller.partial)).pack(side="left", padx=5)
        self._button(diplomacy, "Retraite du secteur", lambda: self._change(
            lambda: self.controller.withdraw(self.front_var.get()))).pack(side="left", padx=5)

        self.ttk.Label(self.view, style="Castle.TLabel",
                       text="Conditions du trône : " + str(state["campaign"]["required"])
                       ).pack(anchor="w", pady=5)
        log = self.tk.Text(self.view, height=11, wrap="word", fg="#e9f2fc",
                           bg="#182a40", relief="flat")
        log.pack(fill="both", expand=True, pady=6)
        log.insert("1.0", "\n".join(str(e) for e in front_state.events[-25:]))
        log.configure(state="disabled")
        self._footer()

    def _concede(self):
        if self.messagebox.askyesno(
                "Défaite", "Abandonner définitivement cette campagne ?",
                parent=self.root):
            self._change(self.controller.concede)

    def battle_screen(self):
        self.page = "battle"
        self._clear()
        game = self.controller.session
        battle = game.fronts.active
        self._heading(battle.mission.name,
                      f"Secteur : {game.fronts.timeline.focused}  |  Tick : {battle.tick}"
                      + (f"  |  Résultat : {battle.result}" if battle.result
                         else "  |  Déploiement" if battle.deploying
                         else f"  |  Tour : {battle.active_id}"))
        nav = self.ttk.Frame(self.view)
        nav.pack(fill="x", pady=4)
        self._button(nav, "Carte des fronts / Diplomatie", self.strategy_screen).pack(
            side="left", padx=5)
        self._button(nav, "Sauvegarder", self.controller.save).pack(side="right", padx=5)
        bar = self.ttk.Frame(self.view)
        bar.pack(fill="x", pady=9)
        if battle.result is not None:
            self.ttk.Label(bar, text="Front terminé — retour à la stratégie").pack(side="left")
        elif battle.deploying:
            players = [u.id for u in battle.units if u.team == "player" and u.alive]
            if self.unit_var.get() not in players:
                self.unit_var.set(players[0] if players else "")
            self.ttk.Combobox(bar, state="readonly", textvariable=self.unit_var,
                              values=players, width=16).pack(side="left", padx=4)
            self._button(bar, "Déployer sur case", lambda: self._tactical(
                {"kind": "deploy", "unit": self.unit_var.get(),
                 "cell": list(self.selection), "facing": self._facing()})).pack(
                     side="left", padx=4)
            self._button(bar, "Début du combat", lambda: self._tactical(
                {"kind": "start_battle"})).pack(side="left", padx=5)
        elif battle.active is not None and battle.active.team == "enemy":
            self._button(bar, "Tour IA", lambda: self._change(
                self.controller.ai_turn)).pack(side="left", padx=4)
        elif battle.active is not None:
            options = ["move", "attack", *battle.active.skills,
                       "item:potion", "item:ether", "item:phoenix",
                       *["object:" + o["id"] for o in battle.mission.objects],
                       *available_operations(battle, battle.active), "end"]
            if self.action_var.get() not in options:
                self.action_var.set(options[0])
            self.ttk.Combobox(bar, state="readonly", textvariable=self.action_var,
                              values=options, width=25).pack(side="left", padx=5)
            self.ttk.Combobox(bar, state="readonly", textvariable=self.facing_var,
                              values=("north", "south", "east", "west"),
                              width=9).pack(side="left", padx=5)
            self._button(bar, "Exécuter", self._execute).pack(side="left", padx=5)
            self._button(bar, "Fin du tour", lambda: self._tactical(
                {"kind": "end", "facing": self._facing()})).pack(side="left", padx=5)

        body = self.ttk.Frame(self.view)
        body.pack(fill="both", expand=True, pady=6)
        self.canvas = self.tk.Canvas(body, background="#172638", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.renderer = CanvasRenderer(self.canvas)
        self.canvas.bind("<Button-1>", self._select_cell)
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<Button-4>", lambda _: self._zoom_step(1))
        self.canvas.bind("<Button-5>", lambda _: self._zoom_step(-1))
        self.canvas.bind("<KeyPress-Left>", lambda _: self._select_delta(-1, 0))
        self.canvas.bind("<KeyPress-Right>", lambda _: self._select_delta(1, 0))
        self.canvas.bind("<KeyPress-Up>", lambda _: self._select_delta(0, -1))
        self.canvas.bind("<KeyPress-Down>", lambda _: self._select_delta(0, 1))
        self.canvas.bind("<Return>", lambda _: self._safe(self._execute))
        self.canvas.focus_set()
        self.info = self.tk.Text(body, width=38, wrap="word", fg="#e9f2fc",
                                 bg="#182a40", relief="flat")
        self.info.pack(side="right", fill="y", padx=(9, 0))
        self._redraw()
        self._button(self.view, "Retour aux fronts", self.strategy_screen).pack(
            anchor="e", pady=6)

    def _facing(self):
        return {"north": [0, -1], "south": [0, 1],
                "east": [1, 0], "west": [-1, 0]}[self.facing_var.get()]

    def _tactical(self, command):
        self._change(lambda: self.controller.execute(command))

    def _execute(self):
        action = self.action_var.get()
        if action == "move":
            cmd = {"kind": "move", "cell": list(self.selection)}
        elif action == "end":
            cmd = {"kind": "end", "facing": self._facing()}
        elif action.startswith("item:"):
            cmd = {"kind": "item", "item": action[5:], "cell": list(self.selection)}
        elif action.startswith("object:"):
            cmd = {"kind": "interact", "object": action[7:]}
        elif action.startswith("siege-attack:"):
            cmd = {"kind": "siege_attack", "object": action[len("siege-attack:"):]}
        elif action.startswith("repair-siege:"):
            cmd = {"kind": "repair_siege", "object": action[len("repair-siege:"):]}
        else:
            cmd = {"kind": "act", "skill": action, "cell": list(self.selection)}
        self._tactical(cmd)

    def _redraw(self):
        if self.canvas is None:
            return
        battle = self.controller.session.fronts.active
        skill = self.action_var.get()
        if skill != "attack" and (battle.active is None or
                                  skill not in battle.active.skills):
            skill = None
        frame = battle_frame(battle, self.selection, skill)
        self.renderer.draw(frame, self.camera)
        detail = ["Cellule : " + str(self.selection), "", "Combattants"]
        detail.extend(f"{u.name} ({u.team}) — PV {u.hp}/{u.max_hp}"
                      for u in frame.actors)
        if frame.forecast:
            detail += ["", "Prévisions", *(str(row) for row in frame.forecast)]
        detail += ["", "Événements", *(str(row) for row in frame.events[-15:])]
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(detail))
        self.info.configure(state="disabled")

    def _select_cell(self, event):
        battle = self.controller.session.fronts.active
        point = self.camera.screen_to_cell(event.x, event.y)
        if battle.board.contains(point):
            self.selection = point
            self._redraw()

    def _select_delta(self, dx, dy):
        battle = self.controller.session.fronts.active
        point = (self.selection[0] + dx, self.selection[1] + dy)
        if battle.board.contains(point):
            self.selection = point
            self._redraw()

    def _zoom(self, event):
        self._zoom_step(1 if event.delta > 0 else -1, (event.x, event.y))

    def _zoom_step(self, delta, anchor=(250, 220)):
        self.camera = self.camera.zoomed(delta, anchor)
        self._redraw()

    def epilogue_screen(self):
        self._clear()
        game = self.controller.session
        labels = {"victory": "Victoire", "accord": "Accord",
                  "defeat": "Défaite"}
        self._heading("Épilogue — " + labels[game.ending],
                      "Le résultat provient des batailles, de la stratégie et des décisions authentifiées.")
        state = game.state()
        text = self.tk.Text(self.view, height=17, fg="#e9f2fc", bg="#182a40",
                            wrap="word", relief="flat")
        text.pack(fill="both", expand=True, padx=20, pady=20)
        rows = [f"Approche : {game.approach}",
                f"Tour stratégique : {state['strategic_turn']}",
                f"Route : {state['campaign'].get('route')}",
                "Secteurs :"]
        rows += [f"  {front}: {row['status']}" for front, row in state["fronts"].items()]
        rows += ["", f"PV du boss / phases : {state['boss_phase_triggered']}",
                 f"Liens tactiques : {', '.join(state['links'])}",
                 "Fin archivée dans un journal replayable."]
        text.insert("1.0", "\n".join(rows))
        text.configure(state="disabled")
        self._button(self.view, "Nouvelle campagne", self._new_game).pack(
            anchor="center", pady=8)
        self._footer()

    def close(self):
        if self.controller.session is not None:
            try:
                self.controller.save()
            except (OSError, RuleError, ValueError) as exc:
                if not self.messagebox.askyesno(
                        "Sauvegarde impossible",
                        str(exc) + "\nQuitter malgré l'échec ?", parent=self.root):
                    return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def launch(content, blueprint, save_path, *, rules, master=None):
    app = CastlePlayerApplication(content, blueprint, save_path,
                                  rules=rules, master=master)
    if master is None:
        app.run()
    return app
