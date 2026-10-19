"""R26.B: optional headless Player controller over the R26 action capability.

No Qt imports, gameplay duplication, or calls into tactical Battle.
A dedicated action preview is deliberately NOT the canonical GameSession
save slot; R25 SceneRouter is required for mid-scene cross-mode persistence.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from sporebound.action_runtime import ActionRuntime, SCALE, validate_scene
from drawtemp.render.committed_fx import CommittedFxDirector


def demo_scene():
    """Generic original sample, not a third-party game's assets or data."""
    return {
        "id": "r26_meadow", "width": 11, "height": 9,
        "walls": [[5, 2], [5, 3], [5, 4], [5, 5], [2, 6],
                  [3, 6], [4, 6], [7, 5], [8, 5]],
        "hero": {"pos": [1, 2], "hp": 8},
        "enemies": [
            {"id": "wolf", "pos": [4, 2], "hp": 2,
             "patrol": [[4, 2], [4, 4]]},
            {"id": "sentinel", "pos": [8, 3], "hp": 3,
             "patrol": [[8, 3], [9, 3]]},
        ],
        "objects": [
            {"id": "supply", "kind": "chest", "pos": [1, 3],
             "item": "gate_key", "requires": ""},
            {"id": "gate", "kind": "door", "pos": [6, 4],
             "item": "", "requires": "gate_key"},
            {"id": "inscription", "kind": "sign", "pos": [3, 5],
             "item": "", "requires": ""},
        ],
    }


class ActionPlayerController:
    """One simulation tick per step; input edges are supplied by the UI.

    The presentation layer may call state() as often as necessary without
    affecting simulation outcomes. A save is verified *before* replacing the
    active runtime, so a failed load never corrupts the current game.
    """

    def __init__(self, scene, *, save_path=None):
        self.scene = validate_scene(scene)
        self.save_path = Path(save_path) if save_path is not None else None
        self.runtime = ActionRuntime(self.scene)
        self.fx = CommittedFxDirector()
        self.paused = False
        self.message = "Explorez la prairie. Ouvrez le coffre avant la porte."
        self.events = ()

    def _nearby(self):
        hero = self.runtime.hero
        candidates = []
        for obj in self.scene["objects"]:
            if obj["kind"] != "sign" and self.runtime.objects[obj["id"]]["opened"]:
                continue
            x = obj["pos"][0] * SCALE + SCALE // 2
            y = obj["pos"][1] * SCALE + SCALE // 2
            dx, dy = hero["pos"][0] - x, hero["pos"][1] - y
            distance = dx * dx + dy * dy
            if distance <= 1600 ** 2:
                candidates.append((distance, obj["id"]))
        return min(candidates)[1] if candidates else ""

    def state(self):
        snapshot = self.runtime.snapshot()
        snapshot["walls"] = deepcopy(self.scene["walls"])
        snapshot["items"] = deepcopy(self.scene["objects"])
        snapshot["width"] = self.scene["width"]
        snapshot["height"] = self.scene["height"]
        snapshot["paused"] = self.paused
        snapshot["prompt"] = self._nearby() if self.runtime.hero["alive"] else ""
        snapshot["message"] = self.message
        snapshot["events"] = deepcopy(self.events)
        snapshot["fx"] = self.fx.snapshot()
        return snapshot

    def step(self, dx=0, dy=0, *, attack=False, dodge=False, guard=False,
             interact=False):
        if self.paused or not self.runtime.hero["alive"]:
            return []
        target = self._nearby() if interact else ""
        events = self.runtime.step({
            "tick": self.runtime.tick + 1, "dx": dx, "dy": dy,
            "attack": attack, "dodge": dodge, "guard": guard,
            "interact": target,
        })
        self.events = deepcopy(events)
        self.fx.observe(self.runtime.snapshot(), events)
        if events:
            self.message = " · ".join(event["kind"].replace("_", " ")
                                      for event in events[-3:])
        return events

    def toggle_pause(self):
        self.paused = not self.paused
        return self.state()

    def save(self):
        if self.save_path is None:
            raise ValueError("No R26 action checkpoint path provided")
        self.runtime.save(self.save_path)
        self.message = "Point de sauvegarde action enregistré."
        return self.state()

    def load(self):
        if self.save_path is None:
            raise ValueError("No R26 action checkpoint path provided")
        verified = ActionRuntime.load(self.save_path, expected_scene=self.scene)
        self.runtime = verified
        self.fx.reset(self.runtime.tick)
        self.paused = False
        self.events = ()
        self.message = "Point de sauvegarde action vérifié et rechargé."
        return self.state()

    def respawn(self):
        if self.runtime.hero["alive"]:
            raise ValueError("Respawn is only available after defeat")
        if self.save_path is not None and self.save_path.is_file():
            verified = ActionRuntime.load(self.save_path, expected_scene=self.scene)
            if verified.hero["alive"]:
                self.runtime = verified
                self.fx.reset(self.runtime.tick)
                self.paused = False
                self.events = ()
                self.message = "Réapparition au point de sauvegarde."
                return self.state()
        self.runtime = ActionRuntime(self.scene)
        self.fx.reset(self.runtime.tick)
        self.paused = False
        self.events = ()
        self.message = "Retour au départ de la scène."
        return self.state()


__all__ = ["ActionPlayerController", "demo_scene"]
