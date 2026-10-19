# R27.D — Four-stage tactical Dungeon Journey (increment)

> **Integration status:** proposed stacked PR above R27.C [#334](https://github.com/faudard/drawTemp/pull/334),
> R27.B [#319](https://github.com/faudard/drawTemp/pull/319), and R27.A
> [#304](https://github.com/faudard/drawTemp/pull/304). No claim of a certified
> R25 SceneRouter, R26 free-motion Player or seamless Zelda-like transition.
> CI/Qt checks are mandatory on the **final** commit SHA before release.

## Purpose

This is a first *actual* four-mission gameplay route using **existing**
DrawTemp contracts:

```
Village · le départ  (extract)
      │ victory: village_cleared / Content.next_missions
      ▼
Temple · la clé d'ambre  (extract behind R27.B key-gated door)
      │ victory: dungeon_cleared / CampaignFlow gate
      ▼
Crypte · le gardien  (eliminate a real tactical enemy)
      │ victory: boss_cleared / CampaignFlow gate
      ▼
Village · le retour  (extract)
      │ victory: return_cleared
      ▼
CampaignFlow ending: r27_homecoming
```

All four maps are separate **tactical missions**. At the end of each
mission the player confirms **Retour en campagne**, then starts the
newly unlocked mission. There is no actual cross-map portal,
free realtime movement, spawn-position transfer, or persisted dungeon
inventory across missions.

## Creator workflow — no JSON editing

From the Studio R27 **Donjons / énigmes** dock, select
**Créer un parcours village → temple → boss → retour**, specify a short
unique prefix (default `r27`). The template builder:

1. Stages its edits on a **detached AuthoringSession**.
2. Uses the existing R5 map editor and R27.A room authoring, including
   the same R27.B key and locked-door records.
3. Adds four canonical missions and a **new campaign**, preserving
   the existing Jeanne/main campaign, story and content.
4. Sets validated Content links, CampaignFlow gates, once-only
   victory outcomes and a verified ending.
5. Commits the entire Content + GameProject pair as **one R1 edit**,
   with a single Undo and Redo.

A duplicate prefix, an invalid field or broken Content/Project
reference aborts without changing the Studio documents.

You can also generate and save a standalone demo directly:

```bash
python -m scripts.r27_dungeon_journey --output /tmp/amber.json
python -m drawtemp.player.qt_app --content /tmp/amber.json --campaign r27_journey
```

On Windows, replace `/tmp/amber.json` with an existing writable
file path. The generator writes the existing paired
`amber.json` and `amber.game.json` documents through the R1
two-file transaction store. You do not edit either JSON manually.

## Expected Player path

- **Village**: walk to the nearby exit cell `(2, 14)` and complete
  the `extract` objective; the temple becomes available.
- **Dungeon**: from `(7, 1)` interact with `r27_amber_key` at
  `(7, 2)`; walk onto `(7, 2)`, unlock `room_door` at
  `(7, 3)`, then reach the goal `(8, 5)` inside the room.
  This uses canonical movement, key and door rules, not a debug teleport.
- **Boss**: fight the authored **Gardien du sanctuaire** in ordinary
  CT combat. His defeat unlocks the return stage and records one
  CampaignFlow consequence.
- **Return**: reach the village exit. The `r27_homecoming` ending
  becomes available in the existing campaign inspector.

The stage flags (e.g. `r27_dungeon_cleared`), completed missions,
reward ledger, XP, equipment and unlock gates belong to **Campaign**.
The opened local dungeon door and collected local key belong to the
**current Battle** and are retained only while its replay/checkpoint
is active; they are **not** claimed to persist if you re-enter the
dungeon after having completed and exited its encounter.

## Test and safety gates

```bash
python -m unittest tests_standalone.test_drawtemp5_r27d_journey -v
python -m unittest tests_standalone.test_drawtemp5_r27c_player -v
python -m unittest tests_standalone.test_drawtemp5_r27_puzzles -v
```

The integration gate covers creation/Undo, canonical Content/Project
round-trip, mission locks, legitimate key/door/movement interactions,
a seeded boss battle, victory settlement and once-only ledger flags.
It verifies GameSession saves at village completion, after key pickup
and after dungeon completion, with a final homecoming checkpoint.

Optional Qt Widgets+Quick smoke (software/offscreen only):

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R27_QT_SMOKE=1 \
python -m unittest tests_standalone.test_drawtemp5_r27_qt -v
```

CI workflow: `.github/workflows/drawtemp-r27d.yml`.
A written test is not evidence of a passing test. Every QA claim depends
on the final GitHub check status.

## Remaining R25/R26/R27 obligations

The multi-genre **6.3** gate remains **NO-GO**: needs scene profiles,
versioned portal/spawn transfers, fixed-step action gameplay, inventory
continuity, persistent world puzzle state, player UI for scene travel,
cross-mode crash recovery and fault injection, gamepad/keyboard/accessibility,
real GPU/goldens and released Player export. This tactical journey
is a concrete integration witness, **not** a replacement for those gates.
