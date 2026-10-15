# R8 — RPG Database & Rules Studio (DrawTemp 5.0)

> **Suite R8.B :** [arbres de talents et rencontres Qt](R8_B_TALENTS_ENCOUNTERS.md). La matrice ci-dessous décrit la tranche historique R8.A, pas l'état cumulé des deux tranches.

## Scope of this PR

This is an **incremental R8 authoring implementation**, not a certification
of all twelve R8 lots. It is based on the merged R0/R1 work on `master`
and deliberately does not depend on an unmerged R2 Studio shell.

| Lot | State in this PR | Evidence / next work |
| --- | --- | --- |
| R8.1 Database Shell | Implemented as a standalone Qt Widgets application | Native 3-pane explorer, search, selection, typed forms and references |
| R8.2 Actors & Archetypes | Authoring of models and editing of placed actors | Existing `Content.archetypes` and `Mission.units`; placement API available, map picking belongs to R5 |
| R8.3 Classes & Jobs | Basic class and prerequisite forms | Job DAG validation, level-gated skills, stats; **visual talent-tree authoring remains** |
| R8.4 Skills & Effects | Implemented for existing skill/effect fields | Cost, target, area, accuracy, effect sequence add/edit/delete/reorder; complex previews remain |
| R8.5 Equipment & Items | Equipment creation/editing/duplicate/removal | Existing `Content.equipment` schema; **new consumable/slot mechanics are not introduced** |
| R8.6 States & Reactions | Partial | Uses runtime status effects, reaction and support selections; complete trigger/reaction editor pending |
| R8.7 Enemy & AI Profiles | Partial | Existing actor behavior field exposed; doctrine/formation visual editors pending |
| R8.8 Troops & Encounters | Not implemented here | Mission-level encounter workflow requires R5/R13 editors |
| R8.9 Global Variables | Read-only reference inventory | Flags are tracked in existing narrative/campaign structures, not inserted into an unrecognized `Content v1` field |
| R8.10 Referential Integrity | Partial | Canonical `Content/GameProject` validation, inbound references on known resources, safe deletion, single-step Undo/Redo. **Stable ID renaming is intentionally not supported** until saved-game references can be migrated safely |
| R8.11 Resource Preview | Partial | Typed properties and skill effect list; portrait/sprite/derived stat rendering depends on R3/R4 |
| R8.12 Bulk Operations | Partial | Atomic, revision-checked command batches and duplication; batch Qt selection/replace pending |

Each edit is previewed with `AuthoringSession.preview_pair` and applied with
`AuthoringSession.apply`. Preview uses a detached copy; failed operations and
stale previews cannot mutate the document or history. No new Content version,
shadow RPG registry, Tk imports in the new Qt UI, or independent save format.

## Launch

Python 3.12 with the optional Qt 6 extra:

```bash
python -m pip install -e ".[qt6]"
drawtemp-qt6-database
drawtemp-qt6-database --content /path/to/jeanne.json
QT_QPA_PLATFORM=offscreen drawtemp-qt6-database --smoke
```

With no path, the UI opens the reference Jeanne project **in memory**.
Saving for the first time uses `Enregistrer sous` to create a Content file
and a matching `.game.json` manifest; neither existing file is overwritten.
An existing project can be opened only if both files are present and valid.
Recovery from a pending interrupted two-file transaction must be resolved
explicitly through the R1 SDK, not hidden by this GUI.

UI workflow: select a family in the left tree; use search and selection in
the middle list; edit typed fields, including effects for skills, on the right.
`Créer` adds a resource with validated defaults, `Dupliquer` clones reusable
definitions, and `Supprimer` rejects referenced resources. `Annuler` and
`Rétablir` call the R1 history. Actor placement is exposed by the headless
database API, but not yet via the map (R5 dependency).

## Reproducible Lancier gate

The test fixture `drawtemp.studio.rpg_database.lancer_example` creates
four resources in one reversible transaction:

- `r8_guard_ally`: an allied protect-status skill with MP cost;
- `r8_lancier` job: skill unlock at level 1 and defense bonus;
- `r8_spear`: a weapon definition with weapon-power bonus;
- `r8_lancier` archetype: spear type, attributes and the guard skill.

Class, equipment and archetype definitions use different namespaces while
preserving canonical IDs. There is no automatic assignment of an equipment
record to an actor: the existing runtime contract does not store an equipped
item as a direct `Unit` field. Tests confirm the guard status is applied
by **real `Battle.execute`** and the Content/GameProject documents round-trip.
The sample project is never overwritten. An existing instance is not
silently changed when an archetype is edited.

## Verification

```bash
python -m unittest discover -s tests_standalone -p 'test_drawtemp5_r8_*.py' -v
QT_QPA_PLATFORM=offscreen python -m drawtemp.studio.rpg_database_qt --smoke
```

The targeted CI workflow runs headless Python tests on Linux, macOS and
Windows (Python 3.12), plus Qt Widgets offscreen on Linux. This is **not**
a GPU certification, an R2 Studio integration, or a manual GUI acceptance
report. The full R8 gate requires visually creating a Lancier in the
integrated Studio and verifying its encounter/equipment workflow in Player.
Do not mark that gate complete based solely on this PR.
