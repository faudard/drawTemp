# R1.5 — Incremental validation / R1.6 — Recovery Journal

The R1 reliability layer extends `EditingContext`, `StudioHistory` and the
existing `Content` + `GameProject` validators. It does **not** replace their
models, undo stack, Player or gameplay save formats. None of the core modules
import Tk.

## Incremental authoring diagnostics (R1.5)

- `IncrementalValidator` caches per-mission cross-reference results using a
  deterministic fingerprint of each mission and the available mission IDs.
- Broken object → door links, missing predecessor events and missing next
  missions produce stable resource keys for the existing Problems panel.
- Existing `Content.from_dict` / `GameProject.from_dict` remain authoritative.
  Reports are not a bypass for validation on commit.
- `begin()` creates a generation lease; `cancel()` invalidates in-progress
  calculations. The scanning callback checks this lease before publishing and
  a report is reusable only while `is_current(report, ...)` succeeds.
- `EditingContext.apply` already pins a preview to its original SHA-256 source;
  this PR also cancels obsolete diagnostics after successful changes. Invalid or
  stale previews never enter the history stack.

## Unsaved-work recovery (R1.6)

- `EditRecoveryJournal` writes a **single compressed current snapshot** of
  both validated documents to `<content>.studio-work.json`, with checksum,
  explicit dirty flags and original on-disk fingerprints. There is no
  unbounded history log and no duplicate authoring document model.
- `StudioHistory.on_change` drives a debounced (350 ms) Tk checkpoint after
  edits, including cross-editor undo/redo. Saving either document refreshes
  the checkpoint's disk fingerprints; saving both clears the dirty draft.
- On Studio startup (or opening another project), the user can **restore in
  memory**, **discard** or **cancel**. Restoration never changes either saved
  JSON; the user must explicitly save the restored documents.
- Changed files, missing/corrupted journal data, interrupted Save All or invalid
  canonical documents cause restoration to fail closed. The existing
  `StudioTransactionStore` save recovery takes priority and remains intact.
- Deliberately uncommitted text in the raw JSON editor is not journaled. It
  must first pass the existing Apply JSON validation.

## Acceptance gate

```shell
python -m unittest tests_standalone.test_editor_reliability_r1 -v
python -m unittest tests_standalone.test_editor_architecture_3723 -v
python -m unittest tests_standalone.test_studio_transaction_3721b -v
```

The primary regression follows one history timeline: move a multi-cell bridge,
edit an actor, relink a switch to another door, edit a tactical event, undo all
four in reverse and redo them in original order. It checks that the final
Content still validates with authored rules and its GameProject remains
Player-readable. Further tests cover stale previews, canceled calculations,
per-mission cache hits, invalid cross-references, interrupted draft recovery,
disk version conflicts, corrupted sidecars and history-change notification.

## Scope

The recovery sidecar is an **editor-only** convenience. Long-session gameplay
checkpointing and persistence migrations remain in R8. No `Content`/
`GameProject` version changes, no new Tk dependency in the headless layer.
