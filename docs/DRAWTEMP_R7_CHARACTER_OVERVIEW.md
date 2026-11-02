# Character Studio — Always-visible Overview & Scalable Library

## Why this refactor

The old desktop workbench showed a combobox labelled "Existing models",
multiple historic Jeanne-only controls, and a preview hidden between tools
and editing switches. For a sprite creator this is not the primary workflow.
The character must stay visible while selecting a body, face, hair, outfit,
color or offset — as in the RPG Maker reference workflow.

## Workspace

- **Character Library dock** (left, searchable, thumb grid, hide/dock/undock):
  a click selects a card, double click/Enter opens it. Filtering never changes
  the current character. Built-in templates and project-owned
  `characters/*.character.json`, `assets/characters/*.character.json` or
  `assets/character_recipes/*.character.json` share the same validated R7
  recipe contract. A Refresh action rescans these folders. Invalid oversized,
  inaccessible or malformed files are ignored.
- **Appearance categories** (permanent): choose Body, Face, Eyes, Front Hair,
  Rear Hair, Clothes, and other supported layers. Editable outfits and facial
  expressions are kept here, along with a small art QA summary.
- **Variations** (permanent): tiled thumbnails of all four-direction variations,
  color presets, custom color, opacity and 1px X/Y controls. Selection updates
  the actual character composite without changing gameplay data.
- **Ready-made looks** (permanent): 15 curated combinations across the existing
  Male/Female/Kid profiles, five each. Villager, Knight, Ranger, Mage, Guard,
  Apprentice, Scout and Traveller are combinations of the **existing** art
  library; they are NOT 15 newly illustrated full sprite sets. Apply to a
  variant in one undoable edit. Reusing a look never overwrites authored clips
  or other characters.
- **Character overview** (always visible): main live transparent checkerboard
  sprite, cropped face or authored portrait, four independently rendered
  cardinal views, existing poses with direct action selection, outfit tabs
  and animation playback. Missing art is labelled "Not authored", not filled
  with unrelated source frames.
- **Animation Tools dock** (bottom, initially collapsed): timeline, duration,
  PNG source, atlas regions and keyframe offsets. From **View → Animation
  Tools** the user can open it without losing the main overview.

The **New Character…** entry is generic; the old Jeanne-specific outfit
generation controls are removed from this UI. Existing Jeanne material is
still readable as a legacy character recipe. Existing R7 authored art
generation commands remain available as separate CLI tools.

## Growing the art library

**Already available:** the versioned `assets/hero_parts` source library has
directional RGBA art families for body, face, eyes, hair, clothes, accessories,
weapons, etc. Each has a transparent 192×192 pixel canvas and common origin.
The 15 looks make different characters by combining these *actual* parts.

**Recommended art-production backlog** for genuinely richer output:

| Folder/category | Next original art target | Expected format |
|---|---|---|
| front_hair | 12 new fringe styles | 4 × 192×192 transparent PNG |
| rear_hair | 12 long/short silhouettes | 4 × 192×192 transparent PNG |
| body/head_shape | 6 new body proportions, including a true child silhouette | 4 PNG per variation |
| face/eyes/brows | 12 coherent face combinations | Complete four-way sets |
| top/bottom | 15 outfits (peasant, knight, scout, mage, etc.) | 4 PNG per piece |
| cap/accessory/weapon | 20 authentic accessory sets | Complete four-way sets |
| authored animations | idle/walk/attack/hit/death, distinct actual frames | Existing R7 timeline clips |

These are **targets**, not claims that the new illustrations are complete.
New transparent PNG families placed in an appropriate existing category
appear automatically in the variation picker. Front/Rear Hair retains the
documented legacy-art fallback until genuinely separated art is supplied.
The source art remains untouched, and the compositor keeps the R7 format.

**Default placement:** current source parts are already registered to the
same 192×192 canvas, so their origin is X=0/Y=0. The look catalog explicitly
stores these defaults by slot. Future art variants can be given documented
offsets and should preserve the foot pivot at (96,191). Offsets remain
independent and editable in the GUI.

## QA and limitations

Headless tests cover look metadata/real images, independent profile variants,
JSON-library searching, malformed-file rejection, undo/redo and animation
isolation. The CI also builds and opens the real Qt workbench offscreen and
asserts the four-view overview, populated library and initially collapsed
timeline tools. This is not a replacement for human visual review on Windows.

~~~powershell
python -m pip install -e ".[qt6,art]"
python -m unittest tests_standalone.test_drawtemp5_r7_overview -v
python -m drawtemp.studio.character_studio --root . --template modular_hero
~~~

On first launch **Modular Hero** is selected (unless `--open` or another
`--template` is supplied). To switch to other templates, use the Character
Library dock, not a combobox. Use Ctrl+L to focus search and Ctrl+S to save.

**Remaining known art gap:** these existing part families provide directional
static appearances. Walk/run/combat pose sets are not fabricated; they must be
authored and approved independently.
