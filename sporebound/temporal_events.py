"""Canonical temporal readiness derived from Battle's deterministic journal.

No parallel trigger dispatcher or persisted pending queue. The event log is
already included in Battle.state and authenticated by replay.
"""

def temporal_status(battle, trigger):
    """Return a temporal gate's state and remaining tick/activation counts."""
    fired = set(battle.fired)
    if any(ref in fired for ref in trigger.get('cancel_after', ())):
        return {'state': 'cancelled', 'remaining_ticks': 0,
                'remaining_activations': 0}

    ticks = trigger.get('delay_ticks', 0)
    activations = trigger.get('delay_activations', 0)
    if not ticks and not activations:
        return {'state': 'ready', 'remaining_ticks': 0,
                'remaining_activations': 0}

    required = trigger.get('after', ())
    alternatives = trigger.get('after_any', ())
    if (any(ref not in fired for ref in required)
            or (alternatives and not any(ref in fired for ref in alternatives))):
        return {'state': 'waiting', 'remaining_ticks': ticks,
                'remaining_activations': activations}

    # Every predecessor is one-shot and emits a real trigger event.
    by_id = {row['id']: (index, row['tick'])
             for index, row in enumerate(battle.events)
             if row['kind'] == 'trigger'}
    if any(ref not in by_id for ref in required):
        return {'state': 'waiting', 'remaining_ticks': ticks,
                'remaining_activations': activations}
    origins = [by_id[ref][0] for ref in required]
    eligible = [by_id[ref][0] for ref in alternatives if ref in by_id]
    if alternatives:
        if not eligible:
            return {'state': 'waiting', 'remaining_ticks': ticks,
                    'remaining_activations': activations}
        origins.append(min(eligible))
    if not origins:
        return {'state': 'waiting', 'remaining_ticks': ticks,
                'remaining_activations': activations}

    origin_index = max(origins)
    elapsed_ticks = max(0, battle.tick - battle.events[origin_index]['tick'])
    elapsed_activations = sum(
        row['kind'] == 'activation'
        for row in battle.events[origin_index + 1:])
    remaining_ticks = max(0, ticks - elapsed_ticks)
    remaining_activations = max(0, activations - elapsed_activations)
    return {'state': ('scheduled' if remaining_ticks or
                      remaining_activations else 'ready'),
            'remaining_ticks': remaining_ticks,
            'remaining_activations': remaining_activations}
