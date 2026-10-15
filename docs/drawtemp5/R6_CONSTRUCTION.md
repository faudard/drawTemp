# DrawTemp 5.0 — R6 Construction Studio: integration contract

This branch implements an **incremental R6 authoring slice** on top of the
already-validated legacy structure and R1 authoring implementations. It does
not claim completion of the roadmap's full P2D renderer/geometry gate.

## Available today

- `drawtemp.sdk.construction.ConstructionWorkspace` operates on the existing
  `AuthoringSession`. Every edit is a **validated preview**, followed by
  an explicit **apply** producing exactly one Undo/Redo transaction.
- Presets come from `sporebound.iso_structures`: Maison, Tour, Ruines,
  Rempart, Escalier, Pont. Placement, duplicate, rotation, door slot, move and
  removal reuse the canonical footprint, underlay and gameplay validators.
  Arbitrary resizing/freeform walls are not implemented by these templates.
- Materials (façade/toiture) and decorative windows reuse
  `sporebound.building_visuals`. Windows **do not** change tactical collision,
  cover, LOS or pathfinding.
- Stacked authored interior decks reuse `sporebound.interior_levels`, with
  surfaces and small decorative features. **These are visual floors, not
  gameplay-authoritative multilevel navigation.**
- Selection uses a typed `ConstructionPick(structure_id, anchor, cell, part)`
  supplied by the real rendered geometry. The controller validates stable
  IDs, anchors, footprints, exterior walls and existing window positions; it
  rejects stale picks and out-of-date edit plans.
- `drawtemp.studio.construction_dock.ConstructionDock` supplies an opt-in,
  real Qt 6 dock for preset placement, materials, doors, windows, levels,
  cutaway intent, undo and redo. It never imports Tk.
- Preserving `Content` and `GameProject` means the historical Player
  consumes the same tactical terrain and structure records. No new
  serialization/migration format is introduced.

## Wiring it into the new R2/R3/R5 applications

```python
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.construction import ConstructionWorkspace
from drawtemp.studio.construction_dock import ConstructionDock

authoring = AuthoringSession.open("jeanne.json")
buildings = ConstructionWorkspace(authoring, "your_mission_id")
dock = ConstructionDock(buildings, main_window)
main_window.addDockWidget(Qt.RightDockWidgetArea, dock)

# Renderer contract: only send a hit resolved by the *drawn* part geometry.
# For no hit, pass a null structure_id.
renderer.building_part_picked.connect(dock.on_renderer_hit)
# Each mutation asks the shared renderer to invalidate affected view regions.
dock.committed.connect(refresh_shared_scene)
dock.level_changed.connect(renderer.set_active_floor)
dock.cutaway_changed.connect(renderer.set_roof_cutaway)
```

The `renderer` and `refresh_shared_scene` names above are integrator-supplied
contracts, **not existing R3 APIs**. Integration must bind actual Qt Quick
picking in R3 and the main map tools/docks in R5; it must not create an
independent Widget canvas or derive a clicked building from guessed pixels.

## Acceptance paths

```bash
python -m unittest tests_standalone.test_drawtemp5_r6 -v

# Python 3.12 + pip install '.[qt6]'
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp5_r6_qt -v
```

A headless test builds a Maison from the Jeanne reference Content, changes the
roof and facade, adds a window, creates two interior decks, paints one cell,
checks tactical board invariance and confirms Save As → Open parity.
Additional gates reject overlap, forged/stale hits, invalid openings and stale
previews; Undo/Redo uses R1's revisioned document history. The Qt smoke exercises
actual dock controls under an offscreen platform.

## Remaining R6 gate items — **not yet certified**

| Roadmap lot | Status in this slice | Remaining |
| --- | --- | --- |
| R6.1 Workspace | Partial: usable Qt dock and SDK | R5 dock registration and native viewport focus |
| R6.2 Geometry picking | Partial: typed/validated render-hit contract | Real R3 roof/wall/window/door GPU hit pass and occlusion QA |
| R6.3 Footprints | Partial: template move/rotate/duplicate | Arbitrary resize/crop and shape constraints |
| R6.4 Walls & roofs | Partial: preset walls, roof style | Modular per-segment geometry, joins/openings |
| R6.5 Materials | Partial: facade/roof presets | Paint each surface with authored palette/atlases |
| R6.6 Volumes | Not started | Cliffs, ramps, relief blending with R5/R3 |
| R6.7 Interiors | Partial: decks, surfaces, decorative props | Rooms, active floor cuts, navigable stairs and furniture |
| R6.8 Fortifications | Partial: Rempart/Tour templates | Gates, drawbridges, siege constructs/logic |
| R6.9 Prefabs | Partial: existing canonical catalog | Custom groups/templates and visible asset library |
| R6.10 Gameplay | Partial: existing ground collision and door slots | True multilevel LOS/traversal and door open/closed actions |
| R6.11 Visual QA | Partial: headless/save/Qt widget tests | GPU goldens, Studio/Player parity, real user click tour |

