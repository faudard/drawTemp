# 2D Tilesets & Four-Quadrant AutoTiles — PR 2

## What is delivered

The Qt Map Studio toolbar exposes a **View: Iso 2.5D / 2D** selector.
Switching views retains the existing `RendererController`, `AuthoringSession`,
current mission, zoom, and fractional map focus. The 2D view is **editable**:
the existing Pencil/Rectangle/Line/Fill/Erase brushes still commit through
the same validated R5 terrain transactions. Right-drag pans; wheel zooms.

A contextual **Tileset 2D** dock shows the eight original native-resolution
terrain sprite swatches. Choosing a swatch selects the existing R5 terrain
brush. The initial visual atlas is **8 materials × 2 variants × 64×64 pixels**,
generated as a deterministic RGBA PNG and decoded in memory by Qt. It does
not use copyrighted graphics from the example screenshot, external downloads,
Pillow or temporary files. Exported Player builds use this same atlas.

## How AutoTile 2×2 works

Each canonical map cell retains exactly one terrain `surface`, height,
collision, movement cost, objective and event state. For **display only**,
the 64×64 2D sprite is subdivided into NW, NE, SW, SE quadrants of 32×32.

Each quadrant checks three neighbors: two cardinal tiles at its external edges
and the diagonal tile touching its corner. Across four quadrants this covers
all **eight neighbors**. Every incoming material can contribute:

- bit 1: horizontal outer boundary (top or bottom);
- bit 2: vertical outer boundary (left or right);
- bit 4: diagonal-only corner (rounded transition).

The eight possible masks per quadrant yield smoothly feathered overlays.
Multiple incoming materials are ordered to handle three-material joins.
For 2D terrain, grass < dirt < sand < cobble < stone < rock, so roads
blend over grassy edges. This ordering is independent from the existing
ISO AutoBlend. Water, bridges and height discontinuities are excluded
from these land-only transitions (the pre-existing shoreline/bridge rules
remain untouched).

The visual result is deterministic and independent of painting order.
Changing one cell affects at most its 3×3 neighborhood. Qt Quick only
requests visible keys via `image://drawtemp-topdown/<10-digit key>`;
the provider keeps at most 256 **distinct 64×64 textures**, not one per cell.

## Files

- `drawtemp/render/autotile2d.py`: headless topology, masks and dirty halo.
- `drawtemp/assets/topdown_tileset.py`: self-contained original PNG atlas.
- `drawtemp/render/topdown_image_provider.py`: cached quarter-composition.
- `drawtemp/render/iso_scene.py`: keys on existing R3 top-down tile records.
- `drawtemp/render/qt_viewport.py`: provider and projection switch.
- `drawtemp/render/TopDownViewport.qml`: textured 2D shared Player/Studio.
- `drawtemp/studio/topdown_tileset_dock.py`: visual terrain brush selection.
- `drawtemp/studio/map_editor.py`: 2D/ISO selection and brush workflow.
- CI: `.github/workflows/drawtemp5-r5.yml`.

## Compatibility

No change to Content, GameProject, tactical commands, replay format,
collision rules, or renderer source of truth. Existing maps load and
automatically receive cosmetic transitions without migration. The existing
isometric and side-view presentations remain unchanged except for the
pre-existing reserved QML `layer` property correction (equivalent to PR #465).

**Not in this PR:** layered Photoshop-style art masks, project-imported
external custom tilesets, manual per-quadrant overrides, or event authoring
(those belong to the separate PR 1 and planned PR 3).

## Testing

```bash
python -m unittest tests_standalone.test_quarter_autotile2d -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_quarter_autotile2d_qt -v
```

Also run the R5 authoring/map Qt suites and full standalone regression matrix.
The new R5 GitHub Actions workflow filters include the tileset modules and
exercise these two test suites on Python 3.10/3.12 and Qt 6.8.3.
