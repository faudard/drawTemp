"""Standalone player session; deliberately independent from the authoring UI.

A campaign is saved atomically per slot. A tactical battle is NOT silently
serialized as campaign progression. Completed battles are committed once.
"""
from pathlib import Path
from copy import deepcopy

from .ai import play_activation
from .campaign import Campaign
from .game_project import GameProject, load_slot, save_slot
from .model import Content, require
from .narrative import StoryBook


class PlayerSession:
    def __init__(self, content: Content, project: GameProject, profile: str | Path):
        project.validate(content)
        self.content=content
        self.project=project
        self.profile=Path(profile)
        self.story=StoryBook(project.story, content, project.campaigns)
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
        require(self.project.campaign(campaign_id) is not None, 'Unknown campaign')
        require(type(slot) is int and 1 <= slot <= self.project.save_slots, 'Invalid slot')
        # A corrupt/missing slot must not replace a valid current session.
        loaded=load_slot(self.profile,self.project,self.content,campaign_id,slot)
        self._select(campaign_id,slot)
        self.progress=loaded
        return self.progress

    def save(self):
        require(self.progress is not None and self.campaign_id is not None, 'No campaign loaded')
        require(self.battle is None or self.finalized, 'Finish the battle before saving campaign progression')
        return save_slot(self.profile,self.project,self.content,self.campaign_id,self.slot,self.progress)

    def learn_talent(self, unit_id, job_id, talent_id):
        """Buy one learned talent, committing the save before changing UI state."""
        require(self.progress is not None and self.campaign_id is not None,
                'No campaign loaded')
        require(self.battle is None or self.finalized,
                'Cannot change the roster during combat')
        require(any(unit.team == 'player' and unit.id == unit_id
                    for mission in self.content.missions.values()
                    for unit in mission.units),
                'Unknown player hero')
        updated = deepcopy(self.progress)
        updated.learn_talent(self.content, unit_id, job_id, talent_id)
        # Save before assigning; a disk failure cannot spend JP in memory.
        save_slot(self.profile, self.project, self.content,
                  self.campaign_id, self.slot, updated)
        self.progress = updated
        return self.progress.talent_catalog(self.content, unit_id, job_id)

    def active_scene(self):
        require(self.progress is not None, 'No campaign loaded')
        return self.story.active_scene(self.progress)

    def available_choices(self):
        require(self.progress is not None, 'No campaign loaded')
        return self.story.choices(self.progress)

    def choose_story(self, choice_id):
        require(self.progress is not None and (self.battle is None or self.finalized),
                'Cannot choose dialogue during combat')
        updated = self.story.choose(self.progress, choice_id)
        # Persist one coherent snapshot containing campaign and narrative state.
        save_slot(self.profile, self.project, self.content,
                  self.campaign_id, self.slot, updated)
        self.progress = updated
        return self.active_scene()

    def available_missions(self):
        require(self.progress is not None, 'No campaign loaded')
        if self.progress.story_pending:
            return []
        return [mid for mid in self.progress.unlocked if mid not in self.progress.completed]

    def begin(self, mission_id):
        require(self.progress is not None and self.battle is None, 'Return to campaign before starting a mission')
        require(not self.progress.story_pending, 'Resolve the pending dialogue first')
        require(mission_id in self.available_missions(), 'Mission is not currently available')
        mission = self.content.missions[mission_id]
        advanced = any(
            unit.behavior in {"coordinated", "phase_boss"} or
            any(tag in {"medic", "healer", "protector"}
                or tag.startswith(("formation:", "boss_phase:"))
                for tag in unit.tags)
            for unit in mission.units)
        if advanced:
            from .tactical_rpg3 import tactical_rpg_rules
            self.battle = self.progress.prepare(
                self.content, mission_id, ruleset=tactical_rpg_rules())
        else:
            self.battle = self.progress.prepare(self.content, mission_id)
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
            updated = deepcopy(self.progress)
            mission_id = self.battle.mission.id
            route_choice = (self.battle.result == 'victory'
                            and mission_id in self.story.after)
            changed = updated.finish(self.battle, unlock_next=not route_choice)
            if changed and route_choice:
                self.story.after_victory(updated, mission_id)
            # Commit only if both reward and narrative state persist successfully.
            save_slot(self.profile, self.project, self.content,
                      self.campaign_id, self.slot, updated)
            self.progress = updated
            self.finalized = True

    def return_to_campaign(self):
        require(self.battle is None or self.finalized, 'Cannot abandon an unresolved battle without confirmation')
        self.battle=None
        self.finalized=False

    def abandon_battle(self):
        """Discard only the uncommitted battle; campaign remains unchanged."""
        self.battle=None
        self.finalized=False
