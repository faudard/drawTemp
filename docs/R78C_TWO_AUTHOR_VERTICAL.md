# R78.C — Two creators, one typed conflict, safe resolution (P0)

**Scope:** executable **local** integration gate on top of R78.A (PR #436)
and R78.B (PR #439). R78 is not a certified remote collaborative product.

## Vertical slice VS-78

1. Two separate `AuthoringSession` instances load canonical Jeanne fixtures.
   Alice edits the mission map tile, mission name and arrival quest title;
   Bob independently edits the same quest title plus quest text and subtitle.
   Neither editor modifies the other's session.
2. Both author snapshots are registered as distinct child nodes of a single
   validated R48 root, keeping explicit immutable declared parent identities.
3. An R78.B reviewer adds a typed comment, reply, change request and release
   task (`12.0`), without authorizing a merge or altering either game.
4. R78.A acquires a single process-local whole-project lease; Bob's competing
   acquisition must be rejected. R30 reports precisely
   `/project/story/scenes/arrival/title` as the disputed typed field. Applying
   with missing choices must not mutate the Studio. Alice explicitly chooses
   Bob's title; their independent terrain and narrative edits survive.
5. The merge is **one R1 Undo step**. An isolated second editor replays the
   same conflict, verifies Undo returns to Alice's exact map and quest,
   and Redo reconstructs the merged documents. This avoids invalidating
   the history/audit checkpoint used by the primary integration run.
6. A single R48 DAG node with both declared parents is explicitly registered,
   followed by task closure, an advisory positive review, and an explicitly
   resolved comment thread. The R48 archive is saved and reopened with
   identical node identities. A separate CAS-protected R48 audit is appended
   and reconciled against the live merged canonical documents.
7. Content/GameProject are explicitly saved with the existing two-document
   store, reopened and compared byte-semantically with the reviewed merge.
   Jeanne's actual GameSession battle completes, saves/loads and is replayed
   from its recording with deterministic seed 17 (existing R48 gameplay gate).
8. An R15 **preview** export runs preflight and packaging with a
   **deliberately non-executable runtime marker** on each OS. The bundled
   Content/GameProject bytes and manifest are checked; duplicate destination,
   damaged bundle and `verify_bundle(require_release=True)` must fail closed.

## Execute

```bash
python -m unittest tests_standalone.test_r78c_two_author_vertical -v
python -m drawtemp.sdk.r78_vertical_gate
python -m drawtemp.sdk.r78_vertical_gate --no-gameplay --no-export
```

No user files are modified: the gate creates a temporary workspace for
snapshots, the review journal, task board, audit, Player save and synthetic
preview bundle, then removes it. The gate is deterministic except for temporary
paths and unseen in-memory lease tokens; those are not part of returned evidence.

CI is declared for Windows, Linux and macOS; tests must **finish passing** on
all hosts before marking this gate green. The existing R78.B Qt offscreen tests
cover the UI separately. This gate does not certify interactive simultaneous
editor UX, real distributed credential/role management, inter-process leases,
a true native executable, redistribution rights, GPU, clean-machine launch
or a downloadable release.

## Explicit NO-GO conditions

- Missing typed conflict choice, stale editor revision, revoked actor or
  expired lease; replay divergence; missing/changed asset rights; mismatched
  R48/R78 audit or journal HEAD; incomplete canonical two-document save;
  overwritten export destination; modified export bundle.
- A synthetic Player marker is **not** a binary and can never be used as
  proof of native launch. The R15 preview export alone cannot pass the
  R39/R60/R70/R80 publication or release gates.
- Production certification requires authenticated team actors and durable
  cross-process repository fencing; two real Studio instances/editors on
  distinct machines; Qt onscreen review/recovery QA; real Player builds
  and assets; independent machine/OS export launch and GPU evidence.

**Status:** engineering integration gate proposed by this PR. Until CI and
physical acceptance evidence are recorded, R78.C and R78 remain unvalidated.
