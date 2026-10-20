"""R50.B graphical Player facade over the *canonical* R26 GameSession slot.

Headless, no Qt import. The shared R3 renderer can project `runtime`, but
all accepted inputs, action settlement and CT return pass through the
replay-checked sporebound PlayerController. No R26 preview sidecar saves.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from sporebound.action_runtime import ActionRuntime, SCALE
from sporebound.action_scene_adapter import authored_action_scene
from sporebound.action_settlement import settlement_keys, victory_coins
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError, require
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


def load_authored_action_pair(content_path):
    """Validate BOTH authoring documents; no fallback to reference content."""
    path = Path(content_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = Content.from_dict(
        raw, rules=authored_rules_for_document(raw))
    manifest = path.with_name(path.stem + ".game.json")
    project = GameProject.from_dict(
        json.loads(manifest.read_text(encoding="utf-8")), content)
    return content, project


class R50BActionController:
    """R26 UI state with one canonical Player slot and explicit UI-only pause."""

    def __init__(self, content, project, profile, *, campaign=None, slot=1,
                 seed=50, new=False):
        require(bool(project.scene_routes),
                "R50.B Qt Player requires a routed action project")
        self.scene_id = project.scene_routes["start"]
        self.scene = authored_action_scene(project, self.scene_id)
        self.fallback = ActionRuntime(self.scene)
        self.player = PlayerController(content, project, profile)
        self.campaign = campaign or project.campaigns[0]["id"]
        self.slot = slot
        if new:
            self.player.new_game(self.campaign, slot, seed=seed)
        else:
            # Do not create or overwrite a slot merely because a GUI opens.
            self.player.load_game(self.campaign, slot)
        self.paused = False
        self.message = "R50.B — combat action, sauvegarde GameSession vérifiée."
        self.events = []

    @property
    def runtime(self):
        return (self.player.session._action
                if self.player.session._action is not None else self.fallback)

    def _nearby(self):
        hero = self.runtime.hero
        candidates = []
        for obj in self.scene["objects"]:
            if obj["kind"] != "sign" and self.runtime.objects[obj["id"]]["opened"]:
                continue
            px, py = (obj["pos"][0] * SCALE + SCALE // 2,
                      obj["pos"][1] * SCALE + SCALE // 2)
            distance = (hero["pos"][0] - px) ** 2 + (hero["pos"][1] - py) ** 2
            if distance <= 1600 ** 2:
                candidates.append((distance, obj["id"]))
        return min(candidates)[1] if candidates else ""

    def state(self):
        """Detached QML/HUD projection; reads never mutate Campaign or Player."""
        snapshot = self.runtime.snapshot()
        game = self.player.session
        done_flag, coins_flag = settlement_keys(self.scene_id)
        settled = game.progress.story_flags.get(done_flag) is True
        can_settle = False
        if game.mode == "campaign" and game.route_scene == self.scene_id and (
                game._action is not None) and not settled:
            try:
                victory_coins(game._action)
            except RuleError:
                pass
            else:
                can_settle = True
        snapshot.update({
            "width": self.scene["width"], "height": self.scene["height"],
            "walls": deepcopy(self.scene["walls"]),
            "items": deepcopy(self.scene["objects"]),
            "mode": game.mode, "route_scene": game.route_scene,
            "paused": self.paused, "settled": settled,
            "can_settle": can_settle,
            "campaign_gold": game.progress.gold,
            "awarded_coin": game.progress.story_flags.get(coins_flag, 0),
            "message": self.message, "events": deepcopy(self.events),
            "prompt": (self._nearby() if game.mode == "campaign"
                       and not settled and snapshot["hero"]["alive"] else ""),
            "slot": self.slot,
        })
        return snapshot

    def step(self, dx=0, dy=0, *, attack=False, dodge=False, guard=False,
             interact=False):
        require(not self.paused, "Action Player is paused")
        game = self.player.session
        done_flag, _ = settlement_keys(self.scene_id)
        require(game.mode == "campaign" and
                game.route_scene == self.scene_id and
                game.progress.story_flags.get(done_flag) is not True and
                self.runtime.hero["alive"],
                "No active R26 Player combat to advance")
        command = {
            "tick": self.runtime.tick + 1, "dx": dx, "dy": dy,
            "attack": attack, "dodge": dodge, "guard": guard,
            "interact": self._nearby() if interact else "",
        }
        committed = self.player.route_action_step(command)
        self.events = deepcopy(committed["events"])
        if self.events:
            self.message = " · ".join(event["kind"].replace("_", " ")
                                      for event in self.events[-3:])
        return self.events

    def toggle_pause(self):
        self.paused = not self.paused
        return self.state()

    def save(self):
        self.player.save()
        self.message = "Slot GameSession sauvegardé et vérifié."
        return self.state()

    def load(self):
        # Failed verification leaves both existing Player state and slot intact.
        self.player.load_game(self.campaign, self.slot)
        self.events = []
        self.paused = False
        self.message = "Slot GameSession vérifié et repris."
        return self.state()

    def settle(self):
        require(not self.paused, "Resume Player before settling R26")
        result = self.player.route_action_settle("after_action_to_ct")
        self.events = []
        self.message = ("Victoire R26 : +" + str(result["coins_awarded"]) +
                        " or. Combat CT lancé ; R pour retour explicite.")
        return self.state()

    def return_from_ct(self):
        require(not self.paused, "Resume Player before exiting CT")
        result = self.player.route_abandon_ct("ct_to_action")
        self.events = []
        self.message = ("CT abandonné sans récompense. Retour à " +
                        result["scene"] + " ; action R26 déjà récompensée.")
        return self.state()

    def respawn(self):
        """No implicit overwrite after defeat: a fresh slot is explicit."""
        raise RuleError(
            "Aucun respawn implicite : utilisez un nouveau slot explicite. "
            "Le checkpoint actuel ne sera pas effacé.")


__all__ = ["R50BActionController", "load_authored_action_pair"]
