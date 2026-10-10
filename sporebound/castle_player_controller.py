"""Save-safe headless command facade for CastleVerticalSlice 2.8 GUI.

All rules live in CastleVerticalSlice, Campaign and MultiFrontSession. The GUI
only calls these intents, and every accepted intent gets a verified checkpoint.
"""
from pathlib import Path

from .ai import choose_command
from .model import require
from .vertical_slice import CastleVerticalSlice


class CastlePlayerController:
    def __init__(self, content, blueprint, save_path, *, rules):
        self.content = content
        self.blueprint = blueprint
        self.rules = rules
        self.save_path = Path(save_path)
        self.session = None

    def new_game(self, *, seed=7, overwrite=False):
        require(overwrite or not self.save_path.exists(),
                "A castle save already exists; choose Continue or confirm replacement")
        candidate = CastleVerticalSlice(self.content, self.blueprint,
                                        seed=seed, rules=self.rules)
        # Do not expose a session that has not successfully checkpointed.
        candidate.save(self.save_path)
        self.session = candidate
        return candidate

    def continue_game(self):
        candidate = CastleVerticalSlice.load(
            self.save_path, self.content, self.blueprint, rules=self.rules)
        self.session = candidate
        return candidate

    def save(self):
        require(self.session is not None, "No castle campaign is loaded")
        return self.session.save(self.save_path)

    def _apply(self, action, *args):
        require(self.session is not None, "No castle campaign is loaded")
        before = self.session.recording()
        try:
            result = action(*args)
            self.save()
            return result
        except Exception:
            self.session = CastleVerticalSlice.from_recording(
                before, self.content, self.blueprint, rules=self.rules)
            raise

    def select_squad(self, members):
        return self._apply(self.session.select_squad, members)

    def set_job(self, hero, job):
        return self._apply(self.session.set_job, hero, job)

    def buy(self, item):
        return self._apply(self.session.buy, item)

    def equip(self, hero, item):
        return self._apply(self.session.equip, hero, item)

    def start(self, approach):
        return self._apply(self.session.start, approach)

    def execute(self, command):
        return self._apply(self.session.execute, command)

    def switch(self, front):
        return self._apply(self.session.switch, front)

    def doctrine(self, front, doctrine):
        return self._apply(self.session.doctrine, front, doctrine)

    def advance(self):
        return self._apply(self.session.advance)

    def route(self, route):
        return self._apply(self.session.select_route, route)

    def negotiate(self):
        return self._apply(self.session.negotiate)

    def partial(self):
        return self._apply(self.session.partial)

    def withdraw(self, front):
        return self._apply(self.session.withdraw, front)

    def concede(self):
        return self._apply(self.session.concede)

    def ai_turn(self):
        require(self.session is not None and self.session.fronts is not None
                and self.session.ending is None, "No active castle battle")
        battle = self.session.fronts.active
        require(not battle.deploying and battle.result is None
                and battle.active is not None and battle.active.team == "enemy",
                "The enemy has no available activation")

        def play():
            initial_actor = self.session.fronts.active.active.id
            for _ in range(3):
                current = self.session.fronts.active
                if (current.result is not None or current.active is None or
                        current.active.id != initial_actor):
                    break
                self.session.execute(choose_command(current))
        return self._apply(play)
