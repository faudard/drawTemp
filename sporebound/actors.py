"""Data-driven actor creation, independent of battle, AI and presentation.

Characters, monsters and summons use the same Unit contract. Kind is descriptive;
team controls allegiance and behavior controls intent selection.
"""
from copy import deepcopy
from dataclasses import fields

from .model import (Unit, require, TEAM_TACTICS, REACTIONS, SUPPORTS, MOVEMENTS, STATUSES)

SPAWN_FIELDS = {'id', 'name', 'team', 'pos', 'facing', 'hp', 'mp'}
RUNTIME_FIELDS = {'ct', 'moved', 'acted', 'cast', 'disengaging', 'statuses'}
TEMPLATE_FIELDS = {f.name for f in fields(Unit)} - SPAWN_FIELDS - RUNTIME_FIELDS - {'archetype'}
ACTOR_KINDS = {'character', 'monster', 'summon'}


class ActorFactory:
    def __init__(self, archetypes=None):
        self.archetypes = deepcopy({} if archetypes is None else archetypes)
        require(isinstance(self.archetypes, dict), 'Archetypes must be an object')
        for key, definition in self.archetypes.items():
            require(isinstance(key, str) and bool(key), 'Archetype needs an id')
            require(isinstance(definition, dict), f'{key}: archetype must be an object')
            require(set(definition) <= TEMPLATE_FIELDS, f'{key}: invalid archetype fields')

    def create(self, spawn):
        require(isinstance(spawn, dict), 'Actor spawn must be an object')
        key = spawn.get('archetype', '')
        require(not key or key in self.archetypes, f'Unknown archetype: {key}')
        values = {**deepcopy(self.archetypes.get(key, {})), **deepcopy(spawn)}
        values['pos'] = tuple(values['pos'])
        values['facing'] = tuple(values.get('facing', (0, 1)))
        values.setdefault('hp', values.get('max_hp', 40))
        values.setdefault('mp', values.get('max_mp', 12))
        return Unit(**values)


def validate_actor(u, skills, archetypes, rules):
    """Validate a resolved spawn or unused archetype independently of a mission."""
    def integer(value, low, high, label):
        require(type(value) is int and low <= value <= high, f'{label}: expected integer {low}..{high}')

    require(u.kind in ACTOR_KINDS, f"{u.id}: actor kind")
    require(u.behavior in rules.behaviors, f"{u.id}: unknown behavior")
    require(not u.archetype or u.archetype in archetypes, f"{u.id}: unknown archetype")
    require(isinstance(u.tags, list) and all(isinstance(tag, str) and tag for tag in u.tags)
            and len(set(u.tags)) == len(u.tags), f"{u.id}: invalid tags")
    require(u.team in {"player", "enemy"}, f"{u.id}: team")
    for key in ("max_hp", "speed", "weapon_power", "attack_range"):
        integer(getattr(u, key), 1, 10000, f"{u.id}.{key}")
    for key in ("max_mp", "attack", "magic", "defense", "magic_defense", "move", "jump", "min_range"):
        integer(getattr(u, key), 0, 10000, f"{u.id}.{key}")
    integer(u.hp, 1, u.max_hp, f"{u.id}.hp")
    integer(u.mp, 0, u.max_mp, f"{u.id}.mp")
    integer(u.ct, 0, 10000, f"{u.id}.ct")
    for key in ("brave", "faith", "class_evade", "shield_evade", "accessory_evade", "weapon_evade", "magic_evade"):
        integer(getattr(u, key), 0, 100, f"{u.id}.{key}")
    require(u.min_range <= u.attack_range, f"{u.id}: range")
    require(u.attack_range_mode in {"fixed", "los"}, f"{u.id}: attack_range_mode")
    integer(u.optimal_range, 0, 10000, f"{u.id}.optimal_range")
    integer(u.falloff_per_tile, 0, 100, f"{u.id}.falloff_per_tile")
    integer(u.engagement_range, -1, 8, f"{u.id}.engagement_range")
    require(all(t in TEAM_TACTICS for t in u.tactics), f"{u.id}: unknown tactic")
    require(u.weapon in {"melee", "spear", "ranged", "focus", "unarmed"}, f"{u.id}: weapon")
    require(u.facing in {(0, 1), (0, -1), (1, 0), (-1, 0)}, f"{u.id}: facing")
    require(u.reaction in REACTIONS and u.support in SUPPORTS and u.movement in MOVEMENTS, f"{u.id}: ability slot")
    require(all(s in skills for s in u.skills), f"{u.id}: unknown skill")
    require(u.cast is None and not u.moved and not u.acted and not u.disengaging, "Mission spawns cannot be mid-turn")
    for status, duration in u.statuses.items():
        require(status in STATUSES, f"{u.id}: status")
        integer(duration, -1, 10000, f"{u.id}.status duration")
        require(duration != 0, "Status duration must not be zero")
    for resistance in u.resistances.values():
        integer(resistance, -100, 100, "resistance")
