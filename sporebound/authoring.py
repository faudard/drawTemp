"""Validated, undo-friendly operations used by the Tk authoring tools.

All operations return a new document; callers decide when to commit it to
their undo stack.  No mutation reaches a live Battle or Campaign.
"""
from copy import deepcopy

from .model import Content, RuleError, require
from .tactical_rpg3 import authored_rules_for_document


def _mission(data, mid):
    return next((m for m in data['missions'] if m['id'] == mid), None)


def _edit(data, mid, change):
    new = deepcopy(data)
    mission = _mission(new, mid)
    require(mission is not None, f'Unknown mission: {mid}')
    change(new, mission)
    return Content.from_dict(
        new, rules=authored_rules_for_document(new)).to_dict()


def _identifier(value, label):
    require(isinstance(value, str) and value.strip() and
            all(c.isalnum() or c in '_-' for c in value) and len(value) <= 64,
            f'{label} must be a unique identifier (letters, digits, _ or -)')
    return value


def _cell(m, pos):
    require(isinstance(pos, (list, tuple)) and len(pos) == 2 and
            all(type(x) is int for x in pos) and
            0 <= pos[0] < m['board']['width'] and 0 <= pos[1] < m['board']['height'],
            'Choose a cell inside the map')
    return list(pos)


def resize_map(data, mid, width, height):
    require(type(width) is int and type(height) is int and 1 <= width <= 128 and
            1 <= height <= 128, 'Map size must be between 1 and 128')
    def change(_, m):
        m['board']['width'], m['board']['height'] = width, height
        # Shrinking may not silently discard objectives, objects, or actors.
        m['board']['tiles'] = [t for t in m['board']['tiles']
                                if t['pos'][0] < width and t['pos'][1] < height]
    return _edit(data, mid, change)


def add_unit(data, mid, uid, name, team, pos):
    _identifier(uid, 'Unit id')
    require(team in ('player', 'enemy', 'neutral'), 'Invalid team')
    require(isinstance(name, str) and bool(name.strip()), 'Unit needs a name')
    def change(doc, m):
        cell = _cell(m, pos)
        require(all(u['id'] != uid for u in m['units']), 'Unit id already exists')
        # Inherit the complete working combat contract, not a partial actor.
        source = next((u for candidate in [m, *doc['missions']]
                       for u in candidate['units'] if u['team'] == team), None)
        require(source is not None, f'No existing {team} unit to use as a template')
        unit = deepcopy(source)
        unit.update(id=uid, name=name.strip(), team=team, pos=cell)
        unit['hp'] = unit['max_hp']
        unit['mp'] = unit['max_mp']
        m['units'].append(unit)
    return _edit(data, mid, change)


def remove_unit(data, mid, uid):
    def change(_, m):
        require(any(u['id'] == uid for u in m['units']), 'Unknown unit')
        m['units'] = [u for u in m['units'] if u['id'] != uid]
    return _edit(data, mid, change)



def set_unit_combat_role(data, mid, uid, *, role="none", formation="none",
                         escort_target=""):
    """Studio 2.7 authoring: preserve unrelated tags and undo via one document edit.

    These are loadout/initial formation tags; the enhanced 2.7 ruleset owns
    their runtime effects. Legacy content and editors remain valid.
    """
    require(role in {"none", "medic", "protector"}, "Unknown tactical role")
    require(formation in {"none", "shield_wall", "phalanx", "escort"},
            "Unknown initial formation")
    require(isinstance(escort_target, str), "Invalid escort target")

    def change(_, mission):
        unit = next((u for u in mission["units"] if u["id"] == uid), None)
        require(unit is not None, "Unknown tactical unit")
        if formation == "phalanx":
            require(unit["weapon"] == "spear", "Phalanx requires spear")
        if formation == "escort":
            ally = next((u for u in mission["units"]
                         if u["id"] == escort_target and u["team"] == unit["team"]
                         and u["id"] != uid and u["hp"] > 0), None)
            require(ally is not None, "Escort requires an existing allied unit")
            from .model import distance
            require(distance(tuple(unit["pos"]), tuple(ally["pos"])) <= 2,
                    "Escort initial target out of range")
        else:
            require(not escort_target.strip(), "Only escort may specify a target")
        tags = [tag for tag in unit.get("tags", [])
                if tag not in {"medic", "protector"}
                and not tag.startswith("formation:")]
        if role != "none":
            tags.append(role)
        if formation != "none":
            tags.append("formation:" + formation
                        + (":" + escort_target if formation == "escort" else ""))
        unit["tags"] = tags

    return _edit(data, mid, change)



def upsert_job_talent(data, job_id, talent_id, *, jp=1, requires=(),
                      exclusive="", stat="", bonus=0, skills=()):
    """Edit one talent in a global job tree, atomically and without raw JSON.

    Talent edges (requires) are validated by Content.validate; cycles and
    dangling dependencies cannot enter an undoable Studio document.
    """
    _identifier(talent_id, "Talent id")
    require(isinstance(job_id, str) and job_id in data.get("jobs", {}),
            "Unknown job")
    require(type(jp) is int and 1 <= jp <= 20, "Talent JP cost must be 1..20")
    require(isinstance(requires, (tuple, list)) and
            all(isinstance(x, str) for x in requires), "Invalid prerequisites")
    require(isinstance(skills, (tuple, list)) and
            all(isinstance(x, str) for x in skills), "Invalid skill references")
    require(isinstance(exclusive, str) and isinstance(stat, str),
            "Invalid talent metadata")
    from .builds3 import STATS
    require(stat in STATS or (stat == "" and bonus == 0),
            "Choose a supported talent stat")
    require(type(bonus) is int and 0 <= bonus <= 100, "Invalid talent bonus")
    row = {"jp": jp}
    if requires:
        row["requires"] = list(requires)
    if exclusive:
        row["exclusive"] = exclusive
    if stat:
        row["bonuses"] = {stat: bonus}
    if skills:
        row["skills"] = list(skills)
    new = deepcopy(data)
    new["jobs"][job_id].setdefault("talents", {})[talent_id] = row
    return Content.from_dict(
        new, rules=authored_rules_for_document(new)).to_dict()


