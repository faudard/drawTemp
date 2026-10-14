# R8.19 — Player Save Manager UI

## User flow

The Player's title screen and campaign footer expose **Gestionnaire de
sauvegardes / Sauvegardes**.

1. Pick a campaign and a slot from the left pane. Standard v2 and
   opt-in long-session saves are visible, but never silently converted.
2. Inspect the health summary: verified/missing/invalid/degraded,
   checkpoint source, sequence, SHA-backed recording identity, journal,
   backup, retained evidence, and warnings.
3. Select a verified historical generation in the right pane.
4. Use **Comparer** to preview campaign progress and tactical changes.
5. For a long-session slot, choose an *unused and different* destination,
   then **Restaurer vers slot libre**. The confirmation explains the
   version selected, the differences and the fact that this is a new copy.
6. The manager rechecks the source archive and the destination under
   exclusive slot locks before copying through `LongSessionStore.initialize`
   and independently replay-verifying the destination. The Player continues
   the original in-memory session unchanged. The destination is selected
   for the next deliberate Continue action.

**No in-place rollback:** R8.19 deliberately does not overwrite the
current live slot. Degraded live saves remain inspectable. Verified
archives can still be restored to a different free slot even when the
current primary is corrupt. The previous `.damaged` evidence, original
`.bak`, journal and archive directory remain untouched.

## Other actions

**Créer archive** uses exactly the R8.18
`LongSessionMaintenance.archive_verified()` path and prompts before
copying. **Conserver 3 archives** first runs the real retention dry-run,
shows archive names to be removed, requests confirmation and passes the
fresh confirmation digest to R8.18. It cannot delete the live save or
reduce archive retention below three via this UI.

The UI never deletes atomic temporary files or damaged evidence.
For detailed clean-up of stale `.tmp` files, use the R8.18
`python -m examples.save_maintenance` CLI; no hidden background tasks.

## Design

- **Headless service:** `sporebound/save_manager.py` manages discovery,
  health, version lists, campaign-level summaries, deltas and restoration
  authorization. It does not import Tk.
- **UI:** `PlayerApplication.save_manager_screen` uses the existing Tk
  styling and the Player's existing `PresentationState`, with a slot
  explorer on the left and archive list, diagnostics and actions on the
  right. It is accessible from the title and from the campaign screen.
- **Existing saves:** `SessionStore` v2 files are browsable but are
  read-only in the Manager. This prevents a false impression that they
  have long-session archive history.
- **Archive verification:** Generation identifiers come from
  `LongSessionMaintenance._archive_dirs()`; arbitrary path fragments are
  rejected. Every chosen archive is verified against SHA-256 manifest
  and deterministic `GameSession` replay. Incompatible project/content/rules
  are refused.
- **Restoration planning:** The token binds campaign, source slot,
  archive generation, source manifest checksum, target slot and saved
  `GameSession` digest. Destination must contain no primary, backup,
  journal, damaged evidence, active lock or retained history.
- **Safety:** Source transaction holds `session_writer_lock` while
  confirming the plan and creating the copy. Destination creation uses
  its own per-slot lock. Existing generations cannot be overwritten.

Checkpoints are summarized by campaign mode, seed, mission completion
and unlocks, key resources when present and the changed progress
fields. A truncated comparison is clearly marked; it is not a claim
of semantic equivalence of different rulesets.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_save_manager_r819.py -v
python -m unittest discover -s tests_standalone -p test_save_maintenance_r818.py -v
python -m unittest discover -s tests_standalone -p test_long_session_player_r8.py -v
python -m unittest discover -s tests_standalone -p test_persistence_fault_r817.py -v
```

CI on Ubuntu, Windows, macOS. The safety gates run headlessly against
the real gameplay/persistence contracts. An additional Linux Xvfb smoke test
opens the actual Tk Save Manager, selects an archived version, previews a
comparison, navigates back and asserts that the save bytes remain unchanged.
The GUI smoke requires the `SPOREBOUND_GUI_SMOKE=1` opt-in and a display.

## Out of scope

Automated remote/cloud backups; replaying an invalid archive; silently
switching the active party to an old checkpoint; automatic stale-lock
recovery; background scans of all campaigns; destructive restore
into an occupied slot.
