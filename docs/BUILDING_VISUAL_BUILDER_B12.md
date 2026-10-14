# B1.2 — Visual Building Builder (direct manipulation)

## UX contract

After choosing **Bâtiments** in the main Studio navigation and switching to
**Iso 2.5D**, clicks on a visible roof, facade, window or door inspect the
**rendered part** rather than accidentally selecting a terrain tile behind it.

| Part | Selection | Context action |
| --- | --- | --- |
| Roof | Outline of selected roof, Exterior tab | Change roof via existing material selector / Apply |
| Facade | Exterior wall tile highlight | Add decorative window at that wall |
| Window | Exterior wall tile highlight | Remove that window |
| Door | Authored door tile highlight, General tab | Toggle between A/B **only if the structure template supports both** |
| Structure sprite | Real persistent structure ID | Select roof when pointer is over its roof silhouette; otherwise facade |

Unsupported operations are disabled. Clicking empty ground clears the
Building inspector's selection without changing tiles. Other Studio modes and
the Player retain their previous click behavior. Direct roof/window selection
does not start an implicit move operation (dragging a component must not
displace the entire house).

## Technical design

- The new `building_visual_picker.py` is read-only and headless. It uses
  Canvas `architecture_*` tags from `iso_architecture.py`, painter order,
  and the existing `IsoGeometry.architecture_instances` identities.
- The existing `structure_at` and building appearance commands remain the
  source of truth for whether a clicked element belongs to a structure and
  whether a wall may accept a window.
- All authoring actions go through `design_change` and the current
  `Document`/Studio global history. No raw Canvas mutations represent edits.
- Selection overlays are presentation-only, tagged
  `building_component_selection`, recreated with the shared map renderer.
- An editing selection does not automatically cut away the roof. Interior
  visibility still follows the user's explicit **Intérieurs** switch.
- Changes to mission, structure ID, or anchor invalidate a stale part pick.
- **No additional save schema**, custom tile type, second renderer or player
  collision rules. Doors use `StructureCommand` and only legal slots;
  windows remain visual and never create tactical openings.

## Gates

```bash
python -m unittest tests_standalone.test_building_visual_picker_b12 -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a -s "-screen 0 1600x900x24" \
    python -m unittest tests_standalone.test_building_visual_b12_gui -v
```

The GUI test constructs an authored Maison with vector facade, selects its
actual rendered roof and facade, adds a window on a supported exterior wall,
saves/reloads, then removes the window. Unit tests independently cover window,
door, roof, facade, painter order, malformed tags and empty areas.

## Follow-up boundaries

B1.2 **does not** create arbitrary wall/door geometry: those are determined by
existing `structure_template` plans. B1.3 can introduce room editing,
stairs and furniture, but must use the canonical interior authoring model and
define a separate Player compatibility gate. A future exact sprite alpha
picker is a possible polish task; until then the visible roof geometry
distinguishes roof vs facade for whole-building PNGs.
