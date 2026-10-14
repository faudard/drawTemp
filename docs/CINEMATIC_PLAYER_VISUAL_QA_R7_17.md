# R7.17 — Cinematic Player Visual QA & Monotonic Playback

**Stacked on #161 (R7.13–R7.16)**. This gate strengthens the existing Player
without modifying cinematic authoring schemas, battle commands or campaign saves.

## The timing bug

The previous `CinematicPlayback._tick` advanced its playhead by exactly 40 ms
on every Tk `after(40)` callback. `after` is a scheduling hint, not a
real-time timer. Any slow canvas redraw, OS scheduling stall or asset load would
make the music and visuals drift from elapsed wall time.

`CinematicTransport` now owns the in-memory playhead, anchored to a monotonic
clock (injectable in tests). UI frames sample its time; rendering frequency does
not change the timeline. The existing pure `frame_at` and `mix_at` projections,
and `CinematicAudioDirector` one-shot semantics, remain canonical.

## End-to-end playback behavior

| Action | Expected result |
| --- | --- |
| Play with a delayed Tk callback | Time derives from monotonic elapsed time, not a fixed +40 ms |
| Pause | Visual and audio clocks both stop |
| Resume | Continues from paused playhead, no catch-up for paused wall time |
| Drag scrub / arrow seek | Reconstructs audio envelopes; never fires historical one-shots |
| Restart | Returns to t=0, unpauses audio channels, permits intentional replay of sounds |
| Interrupt / checkpoint | Returns `clip_id`, `duration_ms`, `time_ms`, `playing` |
| Restore same clip | Recovers playhead, paused/playing state and audio without historical cues |
| Restore another clip / malformed checkpoint | Rejected before modifying audio or playback |
| End / skip twice / close twice | Exactly one completion callback; cleanup idempotent |

**Checkpoints are intentionally in-memory presentation state**, not a new
persistence schema. The cutscene does not commit any StoryBook or GameSession
decision: a narrative scene resumes in the preexisting Player flow.

## QA

Headless:

```sh
python -m unittest tests_standalone.test_r7_cinematic_visual_qa -v
```

GUI/Xvfb (Linux):

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_r7_cinematic_visual_qa_gui -v
```

The GUI test renders an actual Tk Canvas, checks expressive portrait lookup
and fallback, verifies dissolve boundaries, text reveal, audio cue crossing,
pause/checkpoint/restore, delayed tick catch-up and completion-once lifecycle.
The secondary test compares Canvas item types, positions and dialogue text for
identical playheads (structural visual regression without font-specific pixels).

## Release gates

- Existing R7.13–R7.16 CI remains green across 3 OS / supported Python versions.
- R7.17 headless transport tests pass.
- R7.17 Tk/Xvfb smoke passes when a display is available.
- Manual Player checks on Windows and macOS: portrait transparency and scale,
  resize mid-transition, keyboard focus, mixer device present/missing.
- No additional `GameProject`, `GameSession`, `Campaign` or `Battle` fields.

**Known limitation:** the deterministic gate tests Tk drawing structure, timing
and event order; it is not a cross-platform pixel-golden certification.
Real device playback latency and OS-specific font rendering still need manual
assessment before declaring full audiovisual fidelity.
