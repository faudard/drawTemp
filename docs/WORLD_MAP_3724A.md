# 3.7.24A — World Map : mission graph projected onto an authored world

## Delivered scope

A campaign can now carry an optional **world map** in its existing
`.game.json` (GameProject v1), with one location per referenced mission.
World locations store **presentation coordinates only**; they are **not**
tactical tile positions. The canonical narrative/tactical route graph remains
`Mission.next_missions`, and the Player checks the existing
`GameSession.available_missions()` before ever starting a battle.

This is the first slice of **3.7.24 World**, not a general continuous
open-world engine or a travel-time simulation.

## Studio — authoring a world without JSON editing

1. Open the Editor → **Espace projet** → **Carte du monde** (or the **Monde** tab).
2. Click **Créer la carte du monde**. It places all existing missions
   automatically and draws the real mission links.
3. Click a marker to select a mission. Drag it to a new map coordinate.
   Dragging only previews the marker; on mouse release the entire proposed
   project is validated before replacing the in-memory GameProject.
4. Assign a region, select a theme, or add/remove visible mission markers.
   Removing a marker does **not** remove its mission or rewrite its links.
5. Use the Editor's **Annuler/Rétablir** and **Enregistrer tout** controls:
   the existing `StudioHistory` and `StudioTransactionStore` own recovery
   and atomic saves of Content and GameProject.

The editor disallows unknown/duplicate mission markers, coordinates outside
the map, unsupported themes, missing campaign start markers in a partial
world, and more than 160 world locations. All edits are copy-on-write;
a rejected action leaves the previous project and StudioHistory untouched.

## Player — world navigation

During the campaign when there is no active narrative scene, the
**Carte du monde** button opens the same visual projection used in Studio.

- **Green** = mission in `GameSession.available_missions()`.
- **Blue** = completed mission.
- **Grey** = locked or currently unavailable mission.
- Clicking green starts the existing cinematic/mission sequence.
- Clicking grey/blue never starts a battle or changes progression.
- Existing campaign mission list remains available, including missions not
  represented on a partial world map.
- A narrative scene must be resolved before visiting the map; scenes cannot
  be skipped using world markers.

`GameSession` now excludes only the optional decorative `world` field
from the verified **project fingerprint**. This preserves existing saves
after moving or adding presentation-only map pins, while all other content,
rules and campaign configuration continue to be strictly verified.
The actual Campaign save schema and tactical replay format are unchanged.

## Technical ownership

| Responsibility | Existing source or new module |
| --- | --- |
| Tactical mission IDs, graph, unlocks | `Content`, `Mission.next_missions`, `GameSession` (existing) |
| Presentation metadata | `GameProject.world` (optional) |
| Headless validation, transforms, hit testing | `sporebound/world_map.py` |
| Studio + Player graphical projection | `sporebound/world_map_view.py` |
| World authoring and inspector | `sporebound/studio_world_map.py` |
| Existing Studio history and saved project pairing | `StudioHistory`, `StudioTransactionStore` |

Example optional project field:

```json
{
  "world": {
    "width": 960,
    "height": 640,
    "theme": "parchment",
    "nodes": [
      {"mission": "garden", "x": 100, "y": 105, "region": "Valcroix"}
    ]
  }
}
```

**Note:** The example assumes that the campaign's starting mission is
`garden`. Other campaigns must place their own starting mission whenever
they have a represented reachable node.

## Validation gate

- `python -m unittest tests_standalone.test_world_map_3724a -v`
- `SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest
  tests_standalone.test_world_map_3724a_gui -v`
- Existing GameProject, GameSession, Studio history, editor,
  renderer and distribution suites across Linux/macOS/Windows.
- Manually compare the Studio and Player maps, check unlock constraints,
  create/edit/save a world and resume a legacy save.

## Deferred to 3.7.24B/C and later

- Region semantics, travel time, contextual random encounters and route
  costs (would require new gameplay/save contracts).
- Free-roam and multi-map streaming, map transitions to exploration scenes,
  physical character position and save/resume at world coordinates.
- Decorative terrain/coasts/roads from authored atlas rather than the current
  vector fallback, zoom/pan polish, localization and authoring 160+ regions.
- World-specific status of narrative events and editor side panels.

No implicit new gameplay rule or second mission graph should be introduced
while those topics remain unimplemented.
