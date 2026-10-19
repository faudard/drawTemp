# R17.12 — One authored Jeanne game from Studio adapters to an isolated native Player

**Status:** automated R17.12 integration **candidate**, not R17/5.0 certified.
R17.6 real redistribution rights, R14 hardware goldens, machine-clean
installation and human review remain external release requirements.

## Reproducible scenario

The test runs the **canonical** `AuthoringSession` through these existing
workshop interfaces, with no handcrafted game JSON or parallel rules:

1. **MapStudio R5:** rename the reference Jeanne mission and change an
   actual walkable terrain tile.
2. **ConstructionWorkspace R6:** find a footprint accepted by
   `validate_structure_placement`, place a `Maison`, change its facade/roof
   and add a real floor.
3. **DatabaseEditor R8:** install `lancer_example`: real class/archetype,
   protection skill and spear equipment with references.
4. **EventStudio R9:** existing gate + lever, a priority page reacting to
   interaction, hazard and linked dialogue.
5. **Campaign:** change campaign name and game title transactionally.
6. **Cinematic:** attach a typed audio presentation cue to the gate event.
7. **Assets:** copy and register an **actual PNG** from the checked-in Jeanne
   pack; verify the physical bytes before and after export. This test does
   **not** assert the pack's redistribution license.
8. **Studio persistence:** commit the two canonical documents and the R5
   presentation sidecar, reopen them and compare content/project state.
9. **Player:** `build_controller(content_path=...)` loads the authored
   project, starts Jeanne, interacts with the actual lever, validates the
   open door/page and the cinematic, saves slot 1, loads via
   `GameSession.load`, restarts an **independent** Player, resumes the
   narrative and checks exactly one trigger activation. The real Qt
   `Main.qml` + `PlayerBridge` also replay the same episode offscreen.
10. **Export:** preflight physical project assets, stage a **real frozen**
    Player PyInstaller executable in CI, verify the R15 manifest and exact
    Content/GameProject/PNG SHA-256, then archive the output.
11. **Isolated runner:** on Windows, macOS and Linux a **new runner with no
    checkout, pip, Python setup or Studio installation step** extracts only
    the archived native bundle, starts the Player offscreen and verifies
    that a tampered authored Content file is refused.

The standalone hash-only unit test deliberately uses a **fake executable**
to exercise R15 packaging; it never claims that fixture is launchable.
Only the separate native CI job tests the real PyInstaller executable.

## Local commands

```sh
python -m unittest tests_standalone.test_r17_12_cross_workshop -v
python -m drawtemp.quality.r17_cross_workshop \
  --project-dir /tmp/r1712-project --report /tmp/r1712-evidence.json
python -m drawtemp.export.cli check \
  --content /tmp/r1712-project/r1712-jeanne.json
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r17_12_cross_workshop_qt -v
```

With a separately built **real native Player** runtime:

```sh
python -m drawtemp.export.cli export \
  --content /tmp/r1712-project/r1712-jeanne.json \
  --runtime-dir dist/DrawTempPlayer --output /tmp/R17Jeanne
python -m drawtemp.quality.r17_cross_workshop \
  --project-dir /tmp/r1712-project --verify-bundle /tmp/R17Jeanne
```

## What this still does NOT certify

- Most actions are performed through the **same production headless Studio
  adapters**, rather than mouse-driven widgets across *every* Qt workshop.
  Qt Player uses the real QML; user-level Studio click-path remains an
  independent E2E obligation.
- The PNG is real and hash-verified, but its rights are **not attested**.
  No `asset-licenses.json` is invented, and no R17.6 release flag is set.
- The isolated runner verifies an actual native **launch at the title
  screen** and tampering; it does not control a live battle inside that
  relocated frozen process. Canonical battle/replay and QML interaction are
  separately tested on the authored project **before** export.
- A separate CI runner is *not* proof of a physically clean consumer
  installation. Real GPU benchmarks, human-approved visual goldens,
  notarization/signing, installer, accessibility and legal verification
  remain open.
- All tests must pass on the final merged SHA before claiming this
  particular integration gate verified.

Evidence is saved as `r1712-evidence-<OS>`; the JSON explicitly sets
`r17_12_certified=false`, and export JSON sets
`release_certified=false`. These are deliberate fail-closed statuses.
