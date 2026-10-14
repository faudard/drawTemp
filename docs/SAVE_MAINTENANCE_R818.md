# R8.18 — Save Integrity & Retention

## Architecture

`sporebound.save_maintenance.LongSessionMaintenance` is a dedicated
**opt-in maintenance service**, not a new save schema or alternate
`GameSession`. A read-only inventory validates the existing
`SessionStore` v2 checkpoint and its `.bak` file, the
`LongSessionStore` journal, and the replayed in-memory state.

An inventory also reports preserved `.damaged` evidence, an active or stale
`.lock`, recognized atomic-write `.tmp` candidates and each independently
verifiable archive generation.

## Commands

Point `--save` at a selected **long** slot
(`slot_1.long.json`). Use the matching project and content files when
they are not the bundled defaults.

```sh
python -m examples.save_maintenance --save PATH --inspect
python -m examples.save_maintenance --save PATH --archive

python -m examples.save_maintenance --save PATH --retention-plan --keep 3
python -m examples.save_maintenance --save PATH --apply-retention --keep 3 --token DIGEST

python -m examples.save_maintenance --save PATH --temp-plan --min-age-seconds 3600
python -m examples.save_maintenance --save PATH --quarantine-temp --min-age-seconds 3600 --token DIGEST
```

The `--token` is returned by the corresponding read-only plan. It is a
digest of the **actual generation/file inventory**, not a placeholder or a
fixed confirmation string. Re-run the plan and re-confirm it whenever the
files or retention parameters change.

## Archive generation

Archive creation acquires the same per-slot exclusive writer lock as long
session gameplay. It will only copy **healthy, replay-verified** snapshots.
Each archive is a directory next to the slot:

```
slot_1.long.json.history/
  gen-<nanosecond timestamp>-<session digest prefix>/
    slot_1.long.json
    slot_1.long.json.bak        # if present
    slot_1.long.json.journal
    manifest.json
```

The archive contains exact bytes of all available checkpoint generations
and the current journal. The manifest holds SHA-256 checksums, sizes, v2
sequence, and the replay-verified full `GameSession` digest. The service
publishes the complete staged directory by an atomic same-filesystem rename,
then re-verifies it independently. Incomplete `.staging-...` directories
are retained for manual investigation if a process is abruptly killed.

Archives are **not used for automatic rollback**. The existing
`LongSessionStore.load_with_status()` and explicit Player recovery flow
remain the only active-session recovery protocols.

## Retention / recovery guarantees

- Preview is read-only. Every archived generation is verified before a
  retention plan can be produced.
- Retention requires at least **two full archives**; its default is three.
- A mutating retention command must provide the *current* plan digest.
  The service recomputes the plan under the exclusive writer lock.
- Only old, fully validated archive **copies** are deleted. Primary,
  `.bak`, `.journal`, `.damaged`, and archives within the protected
  retention window are never pruned.
- Retention fails when the active slot is degraded or invalid, so a
  potentially valuable historical recovery generation is never deleted
  during a failure investigation.
- Archive corruption or an unknown manifest/layout stops maintenance
  rather than being silently skipped. No damaged archive gets deleted.
- Existing writer locks are never stolen by maintenance.

**Retention deletion is irreversible**, so the user must keep other backups
of irreplaceable saves; this system is not an off-machine backup.

## Temporary-file quarantine

Recognized leftover temp files are only those matching the adjacent
`<slot>.*.tmp` atomic-write pattern. The scan is bounded and the default
age gate is one hour (minimum one minute). A separate plan token is required
to move eligible files into `<slot>.history/quarantine/`, preserving the
original bytes. No `.tmp`, `.damaged`, journal or backup is silently
deleted. The active slot must be healthy.

The quarantine is a **manual** investigation folder. It is intentionally
not subject to archive retention. This may require periodic operator
handling to bound disk consumption.

## CI / acceptance gates

```sh
python -m unittest discover -s tests_standalone -p test_save_maintenance_r818.py -v
python -m unittest discover -s tests_standalone -p test_long_session_r8.py -v
python -m unittest discover -s tests_standalone -p test_long_session_player_r8.py -v
```

Automated on Linux, macOS and Windows. The tests include corrupt manifests,
missing/corrupt live checkpoints, concurrent writer locks, stale retention
plans, old/new temporary files, original byte preservation and archive
replay integrity. No migration of gameplay rules, no automatic cleanup
thread, and no implicit mutation at Player startup.
