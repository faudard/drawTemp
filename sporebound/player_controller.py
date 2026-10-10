"""Headless player application controller. No Tk, audio or rendering imports.

The GUI calls only this facade. Each accepted player intent is checkpointed
using the unified, replay-validated session format (never legacy save slots).
"""
from __future__ import annotations

from pathlib import Path

from .ai import choose_command
from .game_session import GameSession
from .model import require
from .persistence import SessionStore


class PlayerController:
    def __init__(self, content, project, profile):
        project.validate(content)
        self.content = content
        self.project = project
        self.profile = Path(profile)
        self.session = None
        self.campaign_id = None
        self.slot = None

    def path_for(self, campaign_id, slot):
        require(self.project.campaign(campaign_id) is not None, "Unknown campaign")
        require(type(slot) is int and 1 <= slot <= self.project.save_slots, "Invalid slot")
        return (self.profile.with_name(self.profile.stem + "_session_saves")
                / campaign_id / ("slot_" + str(slot) + ".json"))

    def store(self):
        require(self.campaign_id is not None and self.slot is not None, "No save selected")
        return SessionStore(self.path_for(self.campaign_id, self.slot))

    def new_game(self, campaign_id, slot, *, overwrite=False, seed=1):
        path = self.path_for(campaign_id, slot)
        require(overwrite or not path.exists() and not SessionStore(path).backup.exists(),
                "Save already exists; explicit overwrite required")
        # Validate the previous generation without deleting it: SessionStore.save
        # retains the last verified checkpoint as a recovery backup.
        if overwrite and (path.exists() or SessionStore(path).backup.exists()):
            previous = SessionStore(path).load(self.content, self.project)
            require(previous.campaign_id == campaign_id, "Slot belongs to another campaign")
        candidate = GameSession.new(self.content, self.project, campaign_id, seed=seed)
        self.campaign_id, self.slot, self.session = campaign_id, slot, candidate
        self.save()
        return candidate

    def load_game(self, campaign_id, slot):
        path = self.path_for(campaign_id, slot)
        candidate = SessionStore(path).load(self.content, self.project)
        require(candidate.campaign_id == campaign_id, "Save belongs to another campaign")
        self.campaign_id, self.slot, self.session = campaign_id, slot, candidate
        return candidate

    def save(self):
        require(self.session is not None, "No campaign loaded")
        return self.store().save(self.session)

    def _apply(self, action, *args, **kwargs):
        require(self.session is not None, "No campaign loaded")
        # Verify before and after; restore in-memory state on persistence failure.
        old = self.session.recording()
        try:
            result = action(*args, **kwargs)
            self.save()
            return result
        except Exception:
            self.session = GameSession.from_recording(
                old, self.content, self.project)
            raise

    def choose_story_option(self, choice_id):
        return self._apply(self.session.choose_story_option, choice_id)

    def start_mission(self, mission_id):
        return self._apply(self.session.start_mission, mission_id)

    def execute(self, command):
        return self._apply(self.session.execute, command)

    def ai_turn(self):
        """Bound enemy activation: all decisions use engine behavior + session.execute."""
        require(self.session is not None and self.session.active_battle is not None,
                "No active encounter")
        battle = self.session.active_battle
        require(not battle.deploying and battle.active is not None
                and battle.active.team == "enemy", "Not an enemy activation")
        active = battle.active.id
        for _ in range(3):
            battle = self.session.active_battle
            if battle.result or battle.active is None or battle.active.id != active:
                break
            self.execute(choose_command(battle))

    def return_to_campaign(self):
        return self._apply(self.session.return_to_campaign)

    def abandon_encounter(self):
        return self._apply(self.session.abandon_encounter)

    def start_fronts(self, missions, focused):
        require(len(missions) >= 2, "Choose at least two sectors")
        return self._apply(self.session.start_fronts, missions, focused)

    def switch_front(self, name):
        return self._apply(self.session.switch_front, name)

    def set_doctrine(self, name, doctrine):
        return self._apply(self.session.set_doctrine, name, doctrine)

    def advance_fronts(self):
        return self._apply(self.session.advance_fronts)
