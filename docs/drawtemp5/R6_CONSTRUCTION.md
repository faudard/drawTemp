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
