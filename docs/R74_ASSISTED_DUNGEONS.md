# R74.A–B — Assisted dungeon proposals and Qt review

**Status: R74.A–B implemented on feature branch, pending CI and real Qt onscreen testing; NOT a certified R74 release.**

This increment composes the existing R34 deterministic room-graph solver and
prefab matcher with the existing R34.C authoring transaction; it **does not**
create a new map schema, file store, AI backend, second game engine or parallel
Undo stack.

## Usage

```python
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r74_assisted_dungeons import AssistedDungeonController

session = AuthoringSession.new(*reference_project())
assistant = AssistedDungeonController(session)
suggestions = assistant.preview_variants(
    seed=74, biome="ruins", count=3, rooms=8,
    branches=2, locked_goal=True, encounter_budget=2, loot_budget=2,
)
# Preview is read-only, including project history.
for item in suggestions:
    report = item.to_dict()
    print(report["seed"], report["layout"]["route"], report["topology_digest"])

# Human decides: assistant.reject() or explicitly select one proposal.
selected = suggestions[0]
plan = assistant.prepare_selection(selected)  # no edit
transition = assistant.apply(selected)         # exactly one R34 project edit
session.undo()                                 # restores original project
```

## Proven guarantees

- Bounded requests: 1–5 variants, 3–32 rooms, 0–64 encounters/loot budget;
  48 deterministic seed attempts maximum. Strict integer and boolean types.
- A SHA256 topology fingerprint deduplicates variants independently of seed.
  Inability to find enough unique solutions rejects the entire request.
- Each candidate is regenerated/verified with R34's logic solver and R34.B's
  prefab socket matcher before selection; the route goes through the logical
  goal and reaches the logical exit with required keys.
- Provenance captures algorithm/version, seed, library and layout digests.
- Only local **unbound** procedural prefab templates are accepted. External
  asset/mission references are rejected unless future work supplies actual
  registry-linked rights proofs.
- An editor revision lease rejects stale selection. A changed proposal is
  rejected. Actual authoring is opt-in and participates in canonical
  GameProject/Content validation, history, undo and redo.

## What is NOT yet proved

The route is currently a **room graph** proof, not a collision-checked physical
tilemap, an authored R27 puzzle solution, an R27 campaign journey, a GPU
screenshot or a clean-machine executable export. Selection writes a validated
R34 recipe to `GameProject.extensions`, not an automatically populated R5
physical tilemap. The report explicitly sets `physical_route_verified` and
`player_export_certified` to `false` and does not claim a 12.0 release.

## R74.B Qt Studio workflow

From **Outils → R74 • Assistant de donjons vérifiés…** or the Studio
command palette (`r74_dungeons`):

1. Pick a deterministic seed, room/branch constraints (including an optional
   key-before-goal lock), biome, encounter/loot budgets and proposal count.
2. Click **Proposer des variantes**. Inspect each different logical topology
   in the table and graph, and the semantic diff against the first proposal.
3. Optionally click **Garder comme référence**, adjust parameters and regenerate.
   The previously pinned graph persists as an explicit comparison baseline;
   generated room graphs are *not* edited in place. The new constraints yield
   a new candidate that must pass R34 verification again.
4. **Rejeter les propositions** discards unsaved previews and pinned state.
   Changing any generator parameter also invalidates the active proposal.
5. **Appliquer la sélection…** opens a modal requiring an explicit **Oui**
   (default **Non**). Only then is one canonical R34 project transaction
   recorded, and no file is saved automatically.
6. **Annuler l'application / Rétablir l'application** operate on the shared
   AuthoringSession, guarded by the revision last produced by this dialog.
   If another command has modified the history, these buttons refuse to
   act on unrelated edits.

The semantic diff is **room/edge/role/key/lock/route and budget only**.
It is not a rendered tilemap diff, not collision proof, not quest validation.
No remote model or service is used. External asset/mission references remain
refused without a verified rights manifest.

### Regression commands

```bash
python -m unittest tests_standalone.test_drawtemp_r74_assisted_dungeons -v
python -m pip install ".[qt6]"
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r74_assist_qt -v
```

The dedicated `.github/workflows/drawtemp-r74-assist.yml` checks these
and R34 regressions on three OSes. Qt *offscreen* tests cannot stand in for
human onscreen navigation, DPI/accessibility, real GPU or export validation.

## Next R74 increments

- **R74.B:** implemented in this branch, pending evidence and CI.
- **R74.C:** instantiate canonical R27 missions and puzzles in R5 coordinates
  under a single transaction, independently prove physical spawn→goal
  reachability, author/play/save/reload three original dungeons, and certify
  export/asset integrity on target systems.

Run headless regressions:

```bash
python -m unittest tests_standalone.test_drawtemp_r74_assisted_dungeons
```

Roadmap source: [R74 of R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
