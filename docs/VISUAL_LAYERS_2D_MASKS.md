# PR 3 — 2D graphical layers, quadrant alpha masks, stacking and depth

## Why a separate graphics stack?

The existing R5 `MapLayersDock` manages **functional editing categories** such
as Terrain / Objects and stores editor visibility/locks in a `mapbuilder-view.json`
sidecar. It is not a Photoshop-style graphic stack and its visibility cannot
drive Player output.

This PR adds a distinct, persistent **Graphic Layers 2D** dock. The graphics
are stored in the canonical `GameProject.extensions` envelope under
`org.drawtemp.visuallayers` (`schema_version: 1`), validated when the project
is loaded in the Studio **and** Player. There is no third project file.

## User workflow

1. Open **Maps**, set **View → 2D**, then open **Graphic Layers 2D**.
2. Click **+** to create a named layer. The top of the list is the foremost
   layer; **↑ / ↓** reorder it. The checkboxes toggle eye and lock.
3. Adjust **Opacity (0–100%)** or **Depth: Below actors / Above actors**.
4. Select a graphic layer, choose **Layer Paint**, and pick a material in
   **Tileset 2D** or the existing Surface selector; drag on the map.
5. Choose **Mask Paint** and set **NW / NE / SW / SE** alpha 0–255 to
   reveal/hide the corresponding 32×32 tile quadrants. Repeated strokes
   update the selected graphic's mask without changing the base material.
6. Choose **Layer Erase** to delete that layer's sprite at the painted cells.
   Switch back to **Terrain** to paint original gameplay surfaces.
7. The normal **Save Project** and **Undo / Redo** commands persist/revert
   the graphic operations. Locking prevents painting and removal.

A single map cell may contain different materials in different graphic layers,
and a mask can expose the art beneath it. Layer order, opacity and actor-depth
plane affect the actual Qt Quick rendering and are not merely edit-time toggles.

## Model and rendering

Each map has up to 16 ordered graphic layers (lowest first); a layer contains
an ID, name, visible/locked states, opacity, depth plane, and sparse cells.
Each graphic cell stores:

```json
{"pos": [2, 3], "material": "grass", "mask": [255, 0, 128, 255]}
```

Alpha order is **NW, NE, SW, SE**, 0 = transparent, 255 = opaque.
The mask is a four-quadrant alpha map, not an arbitrary pixel-resolution
Photoshop layer mask; freehand pixel brushes are future work.

**Depth policy:** `below` graphics render above the ground but below
characters/objects; `above` render after characters. Within a plane,
the ordered stack controls which graphic is in front. A layer does not
add collision, height, event triggers or movement cost.

The R3 renderer emits visible `visual-layer` draw rows only in top-down
projection. Their `visualKey` addresses the **existing PR 2 bounded Qt
image provider**, which composites masked PNG images without a per-cell
QML Canvas. Sprite alpha can differ per quadrant and the per-layer opacity
then scales the result.

Both the Map Studio and the Player can consume the graphic-enriched detached
scene. The Player's original default isometric camera is unchanged; this
extension only draws when a client chooses the 2D projection.

## Validation, safety and compatibility

- No untrusted scripts, shader code, external URLs or absolute file paths.
- All layer data are checked during `GameProject.from_dict`; invalid mission
  references, duplicate cells/IDs, unknown materials, invalid alpha or
  excessive layer sizes fail closed.
- Editor changes commit via the existing `AuthoringSession.preview_pair`,
  giving one Undo step per stroke. No private history or saves.
- Limits: 16 layers per map and 640 graphic cells per project, also subject
  to the canonical extension's 64 KiB JSON size limit.
- Old maps lacking this extension remain unchanged and render identically.
- The existing functional layer sidecar is unaffected.
- Existing terrain autotiles, collisions, combat rules and save formats
  are unaffected.

## Integration

**Integration PR targets current `master` directly**, which already contains
PR 2's 2D atlas/image provider and the Editor/Events UI. The earlier stacked
PR #486 was merged into the obsolete PR 2 branch, not into `master`; this
rebased integration PR is the actionable path for shipping visual layers.

## Tests and CI

```bash
python -m unittest tests_standalone.test_visual_layers_stack -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_visual_layers_stack_qt -v
```

`.github/workflows/drawtemp-visual-layers.yml` covers Windows/Ubuntu
canonical authoring, model compatibility and offscreen Qt render tests.
The PR must not merge until the required tests are green.
