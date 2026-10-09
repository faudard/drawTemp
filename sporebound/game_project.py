"""High-level game presentation and campaign authoring; independent of Tk and Battle.

The project manifest is intentionally separate from the validated tactical
content v1, so editing a title screen cannot rewrite combat/replay contracts.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path

from .campaign import Campaign
from .model import RuleError, require
from .storage import write_json


@dataclass
class GameProject:
    title: str = 'Sporebound'
    subtitle: str = 'Une aventure tactique'
    campaigns: list[dict] = field(default_factory=list)
    options: dict = field(default_factory=lambda: {
        'language': 'fr', 'music_volume': 70, 'effects_volume': 70,
        'fullscreen': False,
    })
    save_slots: int = 3
    version: int = 1

    @classmethod
    def default(cls, content):
        first = next(iter(content.missions))
        return cls(campaigns=[{'id': 'main', 'name': 'Campagne principale',
                               'start_mission': first, 'description': ''}])

    @classmethod
    def from_dict(cls, data, content):
        require(isinstance(data, dict), 'Project must be an object')
        try:
            project = cls(**data)
        except (TypeError, ValueError) as exc:
            raise RuleError(f'Invalid project structure: {exc}') from exc
        project.validate(content)
        return project

    @classmethod
    def load(cls, path, content):
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')), content)

    def to_dict(self):
        return {'version': self.version, 'title': self.title, 'subtitle': self.subtitle,
                'campaigns': self.campaigns, 'options': self.options, 'save_slots': self.save_slots}

    def validate(self, content):
        require(type(self.version) is int and self.version == 1, 'Unsupported game project version')
        require(isinstance(self.title, str) and 0 < len(self.title.strip()) <= 120,
                'Title must contain 1..120 characters')
        require(isinstance(self.subtitle, str) and len(self.subtitle) <= 240,
                'Subtitle must contain at most 240 characters')
        require(type(self.save_slots) is int and 1 <= self.save_slots <= 9,
                'Save slots must be between 1 and 9')
        require(isinstance(self.options, dict), 'Options must be an object')
        require(set(self.options) == {'language', 'music_volume', 'effects_volume', 'fullscreen'},
                'Unknown or missing option')
        require(self.options['language'] in ('fr', 'en'), 'Language must be fr or en')
        require(type(self.options['fullscreen']) is bool, 'Fullscreen must be boolean')
        for key in ('music_volume', 'effects_volume'):
            volume = self.options[key]
            require(type(volume) is int and 0 <= volume <= 100, f'{key}: expected 0..100')
        require(isinstance(self.campaigns, list) and bool(self.campaigns),
                'At least one campaign required')
        ids = set()
        for campaign in self.campaigns:
            require(isinstance(campaign, dict) and
                    set(campaign) == {'id', 'name', 'description', 'start_mission'},
                    'Campaign needs id, name, description, start_mission')
            cid = campaign['id']
            require(isinstance(cid, str) and 0 < len(cid) <= 64 and
                    all(c.isalnum() or c in '-_' for c in cid) and cid not in ids,
                    'Invalid or duplicate campaign id')
            ids.add(cid)
            require(isinstance(campaign['name'], str) and 0 < len(campaign['name'].strip()) <= 120,
                    'Campaign needs a name')
            require(isinstance(campaign['description'], str) and len(campaign['description']) <= 1000,
                    'Campaign description too long')
            require(campaign['start_mission'] in content.missions,
                    f'Unknown starting mission: {campaign["start_mission"]}')

    def save(self, path, content):
        self.validate(content)
        write_json(path, self.to_dict())

    def campaign(self, campaign_id):
        return next((c for c in self.campaigns if c['id'] == campaign_id), None)

    def new_game(self, campaign_id, content):
        self.validate(content)
        campaign = self.campaign(campaign_id)
        require(campaign is not None, 'Unknown campaign')
        return Campaign(unlocked=[campaign['start_mission']])


def _slot_path(project_path, project, campaign_id, slot):
    require(project.campaign(campaign_id) is not None, 'Unknown campaign')
    require(type(slot) is int and 1 <= slot <= project.save_slots, 'Invalid save slot')
    path = Path(project_path)
    return path.with_name(path.stem + '_saves') / campaign_id / f'slot_{slot}.json'


def save_slot(project_path, project, content, campaign_id, slot, progress):
    """Atomic save using the existing Campaign format and strict slot paths."""
    project.validate(content)
    require(isinstance(progress, Campaign), 'No active campaign to save')
    require(set(progress.unlocked + progress.completed) <= set(content.missions),
            'Campaign references a mission that no longer exists')
    path = _slot_path(project_path, project, campaign_id, slot)
    progress.save(path)
    return path


def load_slot(project_path, project, content, campaign_id, slot):
    project.validate(content)
    path = _slot_path(project_path, project, campaign_id, slot)
    progress = Campaign.load(path)
    require(set(progress.unlocked + progress.completed) <= set(content.missions),
            'Save references a mission that no longer exists')
    return progress
