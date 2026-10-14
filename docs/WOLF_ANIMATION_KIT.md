# Wolf animation kit v2 (derived preview)

The original twelve watercolor wolf PNGs remain unchanged in
`assets/watercolor/sprites/wolf/`. This kit is a **non-destructive preview
extension**: it repeats real source drawings with small foot-anchored shifts and
scales. These are not independently drawn frames, genuine perspective variants,
or verified seamless locomotion cycles.

## Build

```bash
python -m pip install Pillow
python scripts/build_wolf_animation_kit.py
python -m unittest tests_standalone.test_wolf_animation_kit -v
```

This generates `assets/animation_kits/wolf/sprites/wolf/*.png`, `registry.json`
and `kit.json`. The generated pack is deliberately opt-in, with its own
registry; it does not modify the original `assets/watercolor/registry.json`
or silently change the Player. Before using in a project, import the generated
sprites/animation entries into the project's asset registry and assign the
appropriate actor bindings.

## Included clips

| Clip | Playback | Usage |
| --- | --- | --- |
| idle | loop | breathing/stand |
| walk | loop | short movement |
| run | loop | fast traversal preview |
| alert | loop | perceived threat |
| growl | loop | threat vocalization |
| howl | once | pack signal |
| bite | once | melee attack preview |
| pounce | once | lunge/jump |
| defend | once | block/react |
| hit | once | damage reaction |
| death | once | transition to KO |
| dead | still | downed state |

Clip order, per-frame durations and fixed-foot pivots are exposed in
`kit.json` and the v1-compatible `registry.json`.

**Release gate (not yet certified):** artist must draw/approve true in-betweens,
all required camera directions, stable anatomy/pivots, transparent edges, 
contact frames for bite, walk/run foot sliding, and a live Studio/Player playback
at 24, 54 and 96px. This script alone does not meet that gate.
