# R78.A — Local Team Workflows foundation (P0, partial)

This slice introduces **opt-in, local, single-process** team governance using
`drawtemp.sdk.team_workflows`. It is not a hosted collaboration service or a
security boundary around code with direct access to `AuthoringSession`.
Callers must authenticate identities themselves: workspace role names do not
constitute authentication.

## Contract

- `TeamAccessPolicy`: explicit `owner/editor/reviewer/viewer` membership,
  owner-only changes, protected last owner; unlisted actors are denied.
  Viewers/reviewers can inspect revision metadata, not apply changes.
- `TeamLeaseRegistry`: exclusive `project`-wide lease, TTL, token fencing,
  explicit acquire/renew/release, refusal of unknown, expired or revoked actors.
  Leases guard the **entire canonical Content/GameProject pair**, not an
  invented entity store. No cross-process guarantees: remote connectors must
  implement distributed atomic fencing/CAS before remote writes.
- `TeamMergeWorkspace`: roles and leases checked both before preview and before
  apply. Uses the existing `HistoryReviewController`, `RevisionGraph` and
  R30 typed semantic merge. Every conflict requires an explicit resolution;
  stale `AuthoringSession` revisions fail closed. A successful apply is **one
  Undo transaction**, never a file save or network write.
- `register`: an **explicit** immutable R48 DAG checkpoint with both source
  parents; a registration failure cannot automatically roll back the live
  editor. `append_audit`: an **explicit, separate** hash-chained R48 audit
  append with optimistic audit head. A failed append leaves the pending merge
  for review/retry; these operations are not atomic. No implicit export, Git
  commit, audit, or publication.

## Minimal integration sequence

1. Authenticate the author in the host and provide an explicit workspace policy.
2. Construct `TeamLeaseRegistry(policy)` and
   `TeamMergeWorkspace(session, graph, policy, leases)`.
3. Acquire a lease; preview `local_id/incoming_id` (select a maximal common
   base explicitly when ambiguous) and display typed conflicts.
4. Call `apply` with explicit `{json_pointer: "local" | "incoming"}` choices.
5. Call `register` explicitly and, when configured, `append_audit` with the
   inspected expected head. Release the lease. Save Content/GameProject through
   their own existing CAS store **only** when the operator requests it.
6. When audit persistence is not configured, explicitly acknowledge missing
   audit evidence after registration; never claim an audited result.

## Verification and remaining gates

Run: `python -m unittest discover -s tests_standalone -p 'test_r78a_team_workflows.py'`

Coverage includes access revocation, owner safety, lease contention/expiry,
TOCTOU editor changes, typed conflict resolution, one-step Undo, explicit DAG
history and audit CAS. This does **not** certify R78 or VS-78: R78.B still
needs entity-linked reviews/comments/tasks and UI; R78.C needs a complete
two-creator Studio→Player→export scenario, repository-level authentication,
process-spanning CAS, CI evidence and rollback exercises.
