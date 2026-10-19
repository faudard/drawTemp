"""Headless R12 Player flow on top of the canonical R1 Simulation API.

All commands, previews, story choices and persistence run through Simulation.
This module never imports Qt or Tk and never edits the GameSession directly.
"""
from pathlib import Path

from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from drawtemp.sdk.slots import PlayerSlotStore
from drawtemp.core import RuleError
from drawtemp.player.save_manager import SaveManager
from drawtemp.player.preferences import PlayerPreferences
from sporebound.cinematic_transport import CinematicTransport
from drawtemp.cinematics.projection import frame_payload


class PlayerController:
    """Small, deterministic state machine for the standalone Qt Player."""

    def __init__(self, content, project, campaign_id, save_dir, *, seed=17):
        if project.campaign(campaign_id) is None:
            raise ValueError("Unknown campaign: " + campaign_id)
        self.content, self.project = content, project
        self.campaign_id, self.seed = campaign_id, seed
        self.save_dir = Path(save_dir)
        self.saves = SaveManager(self.save_dir, content, project, campaign_id)
        self.autosave_warning = ""
        self._autosaved_key = None
        self.preferences = PlayerPreferences(self.save_dir / 'player-preferences.json')
        self.session = None
        self.show_title = True
        self.selected = [0, 0]
        self.message = self.preferences.warning
        self.forecast = ""
        self.inspected_skill = "attack"
        self._cinematic_clip = None
        self._cinematic_transport = None
        self._cinematic_registry = None
        # R18.C: ephemeral UI confirmation; never stored in save/replay.
        self._pending_target = None

    def _path(self, slot):
        if type(slot) is not int or not 1 <= slot <= self.project.save_slots:
            raise ValueError("Invalid save slot")
        return self.save_dir / ("slot_" + str(slot) + ".json")

    def slots(self):
        return [slot for slot in range(1, self.project.save_slots + 1)
                if self._path(slot).is_file()]

    def backups(self):
        return [slot for slot in range(1, self.project.save_slots + 1)
                if self._path(slot).with_suffix(".json.bak").is_file()]

    def _store(self, slot):
        return PlayerSlotStore(self._path(slot), self.content, self.project,
                               campaign_id=self.campaign_id)

    def inspect_slot(self, slot=1):
        return self._store(slot).inspect()

    def _activate_save(self, loaded, message, *, source=None):
        # No state is touched until the verified GameSession has been loaded.
        self.session = loaded
        self._cinematic_clip = None
        self._cinematic_transport = None
        self._pending_target = None
        self.show_title = False
        self.selected = [0, 0]
        self.inspected_skill = "attack"
        self.forecast = ""
        self.message = message
        self.autosave_warning = ""
        self._autosaved_key = ((id(loaded), loaded.snapshot().revision)
                               if source == "auto" else None)
        return self.state()

    def restore_backup(self, slot=1, *, expected_fingerprints=None):
        verified = self._store(slot).restore_backup(
            expected_fingerprints=expected_fingerprints)
        return self._activate_save(verified, "Sauvegarde de secours restaurée")

    def restore_autosave_backup(self, *, expected_fingerprints=None):
        verified = self.saves.restore_autosave_backup(
            expected_fingerprints=expected_fingerprints)
        return self._activate_save(verified, "Autosauvegarde de secours restaurée",
                                   source="auto")

    def load_autosave(self):
        loaded = self.saves.load_autosave()
        return self._activate_save(loaded, "Autosauvegarde rechargée", source="auto")

    def continue_game(self):
        loaded, source = self.saves.resume()
        title = ("autosauvegarde" if source == "auto"
                 else "emplacement " + str(source))
        return self._activate_save(loaded, "Reprise depuis " + title,
                                   source=source)

    def _checkpoint(self):
        """Auto-save every successfully committed revision, not UI selection.

        Saving can fail after a successful action. Never roll back the engine
        or silently overwrite corrupt autosaves; expose a persistent warning.
        """
        if self.session is None:
            return
        key = (id(self.session), self.session.snapshot().revision)
        if self._autosaved_key == key:
            return
        try:
            self.saves.autosave(self.session)
        except (RuleError, OSError) as exc:
            self.autosave_warning = ("Autosauvegarde impossible : " + str(exc) +
                                     " — sauvegardez manuellement ou restaurez le secours")
        else:
            self.autosave_warning = ""
            self._autosaved_key = key

    def new_game(self):
        self.session = Simulation.new(self.content, self.project, self.campaign_id,
                                      seed=self.seed)
        self._cinematic_clip = None
        self._cinematic_transport = None
        self._pending_target = None
        self.show_title = False
        self.message = "Le voyage de Jeanne commence."
        self.forecast = ""
        self.inspected_skill = "attack"
        self.selected = [0, 0]
        self._autosaved_key = None
        self._checkpoint()
        return self.state()

    def load(self, slot=1):
        path = self._path(slot)
        # Assignment only after successful verification: preserve the live game
        # and the saved file when a checksum/project/rules mismatch is found.
        loaded = self._store(slot).load()
        return self._activate_save(loaded, "Partie rechargée.")
    def save(self, slot=1):
        if self.session is None:
            raise ValueError("No game to save")
        self._store(slot).save(self.session)
        self.message = "Sauvegarde dans l'emplacement " + str(slot)
        return self.state()

    def title(self):
        self.show_title = True
        self._cinematic_clip = None
        self._cinematic_transport = None
        self._pending_target = None
        self.forecast = ""
        return self.state()

    def choose(self, choice_id):
        state = self._current()
        if not state.scene:
            raise ValueError("No dialogue is pending")
        candidates = {choice["id"] for choice in thaw(self.session.choices())}
        if choice_id not in candidates:
            raise ValueError("Unavailable story choice")
        if state.battle is not None:
            self.session.choose_tactical_story_option(choice_id,
                            expected_revision=state.revision)
        else:
            self.session.choose_story_option(choice_id,
                            expected_revision=state.revision)
        return self._changed()

    def start_mission(self, mission_id):
        self._require_cinematic_completed()
        state = self._current()
        if state.mode != "campaign" or state.scene is not None:
            raise ValueError("Resolve the narrative before starting a mission")
        if mission_id not in state.missions:
            raise ValueError("Mission is locked")
        self.session.start_mission(mission_id, expected_revision=state.revision)
        self.selected = [0, 0]
        self.inspected_skill = "attack"
        return self._changed()

    def explore_move(self, dx, dy):
        self._require_cinematic_completed()
        state = self._current()
        if not state.exploration or state.exploration["completed"]:
            raise ValueError("Exploration is unavailable")
        self.session.explore_move(dx, dy, expected_revision=state.revision)
        return self._changed()

    def explore_interact(self, point_id):
        self._require_cinematic_completed()
        state = self._current()
        if not state.exploration or state.exploration["completed"]:
            raise ValueError("Exploration is unavailable")
        stage = thaw(state.exploration)
        point = next((p for p in stage["interactions"] if p["id"] == point_id), None)
        if point is None:
            raise ValueError("Unknown exploration point")
        self.session.explore_interact(point_id, expected_revision=state.revision)
        self.message = point["title"] + " — " + point["text"]
        return self._changed(keep_message=True)

    def explore_actor(self, actor_id, action="talk"):
        self._require_cinematic_completed()
        state = self._current()
        self.session.explore_actor(actor_id, action, expected_revision=state.revision)
        return self._changed()

    def equip_hero(self, hero_id, item_id):
        state = self._current()
        self.session.equip_hero(hero_id, item_id, expected_revision=state.revision)
        return self._changed()

    def unequip_hero(self, hero_id, slot):
        state = self._current()
        self.session.unequip_hero(hero_id, slot, expected_revision=state.revision)
        return self._changed()

    def select_cell(self, x, y):
        state = self._current()
        battle = state.battle
        if battle is None:
            raise ValueError("No tactical battlefield")
        self.selected = [
            max(0, min(battle["width"] - 1, int(x))),
            max(0, min(battle["height"] - 1, int(y))),
        ]
        self._pending_target = None
        self.forecast = ""
        return self.state()

    def request_target(self, kind, skill_id=""):
        """Stage a target action, showing canonical forecasts without RNG use.

        Selection and request cannot change combat revision, replay or saves.
        Confirming rechecks the exact active unit/revision/cell tuple.
        Legacy headless command() remains intentionally available to scripts.
        """
        if kind not in ("move", "attack", "skill"):
            raise ValueError("Unknown target action")
        view = self.state()
        if view["screen"] != "battle" or view["battle"].get("deploying"):
            raise ValueError("Combat non prêt pour une action ciblée")
        battle = view["battle"]
        active = next((unit for unit in battle.get("units", [])
                       if unit["id"] == battle.get("active")), None)
        if active is None or active.get("team") != "player":
            raise ValueError("Ce n'est pas le tour d'une unité alliée")
        if kind == "skill":
            if (not isinstance(skill_id, str) or not skill_id or
                    skill_id not in active.get("skills", ())):
                raise ValueError("Compétence indisponible")
        elif skill_id:
            raise ValueError("Compétence inattendue pour cette action")
        focus = view["tactical"].get("focus") or {}
        if kind == "move":
            move = focus.get("move")
            if not move:
                raise ValueError("Déplacement indisponible vers cette case")
            details = ("Coût " + str(move["cost"]) + " · " +
                       str(len(move.get("risks") or [])) +
                       " risque(s) possible(s), non garanti(s)")
        else:
            # Engine validation (range, LOS and cost), without sampling RNG.
            # The inspector may currently highlight a *different* skill.
            effective_skill = "attack" if kind == "attack" else skill_id
            projected = self.session.tactical_presentation(
                self.selected, effective_skill, expected_revision=view["revision"])
            focus = thaw(projected).get("focus") or {}
            if not focus.get("can_target"):
                raise ValueError(focus.get("error") or "Cible indisponible")
            forecast = focus.get("forecast") or []
            details = (str(len(forecast)) +
                       " effet(s) prévus (non garantis)")
        self._pending_target = {
            "kind": kind, "skill": skill_id, "cell": list(self.selected),
            "revision": view["revision"], "active": battle["active"],
            "details": details,
        }
        return self.state()

    def cancel_target(self):
        """Dismiss a staged action, preserving the last engine checkpoint."""
        self._pending_target = None
        return self.state()

    def confirm_target(self):
        pending = self._pending_target
        if not pending:
            raise ValueError("Aucune action ciblée en attente")
        # Discard the request before checking: stale actions must not be replayed.
        self._pending_target = None
        view = self.state()
        if (view["screen"] != "battle" or
                view["revision"] != pending["revision"] or
                view["selected"] != pending["cell"] or
                view["battle"].get("active") != pending["active"]):
            raise ValueError("Cible ou tour modifié : choisissez l'action à nouveau")
        if pending["kind"] == "skill":
            return self.use_skill(pending["skill"])
        return self.command(pending["kind"])

    def command(self, kind):
        state = self._current()
        battle = state.battle
        if battle is None or battle["result"]:
            raise ValueError("Battle does not accept commands")
        if kind == "deploy":
            command = {"kind": "start_battle"}
        elif kind == "move":
            command = {"kind": "move", "cell": list(self.selected)}
        elif kind == "attack":
            command = {"kind": "act", "skill": "attack", "cell": list(self.selected)}
        elif kind == "end":
            command = {"kind": "end", "facing": [0, 1]}
        else:
            raise ValueError("Unknown tactical command")
        self.session.execute(command, expected_revision=state.revision)
        return self._changed()

    def use_skill(self, skill_id):
        state = self._current()
        battle = state.battle
        if battle is None or battle["result"]:
            raise ValueError("No active combat")
        active = next((u for u in battle["units"]
                       if u["id"] == battle["active"]), None)
        if (active is None or active["team"] != "player" or
                skill_id not in active.get("skills", ())):
            raise ValueError("Skill is unavailable to the active unit")
        self.session.execute({"kind": "act", "skill": skill_id,
                              "cell": list(self.selected)},
                             expected_revision=state.revision)
        return self._changed()

    def use_item(self, item_id):
        state = self._current()
        battle = state.battle
        if battle is None or battle["result"]:
            raise ValueError("No active combat")
        items = battle["inventory"].get("player", {})
        if item_id not in items or items[item_id] < 1:
            raise ValueError("Item unavailable")
        self.session.execute({"kind": "item", "item": item_id,
                              "cell": list(self.selected)},
                             expected_revision=state.revision)
        return self._changed()

    def interact_object(self, object_id):
        state = self._current()
        battle = state.battle
        if battle is None or battle["result"]:
            raise ValueError("No active combat")
        if object_id not in {obj["id"] for obj in battle["objects"]}:
            raise ValueError("Unknown tactical object")
        self.session.execute({"kind": "interact", "object": object_id},
                             expected_revision=state.revision)
        return self._changed()

    def inspect_skill(self, skill_id):
        state = self._current()
        battle = state.battle
        if not battle or battle["result"]:
            raise ValueError("No active battle")
        active = next((unit for unit in battle["units"]
                       if unit["id"] == battle["active"]), None)
        if (active is None or active["team"] != "player" or
                skill_id not in ("attack", *active.get("skills", ()))):
            raise ValueError("Compétence indisponible")
        self.inspected_skill = skill_id
        self._pending_target = None
        self.forecast = ""
        return self.state()

    def level_move(self, level, cell):
        """Use the canonical floor-aware movement command from the Player."""
        state = self._current()
        if not state.battle or state.battle["result"]:
            raise ValueError("No active combat")
        self.session.execute({"kind": "level_move", "level": level,
                              "cell": list(cell)}, expected_revision=state.revision)
        return self._changed()

    def level_attack(self, level, cell):
        """Conservative projectile shot only through authored floor openings."""
        state = self._current()
        if not state.battle or state.battle["result"]:
            raise ValueError("No active combat")
        self.session.execute({"kind": "level_attack", "level": level,
                              "cell": list(cell)}, expected_revision=state.revision)
        return self._changed()

    def toggle_door(self, object_id):
        state = self._current()
        if not state.battle or state.battle["result"]:
            raise ValueError("No active combat")
        if object_id not in {obj["id"] for obj in state.battle["objects"]
                             if obj["kind"] == "door"}:
            raise ValueError("Unknown interactive door")
        self.session.execute({"kind": "door_toggle", "object": object_id},
                             expected_revision=state.revision)
        return self._changed()

    def preview(self, kind):
        """Explain canonical probabilities and path risks, never sample future RNG."""
        state = self.state()
        feedback = state["tactical"]
        if not feedback or state["battle"].get("result"):
            raise ValueError("No tactical preview")
        focus = feedback["focus"]
        if kind == "move":
            move = focus["move"]
            if move is None:
                raise ValueError("Destination inaccessible ou déplacement indisponible")
            risks = move["risks"]
            self.forecast = ("Déplacement · coût " + str(move["cost"]) +
                             " · " + str(len(risks)) + " risque(s) moteur" +
                             (" (réactions possibles, non garanties)" if risks else ""))
        elif kind == "attack":
            if not focus["can_target"]:
                raise ValueError(focus["error"] or "Cible hors de portée")
            effects = focus["forecast"]
            parts = [
                str(effect["kind"]) + " " + str(effect.get("amount", "?")) +
                " sur " + str(effect.get("unit", "?")) +
                (" (" + str(round(effect["chance"] * 100)) + "%)"
                 if type(effect.get("chance")) in (float, int) else "")
                for effect in effects
            ]
            self.forecast = "Prévision (non garantie) : " + (
                ", ".join(parts) if parts else "action valide")
        else:
            raise ValueError("Unsupported preview")
        return self.state()

    def advance_enemy(self, *, limit=40):
        for _ in range(limit):
            state = self._current()
            battle = state.battle
            if battle is None or battle["result"] or state.scene:
                break
            active = next((u for u in battle["units"]
                           if u["id"] == battle["active"]), None)
            if active is None or active["team"] != "enemy":
                break
            self.session.auto_enemy_turn(expected_revision=state.revision)
        return self._changed()

    def finish_battle(self):
        state = self._current()
        if state.battle is None or not state.battle["result"]:
            raise ValueError("Battle is still underway")
        self.session.return_to_campaign(expected_revision=state.revision)
        return self._changed()

    def set_profile(self, profile):
        self.preferences.profile(profile)
        self.message = "Profil clavier : " + profile.upper()
        return self.state()

    def set_binding(self, action, key):
        self.preferences.rebind(action, key)
        self.message = "Commande modifiée : " + action + " = " + key
        return self.state()

    def reset_bindings(self):
        self.preferences.reset()
        self.message = "Commandes du profil restaurées"
        return self.state()

    def set_display(self, name, value):
        self.preferences.set_display(name, value)
        self.message = "Option enregistrée"
        return self.state()

    def resolve_key(self, key, context):
        return self.preferences.resolve(key, context)

    def _require_cinematic_completed(self):
        if self.session is not None and self.session.pending_scene_cinematic() is not None:
            raise ValueError("Terminez ou passez la cinématique avant de poursuivre")

    def _sync_cinematic(self):
        """Create only presentation transport; real progress is in Simulation."""
        if self.session is None or self.show_title:
            self._cinematic_clip = None
            self._cinematic_transport = None
            return None
        candidate = self.session.pending_scene_cinematic()
        if candidate is None:
            self._cinematic_clip = None
            self._cinematic_transport = None
            return None
        clip = thaw(candidate)
        if self._cinematic_clip is None or self._cinematic_clip["id"] != clip["id"]:
            self._cinematic_clip = clip
            self._cinematic_transport = CinematicTransport(clip["duration_ms"])
        return self._cinematic_clip

    def cinematic_pause(self):
        if self._sync_cinematic() is None:
            raise ValueError("No active cinematic")
        self._cinematic_transport.pause()
        return self.state()

    def cinematic_play(self):
        if self._sync_cinematic() is None:
            raise ValueError("No active cinematic")
        self._cinematic_transport.resume()
        return self.state()

    def cinematic_seek(self, time_ms):
        if self._sync_cinematic() is None:
            raise ValueError("No active cinematic")
        self._cinematic_transport.seek(time_ms)
        return self.state()

    def cinematic_skip(self):
        clip = self._sync_cinematic()
        if clip is None:
            raise ValueError("No active cinematic")
        revision = self._current().revision
        self.session.acknowledge_scene_cinematic(clip["id"],
                                                 expected_revision=revision)
        self._cinematic_clip = None
        self._cinematic_transport = None
        return self._changed()

    def cinematic_tick(self):
        if self._sync_cinematic() is not None:
            if self._cinematic_transport.read() >= self._cinematic_clip["duration_ms"]:
                return self.cinematic_skip()
        return self.state()

    def _current(self):
        if self.session is None:
            raise ValueError("No active game")
        return self.session.snapshot()

    def _changed(self, *, keep_message=False):
        self._pending_target = None
        self.inspected_skill = "attack"
        if not keep_message:
            self.message = ""
        self.forecast = ""
        self._checkpoint()
        return self.state()

    def state(self):
        base = {"screen": "title", "title": self.project.title,
                "subtitle": self.project.subtitle, "slots": self.slots(),
                "backups": self.backups(),
                "message": self.message, "forecast": self.forecast,
                "autosave_warning": self.autosave_warning,
                "save_manager": self.saves.catalog(),
                "selected": list(self.selected), "campaign": self.campaign_id,
                "settings": self.preferences.view(),
                "choices": [], "missions": [], "scene": {}, "exploration": {},
                "battle": {}, "tactical": {}, "cinematic": {}, "revision": 0,
                "pending_target": {},
                "gear": {"equipped": {}, "inventory": []}}
        if self.session is None or self.show_title:
            return base
        snapshot = self._current()
        base["revision"] = snapshot.revision
        base["missions"] = list(snapshot.missions)
        progress = thaw(snapshot.progress)
        equipped = progress.get("heroes", {}).get("jeanne", {}).get("equipment", {})
        stock = progress.get("inventory", {})
        base["gear"] = {
            "equipped": dict(equipped),
            "inventory": [
                {"id": item_id, "name": spec.get("name", item_id),
                 "slot": spec["slot"], "count": stock.get(item_id, 0)}
                for item_id, spec in sorted(self.content.equipment.items())
                if stock.get(item_id, 0) > 0
            ],
        }
        base["scene"] = thaw(snapshot.scene) if snapshot.scene else {}
        base["exploration"] = thaw(snapshot.exploration) if snapshot.exploration else {}
        if snapshot.battle:
            # Selection is a UI concern and can outlive a previous mission.
            width, height = snapshot.battle["width"], snapshot.battle["height"]
            self.selected = [min(width - 1, max(0, self.selected[0])),
                             min(height - 1, max(0, self.selected[1]))]
            base["selected"] = list(self.selected)
            projection = self.session.tactical_presentation(
                self.selected, self.inspected_skill,
                expected_revision=snapshot.revision)
            base["tactical"] = thaw(projection) if projection is not None else {}
            battle = thaw(snapshot.battle)
            # The renderer must never receive RNG state, full journals, or rules.
            base["battle"] = {key: battle.get(key) for key in (
                "mission_id", "objective", "width", "height", "units",
                "tiles", "objects", "tick", "active", "result", "deploying",
                "inventory", "zones", "unit_levels")}
            # Stair connectors are authored Content, not mutable battle state.
            base["battle"]["level_links"] = [
                dict(link) for link in
                self.content.missions[battle["mission_id"]].level_links]
        if self._pending_target:
            pending = self._pending_target
            battle = base["battle"]
            # Stale requests can be displayed as invalid, never confirmed.
            base["pending_target"] = {
                "kind": pending["kind"], "skill": pending["skill"],
                "cell": list(pending["cell"]), "details": pending["details"],
                "valid": (snapshot.revision == pending["revision"] and
                          base["selected"] == pending["cell"] and
                          battle.get("active") == pending["active"] and
                          not battle.get("result")),
            }
        if snapshot.scene and (snapshot.battle or not snapshot.exploration or
                               snapshot.exploration["completed"]):
            base["screen"] = "dialogue"
            base["choices"] = thaw(self.session.choices())
        elif snapshot.exploration and not snapshot.exploration["completed"]:
            base["screen"] = "exploration"
        elif snapshot.battle:
            base["screen"] = "result" if snapshot.battle["result"] else "battle"
        else:
            base["screen"] = "campaign"
        clip = self._sync_cinematic()
        if clip is not None:
            if self._cinematic_registry is None:
                self._cinematic_registry = self.project.asset_registry()
            project_file = getattr(self, "asset_project_path", None)
            asset_root = Path(project_file).parent if project_file is not None else None
            position = self._cinematic_transport.read()
            base["cinematic"] = {
                "id": clip["id"], "title": clip["name"],
                "durationMs": clip["duration_ms"],
                "playing": self._cinematic_transport.playing,
                "frame": frame_payload(clip, position, registry=self._cinematic_registry,
                                       asset_root=asset_root),
            }
        return base
