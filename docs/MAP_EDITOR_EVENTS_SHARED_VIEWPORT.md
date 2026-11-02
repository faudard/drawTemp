# R5 Map Editor / Events — shared viewport (PR 1)

## User workflow

Open **Maps** in DrawTemp Studio. The Map Editor toolbar contains a
**Mode: Editor / Events** selector.

- **Editor** retains map painting, construction, map layers and brushes.
- **Events** keeps the same Qt Quick IsoViewport and RendererController
  (zoom, pan, current mission and terrain are not reinitialized). Drag with
  left mouse to pan, use the wheel to zoom, and click a cell to select an
  event marker or choose a location for a new event.
- The contextual Events dock lists all mission events, including events with
  no map position. Trigger/effect markers share the canonical R3 renderer.
- **Add Event at Cell...** creates an enter condition with a message action.
  **Edit First Message...** updates the first message action.
  **Delete Event** removes the chosen event after confirmation. All mutations
  are R9 EventStudio / R1 AuthoringSession transactions and support Undo/Redo.
- Switching modes or selecting a cell/event does not change gameplay data,
  save schema or document revision. Switching missions clears stale selections.

## Architecture

The Qt-free MapEventSession adapter owns only a selected event ID and focus
cell. It delegates to EventStudio. There is no second event database, renderer,
event executor, document history or persistence sidecar. MapWindow switches
QML input policy between edit (paint) and select (event clicks), preventing
terrain painting in Events mode.

The mapbuilder-view.json sidecar remains editor-only. Tactical events stay in
canonical Mission.triggers. Playtest/export continues to use the same Player.

## Follow-up

Full event pages/graph editing remains in the existing R9 workspace.
2D tilesets, 4-quadrant autotiles and visual/mask composition layers are
separate follow-up PRs, not features claimed by this PR.

## Tests

    python -m unittest tests_standalone.test_map_event_session -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_map_editor_events_qt -v

Also run existing R5, R9 and Qt viewport suites in CI.
