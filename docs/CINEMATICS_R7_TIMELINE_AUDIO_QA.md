# R7.13–R7.16 — Cinematic Timeline 3.0, Dialogue, Audio & Event QA

This change extends the **existing** `sporebound/cinematics.py` schema, Cinematic Studio,
`CinematicPlayback`, `CinematicAudioDirector`, `StoryBook` and GameSession chain.
No new trigger namespace, battle command or save-version migration is introduced.

## R7.13 — Plans, motion and transitions

- `actor`, `camera` and `fade` events may define `easing`: `linear`
  (legacy default), `ease_in`, `ease_out`, `ease_in_out` or `step`.
- `camera` events can define `shot` (stable ID) and `transition`: `cut`
  (default), `dissolve` or `wipe`. The transition occupies the first
  quarter of that camera event; its position is derived solely from the timeline.
- Existing multi-track editing, drag-to-move, validation, undo/redo, preview
  and clip triggers remain the source of truth.

## R7.14 — Dialogue presentation

- `dialogue` may define `portrait` (asset binding ID), `expression`:
  `neutral`, `happy`, `sad`, `angry`, `surprised`, `determined`.
  A bound `portrait_<expression>` sprite is preferred; the base portrait
  is the fallback. No portrait is required.
- `chars_per_second` ranges from 0 to 120. Zero means instant text
  (legacy behavior). Character reveal is derived from elapsed milliseconds,
  not frame count, so scrubbing/replay yields identical text.
- The Player offers scrubbing, keyboard step (left/right), pause/play and
  a presentation-only `checkpoint()/restore()` API. An interrupted sequence
  does not apply narrative choices or combat effects.
- **Choices remain canonical in StoryBook**. Displaying a cutscene never commits
  them; the existing campaign/tactical choice UI resumes after the cutscene.

## R7.15 — Audio Timeline 2.0

- Existing `music`, `ambience`, `voice`, `sfx` buses, one-shot cues,
  fades, looping, ducking and backend-optional transport are preserved.
- Optional `volume_to` (0..100) adds linear within-clip gain automation
  from `volume` (or the default 100); the fade envelope still applies.
- `mix_at` is a pure projection; `CinematicAudioDirector.seek()` does not
  re-emit old one-shots. No reliance on pygame, audio hardware or Tk for
  the deterministic tests.

## R7.16 — Event-to-Cinematic QA

Use the **QA événement → choix** control on a cinematic triggered by a story scene.
The selected scene must be linked by `during_tactical_event` or
`after_strategic_event`, and it needs a choice with an authored consequence.
`audit_event_cinematic_path` checks:

1. The original project and event reference validate.
2. The event links to a known scene and chosen canonical StoryBook choice.
3. The scene has a playable cinematic sequence.
4. Frames and audio envelopes are deterministic under forward/backward seeks.
5. Full manifest serialization/revalidation preserves the sampled timeline.
6. A consequence exists (`effects`, `tactical_effects` or `next_scene`).

The report includes the source, scene, all cinematic IDs, choice/effect kinds and
a SHA-256 of sampled audio/visual states. **This is an authoring certificate**, not
proof that a conditional choice is available in every campaign state. The separate
integration regression test executes a real castle lever event, cinematic
acknowledgments, canonical choice application, save/load and journal parity.

## Compatibility / test gates

- Old clips with no new fields render as before. `GameProject.version` remains 1.
- No gameplay consequence is applied by frame evaluation or audio playback.
- Invalid easing, transition, expression, pacing and end volume are rejected by
  the existing strict project validator.
- Run `python -m unittest tests_standalone.test_r7_cinematic_pipeline -v`,
  then the repository's normal unit and GUI CI suites.
- If visuals are absent, portrait fallback remains safe. Audio asset bindings
  must still be provided through the existing Audio Studio.

### Deferred work

A cinematic has no independent branching gameplay logic: branching and choice
conditions belong to StoryBook. The current certificate validates authored
links and an integration replay scenario, **not** exhaustive exploration of
all conditional branches; that remains a distinct branch-coverage gate.
