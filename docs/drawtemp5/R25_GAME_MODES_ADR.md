# ADR R25.A — Game mode capabilities and fixed-step timing

**Status:** proposed code in PR; not a certified DrawTemp 6.1 release.
**Scope:** R25.1 and R25.2 foundation, R25.4 journal primitive, prerequisite for R25.3/R25.5/R25.9.
**Roadmap:** [Creator Studio multi-genres](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md).

## Decision: retain the canonical owners

- `Content` keeps tactical missions, geometry, actors, equipment and skills.
- `GameProject` keeps authoring data and now accepts one *optional* `game_modes` manifest.
- `GameSession` remains the session owner. `scene_profile(id)` reads a detached view; it does **not** switch modes, create a battle or advance a timer.
- `FixedTickJournal` is a headless **primitive** that orders integer-tick commands and verifies replayed state snapshots; it owns no game world, save slot, combat, inventory or campaign state.
- No Qt, QML, Player routing, new renderer, action-combat implementation or second RPG database is created here.

## Schema v1 (optional project property)

```json
{
  "game_modes": {
    "version": 1,
    "default": {"preset": "srpg"},
    "scenes": {
      "arrival": {"preset": "narrative"},
      "r0_village_forest": {"preset": "srpg"}
    }
  }
}
```

A selection contains **either** `{"preset": "srpg|action|classic_rpg|narrative|hybrid"}` **or** `{"profile": {"movement": "...", "combat": "...", "camera": "...", "interaction": "...", "ui": "..."}}`. All five fields must be present for a custom profile. Unknown fields, future versions, incompatible combinations and dangling references fail with `RuleError`.

Scene IDs must refer to existing authored narrative scenes, exploration entries or tactical missions. The schema does not copy the map or story into a second registry. An existing mission must always resolve to `TACTICAL_CT`; a hybrid project explicitly selects `srpg` for every tactical mission. `FREE_REALTIME` currently uses `TOP_DOWN` by contract; this is not yet proof of a complete real-time Player.

### Legacy migration and rollback

An absent or empty `game_modes` means the original SRPG profile. Neither `GameProject.to_dict()` nor `GameSession.recording()` injects the optional property into existing projects, so historical v1 JSON and checkpoint digests remain stable.

This is a **non-destructive read-time migration**, not a project version bump. Explicit rollback means removing the opt-in field from a project **before** creating a new-mode checkpoint; it does *not* silently coerce already-created mode-aware checkpoints. Checksums for genuinely changed projects differ intentionally.

## Fixed-step journal (R25.4 groundwork)

`FixedTickJournal(rate=60, seed=1)` accepts `submit(tick, source, command)` for **future integer ticks** and calls `step(handler)` with inputs ordered by (tick, source, submission sequence). `handler(tick, inputs)` is supplied by the canonical world owner, returning a JSON-serializable snapshot. Each tick records a SHA-256 state fingerprint; `recording()` includes inputs, fingerprints, seed, rate and a manifest checksum. `replay(..., fresh_handler)` re-simulates and refuses divergence.

Tick frequencies are explicitly restricted (20/30/60/120), the horizon and command count are bounded. NaN/non-JSON inputs, unknown schemas, duplicate sequences, noncanonical input order and tampering are rejected. Checkpointing with future unprocessed inputs fails rather than silently discarding inputs.

**Transaction boundary:** a handler exception leaves the journal unadvanced; external game-world mutations must still be rolled back by the `GameSession` owner. R25.B will wire this to transactional snapshots/command replay and R25.E will write a coherent mode-aware checkpoint. A standalone tick journal is *not* a new Player save file.

## Next milestones and gates

| Scope | Status in this PR | Acceptance required later |
|---|---|---|
| R25.1 profile ADR/capabilities | Implemented foundation | SDK/API review, backward compatibility |
| R25.2 optional schema/legacy default | Implemented + headless tests | Full historical fixture matrix |
| R25.3 scene routing/state/spawn | **Not implemented** | Real scene-to-scene transition, no reward duplication |
| R25.4 fixed tick/replay | Journal implemented, **not wired into Player** | GameSession adapter and identical world hashes |
| R25.5 movement adapters | **Not implemented** | CT untouched; continuous movement real |
| R25.6/7 Qt projection/camera | **Not implemented** | Shared Qt Quick picking, goldens/onscreen/GPU |
| R25.8 input/HUD | **Not implemented** | QTest and real input devices |
| R25.9 save/recovery across modes | **Not implemented** | Crash-injection and old save migration |
| R25.10 Studio two-mode authoring | **Not implemented** | Create/playtest without editing JSON |
| R25.11 cross-version CI | Partial standalone tests | Complete Windows/Linux/macOS release matrix |

## Headless test gate

```sh
python -m unittest tests_standalone.test_r25_foundation -v
python -m unittest tests_standalone.test_game_session -v
python -m unittest tests_standalone.test_drawtemp5_r1 -v
```

Record the exact tested SHA, interpreter/OS and CI status in the PR. These are test commands, **not** claims that they have run or passed. Run Qt onscreen/GPU and packaged Player tests separately before declaring the R25 gate.
