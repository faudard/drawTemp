# R78.B — Professional Team Reviews (P1, incremental)

R78.B extends the R48 verified revision DAG and existing `ReviewNoteStore`,
without altering Content/GameProject, GameSession, Player, save formats, Git
history, or R78.A permissions and leases.

## Implementation

- `TeamReviewBoard` is the explicit policy boundary for review metadata.
  The caller must authenticate actor IDs; the local default Studio dialog
  intentionally uses a single untrusted `local` owner, **not** cloud identity.
- R48 typed resource anchors attach comments to a validated immutable
  revision node. Thread replies, resolution and reopen use the existing R48
  hash-chain/CAS notes journal (no second comments store).
- `TeamTaskStore` is a separate optional local JSONL log for **advisory**
  task creation, status updates and per-revision reviews; its records are
  strict, bounded, integrity checked, and append only. All writes require a
  caller-pinned HEAD, writer lock, re-read of bytes and explicit fsync.
  Torn/corrupt logs must be inspected, never auto-repaired.
- **Integration hardening:** `TeamReviewBoard.verify_journals()` checks *both*
  sidecars against the active validated R48 graph: every note/task event must
  identify a known node, the exact document digest and a valid typed resource
  anchor. Validly hashed records from another project's history are rejected
  before reading discussions or appending any further note. Qt checks both
  journals before binding them to the current Studio. This does not provide
  cryptographic authentication or distributed project isolation.
- Tasks attach to validated R48 resource nodes. Each has a stable numeric ID,
  title, assignee, release slug and status (`todo`/`in_progress`/`done`).
  `release_board` groups them by release and state; this is not a release
  authorization, approval gate, exporter or hosted ticket service.
- Per actor/resource/revision review decisions (`approved` or
  `changes_requested`) are recorded as **advisory** immutable events, with
  the last decision superseding only that reviewer's own prior decision.
- Role policy: viewer can inspect, reviewer can comment/review/create and
  advance tasks assigned to them, editor/owner can manage task assignments,
  release labels and titles. Revocation is honored at each API operation.

## Studio usage

Open **Outils → Collaboration / VCS → R78 • Revues et tâches d’équipe locales**.

1. Optionally load a validated R48 history file containing the active Studio
   snapshot (separate history owned by the existing R48 workflow).
2. Choose a local folder for the separate `r78_review_notes.jsonl` and
   `r78_team_board.jsonl` files. Selecting a folder only inspects metadata:
   files are not created until a user explicitly posts an event. Existing
   foreign or corrupt journals are refused without rewriting or repairing them.
3. Choose before/after revisions, inspect the semantic diff and select a
   resource or enter a semantic diff path such as
   `/project/story/scenes/arrival/title`.
4. Publish a comment, advisory change review, or assign a task to a permitted
   member. Explicitly update task status, and refresh to reread remote
   modifications. CAS refusals require review/reload, never silent overwrite.

## Proof and limitations

Run headless: `python -m unittest tests_standalone.test_r78b_team_review_board -v`

For Qt: `QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r78b_team_review_board -v`

The dedicated R78.B GitHub Actions workflow requests Linux, Windows and
macOS headless + offscreen Qt validation. Evidence requires completed runs;
declared CI does not equal passing CI.

Remaining work: no distributed ACL/authentication, remote lock service,
multi-process review protocol, atomic cross-file transaction, mandatory
approval policy, integration with GitHub issues or PRs, or release/export
certification. Explicit R78.C end-to-end two-creator map/quest conflict,
Undo, revision reconciliation, save/export and clean-machine evidence remain
required. R78 overall is **not certified** by this slice.
