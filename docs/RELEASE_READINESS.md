# Fiabilité et distribution — release gate

This gate deliberately **does not** rewrite the tactical engine, historic battle
replay schema, or existing checkpoint hashes. The existing v1 game-session
recording and v2 checkpoint wrapper continue to be verified independently.

## Compatibility policy (no implicit gameplay migration)

1. A checkpoint is only usable with the exact saved content, game-project
   document and rules manifest, after checksum and deterministic replay checks.
   A mismatch reports **which identity differs**, plus short recorded/current
   fingerprints; loading never modifies the save or applies new rules.
2. The Player does not silently fall back to older default rules. A developer
   can explicitly opt in to those *unchanged* rules with
   `PlayerController.load_game(..., allow_legacy_default_rules=True)`. That
   opt-in is not a migration to a new ruleset.
3. An existing `game_session` v1 file can be explicitly upgraded using
   `SessionStore(path).migrate_v1(content, project, rules=rules)`, or the
   Player title-screen action "Migrer une sauvegarde v1". The migration validates
   the old replay, retains the source bytes in `<path>.bak`, writes an atomic
   v2 envelope and re-verifies it. It refuses incompatible data, existing
   backups, unknown versions and incorrect campaigns. It does **not** convert
   content, logic or tactical commands.
4. A new migration between content/rule revisions must be a separately reviewed,
   opt-in, replay-verified transformation with fixture pairs (old/new) and
   diagnostics. Without that migration, the save remains incompatible.
5. If the primary is corrupted and a valid backup loads, the Player presents a
   recovery warning: restored progress may be older. Neither file is repaired
   or overwritten until a further explicit gameplay action/save.

## Player state and lifecycle

- Autosave is synchronous and atomic after accepted gameplay operations.
  Rejected actions leave disk unchanged; an I/O error restores the previous
  in-memory session (not a half-committed UI state).
- Creating a new game publishes the new checkpoint before replacing the current
  session in memory; failures leave the old session selected.
- Closing the Player is idempotent; canceling the "save failed" confirmation
  keeps the window open. Recovery and compatibility failures are shown in the UI.

## Reproducible checks

```sh
python -m unittest discover -s tests_standalone -p test_save_contract.py -v
python -m unittest discover -s tests_standalone -p test_reliability.py -v
python -m unittest discover -s tests_standalone -v
python -m examples.reliability_gate --seeds 1 7 42 99 --output reliability.json
python -m pip install build
python -m build
python scripts/verify_distribution.py dist
```

The separate **Distribution smoke** workflow builds a Python wheel and sdist
on Windows, Linux and macOS, installs the wheel in an isolated venv, and
validates/simulates/replays entirely outside the checkout. Matrix artifacts
are available to download. These are **Python distributions**, not native
double-clickable Windows executables, AppImage packages or signed macOS apps.

## Follow-up gates before calling the full milestone complete

- [ ] Long-running campaign soak test (multiple hours, large journals, disk-full
      and interrupted-process scenarios) with published p95/p99 limits
- [ ] Editor benchmark for many maps/events/assets (load, render, search,
      validation, export and memory), with regression thresholds
- [ ] Automated Tk keyboard-only traversal and focus/shortcut audit on all
      Studio and Player screens under Windows/Linux/macOS
- [ ] Multi-cycle GUI open/close/reopen stress on all platforms, including
      pending callbacks and audio cleanup
- [ ] Platform-specific application bundles (Windows EXE, Linux AppImage/deb,
      macOS app/notarization), asset/path checks and distribution signing
- [ ] Fixture-driven, explicit migration path for a *specific* future content
      or rules revision, retaining provenance and old replay semantics

Do not tag the project "release certified" until these gates are measured.
