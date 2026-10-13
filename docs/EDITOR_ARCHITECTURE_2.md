# Editor Architecture 2.0 — migration progressive (3.7.23)

## Baseline

At introduction `sporebound/editor.py` has 2,167 lines. Keep the original
Tk widgets and callbacks, engine `Battle`, `Content` serialization and
`Document` undo/redo. **Do not introduce a parallel editor schema, a new
world model or a new rendering engine.**

## New boundary: `editor_architecture.py`

- `EditingContext` owns the current Document pointer, mission resolver,
  controllers, revision counter and change subscriptions. It does not own
  the UI or change the file schema.
- `SelectionController` contains the selected mission, focus cell and
  selected cells. `ToolController` mirrors the existing Tk tool selector.
  States are non-persistent and notify only affected views.
- Typed `StructureCommand`, `EntityCommand`, `TacticalEventCommand`
  call the **existing** headless authoring functions: `edit_structure`,
  `entity_editing` and `event_graph.update_condition`.
- `preview` computes a validated Content snapshot without mutation or
  history changes. It pins the origin with a SHA-256 fingerprint.
- `apply` rejects an outdated preview, uses **one** `Document.replace`
  (same Content + authored rules, same undo transaction), increments the
  revision and emits `EditorChange` only after commit. Rejected edits have
  no notifications and no undo entries.
- `ChangeNotifications` dispatches by views (`renderer`, `inspector`,
  `minimap`, `workspace`). It is Tk-free.

## Integrated vertical slice

The Map Editor uses this protocol on:
- Structure edits, moves, duplicates and nudges, including the `Pont`.
- Existing actor and object move, duplicate, edit and remove.

For these commands `design_change` still owns Studio history and JSON
synchronization, but delegates each affected redraw to the subscribed
consumer. `refresh(views=...)` isolates the established renderer cache,
inspector, mini-map and Studio refresh code. Legacy calls to `refresh()`
still refresh all four views without a behavior change.

The event command is a validated **headless integration contract** and has
not yet replaced all Game Studio graph callbacks. This is deliberate: event
editing has a separate Studio-level history and needs a coordinated migration
before its UI can use the same context.

## Gates

Run `python -m unittest tests_standalone.test_editor_architecture_3723 -v`
and the pre-existing GUI/map/structure/entity/studio suites. CI must pass
Windows, macOS and Linux; no replay or Content format changes.

### Next, before 3.7.24 World

1. Move remaining terrain/paste/rectangle/zone actions to typed commands in
   narrow PRs; cover multi-cell paint transactions and rollback.
2. Migrate the narrative/strategic event editors without losing Studio
   history or cross-editor recovery.
3. Introduce typed change footprints and measured dirty regions so inspector
   and mini-map updates are not merely view-scoped but cell-scoped.
4. Profile preview/caches under 100k-cell maps, while preserving the
   `EditorRenderCache` optimization and the exact Player state.
5. Only then start **3.7.24 World**, as a separate milestone with explicit
   world-data and scene-traversal acceptance tests.

Every migration requires: preview → validate → apply → historize →
notify only subscribers; no new gameplay or save-schema changes.
