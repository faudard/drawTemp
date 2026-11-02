# Visual Character Generator (R7)

The optional Qt Widgets Character Studio now exposes the existing
`assets/hero_parts/` library in a RPG Maker-style workflow:

1. Choose **Modular Hero** from the template list. This is a 192 x 192
   transparent four-direction character recipe, with the existing `classic`
   body sprite selected. Existing 64 x 64 Jeanne outfits remain unchanged.
2. Select an **Appearance category** in the left pane (Body, Face, Hair,
   Eyebrows, Nose, Mouth, Clothing, Weapons, and other authored slots).
3. Click a thumbnail in **Variation**; **None** removes that part.
   All four authored directions are selected together. Existing layer tint,
   opacity, and offsets survive changes of part variation.
4. Apply a preset color or choose a custom color. Adjust alpha and use
   **Offset X/Y** or the directional arrows to move **only the selected part**,
   in 1-pixel steps, on **all four directions**. Changes are live, undoable
   (Ctrl+Z), and persisted in the normal R7 character JSON.
5. Use **Existing poses** to navigate authored action/direction clips
   (idle/walk/run/attack/magic/hit/block/death/victory). The timeline still
   edits individual keyframes. Select an action and create missing poses
   from actual artwork as needed.

All operations reuse `CharacterSession`, `render_frame` and
`export_pack`. The published file format remains AssetRegistry v1:
`atlas.png`, `registry.json`, `character.json`.

**Art boundary:** `assets/hero_parts` supplies 192 x 192 static directional
parts, **not** complete frame-by-frame walk/attack sets. The Modular Hero
template therefore includes only authored `idle` directions; it does not
duplicate idle frames and claim to have created movement/combat poses.
Existing R7 action clips are displayed as-is, and they can be authored in
the established animation timeline. Existing non-192 recipes cannot import
these parts without separately supplying art at their canvas resolution.
Custom PNGs still use the existing **Configure layer…** workflow.

## Run and check

~~~sh
python -m pip install ".[qt6,art]"
python -m drawtemp.studio.character_studio --root .
python -m unittest tests_standalone.test_drawtemp5_r7_character_parts -v
python -m drawtemp.studio.character_studio --root . --smoke
~~~

The tests check direction families, recipe validation, invalid paths,
frame rendering, tint/offset persistence, undo/redo and pack export.
GUI visual review and cross-platform smoke are still required.
