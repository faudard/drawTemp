# Storybook v1 — first original chibi art collection

## What is genuinely new

The Character Studio no longer has to rely solely on mixing and recoloring the
historical RPG pieces. This PR adds a reproducible **original art source** in
`drawtemp/assets/storybook_art.py`. On launch it materializes **128 genuine
192 × 192 RGBA PNG sprites**, all with a transparent background and one
coherent, ink-outlined, softly shaded tactical-chibi art direction.

| Modular art category | Distinct illustrated families | Directions | PNG count |
|---|---:|---:|---:|
| Bodies (adult/slender, sturdy, child) | 3 | 4 | 12 |
| Head silhouettes (oval, soft, young) | 3 | 4 | 12 |
| Front Hair (including fringe, swept, waves, spikes) | 6 | 4 | 24 |
| Rear Hair (including bob, curls, braid, ponytail) | 6 | 4 | 24 |
| Torso clothing (tunic, brigandine, robe, hoodie) | 4 | 4 | 16 |
| Lower clothing (pants, shorts, skirt, boots) | 4 | 4 | 16 |
| Facial expressions | 3 | 4 | 12 |
| Eye designs | 3 | 4 | 12 |
| **Total** | **32** | **4** | **128** |

This is **not** a pack of separate finished walking/attacking animations;
each piece is a static directional drawing that can be stacked into the
existing 192x192 R7 canvas. Back-facing eye and face layers may be
intentionally transparent because the character looks away.

Unlike the interim hair split, these Front Hair and Rear Hair silhouettes
are independently defined from the outset, rather than alpha crops of the
same legacy PNG. Male, Female and Kid starter appearances each have their
own body/head proportions and coordinated hair, face and clothing. Every
part remains customizable; there are no gender- or age-locked slots.

**Art production method:** manually designed vector-style primitives drawn
deterministically using Pillow, with soft antialiasing, outlines and palette.
These are original procedural concept artworks, not externally sourced art
or an unmodified AI sheet. Quality still needs human art-direction review;
they are a first genuinely separable kit, not an assertion of
commercially polished final character sprites.

## Technical integration

- Start `Character Studio`: the **Storybook Hero · Original Art** template
  is now the default, with Male / Female / Kid tabs and twelve additional
  coordinated looks (four per profile). All are four-direction composites.
- Each generator output is namespaced
  `assets/hero_parts/{slot}/storybook_v1_{name}_{front|right|back|left}.png`.
  No pre-existing PNG is overwritten. Importantly, it is the **drawing
  recipe** that is versioned; actual PNG files are built locally on demand.
  The build is idempotent and deterministic, and the generated assets are
  portable and can be committed to the project if desired.
- The editor's variation picker and compositor discover these PNGs through
  the existing `PART_CATEGORIES`, `part_paths`, `CharacterSession` and
  `render_frame` mechanisms. No new game/runtime file format.
- Rendered R7 source frames and full composites use the same canvas,
  coordinate origin and fixed pivot (96,191). New source elements start at
  [0,0] offset with independent color, opacity and X/Y adjustments.
- Original Jeanne/prototype library and original Modular Hero template
  remain available from the searchable library.
- Export still emits standard `character.json`, `atlas.png` and
  `registry.json`; incomplete actions are called out by the pre-existing
  non-strict art QA and strict release gate.

## Commands

~~~powershell
python -m pip install -e ".[qt6,art]"
python -m drawtemp.assets.storybook_art --root .
python -m drawtemp.studio.character_studio --root . --template storybook_hero
python -m drawtemp.assets.storybook_art --root . --preview storybook_preview.png
python -m unittest tests_standalone.test_drawtemp5_r7_storybook_art -v
~~~

The optional `--preview` contact sheet contains twelve full looks, each
rendered from their four actual directional composites. Use it as an art QA
board; it is not the source sprite atlas.

### Art QA definition of done

A category variant is considered ready only when the four directional RGBA
PNGs have the correct 192x192 size and common pivot, meaningful visual
differences across directions, controlled alpha, no missing source paths,
a plausible overlay order, stable deterministic bytes, and a successful
character composite and atlas export. CI tests these structural properties.
It does **not** certify all anatomy, styling or motion animation frames.

### Next original-art milestone

Manual illustration pass on hand-drawn FFT-like character proportions,
consistent chibi shoulders, hair/head occlusion and eyes; add contextual
weapons, helmets, capes, and face-portrait expressions. Next, draw complete
separate idle/walk/attack/hit/death frames in all four orientations for each
chosen starter, with timeline preview, instead of duplicating static art.
These future artworks are not included in the present 128-PNG package.
