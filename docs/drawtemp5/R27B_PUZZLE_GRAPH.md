# R27.B — Puzzle Graph & Debugger (increment above PR #304)

**State:** implementation proposed in a *stacked PR*, not a certified
R27 6.3 release. This increment depends on R27.A `DungeonStudio` and its
R1/R5 transactional editor. R25 profiles and R26 action-adventure physics,
Player controls and scene-router transitions are **not** delivered here.

## What works in the canonical tactical simulation

The current `Mission.objects` list remains the **only persisted puzzle
authoring/runtime contract**, the same document already used by lever,
door and chest. This increment introduces opt-in object kinds:

| Kind | Authoring fields | Actual Battle behaviour |
|---|---|---|
| `key` | id, pos, `link` to its door | Adjacent `interact` marks the key `used` and emits a key collection event |
| `door` + `key` | original door, key id | Adjacent `interact` opens only after the referenced key was collected |
| `door` + `sequence` | 2–8 ordered IDs, reset flag | Reusable wrong input optionally resets; correct sequence consumes switches, opens door |
| `plate` | pos, linked door, latch bool | Character/placed block on tile activates plate; latched plate stays active |
| `block` | id, pos | New validated `puzzle_push` command moves 1 tile cardinally, respecting collisions |

A door can have **one** gate policy: key, ordered switch sequence, pressure
plates or the original individual lever. Conflicts and broken references
fail validation before being applied to R1 authoring history or loaded by
Player. Legacy missions without the new kinds are unchanged.

`puzzle_push` example (from a player standing immediately to the right
of an authored block):

```python
battle.execute({
    "kind": "puzzle_push",
    "object": "stone_box",
    "direction": [-1, 0],
})
```

Moves and pushes operate on the same Board/Unit/Mission object state.
An invalid command is rolled back by `Battle.execute`. Key `used`,
sequence progress, pressure latches, door `open`, and block `pos` live
in `Battle.state()`'s existing `objects` record. Therefore
`Battle.recording` and version-3 replay cover them without a parallel
journal. This is **battle-local persistence**, not an inventory item carried
across missions or a cross-scene puzzle checkpoint.

## Graphical authoring and debugger

In the existing **Donjons / énigmes** MapWindow mode:

1. Build a room/locked door with R27.A.
2. Place a **key**, **pressure plate** or **pushable block** at a world cell.
   Choose a door in the dropdown for keys and plates.
3. For ordered switches, place two or more switches through the R27.A tool,
   then enter their IDs separated by commas in the desired order and configure
   the selected door. Choose whether a wrong input resets progress.
4. Inspect the actual **Puzzle Graph** nodes and typed references in the new
   tree; select a node to jump its coordinates into the inspector.
5. Press **Analyser** to run a bounded symbolic search. It reports accessible
   goals and interactables, a sample witness route when one is found, and
   coverage limitations; it does not mutate the authoring document.

The debugger models a **single hero** walking cardinally and collecting keys,
activating single/ordered switches, pushing blocks, occupying plates and
opening doors. It caps exploration at 50,000 states and limits counts to 8
doors, 8 keys, 8 switches, 8 plates, 4 blocks. Reaching a state cap returns
`complete=false` (inconclusive). It does not model CT turn order, enemies,
combat effects, actors coordinating on pressure plates, non-puzzle events,
different floors, actual GPU draw/picking or cross-scene saves. Neither a
witness nor an unreachable-goal report certifies gameplay freedom from
softlocks in the real Player.

## Verification

```bash
python -m unittest tests_standalone.test_drawtemp5_r27_dungeon -v
python -m unittest tests_standalone.test_drawtemp5_r27_puzzles -v
python -m unittest tests_standalone.test_drawtemp5_r5_map tests_standalone.test_drawtemp5_r10 -v
```

Optional actual Qt Widgets/Quick smoke (software/offscreen, not GPU proof):

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R27_QT_SMOKE=1 python -m unittest tests_standalone.test_drawtemp5_r27_qt -v
```

Dedicated CI: `.github/workflows/drawtemp-r27.yml`. No report is green
until it runs on the final head SHA.

## Pending R27/R25/R26 exit gates

- Extend World Graph with spawn-validated portals and replay-safe transitions;
  do not confuse `next_missions` with a Zelda-like seamless transfer.
- Share actual key resources across missions through versioned R25
  GameSession/inventory contracts (not object `used` in a local battle).
- Create/author more puzzle operators, local previewing and reset policies
  with R9 event graphs, typed conditions and reward idempotence.
- Give the Player a contextual `push` action and plate visuals; runtime API
  and Qt dock are not enough for a novice to complete the puzzle.
- Save/load/fault-injection across action scenes, Goldens R3, hardware UI and
  native clean-machine export; run UX tests on the final SHA.

**R27 6.3: NO-GO** until those gaps and R25/R26 dependencies are closed.
