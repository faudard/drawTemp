# R7.18 — Audiovisual Fidelity & Golden Tests

Dependency chain: **#161 → #170 → R7.18**. Work is deliberately stacked
on R7.17 until the parent PRs have merged; do not merge this PR directly
to master before retargeting.

## Portable reference scenes

The reviewed fixture at
`tests_standalone/goldens/r7_18_castle_scene.json` captures six audiovisual
states from the **actual** shared `draw_frame()` and `mix_at()` paths.

| Time | Reference event | Audited rendering |
| --- | --- | --- |
| 0 ms | Opening shot | Camera/actor origin, full wipe, music 80% |
| 250 ms | Entering shot | Half wipe, eased actor position, music 75% |
| 500 ms | Dialogue start | Dialogue panel, expressive portrait, empty reveal |
| 1000 ms | Dialogue mid-beat | Portrait and text, camera/pan/zoom, music 60% |
| 1750 ms | Scene conclusion | No dialogue, half black fade, music 45% |
| 1000 ms (2×) | Enlarged viewport | Same narrative/audio state, scaled actor geometry |

**Golden scope**: semantics, actor geometry, camera values, dialogue layout,
portrait binding request, ordered Canvas text labels, transition and fade
progress, and per-bus mixer gains. This is a portable structural reference:
it is deliberately **not** a byte-for-byte PNG comparison (Tk font raster,
ClearType, subpixel antialiasing, ICC profiles and scaling vary by OS).

The snapshot recorder calls the same renderer as the Studio preview and the
Player. There is no second art/presentation engine or new persisted data.

## Real PNG alpha gate

A GUI smoke test constructs a 2×2 RGBA PNG using only the Python standard
library. It binds that asset as an expressive portrait through `AssetRegistry`,
renders it with `CanvasRenderer`, and checks that both transparent and opaque
texels survive Tk loading. It also redraws the same frame twice and checks
Canvas item type/geometry/text stability while resizing the viewport.

This synthetic alpha proof does **not** assert that all production atlas
assets are present or correct: actual art inventory quality belongs in the
Visual Fidelity release gate.

## How to run

Portable unit tests (full Python/OS matrix):

```sh
python -m unittest tests_standalone.test_r7_cinematic_goldens -v
python -m unittest tests_standalone.test_r7_cinematic_visual_qa -v
```

Tk/Xvfb (Ubuntu editor CI):

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_r7_cinematic_visual_qa_gui \
  tests_standalone.test_r7_cinematic_goldens_gui -v
```

The headless golden suite is included in normal `unittest discover`. The
GUI suite is now an explicit blocking CI step, rather than being silently
skipped in discovery when no display is attached.

## Golden maintenance contract

Reference updates must be **reviewed**. Normal tests only read the committed
JSON; they cannot overwrite it. When visuals are intentionally changed:

1. Document the exact authored change and capture the before/after payload.
2. Update only affected expected fields in the fixture as part of a PR.
3. Run the headless matrix and Tk smoke. Review portrait transparency,
   visible text, movement, overlay order and sound envelope changes.
4. Preserve deterministic hash/checkpoint and game replay invariants.
5. Do not change authoring/saving schemas solely to update the visuals.

## Release gate and limitations

- [ ] Portable headless goldens green on Ubuntu/Windows/macOS and Python 3.10/3.12/3.14.
- [ ] R7.17 existing transport regression tests green.
- [ ] Real Tk PNG alpha, palette, resizing and Canvas parity tests green.
- [ ] Manual Windows and macOS screenshots for multiple DPRs (1×/1.5×/2×):
      fonts, clipping, text wraps, skin tone and portrait alpha.
- [ ] Real speakers/headphones: soundtrack and dialogue offset, audio-device
      absence, ducking/fade timing and interruptions.
- [ ] No changes to `GameProject` schema or gameplay save/replay semantics.

**Not yet certified:** bit-identical raster goldens, real-world audio device
latency, every production artwork variant, manual multi-OS visual acceptance,
or every conditional gameplay branch. Those must be measured separately, not
inferred from a green semantic-golden CI run.
