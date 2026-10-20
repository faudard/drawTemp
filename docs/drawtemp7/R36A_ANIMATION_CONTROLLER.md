# R36.A — Animation Controller & visual Studio (initial implementation)

Status: **proposed code in PR**, not R36 certification. Based on the
[R31–R40 roadmap](../DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md).

## Delivered scope

- `sporebound.animation_graph`: versioned schema v1 for animation states and
  priority-ordered event transitions; references the existing R28
  `GameProject.assets` animation IDs. Maximum 48 states, 128 transitions and
  16 controllers per project. No independent resource registry, game clock,
  hitbox data, gameplay effects or executable code in the document.
- `AnimationStateController`: headless presentation-only interpreter. The
  caller advances it with strictly increasing committed simulation ticks and
  events. Frame selection uses integer arithmetic, a fixed tick rate and the
  existing `AssetRegistry`; no Qt, wall-clock, RNG or PNG decoding is involved.
  The synthetic `finished` event is a **visual clip completion** signal, not
  combat resolution. Snapshots are detached and include a controller-content
  checksum. They are not part of the canonical GameSession save schema.
- `GameProject.extensions["org.drawtemp.animation"]`: project-owned documents,
  validated (including asset references) during GameProject load. Old projects
  without the extension serialize exactly as before.
- `AnimationControllerAuthoring`: stale-revision checks, R1
  `preview_project` / `apply`, one-step Undo/Redo and atomic removal. Invalid
  controllers fail closed, including after a resource is deleted.
- R28D Studio workspace: new **Contrôleur R36** tab to create states,
  transitions and frame previews without typing JSON. Users must first register
  sprite/animation resources through the existing R28 animation workspace.
- Three-OS headless gate and a separate Qt offscreen smoke, including R28/R12
  regression suites. Offscreen Qt does **not** certify GPU rendering.

## State controller example

Given registered `idle_anim` and `attack_anim` animation assets:

```json
{
  "schema_version": 1,
  "id": "hero_animation",
  "initial": "idle",
  "states": [
    {"id": "idle", "animation": "idle_anim"},
    {"id": "attack", "animation": "attack_anim"}
  ],
  "transitions": [
    {"source": "idle", "target": "attack", "on": "attack", "priority": 20},
    {"source": "attack", "target": "idle", "on": "finished", "priority": 10}
  ]
}
```

`AnimationStateController(graph, registry).advance(tick, events)` returns
`state`, `animation`, `frame_index`, `sprite` and `elapsed_ms`. **Only pass
committed events**, after the simulation has resolved the authoritative
action. Rendering may interpolate; it must never use clip position or markers
to compute damage or collisions.

## Gates remaining

| Roadmap | State after this lot |
|---|---|
| R36.1 | Initial validated state controller + Studio authoring; full Player runtime binding pending |
| R36.2 | Frame/impact/hitbox timeline authoring and authoritative R32 sync **pending** |
| R36.3 | Curves, interactive scrubbing, transactional timeline editing **pending** |
| R36.4 | Production atlases, equipment pivots, directional goldens **pending** |
| R36.5–7 | Bounded CPU/GPU VFX, light/occlusion, weather and fallback **pending** |
| R36.8 | Logic/visual tick synchronization end-to-end and replay **pending** |
| R36.9–10 | GPU p95/p99 and reduced-flash accessibility audit **pending** |
| R36.11–12 | Export fail-closed licensing and visual Studio/Player parity **pending** |

**Do not mark 7.6 certified** until the attack/dodge/impact/death vertical
slice works in both action and tactical Player and hardware GPU goldens are
approved for their target backends.
