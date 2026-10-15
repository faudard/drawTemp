"""Headless R12 Player flow on top of the canonical R1 Simulation API.

All commands, previews, story choices and persistence run through Simulation.
This module never imports Qt or Tk and never edits the GameSession directly.
"""
from pathlib import Path
import os
import shutil

from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from drawtemp.player.preferences import PlayerPreferences


class PlayerController:
    """Small, deterministic state machine for the standalone Qt Player."""

    def __init__(self, content, project, campaign_id, save_dir, *, seed=17):
        if project.campaign(campaign_id) is None:
            raise ValueError("Unknown campaign: " + campaign_id)
        self.content, self.project = content, project
        self.campaign_id, self.seed = campaign_id, seed
        self.save_dir = Path(save_dir)
        self.preferences = PlayerPreferences(self.save_dir / 'player-preferences.json')
        self.session = None
        self.show_title = True
        self.selected = [0, 0]
        self.message = self.preferences.warning
        self.forecast = ""

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

    def restore_backup(self, slot=1):
        backup = self._path(slot).with_suffix(".json.bak")
        if not backup.is_file():
            raise ValueError("Aucune sauvegarde de secours")
        verified = Simulation.load(backup, self.content, self.project)
        path = self._path(slot)
        temporary = path.with_suffix(".json.recovering")
        try:
            shutil.copy2(backup, temporary)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        self.session = verified
        self.show_title = False
        self.message = "Sauvegarde de secours restaurée"
        return self.state()

    def new_game(self):
        self.session = Simulation.new(self.content, self.project, self.campaign_id,
                                      seed=self.seed)
        self.show_title = False
        self.message = "Le voyage de Jeanne commence."
        self.forecast = ""
        return self.state()

    def load(self, slot=1):
        path = self._path(slot)
        # Assignment only after successful verification: preserve the live game
        # and the saved file when a checksum/project/rules mismatch is found.
        loaded = Simulation.load(path, self.content, self.project)
        self.session = loaded
        self.show_title = False
        self.message = "Partie rechargée."
        self.forecast = ""
        return self.state()

    def save(self, slot=1):
        if self.session is None:
            raise ValueError("No game to save")
        path = self._path(slot)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            Simulation.load(path, self.content, self.project)
            shutil.copy2(path, path.with_suffix(".json.bak"))
        self.session.save(path)
        self.message = "Sauvegarde dans l'emplacement " + str(slot)
        return self.state()

    def title(self):
        self.show_title = True
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
        state = self._current()
        if state.mode != "campaign" or state.scene is not None:
            raise ValueError("Resolve the narrative before starting a mission")
        if mission_id not in state.missions:
            raise ValueError("Mission is locked")
        self.session.start_mission(mission_id, expected_revision=state.revision)
        return self._changed()

    def explore_move(self, dx, dy):
        state = self._current()
        if not state.exploration or state.exploration["completed"]:
            raise ValueError("Exploration is unavailable")
        self.session.explore_move(dx, dy, expected_revision=state.revision)
        return self._changed()

    def explore_interact(self, point_id):
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
        state = self._current()
        self.session.explore_actor(actor_id, action, expected_revision=state.revision)
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
        self.forecast = ""
        return self.state()

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

    def preview(self, kind):
        state = self._current()
        if not state.battle or state.battle["result"]:
            raise ValueError("No tactical preview")
        if kind == "move":
            command = {"kind": "move", "cell": list(self.selected)}
        elif kind == "attack":
            command = {"kind": "act", "skill": "attack", "cell": list(self.selected)}
        else:
            raise ValueError("Unsupported preview")
        predicted = self.session.preview(command, expected_revision=state.revision)
        old_units = {u["id"]: u for u in state.battle["units"]}
        changes = []
        for unit in predicted.snapshot.battle["units"]:
            before = old_units[unit["id"]]
            if before["hp"] != unit["hp"]:
                changes.append(unit["id"] + " PV " + str(before["hp"]) +
                               " → " + str(unit["hp"]))
            if list(before["pos"]) != list(unit["pos"]):
                changes.append(unit["id"] + " se déplace")
        self.forecast = ", ".join(changes) or "Action validée : aucun changement de PV"
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

    def _current(self):
        if self.session is None:
            raise ValueError("No active game")
        return self.session.snapshot()

    def _changed(self, *, keep_message=False):
        if not keep_message:
            self.message = ""
        self.forecast = ""
        return self.state()

    def state(self):
        base = {"screen": "title", "title": self.project.title,
                "subtitle": self.project.subtitle, "slots": self.slots(),
                "backups": self.backups(),
                "message": self.message, "forecast": self.forecast,
                "selected": list(self.selected), "campaign": self.campaign_id,
                "settings": self.preferences.view(),
                "choices": [], "missions": [], "scene": {}, "exploration": {},
                "battle": {}, "revision": 0}
        if self.session is None or self.show_title:
            return base
        snapshot = self._current()
        base["revision"] = snapshot.revision
        base["missions"] = list(snapshot.missions)
        base["scene"] = thaw(snapshot.scene) if snapshot.scene else {}
        base["exploration"] = thaw(snapshot.exploration) if snapshot.exploration else {}
        if snapshot.battle:
            battle = thaw(snapshot.battle)
            # The renderer must never receive RNG state, full journals, or rules.
            base["battle"] = {key: battle.get(key) for key in (
                "mission_id", "objective", "width", "height", "units",
                "tiles", "objects", "tick", "active", "result", "deploying",
                "inventory", "zones")}
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
        return base
