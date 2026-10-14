"""Deterministic lifecycle of scheduled tactical events.

No mutable timer queue: the authoritative state is the canonical Battle journal
(trigger/activation events), current tick and one-shot fired IDs. These already
survive genuine Battle/GameSession recording and replay.
"""

TEMPORAL_KEYS = frozenset((
    'delay_ticks', 'delay_activations', 'expire_after_ticks',
    'expire_after_activations', 'cancel_after',
))


def _clock(battle, origin, until=None):
    """Ticks and activations elapsed after a journal index (inclusive until)."""
    if until is None:
        end = len(battle.events)
        tick = battle.tick
    else:
        end = until + 1
        tick = battle.events[until]['tick']
    elapsed_ticks = max(0, tick - battle.events[origin]['tick'])
    elapsed_activations = sum(
        row['kind'] == 'activation'
        for row in battle.events[origin + 1:end])
    return elapsed_ticks, elapsed_activations


def _summary(state, *, remaining_ticks=0, remaining_activations=0,
             expires_in_ticks=None, expires_in_activations=None,
             origin_tick=None, reason=None):
    return {
        'state': state,
        'remaining_ticks': remaining_ticks,
        'remaining_activations': remaining_activations,
        'expires_in_ticks': expires_in_ticks,
        'expires_in_activations': expires_in_activations,
        'origin_tick': origin_tick,
        'reason': reason,
    }


def temporal_status(battle, trigger):
    """Project waiting/scheduled/ready/fired/cancelled/expired, read-only.

    A cancellation or expiration is irreversible because ordering is inferred
    from immutable trigger records. Expiry deadlines are exclusive: at exactly
    expire_after_ticks/activations the event can no longer fire.
    """
    event_id = trigger['id']
    fired = set(battle.fired)
    if event_id in fired:
        return _summary('fired')

    delays = (trigger.get('delay_ticks', 0),
              trigger.get('delay_activations', 0))
    expiries = (trigger.get('expire_after_ticks'),
                trigger.get('expire_after_activations'))
    cancel_ids = set(trigger.get('cancel_after', ()))
    first_trigger = {}
    first_cancel = None
    for index, row in enumerate(battle.events):
        if row['kind'] != 'trigger':
            continue
        first_trigger.setdefault(row['id'], index)
        if row['id'] in cancel_ids and first_cancel is None:
            first_cancel = index

    required = trigger.get('after', ())
    alternatives = trigger.get('after_any', ())
    prerequisites_ready = (
        all(ref in fired for ref in required) and
        (not alternatives or any(ref in fired for ref in alternatives)))
    if not prerequisites_ready:
        if first_cancel is not None:
            return _summary('cancelled', reason='cancel_after')
        return _summary('waiting', remaining_ticks=delays[0],
                        remaining_activations=delays[1])

    positions = [first_trigger[ref] for ref in required
                 if ref in first_trigger]
    if len(positions) != len(required):
        return _summary('cancelled' if first_cancel is not None else 'waiting',
                        reason='cancel_after' if first_cancel is not None else None,
                        remaining_ticks=delays[0],
                        remaining_activations=delays[1])
    if alternatives:
        candidates = [first_trigger[ref] for ref in alternatives
                      if ref in first_trigger]
        if not candidates:
            return _summary('cancelled' if first_cancel is not None else 'waiting',
                            reason='cancel_after' if first_cancel is not None else None,
                            remaining_ticks=delays[0],
                            remaining_activations=delays[1])
        positions.append(min(candidates))
    if not positions:
        # A cancellation-only legacy trigger has no scheduling origin.
        return _summary('cancelled' if first_cancel is not None else 'ready',
                        reason='cancel_after' if first_cancel is not None else None)
    origin = max(positions)
    origin_tick = battle.events[origin]['tick']

    def expired_at(ticks, activations):
        return (
            (expiries[0] is not None and ticks >= expiries[0]) or
            (expiries[1] is not None and activations >= expiries[1])
        )

    # Resolve terminal status at the first cancellation, not at the current
    # tick. Otherwise a cancelled event would later turn into "expired".
    if first_cancel is not None:
        if first_cancel <= origin:
            return _summary('cancelled', origin_tick=origin_tick,
                            reason='cancel_after')
        cancel_ticks, cancel_activations = _clock(battle, origin, first_cancel)
        if not expired_at(cancel_ticks, cancel_activations):
            return _summary('cancelled', origin_tick=origin_tick,
                            reason='cancel_after')

    elapsed_ticks, elapsed_activations = _clock(battle, origin)
    if expired_at(elapsed_ticks, elapsed_activations):
        reason = ('expire_after_ticks' if expiries[0] is not None
                  and elapsed_ticks >= expiries[0]
                  else 'expire_after_activations')
        return _summary('expired', origin_tick=origin_tick, reason=reason)
    remaining_ticks = max(0, delays[0] - elapsed_ticks)
    remaining_activations = max(0, delays[1] - elapsed_activations)
    return _summary(
        'scheduled' if remaining_ticks or remaining_activations else 'ready',
        remaining_ticks=remaining_ticks,
        remaining_activations=remaining_activations,
        expires_in_ticks=(None if expiries[0] is None else
                          max(0, expiries[0] - elapsed_ticks)),
        expires_in_activations=(
            None if expiries[1] is None else
            max(0, expiries[1] - elapsed_activations)),
        origin_tick=origin_tick,
    )


def temporal_snapshot(battle):
    """Stable, serializable lifecycle projection in mission authoring order."""
    return [{'id': trigger['id'], **temporal_status(battle, trigger)}
            for trigger in battle.mission.triggers
            if any(key in trigger for key in TEMPORAL_KEYS)]
