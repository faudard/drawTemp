# R36.B3 — Actor binding, R32 collision provenance and cell-light occlusion

**Status:** proposed in [PR #375](https://github.com/faudard/drawTemp/pull/375);
not R36 certification or a production GPU gate.

## 1. Live Player animation binding (R26 + R28 + R36)

New optional `ActionAnimationPresentation` maps actors such as `hero` to
**existing** R36 graph IDs from a validated GameProject. It consumes the
`ActionRuntime.step()` event log only **after** that step commits:

- `hero_attack` → `attack`, `hero_dodge` → `dodge`,
  `hero_hit` → `hit`, `hero_dead` → `death`;
- enemy events similarly trigger `attack`, `hit`, `death` for an
  explicitly bound enemy ID;
- the authored graph controls *visual state selection*, never gameplay.
  Unsupported authored transitions leave the current visual state intact.

The adapter resolves **R28 sprite IDs and frame indices**, not files or
resource URLs. Shared R3 top-down scene records expose `animationState` and
`spriteId`; the viewport shows the authored pose label. Actual PNG region
rendering, atlas pivots, directional/equipment overlays and goldens are
separate R36.4/R36.C gates.

R36.B2 visual marker crossings are converted to bounded *cosmetic* cues.
`fx` remains the authoritative R26 committed-event VFX channel, and is
prioritized over authored cues when combining for the 96-effect render cap.
Presentation exceptions are fail-soft: never roll back combat, rewards, or
an already committed replay entry.

On checkpoint load or respawn, the adapter anchors at the restored tick
and clears transient cues. **Historical transient poses are not reconstructed
from save history**; neither are graphics stored in the R26 checkpoint.

### Opt-in Player launch

```bash
python -m drawtemp.player.action_app \
  --content path/to/content.json \
  --animation-project path/to/content.game.json \
  --hero-controller hero_animation
```

All three switches are required together. Without them, the existing
R26 Action Player demo runs unchanged. Both JSON documents must form a
valid Content/GameProject pair; `--hero-controller` must match an authored
R36 animation controller. This bridge is currently **R26 action mode only**.

## 2. R32 authoritative contact faces

`drawtemp.render.r32_contact_trace.trace_committed_platform_step(runtime)`
uses the **actual** `PlatformPhysics.last_events` and same-tick snapshot.
For `wall`, `land` or `ceiling` events, the read-only projector validates
the R32 collider ID and reconstructs the exact fixed-point contact face
on the authored or committed moving collider AABB.

Each record contains the committed tick, collider ID, contact point and
normal, the collider's AABB, and source `r32_committed_collision`.
Bad references, stale ticks and geometry mismatches fail closed.

The lower-level `trace_platform_contacts(scene, snapshot, events)` works
with **trusted** external snapshots; only the runtime-bound wrapper
authenticates event provenance. Contacts are not calculated from authored
animation markers. AABB geometry is the existing experimental R32 contract,
**not** per-sprite combat hitboxes, arbitrary polygon overlaps or proof of
tactical collision/animation parity.

There is no R32 side-view Player overlay in this increment; headless contact
projection and tests provide the diagnostic source for later integration.

## 3. R26 wall-aware grid light fallback

`drawtemp.render.cell_lighting.project_cell_lighting` implements bounded,
deterministic, tile-centre Bresenham visibility for cosmetic lights over
authored R26 walls. Caps: max 128×128 scene, 8 lights, 5 cells per light.
Wall tiles can receive light; tiles behind an opaque wall do not.

The shared R3 `render_items` optionally publishes `lightShade` per
visible tile. The top-down Qt delegate draws a semi-transparent dark
mask, without modifying `scene_from_action` legacy outputs or any
gameplay LOS. No random numbers or wall-clock state.

**This is cell-level occlusion only.** Qt Quick's separate soft halo
approximation can still bleed visually across an edge; true pixel-level
light/shadow compositing, dynamic occluder geometry, and GPU hardware
quality certification remain open.

## Tests added

```bash
python -m unittest tests_standalone.test_r36_action_actor_binding -v
python -m unittest tests_standalone.test_r36_r32_contact_trace -v
python -m unittest tests_standalone.test_r36_cell_lighting -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r36_action_actor_qt -v
```

All suites and the R32 physics regression are added to the R36 CI.
Tests cover actor tick/pose, deterministic marker replay, failed cosmetic
projection, checkpoint reset, exact committed R32 wall/floor AABB contacts,
invalid/tampered references, deterministic cell shadows, software Qt
launch of a real R1-saved animation project, and unchanged canonical
recordings.

**Validation blocked:** as of this PR update, GitHub Actions returns
`failure` before creating any jobs, including unrelated workflows.
Written tests are **not confirmed passing** until runners execute.

## Gates still open

- Runtime bindings for tactical actors and R32 side-view Player.
- Authorable combat hitbox windows owned by R32/other gameplay logic
  and validated reconciliation against R36 impact presentation.
- Directional sprite/equipment/pivot rendering, richer timeline curves.
- Real scenegraph GPU lights, shaders, per-pixel occlusion,
  weather/water/fog and artist-authored particle emitters.
- 30/60/120 FPS hardware parity, p95/p99 budgets, GPU goldens,
  license/provenance export verification and accessibility audit.
