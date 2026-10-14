# R1.7 — Revision leases and Studio/Player consistency

This follow-up to R1.5/R1.6 closes an ABA hole in the pre-existing
fingerprint-only `EditingContext` protocol. It does not change the persisted
Content/GameProject schemas, Player rules, replay format, or save files.

## Strict revision contract

A `CommandPreview` captures **four** properties of its source: the current
`Document` identity, monotonic `Document.mutation_revision`, monotonic
`EditingContext.revision`, and the SHA-256 of its canonical authoring data.
`EditingContext.apply` checks all four before calling `Document.replace`.

Unlike a content checksum, the Document counter cannot become valid again
after a sequence such as A → B → Undo → A. It advances after:

- Every committed `Document.replace` (including entity and structure edits).
- Every real local `Document.undo` or `Document.redo`.
- `Document.restore_snapshot` invoked by the global StudioHistory undo/redo.
- The existing map brush fast-path commit or rollback.
- Content replacement/rollback while performing Save All.

The separate `EditingContext` generation is invalidated by the existing
StudioHistory change callback, so editing **only GameProject** also revokes a
preview computed before the new project revision.

No successful stale operation publishes an edit, an undo entry or view
notifications. A rejected preview must be recomputed rather than silently
rebased onto a newer document.

## End-to-end gate

`tests_standalone/test_editor_r1_player_gate.py` builds valid authoring
content with a multi-cell bridge, actor, two doors, lever and event, then:

1. Moves the bridge footprint in one edit.
2. Edits an actor name.
3. Relinks the lever to the second door.
4. Changes the tactical event condition.
5. Undoes all four operations and redoes all four.
6. At each step, loads the canonical content/project into the **real**
   `GameSession`, starts the test mission and inspects the runtime
   `Battle.mission` instead of an invented Player projection.

Additional tests verify the ABA scenario, a global StudioHistory restore,
project-only changes and a replacement Document with identical bytes.

## Validation

```sh
python -m unittest -v tests_standalone.test_editor_r1_player_gate
python -m unittest -v \
  tests_standalone.test_editor_reliability_r1 \
  tests_standalone.test_editor_architecture_3723 \
  tests_standalone.test_studio_transaction_3721b
```

The headless gate proves serialized mission compatibility with the actual
Player session and the restored history. A full Tk UI focus/viewport/rendering
smoke remains a separate **GUI** gate; do not claim that GUI rendering is
certified by these tests alone.

This PR is stacked on #164; retarget it to `master` after #164 lands.
