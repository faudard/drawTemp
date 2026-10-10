"""Validated narrative graph, conditional dialogue, and persistent campaign decisions.

Story rules live in the optional GameProject.story section. No executable
scripts or new Battle commands are needed. Existing missions/replays keep their
Content v1 serialization and Campaign slots stay backward-compatible.
"""
from copy import deepcopy
import hashlib
import json

from .model import RuleError, require


def _id(value, label):
    require(isinstance(value, str) and 0 < len(value) <= 64
            and all(ch.isalnum() or ch in '_-' for ch in value),
            f'{label}: expected non-empty safe identifier')


def _scalar(value):
    return type(value) in (bool, int, str) and (
        type(value) is not str or len(value) <= 120)


def _condition(expression, content, depth=0):
    require(depth <= 8 and isinstance(expression, dict), 'Invalid narrative condition')
    if 'all' in expression or 'any' in expression:
        key = 'all' if 'all' in expression else 'any'
        require(set(expression) == {key} and isinstance(expression[key], list)
                and bool(expression[key]), 'Invalid logical condition')
        for child in expression[key]:
            _condition(child, content, depth + 1)
    elif 'not' in expression:
        require(set(expression) == {'not'}, 'Invalid negated condition')
        _condition(expression['not'], content, depth + 1)
    elif 'flag' in expression:
        _id(expression['flag'], 'Flag')
        operations = set(expression) - {'flag'}
        require(len(operations) == 1 and operations <= {'eq', 'gte', 'lte'},
                'Flag condition must use eq, gte or lte')
        op = next(iter(operations))
        value = expression[op]
        require(_scalar(value) and (op == 'eq' or type(value) is int),
                'Invalid flag comparison value')
    elif 'completed_mission' in expression:
        require(set(expression) == {'completed_mission'}
                and expression['completed_mission'] in content.missions,
                'Unknown completed mission in condition')
    elif 'gold_gte' in expression:
        require(set(expression) == {'gold_gte'} and type(expression['gold_gte']) is int
                and 0 <= expression['gold_gte'] <= 1000000, 'Invalid gold condition')
    else:
        raise RuleError('Unknown narrative condition')


def _effect(effect, content):
    require(isinstance(effect, dict), 'Narrative effect must be an object')
    kind = effect.get('kind')
    if kind == 'set_flag':
        require(set(effect) == {'kind', 'flag', 'value'} and _scalar(effect['value']),
                'Invalid set_flag effect')
        _id(effect['flag'], 'Flag')
    elif kind == 'add_flag':
        require(set(effect) == {'kind', 'flag', 'amount'}
                and type(effect['amount']) is int and -10000 <= effect['amount'] <= 10000,
                'Invalid add_flag effect')
        _id(effect['flag'], 'Flag')
    elif kind == 'unlock_mission':
        require(set(effect) == {'kind', 'mission'} and effect['mission'] in content.missions,
                'Unknown mission to unlock')
    elif kind == 'gold':
        require(set(effect) == {'kind', 'amount'}
                and type(effect['amount']) is int and -10000 <= effect['amount'] <= 10000,
                'Invalid gold effect')
    else:
        raise RuleError(f'Unknown narrative effect: {kind}')


def validate_story(raw, content, campaigns):
    """Strict authoring validation, no mutation and no unbounded scene chains."""
    require(isinstance(raw, dict), 'Story must be an object')
    if not raw:
        return
    require(set(raw) <= {'scenes', 'entry_scenes', 'after_mission'}, 'Unknown story field')
    scenes = raw.get('scenes')
    require(isinstance(scenes, list) and bool(scenes), 'Story requires scenes')
    ids, edges = set(), {}
    for scene in scenes:
        require(isinstance(scene, dict) and
                set(scene) == {'id', 'title', 'speaker', 'text', 'choices'}, 'Invalid scene')
        sid = scene['id']
        _id(sid, 'Scene id')
        require(sid not in ids, 'Duplicate scene id')
        ids.add(sid)
        for key, limit in (('title', 120), ('speaker', 120), ('text', 5000)):
            require(isinstance(scene[key], str) and len(scene[key]) <= limit
                    and (key == 'speaker' or bool(scene[key].strip())),
                    f'Invalid scene {key}')
        choices = scene['choices']
        require(isinstance(choices, list) and 1 <= len(choices) <= 20,
                'A scene needs 1..20 choices')
        choice_ids, links = set(), []
        has_default = False
        for choice in choices:
            require(isinstance(choice, dict) and
                    {'id', 'label'} <= set(choice) <=
                    {'id', 'label', 'when', 'effects', 'next_scene'},
                    'Invalid choice')
            _id(choice['id'], 'Choice id')
            require(choice['id'] not in choice_ids, 'Duplicate choice id')
            choice_ids.add(choice['id'])
            require(isinstance(choice['label'], str) and
                    0 < len(choice['label'].strip()) <= 240, 'Invalid choice label')
            if 'when' in choice:
                _condition(choice['when'], content)
            else:
                has_default = True
            effects = choice.get('effects', [])
            require(isinstance(effects, list) and len(effects) <= 20, 'Invalid effects list')
            for effect in effects:
                _effect(effect, content)
            if 'next_scene' in choice:
                _id(choice['next_scene'], 'Next scene')
                links.append(choice['next_scene'])
        require(has_default, f'Scene {sid} needs an unconditional fallback choice')
        edges[sid] = links
    campaign_ids = {c['id'] for c in campaigns}
    entries = raw.get('entry_scenes', {})
    outcomes = raw.get('after_mission', {})
    require(isinstance(entries, dict) and isinstance(outcomes, dict),
            'Story links must be objects')
    require(set(entries) <= campaign_ids, 'Unknown narrative campaign')
    require(set(outcomes) <= set(content.missions), 'Unknown narrative mission')
    for ref in [*entries.values(), *outcomes.values(),
                *(dest for links in edges.values() for dest in links)]:
        require(ref in ids, f'Unknown narrative scene: {ref}')
    # No scene can cause unbounded automatic/interactive narrative loops.
    colors = {}
    def visit(node):
        require(colors.get(node) != 1, 'Narrative scene cycle')
        if colors.get(node) == 2:
            return
        colors[node] = 1
        for child in edges[node]:
            visit(child)
        colors[node] = 2
    for sid in ids:
        visit(sid)


