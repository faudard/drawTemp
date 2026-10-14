# R2 — Resource Explorer & Workspace UX 2.0

**Target:** `master`. Extends **3.7.31**, **3.7.33A** and **3.7.33B**
without introducing a second project index, separate game schema, or
alternative undo/event engine.

## Implemented integration

| Lot | Change | Boundary |
|---|---|---|
| R2.1 | Existing Workspace explorer: filter by family, text, favorites and recent resources. Bookmarks, recent IDs and filter choices are kept in the existing project-local `*.workspace.layout.json` UI sidecar. Incoming/outgoing links still come from `StudioIndex`. | Removed/unknown resources are reconciled on refresh; no authored data touched. |
| R2.2 | Extended multi-selection in the primary resource tree; shared typed property fields with explicit `(mixte)` values. A `BatchPropertyCommand` delegates per-resource changes to `WorkspacePropertyCommand` inside **one** `EditingContext` preview/commit. | Only resources from the same family and mission; actors, placed objects, editable groups or map tiles. No implicit edit of mixed fields. Stale forms and invalid changes are rejected atomically. |
| R2.3 | Existing drag sources and canonical palette placement retained. A pointer-time ghost shows valid/invalid destination cells before release; asset drops show a provisional marker pending canonical validation. Escape cancels the overlay. | Final placement and undo remain the pre-existing map/editor commands; cross-mission restrictions remain in place. |
| R2.4 | From Problèmes, navigate to the indexed resource **and** the existing editable inspector. Clearing text/family/favorites filters prevents deep links from becoming unreachable. Live `WorkspaceModelCache` diagnostics and deltas still drive automatic disappearance. | Does not suppress invalid Content or introduce an alternative validator. |
| R2.5 | Existing docking, tab layout, shortcuts and navigation remain unchanged; explorer state is now saved with the UI layout. Ctrl+D toggles the selected favorite while the tree has focus. | DPI/focus behavior remains owned by ttk/Tk. |
| R2.6 | From a selected door or linked lever, launch the existing **Personnages et événements** contextual gate authoring flow (condition, lever, tactical effect, scene/cinematic and preview). | Reuses `focus_gate_event`/`author_gate_sequence`; no custom JSON or parallel event graph. |
| R2.7 | View direct incoming/outgoing dependencies for selected resources, with third-party dependents called out as an impact warning. Shared graph is `StudioIndex`. | **Preview/analysis only** in this PR: automatic ID rename propagation and destructive batch operations are intentionally not exposed until dependency coverage across all resource types is complete. |

## Automated regression gates

```bash
python -m unittest tests_standalone.test_workspace_r2 -v
python -m unittest tests_standalone.test_workspace_editing_3733a tests_standalone.test_workspace_shell_3731 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_workspace_r2_gui -v
```

The dedicated R2 checks are wired into `.github/workflows/standalone.yml`,
alongside the existing 3.7.31/3.7.33 and full model regressions.

## Reproducible Problems → Inspector → Map gate

1. In a mission, place a door with no incoming switch/ram/catapult link.
   Its warning appears in **Problèmes**.
2. Select its warning and press **Aller à la ressource**. The indexed object
   is revealed on the live map and the shared Workspace inspector opens,
   even if a filter was previously active.
3. Select an existing switch, change its **Porte cible** property to the
   door ID and press **Appliquer les propriétés**.
4. The canonical content is validated, the object link is committed with a
   single Undo entry, and the warning disappears on the next normal Studio
   change notification, without manual refresh. Undo reintroduces it; Redo
   resolves it again.
5. Alternatively choose **Créer interaction depuis la sélection** on a
   door to open the already-existing guided event authoring and simulation.

**Remaining gate coverage:** malformed actor references are generally rejected
by Content validation before they can become a stored Studio problem. A
precisely defined *authorable* actor-reference diagnostic and its specialist
property repair pathway still need an explicit follow-up design; do not
misrepresent the door-reference scenario above as that exact actor scenario.
Similarly, full resource-ID renames/deletions with propagation across Content
and GameProject must be delivered as a separately validated transaction, not
as a blind find/replace of identifiers.

## Non-regression contract

- One `Content` / `GameProject` source of truth, no new save format.
- No Tk dependency in the new headless R2 service.
- No stale preview can overwrite a later document revision.
- Existing renderer, inspector, minimap, Workspace and navigation remain
  linked by the current editor notifications, not by a second event bus.
- No tool may silently delete or rewrite third-party references.
