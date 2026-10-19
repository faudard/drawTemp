"""R42.A2: typed, scoped narrative flags over the ONE Campaign.story_flags ledger.

No new interpreter, persistence format or quest/reputation registry: R9
StoryBook.matches / choose still evaluate ordinary flag conditions/effects.
Scopes are persistent namespaces, not per-visit resets. LivingWorld/R35 faction
reputation remains authoritative separately and is never shadowed here.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require

PREFIX = 'r42_'
MAX_VARIABLES = 128
SCOPES = {'campaign', 'scene', 'mission'}
KINDS = {'bool', 'int', 'text', 'relation'}
_RANGES = {'int': (-1_000_000, 1_000_000), 'relation': (-100, 100)}
_CODE = {'campaign': 'c', 'scene': 's', 'mission': 'm'}


def _identifier(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(ch.isascii() and (ch.isalnum() or ch in '_-')
                    for ch in value))


def state_key(spec):
    """Stable name stored directly in existing Campaign.story_flags."""
    require(type(spec) is dict and type(spec.get('scope')) is str
            and spec['scope'] in SCOPES
            and _identifier(spec.get('owner')) and _identifier(spec.get('id')),
            'Invalid R42 variable identity')
    key = PREFIX + _CODE[spec['scope']] + '_' + spec['owner'] + '_' + spec['id']
    require(len(key) <= 64, 'R42 variable flag key exceeds Campaign limit')
    return key


def _value_allowed(kind, value):
    if kind == 'bool':
        return type(value) is bool
    if kind == 'text':
        return type(value) is str and len(value) <= 120
    if kind in _RANGES:
        lo, hi = _RANGES[kind]
        return type(value) is int and lo <= value <= hi
    return False


def _states(story):
    return story.get('state', []) if story.get('schema_version') == 2 else []


def _condition_references(node, definitions):
    if 'all' in node or 'any' in node:
        for child in node.get('all', node.get('any', [])):
            _condition_references(child, definitions)
    elif 'not' in node:
        _condition_references(node['not'], definitions)
    elif 'flag' in node and node['flag'].startswith(PREFIX):
        key = node['flag']
        require(key in definitions, 'Unknown R42 scoped variable condition')
        spec = definitions[key]
        operator = next(op for op in ('eq', 'gte', 'lte') if op in node)
        require(_value_allowed(spec['kind'], node[operator])
                and (operator == 'eq' or spec['kind'] in ('int', 'relation')),
                'R42 condition type or range mismatch')


def _effect_references(effect, definitions):
    key = effect.get('flag', '')
    if effect.get('kind') not in ('set_flag', 'add_flag') or not key.startswith(PREFIX):
        return
    require(key in definitions, 'Unknown R42 scoped variable effect')
    kind = definitions[key]['kind']
    if effect['kind'] == 'set_flag':
        require(_value_allowed(kind, effect['value']),
                'R42 set_flag violates declared type or bounds')
    else:
        require(kind in ('int', 'relation'), 'Cannot add to a non-integer R42 state')


def validate_state_catalog(story, content, campaigns):
    """Validate declaration owners and all use sites in the canonical R9 graph."""
    entries = _states(story)
    require(type(entries) is list and len(entries) <= MAX_VARIABLES,
            'R42 state catalog exceeds 128 variables')
    ids = {'campaign': {c['id'] for c in campaigns},
           'scene': {s['id'] for s in story['scenes']},
           'mission': set(content.missions)}
    definitions = {}
    for spec in entries:
        require(type(spec) is dict
                and set(spec) == {'id', 'kind', 'scope', 'owner', 'initial'},
                'Malformed R42 state declaration')
        key = state_key(spec)
        require(spec['owner'] in ids[spec['scope']],
                'Unknown canonical R42 state scope owner')
        require(type(spec['kind']) is str and spec['kind'] in KINDS
                and _value_allowed(spec['kind'], spec['initial']),
                'Invalid R42 typed initial value')
        require(key not in definitions, 'Duplicate R42 state variable key')
        definitions[key] = spec
    for scene in story['scenes']:
        for choice in scene['choices']:
            if 'when' in choice:
                _condition_references(choice['when'], definitions)
            for effect in choice.get('effects', []):
                _effect_references(effect, definitions)
    return definitions


def initialize_state(story, progress):
    """Initialize only on the first StoryBook.start; never change existing saves."""
    entries = _states(story)
    keys = [state_key(spec) for spec in entries]
    require(len(progress.story_flags) + len(keys) <= 1000,
            'R42 initial state exceeds Campaign flag budget')
    require(all(key not in progress.story_flags for key in keys),
            'R42 initial state flag collision')
    for spec, key in zip(entries, keys):
        progress.story_flags[key] = deepcopy(spec['initial'])


def verify_state(story, progress):
    """Fail closed on missing, wrong-type or out-of-range save values."""
    for spec in _states(story):
        key = state_key(spec)
        require(key in progress.story_flags and
                _value_allowed(spec['kind'], progress.story_flags[key]),
                'Invalid R42 saved narrative variable: ' + key)


def declare_state(project, content, *, identifier, kind, scope, owner, initial):
    """Copy-on-write authoring mutation suitable for AuthoringSession apply."""
    from .game_project import GameProject
    data = deepcopy(project.to_dict() if isinstance(project, GameProject)
                    else project)
    story = data.get('story', {})
    require(story.get('schema_version') == 2, 'R42 variables require narrative v2')
    story.setdefault('state', []).append({
        'id': identifier, 'kind': kind, 'scope': scope,
        'owner': owner, 'initial': initial})
    return GameProject.from_dict(data, content)


def _find(story, *, identifier, scope, owner):
    key = state_key({'id': identifier, 'scope': scope, 'owner': owner})
    matches = [spec for spec in _states(story) if state_key(spec) == key]
    require(len(matches) == 1, 'Unknown R42 scoped variable')
    return matches[0]


def state_condition(story, *, identifier, scope, owner, operator, value):
    """Compile to R9's existing typed condition language; no new evaluator."""
    spec = _find(story, identifier=identifier, scope=scope, owner=owner)
    require(operator in ('eq', 'gte', 'lte')
            and _value_allowed(spec['kind'], value)
            and (operator == 'eq' or spec['kind'] in ('int', 'relation')),
            'R42 condition operator/type mismatch')
    return {'flag': state_key(spec), operator: deepcopy(value)}


def state_effect(story, *, identifier, scope, owner, action, value):
    """Compile to R9's existing set_flag/add_flag effects."""
    spec = _find(story, identifier=identifier, scope=scope, owner=owner)
    require(action in ('set', 'add'), 'Unknown R42 state action')
    key = state_key(spec)
    if action == 'set':
        require(_value_allowed(spec['kind'], value),
                'R42 effect type or value mismatch')
        return {'kind': 'set_flag', 'flag': key, 'value': deepcopy(value)}
    require(spec['kind'] in ('int', 'relation') and type(value) is int
            and -10000 <= value <= 10000,
            'R42 numeric increment must fit existing add_flag contract')
    return {'kind': 'add_flag', 'flag': key, 'amount': value}


def state_snapshot(story, progress):
    """Detached inspection view; source of truth remains Campaign.story_flags."""
    verify_state(story, progress)
    return tuple({'id': spec['id'], 'kind': spec['kind'],
                  'scope': spec['scope'], 'owner': spec['owner'],
                  'flag': state_key(spec),
                  'value': deepcopy(progress.story_flags[state_key(spec)])}
                 for spec in _states(story))
