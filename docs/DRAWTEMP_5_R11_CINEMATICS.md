# R11 — Cinematic, Audio & Effects Studio (DrawTemp 5.0 / Qt 6)

## Scope and integration

This is the **opt-in Qt 6 R11 vertical slice**, built on the existing:
- canonical GameProject.cinematics (version 1), Content, StoryBook choices and engine triggers;
- sporebound.cinematics.frame_at, CinematicTransport and CinematicAudioDirector;
- immutable camera/actor keyframes, audio envelopes, asset registry and event path auditor.

It does not replace the legacy Tk editors or Player, and it does not create a
second cinematic, save, choice or audio schema. Editing uses a deep-copy
GameProject transaction validated with GameProject.from_dict before every
commit. Undo/Redo restore whole validated project snapshots. Saves use the
existing project writer, with a stale-disk guard.

The **same QML file** (drawtemp/render/CinematicStage.qml) and
drawtemp.cinematics.projection.frame_payload are used by the Qt Studio
and Player. QML never executes tactical or campaign rules.

## Launch

Requires **Python 3.12** with the R0 Qt6 extra:

    python -m pip install ".[qt6]"
    python -m drawtemp.platform.qt_cinematics --mode studio

Open a specific content/project:

    python -m drawtemp.platform.qt_cinematics --mode studio \
      --content sporebound/content/jeanne.json \
      --project sporebound/content/jeanne.game.json

Play the first authored cinematic (or the unsaved demo if none is present):

    python -m drawtemp.platform.qt_cinematics --mode player
    python -m drawtemp.platform.qt_cinematics --mode player --clip jeanne_intro

Smoke command for a machine with a Qt display:

    python -m drawtemp.platform.qt_cinematics --mode studio --smoke

The Studio has a clip list, timeline lanes and event inspectors. Create the
**Introduction Jeanne** sample, select a timeline block, adjust typed
properties and press **Appliquer**. Add another camera, actor, dialogue,
sound, fade or FX track using **+ Piste**. For actor/camera tracks,
**Ajouter image-clé au curseur** inserts a validated motion key.
Undo/Redo and the save button operate on the entire GameProject manifest.
The Player exposes play/pause, scrub/restart, and the identical Qt Quick scene.
The presentation transport also supports seeking, pause/resume, playback
rates 0.25–2× and checkpoint/restore in its public API.

Audio tracks use canonical sound cue bindings from the project asset registry:
music, ambience, voice and SFX with loop, gain automation, fades and ducking.
If a file/device/codec is missing, playback is silent rather than mutating
gameplay or failing the cinematic. A silent demo does not certify audio output.
Actor tracks may reference an existing pose slot (actor_pose) or a validated
AssetRegistry animation binding. The stage picks the correct atlas sprite by
authored event time, including backward seeks and loops. This does not add a
new animation schema or copy the PNGs into the game project.

The existing Audio Studio remains responsible for importing WAV/OGG and
binding sound assets.

## R11 feature / acceptance matrix

| Lot | Implementation | Certification |
| --- | --- | --- |
| R11.1 | Qt timeline lanes, clips, typed editor, Undo/Redo | Headless transaction tests; visual/manual gate outstanding |
| R11.2 | Canonical camera motion, keyframes, zoom, easing, shot transition | Deterministic frame sampling |
| R11.3 | Actor trajectories, keyframes, poses and sampled AssetRegistry animations | Deterministic animation-frame and pose tests; R3 GPU integration pending |
| R11.4 | Speaker, progressive text, portrait, expression | Existing StoryBook alone owns decisions and effects |
| R11.5 | Four audio buses with optional QtMultimedia stage | Deterministic mix and silent-device fallback; device QA outstanding |
| R11.6 | Seeded FX tracks for fire/smoke/rain/fog/light/camera shake | Seek-deterministic metadata; production GPU effects deferred to R3 |
| R11.7 | Canonical campaign/mission/scene/tactical triggers and existing event path QA | Path validation via sporebound.event_cinematic_qa |
| R11.8 | Qt Quick stage reused by Studio and Player; play, pause, seek, speed, resume | Opt-in offscreen Qt smoke and visual parity QA outstanding |
| R11.9 | Strict schema, round-trip, rollback on error, stale-save guard, existing goldens | Local tests plus CI; export/device/real-GPU review outstanding |

