# DrawTemp R26.B — Action Player and canonical campaign handoff

**Status:** experimental incremental PR, stacked on [R26.A #300](https://github.com/faudard/drawTemp/pull/300). The [R25.A profile foundation #298](https://github.com/faudard/drawTemp/pull/298) is an **unmerged dependency** for actual campaign handoff. **Not a certified R26 (6.2) Player or export.**

## Play the opt-in Qt preview

```bash
python -m pip install '.[qt6]'
python -m drawtemp.player.qt_app --action-demo --save-dir ./action-saves
python -m drawtemp.player.qt_app --action-demo --smoke --save-dir ./action-saves
python -m unittest tests_standalone.test_action_player_r26b -v
```

- Keyboard: ZQSD or WASD/arrows to walk, Space melee, Shift dodge,
  Ctrl guard, E context interaction, P pause, F5 action-only checkpoint,
  F9 verified load, R respawn after defeat.
- The top-down scene tracks the player, draws static/dynamic obstacles,
  foes, chests, locked doors, and a small HUD; all actions go through the
  original R26.A fixed-point `ActionRuntime`.
- Qt `Timer` drives logical simulation ticks; presentation cannot inject
  fractional-step gameplay into the engine. Precise 60 Hz wall-clock pacing,
  render interpolation, QGamepad, animation, audio and renderer parity are
  **not yet certified**.
- `ActionPlayerController.state()` returns detached data; failed/forged
  loads preserve the live action session.
- This preview is **not** the production GameSession/Player scene renderer
  or its verified native package. `--action-demo` is rejected for frozen
  builds. The default tactical Player and existing slots are unchanged.

## R25 GameSession campaign handoff: opt-in contract

`drawtemp.sdk.action_encounter.ActionEncounter(session, authored_scene)`

1. Receives a verified canonical `GameSession` in campaign mode, a scene
   ID present in existing GameProject story/exploration, and that scene's
   validated **R25** `scene_profile()` (FREE_REALTIME/ACTION_REALTIME).
   Without R25 the API rejects explicitly; it cannot silently start.
2. Seeds the action inventory from `Campaign.inventory` and records that
   exact baseline within the action replay. Pre-R26.A recordings still omit
   the optional field and replay without migration.
3. Collects action ticks in the R26 headless capability. While the encounter
   is running the canonical Campaign remains unmodified. A
   `r26:<scene_id>` story flag prevents reopening a settled scene.
4. `save()` creates a **preview-only compound checkpoint**: a canonical
   `GameSession.recording()`, the action command replay and checksum in
   a single atomic JSON file. `load()` requires the trusted authored
   scene and verifies **both** sub-recordings; it rejects divergent
   input history and mismatched starting inventory without modifying
   the live campaign.
5. `commit()` requires hero alive, enemies dead and doors opened. It
   checks the original canonical campaign digest (to prevent merging over
   concurrent edits), writes the action inventory and completion flag once
   to `Campaign.progress`, verifies a canonical GameSession v1 round-trip,
   and marks the adapter finished. A failed settlement rolls progress back.
   The caller then saves through the **existing** GameSession serializer.

This bridge is **deliberately not a GameSession mode**: until R25
SceneRouter owns scene membership, transitions and checkpoints, the
preview's action mid-scene data must not be attached to tactical slots or
misrepresented as cross-mode crash recovery. R26.B provides a safe
migration path for R25 integration, not the final production orchestration.

## Verification and next gates

`tests_standalone/test_action_player_r26b.py` covers detached snapshots,
pause/input, save/load and corruption, R26.A replay compatibility,
campaign-profile rejection, canonical reward/inventory handoff, replayed
checkpoint and concurrent mutation rejection.

- **R26.B QA status:** check PR CI per SHA, including `--smoke` with real
  PySide6/QtQuick; no visual GPU or hardware-gamepad gate is claimed.
- **R25.B/C still required:** SceneRouter, versioned action scene authoring
  inside GameProject, profile-aware transitions, one canonical mid-scene
  save/replay and crash-recovery path.
- **R26.C pending:** shared top-down renderer R3 projection, animation/HUD
  parity in default Player, useable skills/equipment, enemy navigation,
  input rebinding and real-gamepad tests, boss and death/respawn rules.
- **R29 gate pending:** 3-OS clean-machine bundles, GPU goldens,
  input-latency/stutter profiling and licences.

Roadmap: [R25–R30](DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md).
