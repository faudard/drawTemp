# Map Builder 4.0 — 3.7.32A: intelligent brushes and bounded fill

This increment **extends** the already shipped Map Editor 3.0 tools. It does
not introduce a second terrain engine, tile format, brush registry, or renderer.

## In the Studio

- Select a **Sol** or **Décor** material, then choose **Pinceau intelligent**.
- Set **Rayon** from 0 to 3 and **Forme** to `diamond` (Manhattan) or `square`.
- Click or drag over the tactical/iso canvas. The same integer line helper as
  the existing brush joins skipped pointer cells. One stroke produces **one**
  undoable, Content-validated edit. A large stroke draws a bounded cursor
  preview rather than thousands of preview shapes.
- For local zone replacement, choose **Sélection**, select a rectangle, choose
  a **Sol**, then click **Remplir sélection**. The flood affects only cells in
  that selection which connect to the starting cell and share its old surface.
  For unrestricted replacement, keep using **Remplir sol**.

## Authoring and rendering contract

`map_builder4.smart_brush_cells` and `surface_region` are headless planners.
They validate the mission and anchors, never mutate inputs and have stable
row-major ordering. `Document.smart_paint` and `Document.flood_surface`
commit the plan through existing `paint_many`, `Content.from_dict`, and
`Document.replace`.

- Surface changes preserve features, height, goals and other unrelated tile
  fields. Ordinary water/bridge block rules continue to apply.
- The **existing** `iso_connections.shoreline_mask` and `bridge_axis` derive
  new water-bank and bridge junctions from neighbour data when rendering.
  No explicit connector data need be saved.
- Invalid strokes (blocked spawns, unsupported brush combinations, bad
  coordinates) are rejected atomically, leaving history unchanged.
- No change to mission JSON, the engine, battle replays or Player persistence.

## Verification

```bash
python -m unittest discover -s tests_standalone -p 'test_map_builder4_3732a.py' -v
python -m unittest discover -s tests_standalone -p 'test_map_fill_3711.py' -v
python -m unittest discover -s tests_standalone -p 'test_map_editor_gui.py' -v
python -m unittest discover -s tests_standalone -v
```

Manual GUI acceptance: surface brush radius 1 in orthographic and isometric
views, pointer jumps, selecting a bounded region, changing its surface,
undo/redo, saving and reopening in the Player. Verify water/bridge shoreline
automatically reconciles after each brush operation.

## Next separate pull requests

- **3.7.32B:** façade, roof, opening, stair and furniture editing using the
  existing interior/structure authoring model.
- **3.7.32C:** persistent visual layer visibility/locking and active floor
  without conflating `tile.height` with tactical floors.
- **3.7.32D:** reusable building and district prefabs backed by standard
  authoring structures, not live script objects.
- **3.7.32E:** deterministic assisted generation with diff preview, one-undo
  apply and post-generation manual editing.

The final fortified-square gate is reserved for an end-to-end Player scenario
after all five increments are integrated, not declared passed by 3.7.32A.
