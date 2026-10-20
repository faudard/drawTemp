# R49.A — Creator Experience audit, commands & timings

> **Incremental P0 foundation, not the R49 gate.** Target 8.9. This change
> makes existing Studio behavior auditable without creating another Content,
> GameProject, authoring history, or telemetry database.

## Scope delivered in this increment

1. **Central command contract (headless):** `CORE_COMMANDS`, workspace IDs
   from the existing R18 navigation contract, and a registry audit that reports
   absent, unlabelled and non-triggerable QAction surfaces. An action registered
   with a Qt trigger is **not** proof that its callback completes successfully;
   no command is marked "executed" based only on registration.
2. **Persisted shortcut collisions:** on Studio startup, normalize the
   currently effective Qt key sequence for each registered command. When two
   commands collide, keep the first registered binding and clear only the
   later command's **active** shortcut. Both actions remain triggerable from
   menus/palette. The collision is shown in Diagnostics. Do not overwrite the
   user's QSettings or silently pick an alternate shortcut.
3. **Local UX timings:** the synchronous Studio operations
   `studio.refresh`, `studio.navigate`, `studio.open`, and
   `studio.workspace_init` collect monotonic elapsed-time observations in a
   bounded per-operation in-memory ring (256 samples by default). Under
   **Outils → Mesures UX locales R49**, show nearest-rank p50/p95/p99 and
   counts. No filenames, document data, user inputs, resource IDs or project
   titles are recorded; no file or network export is performed.
4. **Regression tests:** pure headless tests for duplicate shortcuts,
   inventories, invalid input, nearest-rank percentiles, bounded history,
   and exception propagation; optional Qt smoke with conflicting saved
   accelerator, accessible command and on-demand local report.
5. **CI:** Python 3.12 + Qt software/offscreen smoke on Linux, Windows and
   macOS. Software Qt smoke is not an onscreen human usability test.

## Invariants and failure policy

- No change to the existing Canonical Content/GameProject, GameSession,
  AuthoringSession, save/replay semantics, CT engine, templates or Player.
- Registered QAction IDs must be unique; handlers must be callable or the
  shell fails during construction instead of silently replacing an action.
- Timing records accept a fixed identifier vocabulary. Input must be an
  integer monotonic duration in nanoseconds, never a path or free-form name.
- Exceptions in measured methods propagate unchanged; timing never masks
  failure. Metrics do not imply that a method returning `False` succeeded.
- The command audit is **surface-only**; user-action end-to-end validation
  must exercise individual commands and verify effects/persistence.

## How to verify

```sh
python -m unittest -v tests_standalone.test_r49_experience
python -m compileall -q drawtemp/studio/r49_experience.py drawtemp/studio/qt_shell.py
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.studio.qt_shell --smoke
```

Manual follow-up: configure `shortcuts/playtest=Ctrl+S`, restart Studio.
Save retains Ctrl+S, Playtest remains reachable from the menu/command
palette, and Diagnostics explains the collision. Navigate between project
and maps, open the local metrics panel and verify nonzero observations.
Check full focus/accessibility on physical Windows/Linux/macOS desktops.

## R49 remaining P0 gates

| Roadmap point | State after R49.A | Required next proof |
|---|---|---|
| R49.1 Command audit | Partially addressed | Execute every user-visible command, identify no-op paths with UX captures |
| R49.2 Navigation/focus | Partially addressed | Persist focus per workspace, validate keyboard + onscreen QTest |
| R49.3 Template Wizard | Not included | SRPG/action/RPG/narrative validated with no-JSON UI & licence preflight |
| R49.4 Inspector | Not included | Shared typed inspector with source→usage diagnostics |
| R49.5 Undo/recovery | Not included | Multi-workshop undo + crash/fault-injection tests |
| R49.6 Playtest return | Not included | Studio→Player→Studio precise scene context & diagnostics |
| R49.7/8 Tutorial & a11y | Not included | Independent novice sessions, focus/contrast/DPI tests |
| R49.9 Performance | Instrumented only | Large-project benchmark dataset and p95/p99 against target hardware |
| R49.10 VS-49 | Not included | Third-party creator's project→scene→action→export, screenshots & clean-machine Player |

**Gate decision: OPEN / NOT CERTIFIED.** CI completion, when available,
only proves the software contracts on that commit. Real GPU measurements,
onscreen accessibility, third-party creator studies, licences, export,
and the consolidated R49 gate still require separate evidence.
