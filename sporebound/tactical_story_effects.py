"""Validated, deterministic tactical consequences of narrative choices.

No Tk dependency. The Battle replay remains the authority for tactical state;
GameSession alone authorizes choice commands against the project's StoryBook.
"""
from copy import deepcopy

from .model import require
from .rules.triggers import ValidationContext

SCHEMAS = {
    'open_door': ({'kind', 'object'}, {'kind', 'object'}),
    'hazard': ({'kind', 'pos', 'amount'}, {'kind', 'pos', 'amount'}),
    'status': ({'kind', 'unit', 'status', 'duration'},
               {'kind', 'unit', 'status', 'duration'}),
    'wave': ({'kind', 'actors'},
             {'kind', 'actors', 'max_active', 'lifetime'}),
}


def validate_tactical_effects(effects, content, mission_id, rules):
    """Validate a complete authoring payload for one precise battle mission."""
    require(mission_id in content.missions, 'Unknown tactical scene mission')
    mission = content.missions[mission_id]
    require(isinstance(effects, list) and len(effects) <= 12,
            'Tactical choice requires at most 12 effects')
    context = ValidationContext(
        mission.board, {unit.id for unit in mission.units}, rules,
        content.archetypes, {obj['id'] for obj in mission.objects})
    for effect in effects:
        require(isinstance(effect, dict), 'Tactical choice effect must be an object')
        kind = effect.get('kind')
        require(isinstance(kind, str) and kind in SCHEMAS,
                'Unknown tactical choice effect')
        required, allowed = SCHEMAS[kind]
        require(required <= set(effect) <= allowed,
                'Unknown or missing tactical choice effect fields')
        if kind == 'open_door':
            require(any(obj['id'] == effect['object'] and obj['kind'] == 'door'
                        for obj in mission.objects),
                    'Tactical choice references unknown door')
        else:
            rules.trigger_actions.get(kind).validate(context, effect)
            if kind == 'wave':
                require(len(effect['actors']) <= 8,
                        'Tactical dialogue reinforcement limited to 8 actors')


def apply_tactical_effects(battle, effects):
    """Only called inside Battle's atomic, journalled story-choice boundary."""
    validate_tactical_effects(effects, battle.content, battle.mission.id, battle.rules)
    for effect in effects:
        kind = effect['kind']
        if kind == 'open_door':
            obj = next(obj for obj in battle.mission.objects
                       if obj['id'] == effect['object'])
            obj['open'] = True
            obj['locked'] = False
            pos = tuple(obj['pos'])
            battle.board.tiles[pos] = deepcopy(battle.board.tile(pos))
            battle.board.tiles[pos].blocked = False
            battle.emit('story_door_opened', object=obj['id'])
        else:
            battle.rules.trigger_actions.get(kind).apply(battle, effect)
            battle.emit('story_tactical_effect', effect=kind)
