"""Validated transactional character, skill, class and equipment authoring.

All operations produce a new Content v1 document. A template edit cannot
silently rewrite actors already placed in missions or recorded in replays.
"""
from copy import deepcopy
from dataclasses import asdict

from .actors import TEMPLATE_FIELDS
from .authoring import _identifier, _mission
from .model import Content, Effect, Skill, require
from .rules import default_rules

SKILL_FIELDS = frozenset(Skill.__dataclass_fields__) - {'id', 'effects'}
EFFECT_FIELDS = frozenset(Effect.__dataclass_fields__)
ACTOR_FIELDS = frozenset(TEMPLATE_FIELDS) - {
    'patrol_route', 'facing', 'footprint', 'statuses', 'resistances'
}
INSTANCE_FIELDS = ACTOR_FIELDS | {'name', 'team'}
JOB_BONUSES = frozenset({'max_hp', 'max_mp', 'attack', 'magic', 'defense',
                          'magic_defense', 'move', 'speed'})
EQUIPMENT_BONUSES = JOB_BONUSES | {'weapon_power'}


def _validated(data):
    return Content.from_dict(data).to_dict()


def _skill(data, skill_id):
    return next((row for row in data['skills'] if row['id'] == skill_id), None)


def make_effect(kind='damage', *, power=5, element='physical',
                status='', duration=24, scope='target'):
    require(kind in default_rules().effects, 'Unsupported effect type')
    return asdict(Effect(kind=kind, power=power, element=element,
                         status=status, duration=duration, scope=scope))


def create_skill(data, skill_id, name, *, effect=None, target='enemy',
                 range=1, cost=0):
    _identifier(skill_id, 'Skill id')
    require(isinstance(name, str) and bool(name.strip()), 'Name required')
    new = deepcopy(data)
    require(_skill(new, skill_id) is None, 'Skill already exists')
    row = asdict(Skill(id=skill_id, name=name.strip(),
                       effects=[Effect(**(effect or make_effect()))],
                       target=target, range=range, cost=cost))
    new['skills'].append(row)
    return _validated(new)


def update_skill(data, skill_id, **changes):
    require(changes and set(changes) <= SKILL_FIELDS,
            'Unsupported skill property')
    new = deepcopy(data)
    row = _skill(new, skill_id)
    require(row is not None, 'Unknown skill')
    row.update(deepcopy(changes))
    return _validated(new)


def set_skill_effect(data, skill_id, index, effect, *, insert=False):
    require(isinstance(effect, dict) and set(effect) <= EFFECT_FIELDS
            and 'kind' in effect, 'Invalid effect specification')
    new = deepcopy(data)
    row = _skill(new, skill_id)
    require(row is not None, 'Unknown skill')
    effects = row['effects']
    if insert:
        require(type(index) is int and 0 <= index <= len(effects),
                'Invalid insertion index')
        effects.insert(index, deepcopy(effect))
    else:
        require(type(index) is int and 0 <= index < len(effects),
                'Unknown effect')
        effects[index] = deepcopy(effect)
    return _validated(new)


def remove_skill_effect(data, skill_id, index):
    new = deepcopy(data)
    row = _skill(new, skill_id)
    require(row is not None, 'Unknown skill')
    require(type(index) is int and 0 <= index < len(row['effects']),
            'Unknown effect')
    require(len(row['effects']) > 1, 'Skill must retain at least one effect')
    del row['effects'][index]
    return _validated(new)


def move_skill_effect(data, skill_id, index, direction):
    require(type(direction) is int and direction in (-1, 1),
            'Invalid effect direction')
    new = deepcopy(data)
    row = _skill(new, skill_id)
    require(row is not None and type(index) is int and
            0 <= index < len(row['effects']) and
            0 <= index + direction < len(row['effects']),
            'Cannot move effect outside skill')
    a = row['effects']
    a[index], a[index + direction] = a[index + direction], a[index]
    return _validated(new)


def remove_skill(data, skill_id):
    new = deepcopy(data)
    require(_skill(new, skill_id) is not None, 'Unknown skill')
    new['skills'] = [s for s in new['skills'] if s['id'] != skill_id]
    # Full validator rejects references from units, archetypes and jobs.
    return _validated(new)


def update_archetype(data, archetype_id, **changes):
    require(changes and set(changes) <= ACTOR_FIELDS,
            'Unsupported archetype property')
    new = deepcopy(data)
    require(archetype_id in new.get('archetypes', {}), 'Unknown archetype')
    new['archetypes'][archetype_id].update(deepcopy(changes))
    return _validated(new)


