"""R65.C opt-in Player facade; existing R26/R50 GameSession slots untouched."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from drawtemp.player.action_controller import ActionPlayerController
from sporebound.action_arena_r65 import ActionArenaR65, validate_arena
from sporebound.action_runtime import ActionError


class ActionArenaController(ActionPlayerController):
    """Shared R3 scene projection/FX; R65.C owns the sole combat runtime.

    This standalone demonstration writes only an explicitly selected R65 v3
    checkpoint. It does NOT mutate Campaign inventory, CT or canonical slots.
    """

    def __init__(self, scene, preset, setup, *, save_path=None):
        scene, preset, setup = validate_arena(scene, preset, setup)
        super().__init__(scene, save_path=save_path)
        self.preset = deepcopy(preset)
        self.setup = deepcopy(setup)
        self.runtime = ActionArenaR65(scene, preset, setup)
        self.message = "R65.C : arène action. Vaincre les deux gardes et le boss."

    def state(self):
        view = super().state()
        view["mode"] = "R65_ARENA"
        view["victory"] = view["arena"]["victory"]
        view["hint"] = (
            "Boss phase " + str(view["arena"]["boss"]["phase"])
            + (" — télégraphie !" if view["arena"]["boss"]["casting"] else "")
        )
        return view

    def step(self, dx=0, dy=0, *, attack=False, dodge=False, guard=False,
             interact=False, fire=False, parry=False):
        if self.paused or not self.runtime.hero["alive"] or (
                self.runtime.snapshot()["arena"]["victory"]):
            return []
        events = self.runtime.step({
            "tick": self.runtime.tick + 1,
            "dx": dx, "dy": dy, "attack": attack, "dodge": dodge,
            "guard": guard, "interact": self._nearby() if interact else "",
            "fire": fire, "parry": parry,
        })
        self.events = deepcopy(events)
        try:
            self.fx.observe(self.runtime.snapshot(), events)
            self.fx_warning = ""
        except (TypeError, ValueError, KeyError) as exc:
            self.fx.reset(self.runtime.tick)
            self.fx_warning = "R36 VFX disabled: " + str(exc)
        if events:
            self.message = " · ".join(str(event["kind"]).replace("_", " ")
                                      for event in events[-3:])
        if self.runtime.snapshot()["arena"]["victory"]:
            self.message = "Arène gagnée : les trois adversaires sont vaincus."
        return deepcopy(events)

    def load(self):
        if self.save_path is None:
            raise ActionError("No R65.C checkpoint path provided")
        # Verify fully before replacing committed Player state.
        candidate = ActionArenaR65.load(
            self.save_path, expected_scene=self.scene,
            expected_preset=self.preset, expected_setup=self.setup)
        self.runtime = candidate
        self.fx.reset(self.runtime.tick)
        self.fx_warning = ""
        self.paused = False
        self.events = ()
        self.message = "R65.C checkpoint replay verified."
        return self.state()

    def respawn(self):
        if self.runtime.hero["alive"]:
            raise ActionError("Respawn only after defeat")
        if self.save_path is not None and self.save_path.is_file():
            candidate = ActionArenaR65.load(
                self.save_path, expected_scene=self.scene,
                expected_preset=self.preset, expected_setup=self.setup)
            if candidate.hero["alive"]:
                self.runtime = candidate
                self.fx.reset(self.runtime.tick)
                self.fx_warning = ""
                self.paused = False
                self.events = ()
                self.message = "Réapparition au dernier checkpoint vérifié."
                return self.state()
        # Deliberately no implicit save overwrite. Start a new v3 session.
        self.runtime = ActionArenaR65(self.scene, self.preset, self.setup)
        self.fx.reset(0)
        self.fx_warning = ""
        self.paused = False
        self.events = ()
        self.message = "Nouvelle tentative d'arène."
        return self.state()


__all__ = ["ActionArenaController"]
