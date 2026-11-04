# Studio 2D textured viewport — four-quarter AutoTiles

This change implements the original graphical 2D presentation in the **Tk Studio
map editor** (the `sporebound/editor.py` window), while reusing the existing
Qt/Player top-down atlas rather than creating a second set of materials.

## What changes on screen

- The 2D view renders actual **64×64 RGBA material textures** instead of flat
  green/gray rectangles. Eight materials (`grass`, `dirt`, `sand`, `stone`,
  `cobble`, `rock`, `water`, `bridge`) have two deterministic art variants.
- Four 32×32 quadrants derive their transitions from eight neighbors, using the
  **same topology, mask alpha, priorities and source art** as the Qt Player.
  Grass/dirt/sand/cobble/stone/rock edges feather; mixed materials stack in
  priority order. Neighbors at different elevations never bleed together.
  Water/bridge remain special surfaces, with an explicit water shoreline and
  high/low relief edge cue.
- Named transparent decoration/prop sprites, objects and character sprites
  use the existing packaged visual atlas loaders; placement is anchored to
  the bottom center of authored cells. Units, props, building stamps and
  objects are depth-sorted by map row; no more two-letter placeholders when
  their original sprites are present. Missing/invalid PNGs remain safely
  represented by vector fallback markers.
- Authored `org.drawtemp.visuallayers` `below` and `above` stacks from
  GameProject.extensions render using per-quadrant alpha and layer opacity.
  The draw order is terrain > below-plane art > props/buildings/actors >
  above-plane art > selection. Existing project and tactical JSON formats
  are unchanged. The graphics layers remain authored through the existing
  Qt visual-layer editor; this change reads them in the Tk viewport.
- The left scenery palette displays **actual 2D material texture swatches**
  in 2D mode and existing ISO thumbnails in ISO mode. A visible `Grille`
  checkbox toggles the optional grid without changing gameplay.

## Compatibility and memory

The composition is pure Python using the standard library PNG encoder, no
Pillow dependency, no extra third-party library, no external content or network.
`tile_rgba` is exported by the existing deterministic tileset module.
Tactical collision, movement cost, mission objectives, authoring tools, undo/
redo, paint radius, map picking, save format and isometric renderer are
unchanged.

Each distinct topology/zoom image is referenced by one Canvas-lifetime cache;
the image references are retained while Canvas items exist, so the cache never
evicts an image that would turn a rendered tile blank. The per-frame image
budget falls back to the corresponding base art at high topology cardinality.
Atlas PNGs and mask layers also have bounded LRU byte caches.

## Validation

Headless:

```sh
python -m unittest tests_standalone.test_topdown_tk_renderer -v
python -m unittest tests_standalone.test_quarter_autotile2d -v
```

Windows manual workflow: open a project in `DrawTemp — Game Studio`;
select 2D; paint grass, dirt, stone, water and bridge adjacent to one another;
verify boundary softness and water banks; add vegetation, a building,
characters and objects, then zoom and pan at different window sizes. Enable
and disable Grille, layer visibility and both visual-layer planes. Switch to
Iso 2.5D and back; playtest then stop; undo, save and reopen the same mission.
Check map click/drag accuracy, selected-cell outline and minimap centering.

**Scope:** this is a real textured viewport using the existing starter assets,
not a claim that all sprites have bespoke orthographic artwork. Producing a
larger, coherent 2D pixel-art set and project-imported tilesets is a separate
art/content milestone.