def update_mission_unit(data, mission_id, unit_id, **changes):
    require(changes and set(changes) <= INSTANCE_FIELDS,
            'Unsupported actor property')
    new = deepcopy(data)
    mission = _mission(new, mission_id)
    require(mission is not None, 'Unknown mission')
    actor = next((u for u in mission['units'] if u['id'] == unit_id), None)
    require(actor is not None, 'Unknown unit')
    for key in ('max_hp', 'max_mp'):
        if key in changes:
            resource = 'hp' if key == 'max_hp' else 'mp'
            if actor.get(resource) == actor.get(key):
                actor[resource] = changes[key]
    actor.update(deepcopy(changes))
    return _validated(new)


def create_job(data, job_id, name, *, requires='', requires_level=1,
               bonuses=None, skills=None):
    _identifier(job_id, 'Job id')
    require(isinstance(name, str) and bool(name.strip()), 'Job name required')
    new = deepcopy(data)
    require(job_id not in new.setdefault('jobs', {}), 'Job already exists')
    new['jobs'][job_id] = {'name': name.strip(), 'requires': requires,
                           'requires_level': requires_level,
                           'bonuses': deepcopy(bonuses or {}),
                           'skills': deepcopy(skills or {})}
    return _validated(new)


def update_job(data, job_id, *, name=None, requires=None, requires_level=None,
               bonuses=None, skills=None):
    new = deepcopy(data)
    row = new.setdefault('jobs', {}).get(job_id)
    require(row is not None, 'Unknown job')
    for key, value in (('name', name), ('requires', requires),
                       ('requires_level', requires_level), ('bonuses', bonuses),
                       ('skills', skills)):
        if value is not None:
            row[key] = deepcopy(value)
    return _validated(new)


def remove_job(data, job_id):
    new = deepcopy(data)
    require(job_id in new.get('jobs', {}), 'Unknown job')
    require(not any(j.get('requires') == job_id
                    for key, j in new['jobs'].items() if key != job_id),
            'Another job requires this one')
    del new['jobs'][job_id]
    return _validated(new)


def create_equipment(data, item_id, name, slot, *, price=0, bonuses=None):
    _identifier(item_id, 'Equipment id')
    require(isinstance(name, str) and bool(name.strip()), 'Equipment name required')
    new = deepcopy(data)
    require(item_id not in new.setdefault('equipment', {}),
            'Equipment already exists')
    new['equipment'][item_id] = {'name': name.strip(), 'slot': slot,
                                 'price': price, 'bonuses': deepcopy(bonuses or {})}
    return _validated(new)


def update_equipment(data, item_id, *, name=None, slot=None,
                     price=None, bonuses=None):
    new = deepcopy(data)
    item = new.setdefault('equipment', {}).get(item_id)
    require(item is not None, 'Unknown equipment')
    for key, value in (('name', name), ('slot', slot),
                       ('price', price), ('bonuses', bonuses)):
        if value is not None:
            item[key] = deepcopy(value)
    return _validated(new)


def remove_equipment(data, item_id):
    new = deepcopy(data)
    require(item_id in new.get('equipment', {}), 'Unknown equipment')
    del new['equipment'][item_id]
    return _validated(new)


def parse_bonuses(text, *, equipment=False):
    """Read comma-separated stat=integer pairs from a form."""
    require(isinstance(text, str), 'Invalid stat modifiers')
    allowed = EQUIPMENT_BONUSES if equipment else JOB_BONUSES
    result = {}
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        require(part.count('=') == 1, 'Use stat=integer')
        key, value = (piece.strip() for piece in part.split('='))
        require(key in allowed and key not in result, 'Unknown or duplicate stat bonus')
        require(value.isdecimal() and 0 <= int(value) <= 100,
                'Bonuses must be integers 0..100')
        result[key] = int(value)
    return result


def parse_skill_levels(text, skill_ids):
    """Read comma-separated skill=level pairs for a job."""
    require(isinstance(text, str), 'Invalid skill levels')
    result = {}
    known = set(skill_ids)
    for part in text.split(','):
        if not part.strip():
            continue
        require(part.count('=') == 1, 'Use skill=level')
        sid, level = (piece.strip() for piece in part.split('='))
        require(sid in known and sid not in result, 'Unknown or duplicate skill')
        require(level.isdecimal() and 1 <= int(level) <= 20,
                'Skill level must be 1..20')
        result[sid] = int(level)
    return result
