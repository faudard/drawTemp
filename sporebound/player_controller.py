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
        from .tactical_rpg3 import authored_rules_for_document
        self.rules = authored_rules_for_document(content.to_dict())
        self.project = project
        self.profile = Path(profile)
        self.session = None
        self.campaign_id = None
        self.slot = None
        self.last_load_status = None

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
        store = SessionStore(path)
        if overwrite and (path.exists() or store.backup.exists()):
            previous = self._load_compatible(store)
            require(previous.session.campaign_id == campaign_id,
                    "Slot belongs to another campaign")
        candidate = GameSession.new(self.content, self.project, campaign_id,
                                    seed=seed, rules=self.rules)
        # Publish before switching away from the current in-memory campaign.
        store.save(candidate)
        self.campaign_id, self.slot, self.session = campaign_id, slot, candidate
        self.last_load_status = None
        return candidate

    def load_game(self, campaign_id, slot, *, allow_legacy_default_rules=False):
        path = self.path_for(campaign_id, slot)
        outcome = self._load_compatible(
            SessionStore(path), allow_legacy_default_rules=allow_legacy_default_rules)
        require(not outcome.migrated_from_v1,
                "Legacy v1 save: explicitly migrate_game() before continuing")
        require(outcome.session.campaign_id == campaign_id,
                "Save belongs to another campaign")
        self.campaign_id, self.slot, self.session = campaign_id, slot, outcome.session
        self.last_load_status = outcome
        return outcome.session

    def _load_compatible(self, store, *, allow_legacy_default_rules=False):
        """Never switch gameplay rules silently when loading a replay."""
        from .model import RuleError
        from .rules import default_rules
        try:
            return store.load_with_status(self.content, self.project, rules=self.rules)
        except RuleError as error:
            if (not allow_legacy_default_rules or
                    self.rules.manifest() == default_rules().manifest()):
                raise
            try:
                # Caller opted into the *old* default rules, without converting
                # the journal to the current authored ruleset.
                return store.load_with_status(
                    self.content, self.project, rules=default_rules())
            except RuleError:
                raise error

    def migrate_game(self, campaign_id, slot, *, allow_legacy_default_rules=False):
        """User-initiated v1->v2 envelope upgrade; keep v1 bytes in .bak."""
        from .rules import default_rules
        rules = default_rules() if allow_legacy_default_rules else self.rules
        return SessionStore(self.path_for(campaign_id, slot)).migrate_v1(
            self.content, self.project, rules=rules, expected_campaign_id=campaign_id)

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
                old, self.content, self.project, rules=self.session.rules)
            raise

    def choose_story_option(self, choice_id):
        return self._apply(self.session.choose_story_option, choice_id)

    def explore_move(self, dx, dy):
        return self._apply(self.session.explore_move, dx, dy)

    def explore_interact(self, point_id):
        return self._apply(self.session.explore_interact, point_id)

    def explore_wait(self):
        return self._apply(self.session.explore_wait)

    def explore_actor(self, actor_id, action):
        return self._apply(self.session.explore_actor, actor_id, action)

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

    def available_sieges(self):
        require(self.session is not None, "No campaign loaded")
        return self.session.available_sieges()

    def start_configured_siege(self, siege_id):
        return self._apply(self.session.start_configured_siege, siege_id)

    def start_fronts(self, missions, focused):
        require(len(missions) >= 2, "Choose at least two sectors")
        return self._apply(self.session.start_fronts, missions, focused)

    def switch_front(self, name):
        return self._apply(self.session.switch_front, name)

    def set_doctrine(self, name, doctrine):
        return self._apply(self.session.set_doctrine, name, doctrine)

    def advance_fronts(self):
        return self._apply(self.session.advance_fronts)

    def send_reserves(self, destination, actors):
        return self._apply(self.session.send_reserves, destination, actors)

    def transfer_units(self, destination, placements):
        return self._apply(self.session.transfer_units, destination, placements)

    def escort_convoy(self, convoy_id):
        return self._apply(self.session.escort_convoy, convoy_id)

    def rescue_convoy(self, convoy_id):
        return self._apply(self.session.rescue_convoy, convoy_id)

    def select_route(self, route):
        return self._apply(self.session.select_route, route)

    def negotiate_front(self, front):
        return self._apply(self.session.negotiate_front, front)

    def partial_front(self, front):
        return self._apply(self.session.partial_front, front)

    def withdraw_front(self, front):
        return self._apply(self.session.withdraw_front, front)

    def start_recovery(self, front):
        return self._apply(self.session.start_recovery, front)

    def abandon_recovery(self, front):
        return self._apply(self.session.abandon_recovery, front)