**R6 product gate remains open** until the shared renderer/Player can
create a two-level house, cut away the roof, navigate between actual gameplay
floors, and reload the same appearance and collision state. No green headless
test alone should be taken as visual certification.

## R6.2 — construction in the shared R3/R5 viewport (follow-up)

The initial R6 PR delivered a dock and an abstract hit contract. This
follow-up **renders the real authored buildings** in the Qt Quick scenegraph,
then selects from the exact same projected polygons.

- `scene_from_mission` carries detached `structures` and `interior_floors`
  from canonical `Content`. Studio and Player call this same adapter.
- `building_geometry.building_surfaces` produces individually hit-testable
  south/east facade segments, roof polygon, window/door apertures and selected
  authored interior level tiles; each stores stable structure ID, anchor,
  world cell and (for deck cells) level. Invisible back faces are not pickable.
- The Qt Quick Shape renderer uses those polygon vertices directly.
  `RendererController.buildingAt` tests **only the currently visible rows**
  in reverse scenegraph painter order, using the same camera as tiles/actors.
- The R5 map window adds a contextual **Construction 2.5D** workspace and
  hooks its actual shared renderer's clicks into `ConstructionDock`. Switching
  maps/projects clears stale building identity and keeps one R1 undo history.
  Switching back restores map-painting controls. There is no competing renderer.
- A cutaway hides the visual roof and reveals only authored floor tiles.
  Clicking a floor picks its real level and cell; an un-authored deck or a
  stale selection is rejected by the SDK.

### Verification and limitations

```bash
python -m unittest tests_standalone.test_drawtemp5_r6_geometry -v
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp5_r6_geometry_qt -v
```

These tests check real roof/door/window polygon hits, camera pan and zoom,
cutaway and floor identity, invalid floor picks, canonical save/load parity
and Qt dock-to-map integration. Geometry uses stylized vector faces until R4
asset/atlas mapping is ready; it does not yet provide modular roof segments
or customized footprints. **Upper floors remain decorative, not tactical
traversal/LOS**, so **the complete R6.10 / overall R6 product gate remains
open**. A later dedicated lot must add tested multilevel core semantics
without inventing a second combat state.

## R6.10 — tactical building gameplay (stacked on R6.2)

This tranche connects the existing *validated* multilevel Battle rules to
the construction tools and the standalone Qt Player; it does not invent
separate gameplay physics or a second persistence format.

**Contract and gameplay behavior**
- `ConstructionWorkspace.preview_staircase(world_cell, from_level=N)`
  creates a same-cell, adjacent-floor `level_links` connector via canonical
  authoring. Both endpoints must be walkable and inside the selected building.
  Missing decks, walls, duplicate connectors and invalid costs are rejected
  atomically. The Qt construction dock exposes the landing coordinates and
  floor pair; each edit is one Undo/Redo transaction.
- `preview_gameplay_door()` creates a normal `kind: door` mission object at
  the template's unique entrance, which the Battle already knows how to
  represent as a dynamic blocked/unblocked ground tile. Authoring refuses
  occupied entrances and duplicate objects; visual windows remain cosmetic.
- `door_toggle` is a new replayed Battle command for opening/closing an
  *unlocked* adjacent, ground-floor door. The acting player spends an action.
  Closing on any living ground-floor occupant is rejected. Replay checksum
  and GameSession persistence use the existing battle objects/board.
- `level_move` continues to use the existing authored stair links and
  Dijkstra path budget, so locked/closed door tiles block both ground walking
  and access to upstairs stairs until opened.
- Above ground, only **authored deck cells** are walkable. Crates and pillars
  block movement, and gaps/solid props block same-floor supercover LOS;
  the ground LOS still uses the original tactical board and remains
  byte-for-byte compatible for legacy missions.
- Upper-floor basic ranged/focus attacks may use this validated LOS, while
  normal melee remains range 1. Cross-floor shooting still requires the
  conservative authored aperture rule `level_attack`: a solid ceiling
  prevents projectile fire. Defensive reactions/engagement use each actor's
  actual floor, without interception or overwatch through decks.
- `PlayerController.level_move / level_attack / toggle_door`, Qt bridge
  and QML controls make these commands available without hand-writing JSON.
  The Player shows authored links and current unit floors. Studio/Player
  share the same Content and Battle state; no extra runtime save schema.

**Qualification**
```bash
python -m unittest tests_standalone.test_drawtemp5_r6_10 \
  tests_standalone.test_vertical_combat_3720c2 -v
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_drawtemp5_r6_10_qt -v
```

Acceptance covers a locked entrance, opening it before using stairs to N1,
rejected closing on occupied ground, no LOS through deck holes or pillars,
two-level authorship, history, Battle.replay equality and Player save/load.
This remains a constrained floor graph rather than freeform room walls,
simulation of siege gates on multiple elevations or physically modeled
vertical beams. Those are still future R6.4/R6.8/R6.11 and R14 certification
work; a green headless check alone does **not** complete the full R6 gate.
