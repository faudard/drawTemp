# Map-first Studio viewport UX (November 2026)

This increment improves the existing Tk map editor **without replacing**
the canonical renderer, project model, assets, authoring commands or playtest.

## Layout

- The quick-access bar stays beneath the native File/Edit/Mode/Draw/etc. menu.
- The main map-tool notebook now sizes itself to **the selected tool tab**
  rather than reserving the vertical space required by the largest hidden tab.
  Advanced tools can expand when selected; returning to Map & Combat gives
  the screen back to the canvas.
- Left dock: **Décors** (default) and **Projet** tabs. The scenery tree groups
  actual `PaletteEntry` records by ground, vegetation, props and structures,
  with cached atlas thumbnails and safe placeholders when PNGs are missing.
- Clicking an asset uses the *existing* validated placement path, and then
  clicking or dragging on the map applies the current brush. It does not force
  switching from 2D to isometric projection or open another editor.
- Right dock: existing inspector, groups, prefabs and building tools are
  preserved. Previously saved dock visibility remains customizable. Existing
  layouts first show the left and right dock to expose the new workspace;
  later sessions respect user choices.
- The project navigator is preserved under the **Projet** tab. Ctrl+F reveals
  it and focuses its existing search. The full asset browser remains available
  from the Décors dock.

## Viewport controls

- **− / +**: change map cell size in the existing 24–96 px support range.
- **Ajuster**: fit the current rendered 2D or isometric canvas scroll bounds
  into the viewport; then recenter.
- **Centrer**: pan to the middle of the rendered scene.
- **Ctrl+wheel**: zoom around the pointer (Windows/macOS; Control+Button-4/5
  for Linux). **Middle-button drag**: pan. Existing scrollbars and minimap
  navigation continue working.
- The selected zoom percentage is relative to the existing 54 px/cell base.
  It is an editor visualization setting, not a game data change.
- Playtest action is **Bootstrap-style green** when it offers to start and
  **red** when it offers to stop. The validated detached playtest and editing
  lock logic are unchanged.

## Limitations and validation

This is a **viewer layout/interaction** increment. The 2D tactical canvas
still uses its current schematic cell drawing. A future asset-quality pass
should implement a real orthographic 2D tileset renderer with autotile quadrant
masks and sprite previews; this PR does **not** claim to deliver new art.

Headless viewport math:

```sh
python -m unittest tests_standalone.test_map_viewport_controls -v
```

Manual Windows UX gate: launch `python -m drawtemp editor`, inspect the native
menu and Playtest colors, select terrain in Décors and paint a few cells,
verify undo/redo and save/reopen; switch 2D/Iso without changing map selection;
use Ctrl+wheel, Ajuster, Centrer and minimap; verify the bottom journal, right
inspector, full asset library, Project search, F11 map focus and persisted dock
visibility. Check at 1280×850 and smaller resizable window sizes.
