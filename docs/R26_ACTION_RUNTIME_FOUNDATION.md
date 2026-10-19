# R26.A — Action Adventure Runtime: first headless vertical slice

Status: **implemented on an incremental PR branch**, not an R26 (6.2) release
certification. Source of truth: [multi-genre roadmap](DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md)
§6. This package is intentionally opt-in and not connected to Qt, Studio,
the shipped Player or the pre-existing GameSession until the R25 contracts
have been implemented and certified.

## What this change provides

- `sporebound.action_runtime.ActionRuntime(scene)`: pure Python, fixed 60 Hz
  rules capability. Integers represent 1/1000 tile, so frame rate and rendering
  delta never enter movement, damage, collision, or enemy decisions.
- Strict, bounded action scene schema: walls, hero, enemies, patrols,
  interaction objects. Reject unknown fields, invalid spawns and duplicate IDs.
- R26.1: 4/8 direction movement with diagonal normalization (no optional
  acceleration yet).
- R26.2: tile and actor collisions using fixed-radius AABB footprints,
  axis-by-axis sliding. Knockback and trigger volumes remain future work.
- R26.3: melee with facing, fixed range, cooldown, enemy hit/stun/death.
- R26.4: dodge and temporary invulnerability; stamina and guarded contact
  damage. Anticipation/telegraph animations require Player work.
- R26.5: bounded deterministic patrol, chase, attack, return and death
  states. Pathfinding around walls is planned for R27.8.
- R26.6/7 (partial): deterministic chest loot, locked door, signs, inventory
  and persistent interaction flags. The authoritative tactical inventory,
  equipment and scene transitions must later be connected through GameSession.
- R26.12 (partial): exact tick command journaling, canonical state checksum,
  strict scene identity and replay verification, atomic JSON writes. Restore
  re-executes inputs; it does not apply unverified mutated state.

### Minimal Python usage

```python
from sporebound.action_runtime import ActionRuntime

world = {
    "id": "forest", "width": 8, "height": 8,
    "walls": [[4, 4]], "hero": {"pos": [1, 1], "hp": 6},
    "enemies": [{"id": "wolf", "pos": [2, 1], "hp": 2,
                 "patrol": [[2, 1], [2, 2]]}],
    "objects": [{"id": "chest", "kind": "chest", "pos": [1, 2],
                 "item": "key", "requires": ""}],
}
runner = ActionRuntime(world)
events = runner.step({"tick": 1, "dx": 1, "attack": True})
snapshot = runner.snapshot()  # JSON-friendly detached UI state
runner.save("forest.action.json")
restored = ActionRuntime.load("forest.action.json", expected_scene=world)
assert restored.digest() == runner.digest()
```

A real UI sends **one validated command per logical tick**, and can draw any
number of interpolated frames from snapshots. No commands are inferred from
rendering FPS. Commands must have `tick` equal to the preceding tick + 1;
invalid input never advances the runtime. This is a **prototype capability**,
not yet a GameSession save slot, canonical replay, or Player scene.

## Compatibility

No changes to `GameSession`, `Battle`, `Content` or `GameProject`, and
no alteration of tactical command/replay/save serialization. The test gate
checks headless interactions, invalid inputs, determinism and save tampering.
Existing legacy test suites remain responsible for the tactical regression
gate; no certification of those suites is claimed in this document.

## Acceptance coverage and remaining R26 work

| Roadmap | This PR | Needed for closure |
|---|---|---|
| 26.1 | Movement at integer ticks | Optional acceleration and Player input device tests |
| 26.2 | Walls and dynamic actor collision | Hitbox authoring, triggers, knockback |
| 26.3 | Melee, cooldown, stun and hit events | Interruptions and visual/audio feedback |
| 26.4 | Guard, dodge, stamina, iframes | Telegraph animation, ability rules |
| 26.5 | Patrol/chase/attack/return/death | Pathfinding and proper enemy authored sensors |
| 26.6–7 | Chest/door interactions; prototype inventory | Connect canonical inventory, events and SceneRouter |
| 26.8–11 | Not delivered | Action HUD, projectiles, boss, animation/audio/VFX |
| 26.12 | Action-only deterministic replay/atomic save | GameSession/recovery fault-injection |
| 26.13–14 | Not delivered | Actual gamepad testing, Player mini-combat, respawn |

**R26 release gate not met.** The next PR should consume R25 scene profiles
and SceneRouter/GameSession ownership once available, not add another
independent persistent world. R26 remains blocked for end-to-end certification
until R25 and upstream R17 compatibility gates have concrete evidence.
