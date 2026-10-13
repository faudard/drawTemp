# Entity & Event Studio 3.5B — durable scheduling lifecycle

## Architecture and persistence

Build on 3.5A (#137). **No second scheduler, mutable queue, or new save schema.**
Every lifecycle state is derived from the canonical Battle event journal,
the monotonic tick, and the set of one-shot fired triggers.

Battle.state() includes `scheduled_events` only when timed/cancellable
triggers are present. This read-only projection becomes part of the existing
Battle.recording() digest. GameSession recordings and Battle.replay()
recompute it deterministically from the command log. Historical missions
without these guards retain their former state/digest shape.

The states are:

| State | Meaning |
| --- | --- |
| waiting | Predecessor chain has not completed |
| scheduled | Armed but the delay in ticks/activations is not yet complete |
| ready | Delay elapsed; the normal trigger condition can be evaluated |
| fired | One-shot action successfully fired; it remains terminal |
| cancelled | A cancel_after trigger occurred before expiry/fire |
| expired | Time or activation deadline reached before firing |

`temporal_snapshot(battle)` lists the states in stable mission order for
Studio inspection, saving and replay comparison. No flags are persisted in
Content or an alternative runtime.

## Validation and deadlines

Optional `expire_after_ticks` and `expire_after_activations` are positive
integers from 1 to 10,000, anchored on the same predecessor events as delay.
If both expiry dimensions are present, reaching **either** expires the
event. If a delay and expiry use the same dimension, expiry must be **greater**
than that delay. At the expiry boundary the event cannot fire.

Cancellation still uses the 3.5A `cancel_after` list. It is effective only
before the event fires. Cancellation and expiration are terminal: a cancelled
event cannot later become expired, and an already-expired event cannot
become cancelled by a later trigger. The deterministic event log establishes
the chronological outcome.

No native GUI clock, timer thread, or editor-only effect application is used.
Only the canonical dispatcher is allowed to fire tactical actions.

## Authoring

`event_graph.configure_schedule` now accepts the expiry fields. None
preserves the current authoring value; 0 removes a delay or expiry.
Validation rejects impossible windows, booleans, invalid IDs, and timer
events with no predecessor. Editing a primary predicate retains scheduling.

## Test gate

    python -m unittest tests_standalone.test_event_lifecycle_35b -v
    python -m unittest tests_standalone.test_event_timing_35a -v
    python -m unittest tests_standalone.test_event_chains_32 tests_standalone.test_game_session -v

Required:
- expiry and cancellation are monotonic, cannot later switch terminal reason;
- no double-fire after cancellation or expiration;
- saving and reopening the GameSession reconstructs the exact same snapshot;
- real Battle.replay authenticates digest including lifecycle state;
- legacy mission state/digest remains unchanged;
- no cross-branch merge with pending #129/#131 until those CI conflicts are resolved.

3.5C will render this read-only snapshot as a timeline. It must not
reimplement the scheduling decisions in Tkinter.