def matches(expression, progress):
    if 'all' in expression:
        return all(matches(child, progress) for child in expression['all'])
    if 'any' in expression:
        return any(matches(child, progress) for child in expression['any'])
    if 'not' in expression:
        return not matches(expression['not'], progress)
    if 'completed_mission' in expression:
        return expression['completed_mission'] in progress.completed
    if 'gold_gte' in expression:
        return progress.gold >= expression['gold_gte']
    observed = progress.story_flags.get(expression['flag'])
    if 'eq' in expression:
        return type(observed) is type(expression['eq']) and observed == expression['eq']
    target = expression.get('gte', expression.get('lte'))
    if type(observed) is not int:
        return False
    return observed >= target if 'gte' in expression else observed <= target


class StoryBook:
    def __init__(self, raw, content, campaigns):
        validate_story(raw, content, campaigns)
        self.raw = deepcopy(raw)
        self.scenes = {scene['id']: scene for scene in raw.get('scenes', [])}
        self.entry = dict(raw.get('entry_scenes', {}))
        self.after = dict(raw.get('after_mission', {}))
        self.digest = (hashlib.sha256(json.dumps(raw, sort_keys=True,
                       ensure_ascii=False).encode('utf-8')).hexdigest() if raw else '')

    def initialize(self, progress, campaign_id):
        if progress.story_started:
            require(progress.story_digest == self.digest, 'Story definition differs from saved campaign')
            return
        require(not progress.story_digest or progress.story_digest == self.digest,
                'Story definition differs from saved campaign')
        progress.story_started = True
        progress.story_digest = self.digest
        # A legacy saved campaign with finished missions does not restart an intro.
        if not progress.completed:
            progress.story_pending = self.entry.get(campaign_id, '')

    def after_victory(self, progress, mission_id):
        scene = self.after.get(mission_id, '')
        if scene:
            require(not progress.story_pending, 'Finish the current story scene first')
            progress.story_pending = scene

    def active_scene(self, progress):
        if not progress.story_pending:
            return None
        require(progress.story_digest == self.digest, 'Story definition differs from saved campaign')
        scene = self.scenes.get(progress.story_pending)
        require(scene is not None, 'Unknown pending narrative scene')
        return deepcopy(scene)

    def choices(self, progress):
        scene = self.active_scene(progress)
        if scene is None:
            return []
        return [deepcopy(choice) for choice in scene['choices']
                if 'when' not in choice or matches(choice['when'], progress)]

    def choose(self, progress, choice_id):
        """Apply one validated choice to a copy; no partial story mutations."""
        scene = self.active_scene(progress)
        require(scene is not None, 'No active story scene')
        selected = next((c for c in self.choices(progress) if c['id'] == choice_id), None)
        require(selected is not None, 'Choice is unavailable')
        updated = deepcopy(progress)
        for effect in selected.get('effects', []):
            kind = effect['kind']
            if kind == 'set_flag':
                updated.story_flags[effect['flag']] = deepcopy(effect['value'])
            elif kind == 'add_flag':
                flag = effect['flag']
                before = updated.story_flags.get(flag, 0)
                require(type(before) is int, 'Cannot add to a non-integer flag')
                updated.story_flags[flag] = before + effect['amount']
                require(-1000000 <= updated.story_flags[flag] <= 1000000,
                        'Story flag exceeds limits')
            elif kind == 'unlock_mission':
                if effect['mission'] not in updated.unlocked:
                    updated.unlocked.append(effect['mission'])
            elif kind == 'gold':
                require(0 <= updated.gold + effect['amount'] <= 1000000,
                        'Insufficient gold for story choice')
                updated.gold += effect['amount']
        updated.story_history.append({'scene': scene['id'], 'choice': selected['id']})
        require(len(updated.story_history) <= 10000, 'Too many narrative decisions')
        updated.story_pending = selected.get('next_scene', '')
        return updated
