# R48.C1 — Two-author Jeanne vertical gate

## Goal and contract

This gate checks that the offline R48 collaboration implementation can
review and merge **two independently authored versions** of the same
Content/GameProject pair, save and reopen the canonical documents, maintain
the optional revision archive/review notes/audit sidecars, and still execute
a **real deterministic Jeanne gameplay session** with save/load and replay.

It is an integration **regression test**, not certification that R48 is ready
to merge, not collaborative networking and not on-screen Qt testing.

The executable gate is `drawtemp.sdk.r48_vertical_gate`; its Python
unittest suite is `tests_standalone.test_drawtemp_r48c_vertical`.

## Two-author scenario (base: the immutable R0 reference)

| Author | Changes | Expected semantic effect |
| --- | --- | --- |
| Alice | Renames village mission; changes tile (1,4) cobble→grass; changes scene `arrival` title | Map edit preserved; one contested scene title |
| Bob | Changes scene `arrival` text and title; sets project subtitle | Narrative/subtitle preserved; title conflict |
| Reviewer | Chooses **incoming/Bob** for `/project/story/scenes/arrival/title` | Exactly one explicit conflict decision, one R1 Undo transaction |
| History | Adds the reviewed merged revision as a child of both author nodes | 4 distinct DAG nodes (base, Alice, Bob, merge), persisted and revalidated |

The gate first passes an **empty conflict decision map**, requires failure
without any editor mutation, and then explicitly selects the incoming title.
It checks that Alice's terrain and mission changes and Bob's dialogue/subtitle
are all preserved.

The post-merge project is then saved to a fresh canonical sibling pair
(Content JSON + GameProject JSON) and reopened through `AuthoringSession.open`.
A separate DAG archive, scene-review thread (comment + resolve), and audit
entry are created, reopened and verified. The audit result is **advisory**:
an `aligned` state is not an author-proof or guarantee of completeness.

### Gameplay/replay gate

The merged Content/GameProject is validated by the **existing** canonical
`Content.from_dict` and `GameProject.from_dict` implementations.
`GameSession` uses seed **17**, selects `enter`, starts
`r0_village_forest`, opens the gate through the `lever` interaction,
and runs the same deterministic AI command planner as the original R0 parity
gate. Victory is required before 700 activations.

The game is explicitly saved and reopened with `GameSession.load`;
`GameSession.from_recording` must replay to an equivalent canonical
recording (normalizing only ephemeral battle UUIDs as in R0). The replay
source bytes may not change during loading.

## Crash/restart cases

The integration suite injects failure between the Content and GameProject
replacements. It requires `AuthoringSession.open` to fail with
`recovery_required`, then exercises both **explicit** choices:
`AuthoringSession.recover(path, "rollback")` and
`AuthoringSession.recover(path, "complete")`. Neither recovers
automatically.

A second injection makes the DAG's archive `os.replace` fail before
publication. The last valid archive must remain intact, and the Studio's
session must remain unchanged. Corrupted archives and stale publications must
not be overwritten. Sidecars are independent of game saves.

These are **simulated exceptions**, not failing physical media or real
power loss.

### R48.C2 partial — independent-process writer gates

`tests_standalone.test_drawtemp_r48c_processes` also launches two actual
Python interpreters via `multiprocessing.get_context("spawn")` and a
start barrier. Both independently validate and attempt to create the
same absent history archive using `LocalHistoryStore.save(...,
expected_digest=None)`: **exactly one** can succeed, the other must be
refused due to the exclusive lock or optimistic create-only check. The
remaining archive must reload, contain the winner's revision and
leave no normal writer lock behind.

A separate child process terminates deliberately via `os._exit(37)`
while holding the writer lock. A different process then attempts to
publish, which must **fail closed** without creating the archive.
The test itself subsequently inspects/removes that stale lock to
exercise explicitly owner-directed recovery. Production does not
steal or silently clear stale locks.

```bash
python -m unittest tests_standalone.test_drawtemp_r48c_processes -v
```

These are genuine independent-process scenarios, but are **not**
power-loss, disk corruption, distributed locking or actual
cross-machine collaboration tests.

## Reproduce locally

```bash
python -m pip install .
python -m unittest tests_standalone.test_drawtemp_r48c_vertical -v
python -m unittest tests_standalone.test_drawtemp_r48c_processes -v
python -m drawtemp.sdk.r48_vertical_gate
python -m drawtemp.sdk.migration \
    --verify-baseline docs/drawtemp5/reference-baseline.json
```

Run separately with optional PySide6 for existing R48.B Qt controls:

```bash
python -m pip install '.[qt6]'
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest \
  tests_standalone.test_drawtemp_r48b_history_qt \
  tests_standalone.test_drawtemp_r48b2_review_notes -v
```

The workflow `.github/workflows/drawtemp-r48a-collaboration.yml`
includes the integration suite and the executable gate on the Linux,
macOS and Windows headless matrix.

## Unmet release gates

- GitHub Actions must **actually create jobs and execute tests** on all
  three OS; a workflow run with `jobs=[]` is not test evidence.
- Extend interrupted *publication* tests to process death at every stage,
  coordinated disk interruptions and real physical recovery. The
  basic independent-process publication race and orphan lock gate are
  now included; this is not hardware fault certification.
- Verify Player **export** output and reproducibility; C1 checks gameplay
  save/load and replay, not export packaging.
- Validate R48.B with screen readers (NVDA, VoiceOver) and GUI *onscreen*.
- Provenance remains declared, unauthenticated. The DAG, notes, audit and
  canonical Content/GameProject are separate files and **do not form a
  multi-file atomic transaction**.
