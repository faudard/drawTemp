# R74.A–C2 — Assisted dungeon proposals, Qt review and spatial R34/R5 parity

**Status: R74.A–B plus an incremental R74.C1 implementation on the feature branch; CI, physical Player walkthrough and clean-machine export not yet certified.**

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

## R74.C1 — Three real physical key/door maps (partial)

Within the R74 Qt dialog, **Proposer des variantes** with exactly three
unique R34 proposals, then **Préparer 3 cartes R27**. A detached sandbox built
from the current canonical project creates:

- `<prefix>_dungeon_1` — Archives, locked room entrance x=5;
- `<prefix>_dungeon_2` — Galerie, locked room entrance x=7;
- `<prefix>_dungeon_3` — Sanctuaire, locked room entrance x=9.

Every 16x16 mission has a **real R5 tilemap**, **real R27 locked door
and collectible key**, player spawn adjacent to that door, and an extract
goal behind its solid walls. The maps form a three-mission campaign using
canonical `Content.next_missions` and `GameProject.campaigns`. Existing
story, saves and Jeanne missions are retained unchanged.

The R27 puzzle debugger proves a **bounded single-hero walk/collect/open
witness** on authored physical cells before a live project write is even
proposed. It discloses that combat AI is not modeled. The preview includes
per-mission witness commands, state counts, canonical mission digest and R34
source-seed/topology digest. A partial or inconclusive proof rejects the entire
batch. The `PhysicalDungeonPreview` holds exactly one unapplied
`AuthoringSession` transaction. **Créer les 3 cartes…** asks a separate
default-**Non** modal confirmation; no disk save occurs. Undo and Redo use
the same editor history, and a stale revision or pre-existing generated
IDs fail closed.

Headless API:

```python
from drawtemp.studio.r74_physical_dungeons import (
    prepare_physical_dungeons, apply_physical_dungeons
)

physical = prepare_physical_dungeons(
    assistant, suggestions, prefix="r74")
print(physical.to_dict()["proofs"])  # each real R27 symbolic witness
# Only with explicit author approval:
applied = apply_physical_dungeons(assistant, physical)
assistant.session.undo()
```

**Important scope:** These three different editable puzzle missions are
derived from R74's seed-validated proposals, **not** a spatial instantiation of
each 8-room R34 topology. `r34_graph_parity=false`. A solution in the
symbolic R27 puzzle debugger is **not** proof of tactical AI survival, human
playability, full campaign completion, graphics or export. An added GameSession
test exercises key pickup and checkpoint save/load; the full three-dungeon
Player/GUI gameplay trace and clean-machine package gate remain outstanding.

### R74.C1 regression

```bash
python -m unittest tests_standalone.test_drawtemp_r74_physical_dungeons -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r74_assist_qt -v
```

## R74.C2 — Full R34 room/edge topology on canonical R5 maps

**Outils → R74 • Assistant de donjons vérifiés… → Proposer des variantes →
Préparer R74.C2 multi-salles → Créer 3 donjons multi-salles…**

This new path is **separate from the simpler R74.C1 sample**. It materializes
each R34 proposal in a real standalone R5 mission, including every room and
every neighbor edge, instead of drawing a single key/door room.

- Supports `room-graph-v1` with **3..12 rooms** (larger or more complex graphs
  fail closed): straight spine, up/down leaf branches, third branch left of
  entry when required by the source generator.
- Every room has a **5×5 walkable footprint**, with one corridor per exact
  undirected graph edge. All uncarved board cells are actual blocked R5 wall
  tiles; corridors cannot cross, connect third rooms, or introduce shortcuts.
- A **real R27 locked door** occupies the precise corridor identified by
  the R34 lock, and a **real collectible key** appears at the key-room center.
- Layout proof extracts corridor components *independently* after masking
  rooms and compares the resulting adjacency graph to all R34 neighbors.
  The blocked-gate flood fill proves the exit and goal cannot be reached
  before the key but the key remains reachable.
- The R27 bounded single-player puzzle analyzer supplies **separate**
  key/door/walk witnesses to the R34 goal-room center and the exit-room
  center. Both must be verified; no false fallback or partial proposal set.
- The Studio uses the selected R74 variant row to display a **scaled
  physical map preview** with room rectangles, actual corridor footprints and
  markers **E** (entry), **K** (key), **D** (door), **G** (goal) and
  **S** (exit). Switching variants selects its own R27 witness report.
- A canonical `GameProject.campaigns` entry links the three missions using
  existing `Mission.next_missions`, while `AuthoringSession` owns one
  opt-in transaction and the same Undo/Redo history. No disk writes until
  the user explicitly saves.
- `SpatialDungeonPreview` reports source topology hashes, exact room
  centers/edges, pixel dimensions, goal/exit witnesses, mission digests and
  conservative certification flags. Its evidence hash detects alterations
  before apply.

The deterministic geometry intentionally has a **physical-size bound**.
Loot is represented conservatively by one R27 chest in rooms with loot;
R34 numerical encounter/loot allocation is **not certified to match**
tactical unit/chest counts. The generated mission retains a default enemy;
enemy AI, combat survival, Player export, GPU/UI ergonomics and performance
under full content load are **not modeled by the symbolic proof**.
`combat_and_resource_parity=false` and `player_export_certified=false`.
R74.C3 must close those gaps, with full play, reload, packaging and licensing.

Headless example (run before choosing Apply):

```python
from drawtemp.studio.r74_spatial_dungeons import (
    prepare_spatial_dungeons, apply_spatial_dungeons,
)

preview = prepare_spatial_dungeons(assistant, suggestions, prefix="r74s")
for proof in preview.to_dict()["proofs"]:
    assert proof["physical_edges"] == proof["r34_edges"]
    print(proof["mission"], proof["goal_witness"], proof["exit_witness"])
# Explicit author approval is required before calling the following:
transition = apply_spatial_dungeons(assistant, preview)
```

Focused tests:

```bash
python -m unittest tests_standalone.test_drawtemp_r74_spatial_dungeons -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r74_assist_qt -v
```

## Next R74 increments

- **R74.B:** implemented in this branch, pending evidence and CI.
- **R74.C2:** implemented on the dedicated follow-up branch; awaits executed
  cross-platform tests, real Player checks and integration review.
- **R74.C3:** complete all three dungeons in a real Player session with
  authored combat/puzzle progression, save/reload and canonical export, then
  run on-screen, GPU, clean-machine and licensed-asset certification gates.

Run headless regressions:

```bash
python -m unittest tests_standalone.test_drawtemp_r74_assisted_dungeons
```

Roadmap source: [R74 of R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
