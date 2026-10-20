# R41.B1 — Party Studio & Player roster bridge

**Roadmap:** [DrawTemp 8.1 / R41](../DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md)  
**Status:** proposed implementation in PR #381, not R41.B complete, not certified.

## Delivered in this incremental code candidate

1. `drawtemp/studio/party_authoring.py` reads hero identities from canonical `Content.missions[*].units` and publishes a **revision-checked AuthoringSession preview**. The original R1 validator rejects unknown IDs, duplicate/reordered invalid memberships, stale previews, missing RPG_TURN profile and incompatible project changes. A successful apply is a *single Undo/Redo transaction* in the existing Studio owner.
2. `drawtemp/studio/party_qt.py` adds an accessible Qt Widgets authoring dialog: campaign selection, recruitable / initially recruited / initially active checkboxes, group capacity, explicit preview and apply. It does not edit disk, spawn heroes, or replace `AuthoringSession`. It is reachable from **Studio → Outils → R41 • Groupe RPG classique…**.
3. `drawtemp/sdk/simulation.py` exposes the R41 party selection, recruitment and active/reserve operations through the established R1 `Simulation` revision and rollback boundary.
4. `drawtemp/player/controller.py` exposes the party as a detached read-only projection and accepts active/reserve toggles via `Simulation`, preserving autosaves, the canonical Campaign hero XP and inventory. No unrestricted recruitment button is exposed in the Player: campaign recruitment triggers remain future work.
5. `drawtemp/player/Main.qml` displays a compact party panel in exploration for projects explicitly configured for RPG_TURN, without adding a second renderer or changing the default tactical HUD.

## Headless and GUI test plan

```sh
python -m unittest tests_standalone.test_r41_classic_party -v
python -m unittest tests_standalone.test_r41_party_studio -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r41_party_qt -v
python -m unittest tests_standalone.test_r25_foundation tests_standalone.test_game_session -v
```

The R41 workflow covers Linux, Windows and macOS for headless tests plus a Linux Qt offscreen smoke. These commands are **not local pass claims**. Final SHA/runner logs and physical Qt/GPU checks are required.

## Gate status and remaining work

- **R41.A**: authored profiles, single-owner party roster and replay-checked session checkpoints — code in review; CI and regression proof pending.
- **R41.B1**: Party Studio transaction and Player active/reserve HUD — code in review; CI and human UX/onscreen validation pending.
- **R41.B2**: typed, versioned *Encounter Studio* (source enemies/abilities from Content), actual RPG_TURN battle actions, KO, flee, item consumption and victory/defeat **not implemented here**.
- **R41.B3**: Player turn-based screen, target selection, keyboard/gamepad navigation and deterministic mid-encounter checkpoint **not implemented here**.
- **R41.C**: three-hero original village→dungeon→two combats→loot→return Player PC vertical slice, export/CI tri-OS, asset rights, GPU and third-party playtest **not implemented here**.

The project's historical GRID_CT combat, migrations and old Jeanne save format are unchanged unless a project opts in to the party extension. No new mode is silently injected into existing files. **No release gate should pass based on this increment alone.**