def remove_job_talent(data, job_id, talent_id):
    """Prevent dangling edges; removal is a single undoable edit."""
    require(job_id in data.get("jobs", {}), "Unknown job")
    new = deepcopy(data)
    talents = new["jobs"][job_id].get("talents", {})
    require(talent_id in talents, "Unknown talent")
    require(not any(talent_id in spec.get("requires", [])
                    for name, spec in talents.items() if name != talent_id),
            "Cannot remove a prerequisite used by another talent")
    del talents[talent_id]
    return Content.from_dict(
        new, rules=authored_rules_for_document(new)).to_dict()


def add_object(data, mid, oid, kind, pos, *, link='', destination=None):
    _identifier(oid, 'Object id')
    require(kind in ('door', 'switch', 'chest', 'ram', 'catapult', 'passage', 'defense'),
            'Unknown object type')
    def change(_, m):
        cell = _cell(m, pos)
        require(all(o['id'] != oid for o in m['objects']), 'Object id already exists')
        obj = {'id': oid, 'kind': kind, 'pos': cell}
        if kind in ('switch', 'ram', 'catapult'):
            require(any(o['id'] == link and o['kind'] == 'door' for o in m['objects']),
                    'Choose an existing door id for this object')
            obj['link'] = link
        elif kind == 'passage':
            obj['destination'] = _cell(m, destination)
        elif kind == 'defense':
            obj.update(team='enemy', cells=[cell], charges=2, power=15)
        m['objects'].append(obj)
    return _edit(data, mid, change)


def remove_object(data, mid, oid):
    def change(_, m):
        require(any(o['id'] == oid for o in m['objects']), 'Unknown object')
        m['objects'] = [o for o in m['objects'] if o['id'] != oid]
    return _edit(data, mid, change)


def add_event(data, mid, eid, *, condition, action='message', pos=None,
              tick=10, unit='', text='', amount=4):
    """Small guided subset of engine trigger rules; JSON retains advanced rules."""
    _identifier(eid, 'Event id')
    require(condition in ('tick', 'enter', 'defeated', 'hp_below'), 'Unknown condition')
    require(action in ('message', 'hazard'), 'Unknown action')
    def change(_, m):
        require(all(t['id'] != eid for t in m['triggers']), 'Event id already exists')
        event = {'id': eid, 'condition': condition}
        if condition == 'tick':
            event['value'] = tick
        elif condition == 'enter':
            event['pos'] = _cell(m, pos)
        elif condition in ('defeated', 'hp_below'):
            require(any(u['id'] == unit for u in m['units']), 'Select an existing unit')
            event['unit'] = unit
            if condition == 'hp_below':
                event['percent'] = 50
        if action == 'message':
            event['actions'] = [{'kind': 'message', 'text': text}]
        else:
            event['actions'] = [{'kind': 'hazard', 'pos': _cell(m, pos), 'amount': amount}]
        m['triggers'].append(event)
    return _edit(data, mid, change)


def remove_event(data, mid, eid):
    def change(_, m):
        require(any(e['id'] == eid for e in m['triggers']), 'Unknown event')
        m['triggers'] = [e for e in m['triggers'] if e['id'] != eid]
    return _edit(data, mid, change)


def add_blank_mission(data, mid, name, width=8, height=8):
    """Create a playable blank board with two existing actor templates."""
    _identifier(mid, 'Mission id')
    require(isinstance(name, str) and bool(name.strip()), 'Mission needs a name')
    require(type(width) is int and type(height) is int and 4 <= width <= 128 and
            4 <= height <= 128, 'Blank map size must be between 4 and 128')
    new = deepcopy(data)
    require(_mission(new, mid) is None, 'Mission id already exists')
    template = new['missions'][0]
    actors = []
    for team, pos in [('player', [1, height - 2]), ('enemy', [width - 2, 1])]:
        original = next((u for m in new['missions'] for u in m['units']
                         if u['team'] == team and tuple(u.get('footprint', (1, 1))) == (1, 1)), None)
        require(original is not None, f'A single-cell {team} actor is required')
        actor = deepcopy(original)
        actor['pos'] = pos
        actors.append(actor)
    mission = deepcopy(template)
    mission.update(id=mid, name=name.strip(),
                   board={'width': width, 'height': height, 'tiles': []},
                   units=actors, objective='eliminate', goal=[], objects=[],
                   triggers=[], deployment=[], protected_id='', relic=None,
                   next_missions=[])
    new['missions'].append(mission)
    return Content.from_dict(
        new, rules=authored_rules_for_document(new)).to_dict()


def set_mission_properties(data, mid, *, name, objective, reward, next_missions):
    require(isinstance(name, str) and bool(name.strip()), 'Mission needs a name')
    require(isinstance(next_missions, list), 'Next missions must be a list')
    def change(_, m):
        m['name'] = name.strip()
        m['objective'] = objective
        m['reward'] = reward
        m['next_missions'] = next_missions
    return _edit(data, mid, change)
