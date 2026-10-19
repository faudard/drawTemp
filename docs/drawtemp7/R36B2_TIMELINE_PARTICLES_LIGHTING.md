# R36.B2 — Visual timeline, bounded particles & 2D lighting fallback

**Status:** incremental PR #375 code, pending CI execution. This is *not* full
R36.2–12 or a certified GPU-lighting implementation.

## R36.B2 authoring contract

- `sporebound.animation_timeline`: separate opt-in project-owned extension
  `org.drawtemp.animation.timeline` v1. Historical controller v1 documents
  remain byte-for-byte compatible and existing R28 sprite/animation manifests
  are unchanged.
- Each timeline binds exactly one existing R36 Animation Controller and
  contains visual marker tracks by its state ID. Markers carry a portable ID,
  `at_ms` within the linked R28 clip and one of `spark`, `dust`, `trail`,
  `glow`. Up to 16 timelines / 48 state tracks / 32 markers per state.
- **No `damage`, `hitbox`, `collision` or script callbacks** are accepted
  as marker actions. Markers cannot commit player actions or move R32
  colliders. Combat impacts continue to originate only from committed
  R26/R32 rule events.
- `cues_crossed(..., entered_tick, from_tick, to_tick, tick_rate)` accepts a
  bounded interval of authoritative simulation ticks and returns stable,
  deterministic visual cue records, including loop-cycle identity.
  Sampling/render FPS cannot create extra markers. Queries are limited to
  512 ticks and 128 cues.
- `AnimationTimelineAuthoring`: preview/apply/remove through canonical R1
  transactions, revision guards, undo/redo and project validation.
  Removal of a controller referenced by a timeline is rejected by project
  validation, rather than silently orphaning the timeline.
- **Studio / Animation / Timeline R36**: select a controller and animation
  state, edit typed cue/time markers, preview committed tick intervals,
  validate and apply. No JSON authoring required.

## First light and particle path

- `drawtemp.render.vfx2d.project_vfx` is a pure bounded plan projected from
  existing R36.B1 committed `fx` snapshots. Stable SHA-256 directions
  replace RNG, with at most **128 live particle records** and **8 halos**.
- Configurable quality in the pure render-plan API: density `0..3`,
  ambient overlay alpha `0..0.25`, lights on/off and reduced motion.
- `ActionPreview.qml` renders cheap Qt Quick points, a dark ambient tint,
  and three concentric rings per light. **This is a non-occluding software-
  capable approximation**, not a shader solution, GPU particle compute,
  shadow caster, ray marching, volumetric lighting or weather system.
- The **M** reduced-flash preference hides the burst/particle/halo layers.
  It never touches game commands, timestamps, saves or rewards.

## Acceptance gates added

```bash
python -m unittest tests_standalone.test_r36_animation_timeline -v
python -m unittest tests_standalone.test_r36_vfx2d -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r36_animation_timeline_qt -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_r36_committed_fx_qt -v
```

CI has been updated for Linux/Windows/macOS headless tests plus separate Qt.
At the time of implementation, GitHub Actions returned failed workflow
runs with **no jobs created**, so tests have **not** been certified.

## Explicitly still outstanding

- R36.2: frame-event audio cues and gameplay-authoritative hitbox trace
  linked to R32/other gameplay, with unit/tactical parity.
- R36.3: cubic curves, drag/reorder multitrack Qt timeline and keyframe
  undo transactions with dedicated viewport golden snapshots.
- R36.5–7: emitter authoring presets, adaptive CPU/GPU batches, occluder
  geometry, true light/shadow, weather/water/fog and backend fallbacks.
- R36.8–12: complete deterministic end-to-end synchronization, tested
  Godot/Qt? **No Godot target is claimed**; hardware GPU baselines,
  reduced-flash audit and licensed-export asset provenance.

Never mark the R36 release gate complete based solely on software/offscreen
view instantiation.
