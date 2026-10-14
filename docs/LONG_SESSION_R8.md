# R8.9–R8.13 — Long Session Persistence & Reliability

The new `sporebound.long_session` layer is **opt-in**. It builds on
`SessionStore` v2 and the existing verified `GameSession` v1 recording.
It does **not** rewrite PlayerController slots, content JSON, gameplay rules,
Battle/MultiFront replay schemas, or any existing saves.

## R8.9 — Long Session Checkpoints

```python
from sporebound.long_session import LongSessionAutosave, LongSessionStore

store = LongSessionStore("saves/jeanne.json", checkpoint_every=32)
store.initialize(session)  # new destination only
player = LongSessionAutosave(session, store)
player.perform("ui-click-0001", "choose_story_option", "assault")
player.perform("ui-click-0002", "start_mission", "gate")

loaded = store.load_with_status(content, project, rules=rules)
print(loaded.source, loaded.sequence, loaded.applied, loaded.degraded)
player = LongSessionAutosave(loaded.session, store)
store.compact(content, project, rules=rules)  # optional explicit snapshot
```

Accepted actions are recorded in `<save>.journal` as a bounded, SHA-256
chained sequence: request ID, operation, arguments and before/after replay
digests. Both the journal and full checkpoint use flush + fsync + atomic
replace (via `sporebound.storage`). The checkpoint is only published **after**
the accepted action is durable in the journal. Each full snapshot is
independently checked by `GameSession.from_recording`.

When an operation creates a new Battle identity (UUID), the journal includes
a replay-verified full recording boundary, avoiding fabricated identifiers on
replay. Such entries are **not** delta-compressed. Compaction bounds journal
length to the configured 1–256 operations; a large entry may require a
smaller interval or a larger configured byte limit.

## R8.10 — Crash Recovery

- Failed/partial atomic journal writes leave the previous durable state
  readable. The `LongSessionAutosave` wrapper restores its in-memory session
  from the **durable** state when an operation fails.
- Crash *after* publishing a full checkpoint but *before* pruning the old
  journal: its terminal digest matches the new checkpoint, so the journal
  is **not replayed twice**.
- The original `.bak` can be chosen as a fallback when its replay is valid;
  `degraded=True` means the newer checkpoint is unavailable. Loading never
  automatically overwrites either candidate.
- To **explicitly** restore a verified outcome, call
  `store.restore(outcome, expected_digest=outcome.session.recording()["digest"])`.
  The primary bytes are preserved in `<save>.damaged` before replacement.
  The operation refuses to overwrite an existing evidence file.
- A corrupt non-empty journal that cannot be paired with a verified checkpoint
  is **not ignored**. The user must inspect the files; no speculative replay.

Each operation needs a **stable, caller-owned request ID**. Repeated IDs do
not apply twice while retained. The last 128 IDs survive compaction; this is
bounded idempotency, **not** an unlimited historical request registry.
Use a single process per save file; interprocess locking is not included.

## R8.11 — Explicit Versioned Migration

```python
dest = LongSessionStore("saves/migrated.json")
result = dest.migrate_from("saves/original-v1-or-v2.json",
                           content, project, rules=rules)
```

This only imports a **verified compatible** v1 `game_session` recording or
v2 `session_checkpoint` envelope to a **different destination**. The source
file stays byte-for-byte intact. Identical content, project and rules are
required. A file with an unknown schema or a different gameplay identity
fails closed; there is **no silent content/rules rewrite**. A semantic
migration between incompatible authored rules or projects requires a
separately designed, validated conversion plan.

## R8.12 — Multi-front Persistence

The entire multi-front recording is persisted by the existing canonical
`GameSession` format, not duplicated by a new strategic subsystem. In
particular, active focus, reserves, convoys, tactical battles, relief/
reinforcements, global strategic turns, settled rewards and optional
recovery missions remain replay-validated under the same content and rules.

Call journaled `start_fronts`, `switch_front`, `advance_fronts`,
`send_reserves`, `transfer_units`, `start_recovery`, and related public
`GameSession` methods; never edit `fronts.timeline` or a `Battle` directly.
The tests compare full recorded state, not just the on-screen active sector.

## R8.13 — Stress and Soak

```sh
python -m unittest discover -s tests_standalone -p test_long_session_r8.py -v
python -m unittest discover -s tests_standalone -p test_persistence_v2.py -v
python -m examples.persistence_soak --iterations 3 --commands 48 --output persistence-r8.json
```

The seed-based soak creates and deletes independent campaign slots, grows
tactical journals, performs compaction and reload cycles, tests retries,
and runs the existing **three-mission** uninterrupted-versus-resumed gate
with fronts and story consequences. The JSON includes p50/p95/p99 operation
latency, largest checkpoint, Python `tracemalloc` peak, digest and seed.
These are **measurements**, not preset performance budgets; OS resident
memory and disk fsync latency must be profiled separately on reference hosts.

## Gates / limits

| Lot | Observable gate |
| --- | --- |
| R8.9 | 45+ commands, repeated verified compaction and exact continuation |
| R8.10 | Incomplete journal write, stale journal after publication, explicit backup restoration without duplicate action |
| R8.11 | v1 or v2 source untouched, explicit import, incompatible project rejected |
| R8.12 | Strategic history and focused Battle equal after full replay |
| R8.13 | Versioned JSON with seed, digest, checkpoint size, latency and peak Python allocation |

No automatic integration into the Player UI is enabled by this PR. The
existing v2 workflow remains the production default until the long-session
gate is proven on all CI operating systems.