**Gate status: not yet certified.** The R11 vertical slice is executable, but
the full integration gate depends on shared isometric renderer (R3), asset
pipeline (R4), Event Studio (R9) and Player runtime (R12), which are separate
milestones. The stage currently renders a stylized preview with asset sprite
bindings; it does not pretend to replace the future GPU isometric viewport.
No proof of audio device output or real-GPU/Studio-Player screenshot equivalence
is claimed without actual execution.

## Data addition: deterministic FX

Canonical cinematic event type fx adds strictly validated fields:

    {
      "id": "village_smoke", "kind": "fx",
      "start_ms": 8000, "duration_ms": 3000,
      "effect": "smoke", "intensity": 0.65,
      "seed": 48, "at": [0.72, 0.52]
    }

Available effects: fire, smoke, rain, fog, light, camera_shake. Coordinates
are normalized; intensity is 0..1; seed is an unsigned 31-bit integer. The
result is computed from the authored seed and playhead, so backward/forward
seeks produce identical frame metadata. Old events/clips remain valid, with
the same sampled result. No new project version, migration or gameplay
command is introduced.

## Tests

    python -m unittest tests_standalone.test_r11_qt_cinematics -v
    python -m unittest tests_standalone.test_r7_cinematic_pipeline -v
    python -m unittest tests_standalone.test_r7_cinematic_goldens -v

On a GUI-capable CI runner with PySide6 installed:

    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
    DRAWTEMP_QT_GUI_SMOKE=1 \
    python -m unittest tests_standalone.test_r11_qt_cinematics -v

The optional Qt smoke is not a substitute for full manual input, DPI,
multiscreen, audio-device and GPU screenshot checks. A QA review should also
play the Jeanne introduction, inspect missing asset diagnostics, verify
pause/seek/restore, then exercise a canonical scene choice and compare
save/replay hashes with legacy.

## R11.10 — Timeline Direct Editing (follow-on)

The Qt Studio timeline now supports **direct horizontal dragging** of a clip
block and independent dragging of the white motion-key diamonds. The timing
ruler is in seconds, the grid snaps to **100 ms** (the last valid event start
and strict interior keyframe endpoints are clamped even off-grid), and a
click on free timeline space seeks the Studio preview.
Selected tracks/keyframes can also be nudged with **Left/Right (100 ms)** or
**Shift+Left/Right (1 s)** without grabbing the mouse.

An edit is **preview-only while dragging**. Exactly one transaction is
committed on mouse release; rejected motion and stale revision operations
cannot corrupt the GameProject or create a half-finished Undo step. Selecting
an existing block/key without moving it never rounds its original timestamp.
The cursor is preserved on normal edits, and Undo/Redo returns to valid
authoring state. Both actor/camera keyframes and audio/FX event durations
continue to use the original schema and existing validation.

Qt audio preview pause/seek now also pauses newly reconstructed tracks,
including one-shot cues. Seek/restore and clip changes explicitly stop
transient cues so a cutscene cannot keep speaking from an abandoned position.
These are presentation-only changes; gameplay timing is untouched.

Tests:
```
python -m unittest tests_standalone.test_r11_timeline_editing -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  DRAWTEMP_QT_GUI_SMOKE=1 \
  python -m unittest tests_standalone.test_r11_timeline_editing.TimelineQtSmokeTests -v
```

**Gate:** interactive Qt smoke and cross-platform headless CI required;
manual real-input review (drag threshold, keyboard, DPI, touchpad) remains
separate from offscreen certification. This incremental UI does not claim
that R3/R9/R12 production parity or physical audio output is complete.

## Remaining work for final R11 gate

- Replace stylized actor/effect placeholders with the R3 shared isometric GPU
  viewport, while keeping the projection and one QML presentation contract.
- Bind the finished character animation atlas and voice assets (R4/R7).
- Complete detailed keyframe pose/zoom editing, multi-selection and accessible
  keyboard alternatives; direct timeline/retime is present as R11.10.
- Certify event-to-cinematic-to-campaign consequence on the R9/R12 Qt
  integration, including interruptions and resumed saved campaigns.
- Record real sound-card latency/mixing, export and Windows/macOS/Linux
  visual QA evidence before marking R11 complete.
