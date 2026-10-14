# R7.19 — Cinematic Studio UX 4.0

Stack: **#161 → #170 → #179 → R7.19**. This increment reuses
`GameProject.cinematics`, `frame_at`, `mix_at`, `CinematicPlayback`
and the existing project validation/history. It does not create a parallel
editor, a Tk dependency in the game model or a new save version.

## Workspace

The cinematic panel is divided into three contextual inspectors:
**Animation / caméra**, **Dialogue / portrait**, and **Son / musique**.
The full timeline shows stable lanes for décor, camera, actors, dialogue,
fades, music, ambience, voices and SFX. Clip editing, the instant preview,
the full playback window, the link QA and project Save remain accessible.

- Drag a coloured block horizontally to move an event. While dragging,
  a dashed ghost previews the destination; the persistent edit is committed
  **once, on mouse release**. Vertical moves do not mutate event kinds/buses.
- Select an actor/camera block and click **Ajouter au curseur** to create
  an interior keyframe with the current evaluated position (and zoom
  for cameras). A white diamond appears at the correct absolute timeline time.
- Drag a diamond horizontally to retime its keyframe, or select it from the
  keyframe list to edit its **local time, X/Y and camera zoom**.
- **Ajuster durée** scales local key times while preserving relative ordering.
  It refuses invalid compression instead of silently merging keys.
- **Dupliquer** creates a new stable event ID; the original remains unchanged.
- Undo/Redo restores the whole validated GameProject transaction.

The preview pane includes a 4-bus **audio envelope monitor** derived
from `mix_at(clip, ms)`. It displays authored gains, fades, overlap and
ducking but does not claim to show a sampled waveform or accurate device
latency. The text/portrait render is the same `draw_frame` path used by
the standalone Player. The timeline playhead now respects each clip's full
duration, rather than an 8-second fixed scale.

## Data contract and runtime

Existing actor/camera events are unchanged and remain valid. A new actor
may optionally contain interior keys:

```json
{
  "id": "jeanne_walk",
  "kind": "actor",
  "start_ms": 0,
  "duration_ms": 2000,
  "actor": "jeanne",
  "from": [0.15, 0.65],
  "to": [0.65, 0.65],
  "easing": "linear",
  "keyframes": [
    {"at_ms": 800, "pos": [0.4, 0.6]}
  ]
}
```

Camera keys use the same `at_ms` and `pos` plus required `zoom`.
The existing `from`/`to` and zoom endpoints are still the boundaries.
Local timestamps are integers strictly between 0 and the event duration,
sorted/unique, with at most 32 interior keyframes. Coordinates and
zoom bounds use the established cinematic validator.

`motion_at(event, ms)` interpolates piecewise with the event's easing
curve. **Legacy events with no keys preserve their prior interpolation
exactly.** Inserting an interior key on a non-linear easing curve preserves
the pose *at that key* and the endpoint poses; because easing is now applied
within each new segment, the in-between path can change. This is an
intentional authoring operation, not an invisible migration.

Every edit runs through `GameProject.from_dict(...)` validation and
one existing Studio history step. Rejected duplicate timestamps, invalid
positions or keys beyond duration leave the project untouched.

## Verification

Headless checks, included in the normal cross-platform unittest discovery:

```sh
python -m unittest tests_standalone.test_r7_cinematic_studio4 -v
```

Real Tk/Xvfb GUI gate, added explicitly to the editor CI:

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_r7_cinematic_studio4_gui -v
```

Acceptance covers legacy persistence, keyed interpolation, malformed input,
copy/move/resize, visual keyframe handles, contextual tabs, undo/redo and
manifest save/reload. The existing R7.18 audiovisual goldens continue
to protect the unchanged Player presentation.

## Merge and deferred work

Merge #161, then #170, then #179, rebase/retarget this PR to master,
run full CI and complete manual keyboard/DPI checks.

This PR does **not** implement sampled audio waveform decoding,
frame-by-frame sprite animation keying, arbitrary bezier tangents or
multi-user concurrent authoring. Those require separate acceptance tests.
