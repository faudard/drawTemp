"""2.8.2 — Replay-safe bridge from authored Campaign & Siege Studio to Player.

No new siege contract: authored content, rules, slot paths and checkpoints remain
owned by siege_authoring and MultiFrontSession. This adapter is display-free.
"""
from copy import deepcopy
from pathlib import Path

from . import siege_authoring
from .fronts import MultiFrontSession
from .model import require
from .rules import default_rules
from .siege_story import SiegeStory
from .ai import choose_command


def active_side_encounter(fronts):
    """Return (kind, key, battle) in the same priority as the strategic UI."""
    for kind, attr in (("recovery", "recovery_battles"),
                       ("pursuit", "pursuit_battles"),
                       ("rescue", "rescue_battles")):
        battles = getattr(fronts, attr)
        if battles:
            key = sorted(battles)[0]
            return kind, key, battles[key]
    return None


class AuthoredSiegeRun:
    """Presentation-only facade exposing the Castle Player battle interface."""
    def __init__(self, fronts, blueprint):
        self.fronts = fronts
        self.blueprint = deepcopy(blueprint)
        self.approach = blueprint["id"]

    @property
    def ending(self):
        if self.fronts.campaign is not None:
            status = self.fronts.campaign.state(self.fronts)["status"]
            if status == "victory":
                return "victory"
            if status == "defeat":
                return "defeat"
            return None  # Blocked fronts can still be recovered tactically.
        if any(row["status"] == "active"
               for row in self.fronts.timeline.fronts.values()):
            return None
        return ("victory" if all(row["status"] == "victory"
                for row in self.fronts.timeline.fronts.values()) else "defeat")


