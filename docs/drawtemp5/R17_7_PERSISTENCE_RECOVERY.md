# R17.7 — Recoverable Player checkpoints and deterministic resume

Scope: canonical `GameSession v1` via the existing
`PlayerSlotStore` and `SaveManager`. This is an incremental hardening of
the R1.8/R12.10 persistence contract, **not** a second save format.

## Failure paths hardened

1. **Manual restore must not downgrade.** A valid `slot_N.json` is never
   replaced by a valid but older `slot_N.json.bak`. The low-level store now
   returns `SlotError(code="primary_valid")`, regardless of the caller.
   This was already enforced in the autosave manager, not for manual slots.
2. **Interrupted recovery remains retryable.** If a failure happens after
   writing `slot_N.json.damaged` but before publishing the verified backup,
   the next explicit restore may reuse that forensic archive **only if its
   bytes exactly match** the still-corrupt primary. Differing evidence stops
   recovery; it must never be silently overwritten.
3. **Filesystem race protection.** The paths are rechecked for symlinks
   inside the canonical writer lock, after entering the critical section.
4. **External modification detection.** The read-only save catalogue now
   includes metadata change time (`st_ctime_ns`) in its invalidation
   signature. On POSIX this catches even in-place changes where an external
   tool restores file size and `mtime`. On Windows `ctime` is creation
   metadata; it is **not** a full same-size/same-mtime tampering defense.
   The actual load always replays/verifies the checkpoint.

## Fault injection / acceptance tests

```bash
python -m unittest \
  tests_standalone.test_r17_persistence_recovery \
  tests_standalone.test_drawtemp5_r1d \
  tests_standalone.test_drawtemp5_r12_save_manager \
  tests_standalone.test_drawtemp5_r1e -v
```

The tests exercise lossless backup restoration, the refusal to replace a
healthy manual save, interruption after evidence archival, a second explicit
recovery attempt, already-existing **different** forensic bytes, corrupt
backups, missing primaries, and catalogue refresh. Existing R1.E replay
certification checks independently re-executed CT/RNG/events/front states
and disk round trips; these tests must also pass on the final merge SHA.

## Remaining R17.7 / 5.0 release gates

- Full campaign and multi-front crash injection, including reward/final-state
  restoration across physical restart, on Linux/macOS/Windows.
- Reproducible checkpoints and verified checksum manifests for a real game
  exported from Studio, not just the reference fixture.
- Recovery UI for unexpected errors (R17.11) with user-approved actions.
- Never call R17 closed solely from passing offscreen/headless tests.
