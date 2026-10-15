# DrawTemp 5.0 — R2.C Universal Inspector + R2.D Resource Explorer

This tranche extends the merged R2 shell. It deliberately reuses the canonical
`AuthoringSession`, `Content`, `GameProject` and R1 `StudioHistory`. It does
not add a save schema, a resource database or independent Undo stacks.

## R2.C — Typed Universal Inspector

The headless `drawtemp.studio.inspector_model` publishes `PropertySpec`,
`shared_specs`, `common_value`, `preview_properties` and `edit_properties`.
The Qt form is built from those contracts, rather than raw JSON or widget types
guessed from mutable data.

- **Project:** title.
- **Maps:** name, reward and target ticks.
- **Placed units:** name, hit points, attack, speed and movement.
- **Objects:** name and amount; doors also expose HP and locked.
- **Campaigns:** name.
- **Narrative scenes:** title, speaker and multiline text.
- **Cinematics:** name when explicitly stored in the canonical document.
- **Other structures:** read-only until a documented typed authoring contract is
  available; event commands remain in R9.

Multi-selection displays the **intersection of compatible field specifications**.
A mixed value is represented visually, and **is never committed implicitly**.
Only controls explicitly modified by the user are included in one
`preview_pair` / `apply` transaction. Each action is one Undo step for all
selected resources. A stale selection, invalid number/boolean, absent resource,
duplicate selection, forbidden field or failed canonical validation rejects
the entire operation; the Qt inspector shows an inline error. Editing a
property never changes an ID or a reference.

The preview accepts `expected_revision` so edits arriving from another
workspace during form preparation cannot overwrite newer documents. The
`AuthoringSession` enforces the commit revision even when a preview is reused.

## R2.D — Resource Explorer

The existing `QStandardItemModel` preserves stable
`(family, mission_id, resource_id)` identities and now provides:

- Case-insensitive search by label or ID, grouped by resource family.
- Family and mission facets, with a persistent QSettings favorites list.
- Directed **incoming/outgoing** reference filters anchored to the selection.
- Context actions to open, favorite, inspect incoming, inspect outgoing.
- Double-clickable links in the Inspector with navigation back to the
  corresponding resource in the explorer; links to maps, actor records and
  campaigns route to their native workspaces when available.
- Selection restoration across authoring revisions and facet resets when
  jumping directly to a referenced resource.

`drawtemp.studio.resource_links` computes edges only for **typed,
supported references** such as switch→door (`link`), trigger→actor,
campaign→mission, narrative→scene and explicit scene-entry associations.
Mission-local identities remain scoped; matching text, human labels or
identical IDs in another mission never create a link. Unrecognized/opaque
references are not indexed. The graph is **advisory**, not authoritative:
it must not be used to decide whether rename/delete is safe.

## Reproduction and validation

```bash
python -m pip install -e ".[qt6]"
python -m unittest tests_standalone.test_drawtemp5_r1_authoring \
  tests_standalone.test_drawtemp5_r2 \
  tests_standalone.test_drawtemp5_r2_cd -v

drawtemp-studio5
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --smoke --workspace project
```

CI executes the regression on Python 3.12 Linux, Windows and macOS. The tests
exercise typed validation, multi-select atomicity, undo/redo, stale previews,
scoped duplicate IDs, relation navigation, Qt widgets and favorites.

## Remaining release gates

- Validate complete GUI flows against authored real-game files, including
  visually rendering large maps and extensive event graphs.
- Expand typed coverage for event commands, structures, database definitions
  and cinematic tracks once their owning workspaces expose stable
  per-field authoring APIs.
- Certify accessibility, focus order, screen readers, FR/EN localization and
  visual density manually on each OS.
- Profile model refresh/filter/reference indexing on very large projects.
- Cross-editor integration of R9/R11 under shared history (R2.B / INT-02)
  remains a separate dependency.

These changes do **not** claim the complete R2 milestone is certified.