class AuthoredSiegeController:
    def __init__(self, content, blueprint, project_path, slot=1, *, rules=None,
                 project=None):
        siege_authoring.validate_blueprint(blueprint, content,
                                          {blueprint["campaign_id"]})
        self.content, self.blueprint = deepcopy(content), deepcopy(blueprint)
        self.project_path = Path(project_path)
        self.slot = slot
        self.save_path = siege_authoring._save_path(
            self.project_path, blueprint["id"], slot)
        self.rules = rules if rules is not None else default_rules()
        if project is not None:
            project.validate(content)
            require(project.campaign(blueprint["campaign_id"]) is not None
                    and any(row == blueprint for row in project.sieges),
                    "Narrative siege does not belong to the authored project")
        self.project = deepcopy(project) if project is not None else None
        self.story = None
        self.session = None

    def _check(self, fronts):
        require(fronts.content.to_dict() == self.content.to_dict()
                and fronts.missions == self.blueprint["fronts"]
                and fronts.initial_specs == self.blueprint["specs"]
                and fronts.links == self.blueprint["links"]
                and fronts.initial_campaign == self.blueprint["campaign"]
                and fronts.initial_logistics == self.blueprint.get("logistics")
                and fronts.rules.manifest() == self.rules.manifest(),
                "Current session differs from authored siege definition")

    def _replace(self, fronts):
        self._check(fronts)
        self.session = AuthoredSiegeRun(fronts, self.blueprint)
        return self.session

    def new_game(self, *, seed=1, overwrite=False):
        require(overwrite or not self.save_path.exists(),
                "A save exists in this siege slot")
        candidate = siege_authoring.make_session(
            self.blueprint, self.content, seed=seed, rules=self.rules)
        self._check(candidate)
        story = (SiegeStory(self.project, self.content, self.blueprint, candidate)
                 if self.project is not None else None)
        siege_authoring.save_siege_slot(
            self.project_path, self.blueprint, self.slot, candidate,
            narrative=story.recording() if story else None)
        self.story = story
        return self._replace(candidate)

    def adopt(self, fronts, *, overwrite=False):
        """Begin at an already edited Studio session, no implicit slot overwrite."""
        require(overwrite or not self.save_path.exists(),
                "A save exists in this siege slot")
        self._check(fronts)
        story = (SiegeStory(self.project, self.content, self.blueprint, fronts)
                 if self.project is not None else None)
        siege_authoring.save_siege_slot(
            self.project_path, self.blueprint, self.slot, fronts,
            narrative=story.recording() if story else None)
        self.story = story
        return self._replace(fronts)

    def continue_game(self):
        candidate, narrative = siege_authoring.load_siege_slot(
            self.project_path, self.blueprint, self.slot,
            self.content, rules=self.rules, _with_narrative=True)
        if narrative is not None:
            require(self.project is not None,
                    "Narrative save needs its original project manifest")
            story = SiegeStory.replay(
                narrative, self.project, self.content, self.blueprint,
                candidate.recording(), rules=self.rules)
        else:
            story = (SiegeStory(self.project, self.content, self.blueprint, candidate)
                     if self.project is not None else None)
        self._replace(candidate)
        self.story = story
        return self.session

    def save(self):
        require(self.session is not None, "No siege is active")
        return siege_authoring.save_siege_slot(
            self.project_path, self.blueprint, self.slot, self.session.fronts,
            narrative=self.story.recording() if self.story is not None else None)

    def _apply(self, method, *args):
        require(self.session is not None, "No siege is active")
        require(self.story is None or self.story.active_scene() is None,
                "Finish the pending narrative scene before tactical orders")
        old = self.session.fronts.recording()
        old_story = self.story.recording() if self.story is not None else None
        try:
            result = method(*args)
            if self.story is not None:
                self.story.sync(self.session.fronts)
            self.save()
            return result
        except Exception:
            # Reconstruct from the exact previous journal rather than trusting
            # a partially applied tactical/strategic in-memory mutation.
            self._replace(MultiFrontSession.replay(old, rules=self.rules))
            if old_story is not None:
                self.story = SiegeStory.replay(
                    old_story, self.project, self.content, self.blueprint,
                    old, rules=self.rules)
            raise

    def active_scene(self):
        return self.story.active_scene() if self.story is not None else None

    def available_choices(self):
        return self.story.choices() if self.story is not None else []

    def pending_cinematic(self):
        return self.story.next_cinematic() if self.story is not None else None

    def acknowledge_cinematic(self, clip_id):
        """Record an explicit finished/skipped cutscene at this replay boundary."""
        require(self.story is not None and self.session is not None,
                "No active narrative session")
        previous = self.story.recording()
        try:
            self.story.acknowledge_cinematic(
                clip_id, len(self.session.fronts.history))
            self.save()
        except Exception:
            self.story = SiegeStory.replay(
                previous, self.project, self.content, self.blueprint,
                self.session.fronts.recording(), rules=self.rules)
            raise

    def choose_story_option(self, choice):
        require(self.story is not None and self.session is not None,
                "No active narrative session")
        old = self.story.recording()
        try:
            self.story.choose(choice, len(self.session.fronts.history))
            self.save()
            return self.active_scene()
        except Exception:
            self.story = SiegeStory.replay(
                old, self.project, self.content, self.blueprint,
                self.session.fronts.recording(), rules=self.rules)
            raise

    def active_encounter(self):
        require(self.session is not None, "No siege is active")
        return active_side_encounter(self.session.fronts)

    def current_battle(self):
        side = self.active_encounter()
        return side[2] if side else self.session.fronts.active

    def execute(self, command):
        side = self.active_encounter()
        f = self.session.fronts
        if side:
            kind, key, _ = side
            return self._apply(getattr(f, "execute_" + kind), key, command)
        return self._apply(f.execute, command)

    def ai_turn(self):
        battle = self.current_battle()
        require(not battle.deploying and battle.result is None
                and battle.active is not None and battle.active.team == "enemy",
                "No enemy activation to play")

        def play():
            actor = battle.active.id
            for _ in range(3):
                now = self.current_battle()
                if (now is not battle or now.result is not None or
                        now.active is None or now.active.id != actor):
                    break
                # Execute via session journal, never Battle.execute directly.
                side = self.active_encounter()
                f = self.session.fronts
                if side:
                    getattr(f, "execute_" + side[0])(side[1], choose_command(now))
                else:
                    f.execute(choose_command(now))

        return self._apply(play)

    def switch(self, front):
        return self._apply(self.session.fronts.switch, front)

    def doctrine(self, front, value):
        return self._apply(self.session.fronts.set_doctrine, front, value)

    def advance(self):
        return self._apply(self.session.fronts.advance)

    def negotiate(self):
        f = self.session.fronts
        return self._apply(f.negotiate_front, f.timeline.focused)

    def partial(self):
        f = self.session.fronts
        return self._apply(f.partial_front, f.timeline.focused)

    def withdraw(self, front):
        return self._apply(self.session.fronts.withdraw_front, front)

    def route(self, route):
        return self._apply(self.session.fronts.select_route, route)

    def recover(self, front):
        return self._apply(self.session.fronts.start_recovery, front)

    def abandon_recovery(self, front):
        return self._apply(self.session.fronts.abandon_recovery, front)

    def transfer(self, destination, unit, cell):
        return self._apply(self.session.fronts.transfer_units,
                           destination, {unit: cell})

    def dispatch(self, destination, actors):
        return self._apply(self.session.fronts.send_reserves,
                           destination, actors)

    def escort(self, convoy):
        return self._apply(self.session.fronts.escort_convoy, convoy)

    def rescue(self, convoy):
        return self._apply(self.session.fronts.start_rescue, convoy)

    def salvage(self, convoy):
        return self._apply(self.session.fronts.salvage_convoy, convoy)

    def negotiate_convoy(self, convoy):
        return self._apply(self.session.fronts.negotiate_convoy, convoy)

    def pursue(self, convoy):
        return self._apply(self.session.fronts.start_pursuit, convoy)

    def abandon_side(self):
        side = self.active_encounter()
        require(side is not None, "No active side mission")
        kind, key, _ = side
        fn = {"recovery": "abandon_recovery", "pursuit": "abandon_pursuit",
              "rescue": "abandon_convoy"}[kind]
        return self._apply(getattr(self.session.fronts, fn), key)
