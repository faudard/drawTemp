# Isometric Map Builder 2.5D (3.7.9)

The editor now supports interactive, orthogonal map authoring in two views:
the existing top-down grid and a new editable isometric projection. Neither
view changes tactical coordinates or the underlying headless battle engine.

## Workflow

Open `python -m sporebound editor --content <content.json>`, choose a
mission, and toggle **Vue isométrique 2.5D**.

- **Sol** paints independent surface materials: grass, dirt, stone, cobble,
  sand, rock, water, bridge. Dragging interpolates missing cells.
- **Décor** paints trees, bushes, boulders, ruins, crates, lanterns,
  stairs and modular stone walls. **Effacer décor** clears the prop layer.
- **Niveau / Fixer niveau** paints absolute elevations 0..99. Legacy
  `height+` and `height-` brushes remain available.
- Use **Rectangle** for fills; **Sélection**, **Copier cases**, **Collage**,
  rotations/mirrors and reusable stamps for larger assemblies.
- `examples/river_stone_bridge.stamp.json` contains a 9x7 river crossing
  with elevated banks, a stone bridge, trees and ruins. Load it with
  **Charger modèle**, and click to place.

Each brush stroke is undoable in one history entry. Existing maps without
these fields are compatible.

## Data / simulation contract

A `Tile` gains optional `surface` (default `grass`) and `feature`
(default empty), both checked against allowlists by `Content`. The
existing terrain stamp version 1 is retained and now preserves these
attributes. The runtime remains headless; no external Tk dependency is
introduced to the tactical model.

Water automatically blocks a tile and a bridge reopens it. Stone walls
block their cells; clearing a placed wall unblocks that cell. Other props
are decorative and do not affect movement, cover or line of sight.
Collision-invalid edits are atomically rejected.

## Current rendering limits

The preview now uses an original, bundled transparent **PNG texture atlas**
(`sporebound/content/art/iso/terrain.png`), with 16 tiles:
8 materials × 2 deterministic texture variants, each 96 × 48 pixels.
`IsoTerrainAtlas` crops and caches resized Tk images for the current zoom,
and falls back to the vector rendering when unavailable. The atlas is
included in packaged wheels through `pyproject.toml`.
The textured tiles are a **first integrated art prototype**, not final
hand-painted illustrations. Cliff faces, tall props and water ripples
remain vector shapes. There is no animated water. A prop occupies one
cell; large objects can be authored as multi-cell stamps. The current
isometric picker targets the top diamond, not a vertical cliff face.
Playtests continue in the original tactical grid view.

Future steps: integrate polished painterly prop/character atlases,
automatic shoreline and bridge-end transitions, multi-cell decorative
objects, depth-aware occlusion, and viewport-aware draw caching.

### Atlas replacement contract

Artists can replace the bundled PNG while retaining the material ordering
`grass, dirt, stone, cobble, sand, rock, water, bridge`, two horizontally
adjacent variants per material, 96 × 48 pixels per frame (1536 × 48 total),
and transparent corners around each centered diamond.
Changing tile geometry or material identifiers requires updating
`ATLAS_MATERIALS`, `ATLAS_VARIANTS`, `ATLAS_TILE_SIZE` and the tests.
The source PNG is original to this repository; no sprites were sliced from
the supplied single-map illustration (which is not a reusable tilesheet).

## Regression gates

```sh
python -m unittest discover -s tests_standalone -p test_iso_map_builder.py -v
python -m unittest discover -s tests_standalone -p test_map_transform.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```
