# Interior Builder 2.0 — review and release gate (3.7.20)

**Status:** implementation candidate, **not yet accepted**. This record is the
RFC review checklist for tactical floors; merging the implementation is a
separate decision from merging the visual authoring tools.

## Explicit boundaries

| Tranche | Scope | No implicit behaviour |
| --- | --- | --- |
| A — Interiors | Roof cutaway, interior floor projection, props, per-deck visibility and picking, undo/redo | No change to combat merely because a roof is hidden |
| B — Tactical decks | `unit_levels`, `level_links`, per-deck occupancy/pathfinding, explicit level moves, scoped attacks, checkpoints/replays | `tile.height` is **terrain elevation**, never an implicit floor ID |

N0 is the legacy tactical board. Authored interior decks N1..N3 have explicit
walkability in `interior_floors` and persistent building identities. An
address is `(level, x, y)`. A unit on N0 and one on N1 may share an XY cell.
Stairs link explicitly validated endpoints; overlap alone never creates a
connection. Existing Content v1 without multilevel fields must round-trip
unchanged.

The current cross-deck attack implementation is *restricted*: only adjacent
levels, basic ranged/focus attacks through a genuine missing upper-floor tile,
and no full 3D ray tracer. AoE, falling, multilayer monster footprints and
rotated-stair remapping remain unresolved.

## Reproducible release scenario

Generate the tower using the authoring APIs (no hand-edited JSON):

```sh
python -m examples.layered_tower_3720_gate --output /tmp/interior_tower.json
python -m sporebound editor --content /tmp/interior_tower.json
python -m unittest tests_standalone.test_interior_builder_3720_gate -v
```

In the editor and Player, inspect the **Tour** at (3,3) with the roof shown
then cut away. Check N0 and N1 independently, inspect the stair at (4,5),
and pick a floor cell, prop and actor. Repeat at zooms 24, 54 and 96, with
automatic cutaway when an actor enters the building.

The deterministic headless gate then proves, in one continuous battle:

1. Actor starts in the tower on N0 (4,5); enemy is on N1 (4,4).
2. Attacking from N0 is rejected without consuming the action or modifying
   the battle digest.
3. `level_move` follows the authored stair to N1 (4,5).
4. The actor attacks its now-adjacent enemy on N1.
5. Content is saved and read back; battle checkpoint is saved and restored;
   full replay and restored digests must match the original.
6. The tower's N0 tile at (4,4) remains elevation 2 while the enemy occupies
   `level_id=1`: these are different concepts.

Existing GUI smoke suites `test_iso_interiors_3720a_gui`,
`test_interior_levels_3720b_gui` and `test_tactical_levels_3720c_gui`
exercise real Tk/Xvfb and render/pick at multiple zooms. A human still needs
to verify clipping, roof visibility, stairs, furniture, selection and Player
presentation visually.

## Required sign-offs before shipping

- [ ] RFC explicitly accepted: level identity, stair costs, occupancy,
      same-deck combat and narrow cross-deck LOS policy
- [ ] Integration conflicts resolved with the current `master`; preserve
      entity-editor, structure-editing and narrative changes from other PRs
- [ ] CI Python 3.10/3.12/3.14 on Linux/macOS/Windows and Tk/Xvfb green on the
      final **merged** SHA
- [ ] Test suite plus gate scenario passes without skips other than the normal
      GUI opt-in outside Xvfb
- [ ] Manual Map Editor and Player verification, including save/reopen and
      floor picking with a character present on the other deck
- [ ] Legacy Content v1 round-trip and historical recording digest unchanged
- [ ] Authoring policy agreed for rotating/deleting a parent structure with
      authored decks, stair links and upper-level actors
- [ ] Benchmark a castle/tower scene with overlapping floors

**Do not declare Interior Builder 2.0 complete** until the items above are
verified. In particular, an all-green CI on a branch that diverges from
`master` is not sufficient for the final integration gate.
