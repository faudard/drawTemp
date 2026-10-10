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
        available = set(self.available_missions())
        require(all(isinstance(name, str) and bool(name) and
                    isinstance(mid, str) and mid in available
                    for name, mid in missions.items()), "Front mission is locked")
        require(len(set(missions.values())) == len(missions),
                "Duplicate mission in fronts")
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
            require(not (self.fronts.rescue_battles or self.fronts.pursuit_battles
                         or self.fronts.recovery_battles),
                    "Finish tactical side missions first")
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

    def recording(self):
        """Portable v1 checkpoint; embedded tactical journals verify by replay."""
        tactical = None
        if self.battle is not None:
            tactical = self.battle.recording()
            Battle.replay(tactical, rules=self.rules)
        elif self.fronts is not None:
            tactical = self.fronts.recording()
            MultiFrontSession.replay(tactical, rules=self.rules)
        data = {
            "version": self.VERSION, "kind": "game_session",
            "campaign_id": self.campaign_id, "seed": self.seed,
            "content_digest": digest(self.content.to_dict()),
            "project_digest": digest(self.project.to_dict()),
            "rules": self.rules.manifest(),
            "progress": {"version": 1, **asdict(self.progress)},
            "mode": self.mode, "tactical": tactical,
            "finalized": self.finalized,
            "settled_fronts": sorted(self.settled_fronts),
        }
        return {**data, "digest": digest(data)}

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def from_recording(cls, data, content, project, *, rules=None):
        require(isinstance(data, dict) and data.get("version") == cls.VERSION
                and data.get("kind") == "game_session", "Unsupported game session")
        require(set(data) == {"version", "kind", "campaign_id", "seed",
                "content_digest", "project_digest", "rules", "progress",
                "mode", "tactical", "finalized", "settled_fronts", "digest"},
                "Malformed game session")
        require(data["digest"] == digest({k: v for k, v in data.items()
                                         if k != "digest"}), "Game session checksum mismatch")
        rules = rules if rules is not None else default_rules()
        require(data["content_digest"] == digest(content.to_dict()), "Content mismatch")
        require(data["project_digest"] == digest(project.to_dict()), "Project mismatch")
        require(data["rules"] == rules.manifest(), "Ruleset mismatch")
        session = cls(content, project, data["campaign_id"],
                      seed=data["seed"], rules=rules)
        session.progress = Campaign.from_dict(data["progress"], ruleset=rules)
        session.story.initialize(session.progress, session.campaign_id)
        require(set(session.progress.unlocked + session.progress.completed)
                <= set(session.content.missions), "Unknown campaign mission")
        mode = data["mode"]
        require(mode in {"campaign", "battle", "fronts"}, "Invalid session mode")
        settled = data["settled_fronts"]
        require(isinstance(settled, list) and all(isinstance(s, str) for s in settled)
                and len(set(settled)) == len(settled), "Invalid settlement log")
        require(type(data["finalized"]) is bool, "Invalid finalization flag")
        if mode == "campaign":
            require(data["tactical"] is None and not data["finalized"] and not settled,
                    "Idle session has tactical state")
        elif mode == "battle":
            require(isinstance(data["tactical"], dict) and not settled,
                    "Invalid standalone battle state")
            session.battle = Battle.replay(data["tactical"], rules=rules)
            require(session.battle.mission.id in
                    session.progress.unlocked + session.progress.completed,
                    "Unknown or locked tactical mission")
            session.finalized = data["finalized"]
            require(session.finalized == (session.battle.result in ("victory", "defeat")),
                    "Battle finalization mismatch")
        else:
            require(isinstance(data["tactical"], dict) and not data["finalized"],
                    "Invalid multi-front state")
            session.fronts = MultiFrontSession.replay(data["tactical"], rules=rules)
            require(set(session.fronts.missions.values()) <=
                    set(session.progress.unlocked + session.progress.completed)
                    and set(settled) <= set(session.fronts.missions),
                    "Unknown multi-front mission or settlement")
            for front, battle in session.fronts.battles.items():
                require((front in settled) == (battle.result in ("victory", "defeat")),
                        "Front finalization mismatch")
            session.settled_fronts = set(settled)
        return session

    @classmethod
    def load(cls, path, content, project, *, rules=None):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls.from_recording(data, content, project, rules=rules)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuleError(f"Invalid game session: {exc}") from exc
