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
| R2.7 | Canonical dependency graph, guarded actor/object ID refactors, safe deletion, paired cinematic actor-cue migration and scene/campaign ID migration. | Unknown references reject the operation. Campaign renames require a known project path and no existing old-ID save-slot directory; batch deletion and arbitrary family renames remain unsupported. |

## Automated regression gates

```bash
python -m unittest tests_standalone.test_workspace_r2 -v
python -m unittest tests_standalone.test_workspace_editing_3733a tests_standalone.test_workspace_shell_3731 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_workspace_r2_gui -v
```

The dedicated R2 checks are wired into `.github/workflows/standalone.yml`,
alongside the existing 3.7.31/3.7.33 and full model regressions.

## Actor reference diagnostic gate (R2.4)

Existing tactical `despawn` actions may legally reference an ID not present in
the mission (for example, a future spawn). The Studio now distinguishes known
future spawn/wave IDs and flags unresolved ones as **authoring warnings**.
Events are indexed under `tactical_event:<mission>/<id>` in the canonical
Workspace tree; a single-despawn event exposes a typed actor-reference choice.

1. Author a trigger with a `despawn` action pointing to a nonexistent actor.
2. Select the issue in **Problèmes** and press Return.
3. The existing **Espace projet** inspector opens on the tactical event.
4. Select the existing actor ID in **Référence acteur (despawn)** and apply.
5. The warning disappears on the next normal change notification. Undo restores
   it. Other event edits remain in the existing specialized graph editor.

This is a missing **actor reference in an event** and is not a change to the
actor's immutable ID. Reference errors already rejected by Content's strict
validation still cannot be stored as authorable documents.

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

**Remaining scope:** the actor-reference warning above covers a concrete
authorable `despawn` case. Global authoring-reference diagnostics still need
broader field coverage. Renaming actors/objects is supported with guarded
mission-local propagation, and scenes/campaigns with validated typed
cross-document propagation. A known actor cue in a `before_mission`,
`after_mission` or same-mission `tactical_event` cinematic can be
migrated alongside Content through the existing `StudioHistory`. Unknown
GameProject/opaque references and ambiguous cross-mission cues are *refused*.
Single-resource deletion is allowed only after the canonical delete command
and conservative reference checks validate; batch destructive refactoring
and unrestricted cross-document migrations are not supported.

## R2.7 — resource lifecycle gate

1. Rename a placed actor with a `protected_id`, tactical target or
   editor-group membership: all known references follow the new ID.
2. Rename an actor referenced in an explicit same-mission cinematic actor
   track: preview and validate both `Content` and `GameProject`, then
   capture one **StudioHistory** checkpoint. Global Undo/Redo restores both.
3. Attempt to rename an actor used by a cinematic triggered by a different
   mission, or by an opaque project reference: **reject before committing**.
4. Delete an unreferenced chest: the canonical entity removal validates and
   adds one Undo/Redo entry. Delete a door with a linked switch: **reject**,
   leaving both the Content and history unchanged.
5. Changing a resource after opening the inspector invalidates the baseline;
   stale renames/deletions cannot proceed.

6. Rename a **scene** from the Workspace: propagate all incoming
   `next_scene` choices, `entry_scenes`, `after_mission`,
   `after_strategic_event`, `during_tactical_event`, world-road
   events, cinematic triggers and Content `after_choice.scene` guards.
   Validate both documents before a single global Undo/Redo checkpoint.
7. Rename a **campaign**: propagate `entry_scenes` keys,
   `siege.campaign_id` and `campaign_start` cinematic targets. The
   old save slot namespace `<project-stem>_saves/<old-campaign-id>`
   must not exist. The editor never silently migrates saved campaigns.
8. Try introducing an opaque leftover ID or using a stale inspector:
   all documents stay unchanged and the operation fails closed.

**Note:** with a paired-document edit the global Studio Undo/Redo is the
authoritative history. The existing save transaction store persists the two
validated files together; no new disk format is added.

## Non-regression contract

- One `Content` / `GameProject` source of truth, no new save format.
- No Tk dependency in the new headless R2 service.
- No stale preview can overwrite a later document revision.
- Existing renderer, inspector, minimap, Workspace and navigation remain
  linked by the current editor notifications, not by a second event bus.
- Renames update known mission-local references and supported same-mission
  cinematic actor cues; unknown/cross-mission links are rejected.
- Deletion requires a confirmation and validated absence of dangling links.
- No tool may silently delete or rewrite third-party references.
