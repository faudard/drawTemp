# R27.A — World / Room / Dungeon authoring (incremental PR)

**Status: code proposed, not R27 (6.3) certification.** Based on the
multi-genre roadmap introduced in PR #289. Branch starts at `master`
after #289/#285. R25/R26 are prerequisites for actual top-down free
movement and scene transitions; the existing R1/R5/R10 tactical content
contracts are preserved by this interim tranche.

## Where to find the tools

Run `drawtemp-map-editor`, open or create an existing R1 content/project pair,
and select **Donjons / énigmes** in the contextual mode selector. The existing
Qt Quick R3 viewport remains the only renderer. The contextual dock adds:

1. **Créer une carte de donjon liée**: chooses a stable map id/name and creates
   a 16×16 playable tactical mission linked to the current one. The edge is the
   real `Mission.next_missions` campaign progression link; this is **not**
   a seamless portal or action-adventure scene transition.
2. **Construire salle + porte verrouillée**: paint a minimum 5×5 enclosed stone
   room inside the current board. The entrance must lie on a wall, not at a
   corner. It becomes a true `Mission.objects` locked door, named
   `room_door` (or a unique suffixed identifier). Existing authored tiles,
   objects, buildings and actor wall spawns are protected.
3. **Placer l'interaction**: add a door on an existing room wall, a lever linked
   to a real door, or a chest with an existing battle loot amount. Clicking a
   map cell sets the object placement coordinates. Each operation is one
   validated R1 transaction and supports shared Undo/Redo and save.
4. **Relier la carte**: updates the actual campaign graph. The R10 world
   presentation remains attached to Mission IDs, with no second graph.
5. **Analyser**: bounded static exploration of four-neighbour movement,
   player spawns, locked/open doors, levers usable from adjacent cells, chests
   and goal tiles. Reports unreachable goals/interactions and refuses to mark
   an incomplete state search as successful.

Example workflow: create a village-connected dungeon, build a room with a
locked door at (7,3), put a lever at (7,2) linked to `room_door`, add a chest
at (8,7), and paint a goal at (8,8). Analyse the room with and without the
lever. Save, reopen, undo and redo. The tactical Player already knows the
`door`/`switch`/`chest` object kinds and can process interactions;
the analysis is **not** itself a Player playthrough.

## Contracts and safety

- R1 `AuthoringSession.preview_pair/apply` remains the single writer.
  No extra JSON truth, second history or new sidecar format.
- R5 tile schema and R10 `next_missions` link are reused. Legacy projects
  with no dungeon rooms serialize identically; new room tiles and objects are
  validated by existing `Content` validators.
- Edits are rejected atomically on overlaps, out-of-bounds room dimensions,
  missing linked doors and invalid object coordinates.
- Undo/Redo and save/reopen are exercised headlessly. No Qt GUI, GPU,
  external-machine export or human UX certificate is claimed here.
- **Static puzzle diagnostics are limited**. They ignore combat, dynamic
  actor blockers, narrative conditions, CT actions, key inventory semantics,
  timed puzzles and crash-between-scene recovery. Up to eight doors and
  50,000 search states by default; exceeding either bound makes the result
  inconclusive. A clean result is *not* a proof that the game cannot softlock.

## Tests

```sh
python -m unittest tests_standalone.test_drawtemp5_r27_dungeon -v
python -m unittest tests_standalone.test_drawtemp5_r5_map -v
python -m unittest tests_standalone.test_drawtemp5_r10 -v
```

## Still outstanding for R27.B and the release gate

- R25 profiles, scene router/spawn, top-down projection and cross-mode saves;
  R26 deterministic free movement, collisions and ARPG interactions.
- Versioned persistent keys/pressure plates/pushable blocks, multi-switch
  conditions, resets and sequence puzzle state integrated with the R9 event
  graph; no pretend support through opaque/unvalidated JSON.
- Interactive puzzle graph/debugger with genuine undoable nodes, test-selected
  playtest and visual Studio/Player parity/goldens.
- Villages, dungeon rooms and a boss generated and **played** entirely from
  graphical authoring, inter-scene returns, key/lever/gate persistence,
  checkpoint fault-injection, action replay and export from clean machines.

**Release 6.3 remains NO-GO** until the required R25/R26 dependencies,
R27.B implementation, multi-OS CI and end-to-end acceptance are proven.
