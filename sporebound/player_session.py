"""Standalone player session; deliberately independent from the authoring UI.

A campaign is saved atomically per slot. A tactical battle is NOT silently
serialized as campaign progression. Completed battles are committed once.
"""
from pathlib import Path

from .ai import play_activation
from .campaign import Campaign
from .game_project import GameProject, load_slot, save_slot
from .model import Content, require


class PlayerSession:
    def __init__(self, content: Content, project: GameProject, profile: str | Path):
        project.validate(content)
        self.content=content
        self.project=project
        self.profile=Path(profile)
        self.campaign_id=None
        self.slot=None
        self.progress=None
        self.battle=None
        self.finalized=False

    def _select(self, campaign_id, slot):
        require(self.project.campaign(campaign_id) is not None, 'Unknown campaign')
        require(type(slot) is int and 1 <= slot <= self.project.save_slots, 'Invalid slot')
        self.campaign_id=campaign_id
        self.slot=slot
        self.battle=None
        self.finalized=False

    def new_game(self, campaign_id, slot):
        """Explicit new-game action; never overwrite an existing slot silently."""
        self._select(campaign_id, slot)
        progress=self.project.new_game(campaign_id,self.content)
        self.progress=progress
        self.save()
        return progress

    def load_game(self, campaign_id, slot):
        self._select(campaign_id,slot)
        # Only commit progress after loading succeeds.
        self.progress=load_slot(self.profile,self.project,self.content,campaign_id,slot)
        return self.progress

    def save(self):
        require(self.progress is not None and self.campaign_id is not None, 'No campaign loaded')
        require(self.battle is None or self.finalized, 'Finish the battle before saving campaign progression')
        return save_slot(self.profile,self.project,self.content,self.campaign_id,self.slot,self.progress)

    def available_missions(self):
        require(self.progress is not None, 'No campaign loaded')
        return [mid for mid in self.progress.unlocked if mid not in self.progress.completed]

    def begin(self, mission_id):
        require(self.progress is not None and self.battle is None, 'Return to campaign before starting a mission')
        require(mission_id in self.available_missions(), 'Mission is not currently available')
        self.battle=self.progress.prepare(self.content,mission_id)
        self.finalized=False
        self._finish_if_done()
        return self.battle

    def command(self, action):
        require(self.battle is not None and not self.finalized, 'No active combat')
        self.battle.execute(action)
        self._finish_if_done()

    def ai_turn(self):
        require(self.battle is not None and not self.finalized and not self.battle.deploying,
                'No active AI turn')
        require(self.battle.active is not None and self.battle.active.team == 'enemy',
                'It is not an enemy turn')
        play_activation(self.battle)
        self._finish_if_done()

    def _finish_if_done(self):
        if self.battle is not None and self.battle.result in ('victory','defeat') and not self.finalized:
            self.progress.finish(self.battle)
            self.finalized=True
            self.save()

    def return_to_campaign(self):
        require(self.battle is None or self.finalized, 'Cannot abandon an unresolved battle without confirmation')
        self.battle=None
        self.finalized=False

    def abandon_battle(self):
        """Discard only the uncommitted battle; campaign remains unchanged."""
        self.battle=None
        self.finalized=False
