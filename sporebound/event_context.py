"""Contextual tactical-event inspection and an isolated, real-engine preview.

No alternative condition/action evaluator or new persisted event schema. The
preview uses the battle rule registry and dispatcher on a disposable Battle.
It does not advance turns, execute campaign consequences or save anything.
"""
from copy import deepcopy

from . import event_graph
from .engine import Battle
from .model import Content, RuleError, require
from .rules import triggers
from .tactical_rpg3 import authored_rules_for_document


def inspect_event(data, mission_id, event_id, project=None):
    """Project the canonical mission trigger and *mission-level* related assets."""
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    event = next((e for e in mission.get('triggers', [])
                  if e['id'] == event_id), None)
    require(event is not None, 'Unknown tactical event')

    scene_id = ''
    clips = []
    if project is not None:
        scene_id = project.story.get('after_mission', {}).get(mission_id, '')
        clips = [
            {'id': clip['id'], 'stage': clip['trigger']['kind']}
            for clip in project.cinematics
            if clip['trigger']['kind'] in ('before_mission', 'after_mission')
            and clip['trigger']['target'] == mission_id
        ]
    return {
        'mission_id': mission_id,
        'event_id': event_id,
        'condition': event_graph.condition_title(event),
        'actions': [event_graph.action_title(action)
                    for action in event['actions']],
        'scene_id': scene_id,
        'cinematics': clips,
        # Cinematics and story currently attach to missions/scenes, never
        # directly to Mission.triggers. Do not imply event-level playback.
        'links_scope': 'mission',
    }


def preview_event(data, mission_id, event_id, *, tick=0):
    """Dispatch one authored trigger in a disposable battle at a sampled tick.

    The mission is initially instantiated with no triggers, so the Battle
    constructor cannot fire the target (or unrelated rules) before the test.
    The actual engine dispatcher then evaluates only the selected trigger.
    Setting a tick is a predicate probe, NOT simulation of intervening turns.
    """
    require(type(tick) is int and 0 <= tick <= 100000,
            'Preview tick must be an integer from 0 to 100000')
    context = inspect_event(data, mission_id, event_id)
    # Preserve the same rule family selection used by the Studio and Player.
    # It must inspect the full authored document BEFORE removing triggers.
    rules = authored_rules_for_document(data)
    snapshot = deepcopy(data)
    mission = next(m for m in snapshot['missions'] if m['id'] == mission_id)
    trigger = next(e for e in mission['triggers'] if e['id'] == event_id)
    mission['triggers'] = []
    battle = Battle(Content.from_dict(snapshot, rules=rules),
                    mission_id, seed=1, rules=rules)
    battle.tick = tick
    battle.mission.triggers = [trigger]

    initial_ids = {u.id for u in battle.units}
    first_event = len(battle.events)
    error = ''
    try:
        # Real runtime, including condition matching and sequential actions.
        triggers.dispatch(battle)
    except (RuleError, ValueError, KeyError, IndexError) as exc:
        error = str(exc)
    final_ids = {u.id for u in battle.units}
    return {
        'mission_id': mission_id,
        'event_id': event_id,
        'tick': tick,
        'fired': event_id in battle.fired,
        'actions': context['actions'],
        'events': deepcopy(battle.events[first_event:]),
        'spawned': sorted(final_ids - initial_ids),
        'despawned': sorted(initial_ids - final_ids),
        'error': error,
        'isolated': True,
    }
