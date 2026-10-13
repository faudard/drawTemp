# Entity & Event Studio 3.5A — Temporal Scheduling

## Goal

Schedule tactical events **after N battle ticks or N unit activations** without a
second dispatcher, a queue hidden in the editor, or a new save format. The
feature is independent of the visual branch builder in PR #131.

## Canonical event data

A standard Mission.triggers entry may optionally contain:

- delay_ticks: integer 1..10000
- delay_activations: integer 1..10000
- cancel_after: one to eight IDs of other triggers in the same mission

At least one predecessor in after (or after_any once 3.4 is integrated) must
anchor a delay. Combined delays are conjunctive: a scheduled event becomes
eligible only when both thresholds have passed and its existing condition and
when predicates are true. No premature side effects are applied.

The scheduling origin is the most recent mandatory predecessor; an OR
alternative is measured from the first fired alternative. The source is the
actual trigger and activation records emitted by Battle, not a synthetic
Studio clock. A cancellation trigger prevents an unfired scheduled event from
executing; it never undoes an effect already executed.

## Authoring and compatibility

event_graph.configure_schedule(data, mission_id, event_id, ...) updates the
existing Mission.triggers atomically through Content.from_dict. Zero clears a
delay; an empty list clears the cancellation guard. Updating the primary
condition preserves existing scheduling fields. condition_summary renders the
guards in the Event Studio's existing inspector.

temporal_events.temporal_status(battle, trigger) returns ready, waiting,
scheduled, or cancelled with remaining ticks and activations. The 3.5C
visual timeline can consume this same read-only projection.

Battle.state already includes the event log, trigger IDs and RNG state. A
real Battle.recording and Battle.replay validates deterministic results.
Legacy triggers take their existing dispatcher path without new scans.

This PR makes no changes to 3.4 branching / 3.5 visual choice wizards and
must be integrated with those independently. It does not assert that a
hand-prepared preview is an authenticated Player replay.

## Verification

    python -m unittest tests_standalone.test_event_timing_35a -v
    python -m unittest tests_standalone.test_event_chains_32 tests_standalone.test_event_graph -v

Gate: all legacy timing unchanged, no duplicate fire, invalid references
rejected, zero mutations after a rejected authoring operation, and authentic
replay checksum preserved. 3.5B/C will address explicit expiration,
long-session profiling and Studio timeline visualization.
