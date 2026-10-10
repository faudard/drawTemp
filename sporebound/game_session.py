"""Unified campaign, story and tactical lifecycle. No UI or new combat rules."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json

from .ai import play_activation
from .campaign import Campaign
from .engine import Battle
from .fronts import MultiFrontSession
from .model import RuleError, require
from .narrative import StoryBook
from .rules import default_rules
from .storage import write_json


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GameSession:
    """Compose Campaign, StoryBook, Battle and MultiFrontSession.

    This uses a new explicit session save format. Existing PlayerSession slots
    and historical battle/multi-front replay formats are untouched.
    """
    VERSION = 1

    def __init__(self, content, project, campaign_id, *, seed=1, rules=None):
        self.rules = rules if rules is not None else default_rules()
        content.validate(rules=self.rules)
        project.validate(content)
        require(project.campaign(campaign_id) is not None, "Unknown campaign")
        require(type(seed) is int, "Invalid seed")
        self.content, self.project = deepcopy(content), deepcopy(project)
        self.campaign_id, self.seed = campaign_id, seed
        self.story = StoryBook(project.story, content, project.campaigns)
        self.progress = project.new_game(campaign_id, content)
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()

    @classmethod
    def new(cls, content, project, campaign_id, **kwargs):
        return cls(content, project, campaign_id, **kwargs)

    @property
    def mode(self):
        return "fronts" if self.fronts is not None else (
            "battle" if self.battle is not None else "campaign")

    @property
    def active_battle(self):
        return self.fronts.active if self.fronts is not None else self.battle

    def active_scene(self):
        return self.story.active_scene(self.progress)

    def available_choices(self):
        return self.story.choices(self.progress)

    def available_missions(self):
        if self.progress.story_pending:
            return []
        return [m for m in self.progress.unlocked if m not in self.progress.completed]

    def choose_story_option(self, choice_id):
        require(self.active_battle is None or self.active_battle.result is not None,
                "Finish combat before choosing dialogue")
        updated = self.story.choose(self.progress, choice_id)
        self.progress = updated
        return self.active_scene()

    def start_mission(self, mission_id):
        require(self.mode == "campaign", "End the current encounter first")
        require(mission_id in self.available_missions(), "Mission is locked")
        # Campaign.prepare can materialize heroes: use a throwaway roster.
        battle = deepcopy(self.progress).prepare(
            self.content, mission_id, seed=self.seed, ruleset=self.rules)
        self.battle, self.finalized = battle, False
        self._settle()
        return battle

    def start_fronts(self, missions, focused, *, specs=None, links=None,
                     logistics=None, campaign=None):
        require(self.mode == "campaign", "End the current encounter first")
        require(isinstance(missions, dict) and bool(missions) and focused in missions,
                "Invalid front mapping")
        require(len(set(missions.values())) == len(missions),
                "Duplicate mission in fronts")
        available = set(self.available_missions())
        require(all(isinstance(mid, str) and mid in available
                    for mid in missions.values()), "Front mission is locked")
        prepared = deepcopy(self.content)
        for mid in missions.values():
            battle = deepcopy(self.progress).prepare(
                self.content, mid, seed=self.seed, ruleset=self.rules)
            # Battle.mission is live; Battle.content still holds authored units.
            prepared.missions[mid] = deepcopy(battle.content.missions[mid])
        self.fronts = MultiFrontSession(
            prepared, missions, focused, seed=self.seed, rules=self.rules,
            specs=specs, links=links, logistics=logistics, campaign=campaign)
        self.settled_fronts.clear()
        return self.fronts

    def _commit(self, battle):
        updated = deepcopy(self.progress)
        route = battle.result == "victory" and battle.mission.id in self.story.after
        changed = updated.finish(battle, unlock_next=not route)
        if changed and route:
            self.story.after_victory(updated, battle.mission.id)
        self.progress = updated

    def _settle(self):
        if self.fronts is not None:
            for front, battle in self.fronts.battles.items():
                if front not in self.settled_fronts and battle.result in ("victory", "defeat"):
                    self._commit(battle)
                    self.settled_fronts.add(front)
        elif self.battle is not None and not self.finalized and self.battle.result in ("victory", "defeat"):
            self._commit(self.battle)
            self.finalized = True

    def execute(self, command):
        require(self.active_battle is not None, "No tactical combat")
        require(not self.progress.story_pending, "Resolve pending dialogue first")
        before = deepcopy((self.progress, self.battle, self.fronts,
                           self.finalized, self.settled_fronts))
        try:
            if self.fronts is not None:
                self.fronts.execute(command)
            else:
                require(not self.finalized, "Combat already completed")
                self.battle.execute(command)
            self._settle()
        except Exception:
            (self.progress, self.battle, self.fronts,
             self.finalized, self.settled_fronts) = before
            raise
        return self.active_battle

    def switch_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.switch(front)
        return self.active_battle

    def advance_fronts(self):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        before = deepcopy((self.progress, self.fronts, self.settled_fronts))
        try:
            state = self.fronts.advance()
            self._settle()
        except Exception:
            self.progress, self.fronts, self.settled_fronts = before
            raise
        return state

    def set_doctrine(self, front, doctrine):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.set_doctrine(front, doctrine)

    def ai_turn(self):
        require(self.mode == "battle" and not self.finalized and
                not self.battle.deploying, "No standalone AI combat")
        require(self.battle.active is not None and self.battle.active.team == "enemy",
                "Not an enemy activation")
        before = deepcopy((self.progress, self.battle, self.finalized))
        try:
            play_activation(self.battle)
            self._settle()
        except Exception:
            self.progress, self.battle, self.finalized = before
            raise

    def return_to_campaign(self):
        if self.fronts is not None:
            require(all(row["status"] != "active"
                        for row in self.fronts.timeline.fronts.values()),
                    "Fronts still active; abandon explicitly")
        elif self.battle is not None:
            require(self.finalized, "Combat still active; abandon explicitly")
        self.abandon_encounter()

    def abandon_encounter(self):
        """Discard uncompleted tactical progress, not already settled rewards."""
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()
