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

The new preview is vector art composed with Tk Canvas, not a finished
painted tileset or a true 3D renderer. River connections and cliff faces
are geometric, with no asset atlas or animated water. A prop occupies one
cell; large objects can be authored as multi-cell stamps. The current
isometric picker targets the top diamond, not a vertical cliff face.
Playtests continue in the original tactical grid view.

Future steps: import authored sprite atlases, automatic shore transitions,
multi-cell decorative objects, depth-aware occlusion, and viewport caching.

## Regression gates

```sh
python -m unittest discover -s tests_standalone -p test_iso_map_builder.py -v
python -m unittest discover -s tests_standalone -p test_map_transform.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```
