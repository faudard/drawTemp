# Visual Character Generator (R7)

The optional Qt Widgets Character Studio now exposes the existing
`assets/hero_parts/` library in a RPG Maker-style workflow:

1. Choose **Modular Hero** from the template list. This is a 192 x 192
   four-direction character recipe with three independent **Male / Female /
   Kid** tabs. Each preset starts from actual modular body, face, eyes,
   hair and clothing components. All categories remain fully available in
   every preset (no sex- or age-locked appearance choices). Existing 64 x 64
   Jeanne outfits remain unchanged.
2. Select an **Appearance category** in the left pane (Body, Face, Hair,
   Eyebrows, Nose, Mouth, Clothing, Weapons, and other authored slots).
3. Switch between **Male**, **Female** and **Kid** to work on independent
   editable variants of the same recipe. Changes to hair, color and offsets
   in one tab do not modify the other two. This is also safe with older
   `Modular Hero` saves containing only a `default` variation: selecting
   a new profile adds it without deleting the previous appearance.
4. Click a thumbnail in **Variation**; **None** removes that part.
   All four authored directions are selected together. Existing layer tint,
   opacity, and offsets survive changes of part variation.
5. Apply a preset color or choose a custom color. Adjust alpha and use
   **Offset X/Y** or the directional arrows to move **only the selected part**,
   in 1-pixel steps, on **all four directions**. Changes are live, undoable
   (Ctrl+Z), and persisted in the normal R7 character JSON.
6. Use **Existing poses** to navigate authored action/direction clips
   (idle/walk/run/attack/magic/hit/block/death/victory). The timeline still
   edits individual keyframes. Select an action and create missing poses
   from actual artwork as needed.

All operations reuse `CharacterSession`, `render_frame` and
`export_pack`. The published file format remains AssetRegistry v1:
`atlas.png`, `registry.json`, `character.json`.

**Profile limits:** The **Kid** visual starter uses a youthful face, hair,
eyes and clothing assembled from existing assets. The library does not yet
contain a separately drawn child-proportioned body, so this is not a
certified age-specific silhouette. The tabs are appearance presets, not
gameplay gender/age classifications.

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
python -m drawtemp.studio.character_studio --root . --template modular_hero
python -m unittest tests_standalone.test_drawtemp5_r7_character_parts -v
python -m drawtemp.studio.character_studio --root . --smoke
~~~

The tests check direction families, recipe validation, invalid paths,
frame rendering, tint/offset persistence, undo/redo and pack export.
GUI visual review and cross-platform smoke are still required.
The CI includes an offscreen Qt smoke test that actually switches through
all three profile tabs; no final CI result should be claimed before the
GitHub Actions jobs finish. Non-strict exports may include only authored
`idle` poses with a **missing_animation** diagnostic; strict production
exports still require the complete action/direction coverage.
