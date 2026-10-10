# 2.4.4 — Headless reliability gate

## Reproduce

```sh
python -m unittest discover -s tests_standalone -p test_reliability.py -v
python -m examples.reliability_gate --seeds 1 7 42 99 --output reliability.json
```

The standalone CI runs both the full tests and the campaign gate on Python
3.10/3.12/3.14, Windows, macOS and Linux. Each matrix cell uploads its own JSON
report with seed, ending, deterministic digest, command count, checkpoint count,
maximum checkpoint bytes and individual save/load durations in seconds.
Durations are observations, not hardware-independent performance thresholds.
Failed correctness assertions or the 200-command per-battle limit fail the job.

## What the gate proves

- A compact, deliberately easy three-mission fixture uses only public session
  operations and real engine commands. It starts with a narrative decision,
  opens two fronts, advances the strategic clock, switches focus, resolves both
  battles, completes a final mission and chooses one of two conditional endings.
- Six campaign/ending cases in unit tests compare uninterrupted runs with runs
  saved/reloaded after every tactical command and at lifecycle boundaries. CI's
  separate report covers eight campaign/ending cases with interval-three saves.
- Every checkpoint roundtrip compares the exact session recording. The live
  battle state, RNG, events, campaign rewards, story flags and journals are
  reconstructed from disk. A separate test reloads in a fresh Python process.
- Independently started campaigns intentionally get different Battle UUIDs.
  Only the final cross-run comparison normalizes those UUIDs, preserving their
  cardinality/uniqueness; it also includes every AI-selected tactical command's
  resulting battle digest (which covers RNG/events). Disk roundtrips never
  normalize identities. Three rewards and 300 hero XP must be awarded exactly
  once; the mercy ending adds exactly 25 gold.
- A separate integration test uses the existing castle content, causal links
  and logistics. It chooses an authored briefing option, deploys at the gate,
  advances other fronts, switches to the ramparts, saves, discards the session,
  reloads and executes the same next command as an uninterrupted control.
- A 120-command journal survives four checkpoints. A fixed-seed invalid command
  corpus verifies no state, RNG, journal or autosave mutation, and compares the
  next accepted action against a restored control.
- Disk replace failures leave the primary readable, retain a valid recovery
  generation, and clean temporary files. Malformed/truncated/invalid-UTF-8
  primaries recover from backup without repairing or overwriting either file.
- Checkpoint limits are tested at exact UTF-8 byte size and one byte below.

This is headless lifecycle certification, not completion of the rendered castle
vertical slice, UI autosave integration, large-scale balancing, or a performance
budget for multi-hour campaigns. Longer stress profiles and p95/p99 baselines
remain follow-up work.

## Defects caught and corrected

1. Checkpoint preflight previously measured compact JSON while storage wrote
   indented JSON. Files could pass the write limit and then fail their own read
   limit. `storage.json_text` now defines the exact UTF-8/LF representation for
   both measurement and writing on every OS.
2. MultiFront replay reconstructs tactical state but historically generated new
   Battle UUIDs. GameSession checkpoints now include optional `front_battle_ids`
   for main, rescue, pursuit and recovery battles, protected by the session
   checksum. Load verifies group membership, exact live-battle keys and unique
   nonempty IDs, then restores identities before subsequent reward/bond tracking.
   Old v1 session files without this optional metadata still load; they cannot
   recover UUIDs that were never stored. Standalone historical MultiFront replay
   formats and their checksums remain unchanged.
3. Non-object tactical commands leaked AttributeError in standalone battles.
   They now fail with RuleError before changing state, consistently with fronts.
4. Boolean session versions are rejected rather than accepting `True == 1`.

The preceding asset PR's macOS/Windows test failure was also corrected on that
PR: expected temporary paths now use the same canonical resolution as the asset
resolver. The correction is included in this branch's base.
