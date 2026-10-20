"""R78.C — deterministic two-author map+quest collaborative vertical evidence.

Requires existing R48 semantic history, R78.A explicit leases and R78.B
advisory review metadata. No cloud, distributed actor authentication, native
player build, release certification or silent merge/save/export.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.audit_reconciliation import reconcile_audit
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.project_history_store import LocalHistoryStore
from drawtemp.sdk.r48_vertical_gate import (
    ANCHOR, CONFLICT, MISSION, TILE, _alice_pair, _bob_pair, _gameplay_gate,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.review_notes import ReviewNoteStore
from drawtemp.sdk.semantic_review import fingerprint_pair
from drawtemp.sdk.team_review_board import TeamReviewBoard, TeamTaskStore
from drawtemp.sdk.team_workflows import (
    TeamAccessPolicy, TeamLeaseRegistry, TeamMergeWorkspace, TeamWorkflowError,
)
from drawtemp.export.r15 import (
    ExportError, _native_name, export_game, preflight, verify_bundle,
)

RELEASE = "12.0"
CHOICE = "incoming"


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def build_editors():
    """Create independent canonical authoring sessions and declared DAG nodes."""
    content, project = reference_project()
    root_session = AuthoringSession.new(content, project)
    root_data = root_session.snapshot().to_dict()
    graph = RevisionGraph()
    root = graph.add(
        make_revision(root_data["content"], root_data["project"], author="root"),
        label="Jeanne — base validée")

    alice_session = AuthoringSession.new(content, project)
    alice_session.apply(alice_session.preview_pair(
        _alice_pair, kind="r78c-alice-map-and-quest"))
    alice_data = alice_session.snapshot().to_dict()
    alice = graph.add(
        make_revision(alice_data["content"], alice_data["project"],
                      author="alice", parents=(root.revision.digest,)),
        parents=(root.node_id,), label="Alice — carte et quête")

    bob_session = AuthoringSession.new(content, project)
    bob_session.apply(bob_session.preview_pair(
        _bob_pair, kind="r78c-bob-quest"))
    bob_data = bob_session.snapshot().to_dict()
    bob = graph.add(
        make_revision(bob_data["content"], bob_data["project"],
                      author="bob", parents=(root.revision.digest,)),
        parents=(root.node_id,), label="Bob — quête et dialogue")
    _require(alice.revision.digest != bob.revision.digest,
             "Independent authors produced indistinguishable snapshots")
    _require(root_session.snapshot().to_dict() == root_data,
             "Authoring root was modified")
    return {
        "graph": graph, "root": root, "alice": alice, "bob": bob,
        "root_session": root_session, "alice_session": alice_session,
        "bob_session": bob_session, "alice_data": alice_data,
        "bob_data": bob_data,
    }


def _assert_merged(snapshot):
    mission = next(row for row in snapshot["content"]["missions"]
                   if row["id"] == MISSION)
    terrain = next(tile for tile in mission["board"]["tiles"]
                   if tile["pos"] == list(TILE))
    story = next(row for row in snapshot["project"]["story"]["scenes"]
                 if row["id"] == "arrival")
    _require(mission["name"] == "Village — route d'Alice",
             "Alice's edited mission was lost")
    _require(terrain["surface"] == "grass", "Alice's edited terrain was lost")
    _require(story["title"] == "La lisière — version Bob",
             "Incoming explicit quest title choice was not applied")
    _require(story["text"] ==
             "Jeanne prépare le groupe avant d'ouvrir la porte.",
             "Bob's independent narrative field was lost")
    _require(snapshot["project"]["subtitle"] == "Chroniques de la lisière",
             "Bob's independent project change was lost")


def _undo_gate(history, policy):
    """Exercise real Undo/Redo on a second isolated editor before publication."""
    undo_session = AuthoringSession.new(
        history["alice_data"]["content"], history["alice_data"]["project"])
    leases = TeamLeaseRegistry(policy)
    lease = leases.acquire("alice")
    workspace = TeamMergeWorkspace(undo_session, history["graph"], policy, leases)
    review = workspace.preview(
        "alice", lease.token, local_id=history["alice"].node_id,
        incoming_id=history["bob"].node_id)
    _require(tuple(conflict.path for conflict in review.conflicts) == (CONFLICT,),
             "Undo rehearsal did not see the real quest conflict")
    baseline = undo_session.snapshot().to_dict()
    transition = workspace.apply("alice", lease.token, review, {CONFLICT: CHOICE})
    _assert_merged(transition.snapshot.to_dict())
    undone = undo_session.undo().snapshot.to_dict()
    _require(undone["content"] == baseline["content"] and
             undone["project"] == baseline["project"],
             "One Undo did not restore the original Alice map and quest")
    redone = undo_session.redo().snapshot.to_dict()
    _assert_merged(redone)
    _require(not undo_session.storage_status()["has_destination"],
             "Undo rehearsal unexpectedly saved the editor")
    leases.release("alice", lease.token)
    return {"undo_restored": True, "redo_restored": True}


def _review_gate(history, policy, folder):
    notes = ReviewNoteStore(folder / "review-notes.jsonl")
    tasks = TeamTaskStore(folder / "team-board.jsonl")
    board = TeamReviewBoard(history["graph"], policy, notes, tasks)
    _require(not notes.path.exists() and not tasks.path.exists(),
             "Review journals must not appear before explicit publication")

    first = board.note("chloe", node_id=history["bob"].node_id,
                       path=CONFLICT, expected_head=None,
                       text="Les deux auteurs modifient le titre de la quête.")
    reply = board.note("bob", node_id=history["bob"].node_id,
                       path=CONFLICT, expected_head=first["digest"],
                       text="Je propose de conserver ma formulation.",
                       thread=first["sequence"])
    asked = board.review("chloe", node_id=history["bob"].node_id,
                         path=CONFLICT, expected_head=None,
                         decision="changes_requested",
                         summary="Une résolution explicite est obligatoire")
    task = board.create_task("alice", node_id=history["bob"].node_id,
                             path=CONFLICT, expected_head=asked["digest"],
                             title="Arbitrer le titre d'arrivée", assignee="chloe",
                             release=RELEASE)
    progress = board.change_task("chloe", task_id=task["task"],
                                 expected_head=task["digest"],
                                 status="in_progress")
    _require(progress["status"] == "in_progress", "Team task did not advance")
    _require(len(board.discussions("alice", history["bob"].node_id,
                                   ANCHOR)) == 1,
             "Typed quest anchor did not bind the review thread")
    _require(len(board.decisions("alice", node_id=history["bob"].node_id)) == 1,
             "Change request was lost")
    return board, first, reply, task


def _export_preview(saved_content_path, folder):
    """Exercise real R15 staging/integrity, NOT native runtime certification.

    A deliberately non-executable Player marker is used. This proves only
    that the canonical merged game data survives R15 preview packaging. A
    real, separately built Player and physical PC certification are required.
    """
    checked = preflight(saved_content_path, require_licenses=False)
    _require(checked["passed"], "Merged Content/GameProject failed R15 preflight")
    runtime = folder / "synthetic-runtime-not-for-release"
    runtime.mkdir()
    (runtime / _native_name()).write_bytes(
        b"DRAWTEMP R78.C NON-EXECUTABLE BUNDLE TEST MARKER\n")
    output = folder / "preview-bundle"
    exported = export_game(saved_content_path, runtime, output,
                           require_licenses=False, release=False)
    manifest = verify_bundle(exported)
    _require(manifest["release_candidate"] is False,
             "Preview bundle was incorrectly marked as releasable")
    _require((output / manifest["content"]).read_bytes() ==
             saved_content_path.read_bytes(), "Content bytes changed in export")
    companion = saved_content_path.with_name(saved_content_path.stem + ".game.json")
    bundled_companion = output / ("game/" + companion.name)
    _require(bundled_companion.read_bytes() == companion.read_bytes(),
             "GameProject bytes changed in export")
    try:
        verify_bundle(output, require_release=True)
    except ExportError:
        pass
    else:
        raise AssertionError("Synthetic preview was incorrectly release-certified")
    try:
        export_game(saved_content_path, runtime, output, release=False)
    except ExportError:
        pass
    else:
        raise AssertionError("Export overwrote an existing destination")
    return {"preflight": "passed", "bundle_integrity": "passed",
            "native_runtime": "synthetic-not-executable",
            "release_certified": False, "strict_release_rejected": True,
            "files": len(manifest["files"])}


def _execute(folder, *, run_gameplay, run_export):
    history = build_editors()
    graph, alice, bob = history["graph"], history["alice"], history["bob"]
    policy = TeamAccessPolicy({
        "owner": "owner", "alice": "editor", "bob": "editor",
        "chloe": "reviewer", "guest": "viewer",
    })
    undo = _undo_gate(history, policy)
    board, note, reply, task = _review_gate(history, policy, folder)
    _require(len(graph) == 3, "Advisory review changed canonical history")

    leases = TeamLeaseRegistry(policy)
    lease = leases.acquire("alice")
    try:
        try:
            leases.acquire("bob")
        except TeamWorkflowError as error:
            _require(error.code == "lease_busy",
                     "Unexpected rejection instead of exclusive lease contention")
        else:
            raise AssertionError("Bob took a lease while Alice already holds it")
        studio = history["alice_session"]
        before = studio.snapshot().to_dict()
        workspace = TeamMergeWorkspace(studio, graph, policy, leases)
        review = workspace.preview(
            "alice", lease.token, local_id=alice.node_id,
            incoming_id=bob.node_id)
        _require(tuple(row.path for row in review.conflicts) == (CONFLICT,),
                 "Expected one typed map/quest conflict")
        try:
            workspace.apply("alice", lease.token, review, {})
        except ValueError:
            pass
        else:
            raise AssertionError("Unresolved same-quest conflict was applied")
        _require(before == studio.snapshot().to_dict(),
                 "Invalid merge mutated the editor")
        transition = workspace.apply(
            "alice", lease.token, review, {CONFLICT: CHOICE})
        merged = transition.snapshot.to_dict()
        _assert_merged(merged)
        joint = workspace.register("alice", lease.token,
                                   label="R78.C — fusion carte et quête")
        _require(joint.parents == (alice.node_id, bob.node_id),
                 "Merged history did not preserve both parents")
        _require(len(graph) == 4, "Expected a single immutable merge node")

        done = board.change_task(
            "chloe", task_id=task["task"],
            expected_head=board.tasks.inspect()["head"], status="done")
        approved = board.review(
            "chloe", node_id=joint.node_id,
            path=CONFLICT, expected_head=done["digest"],
            decision="approved", summary="Arbitrage R30 vérifié en lecture seule")
        final_note = board.note(
            "chloe", node_id=bob.node_id, path=CONFLICT,
            expected_head=reply["digest"], kind="resolve",
            thread=note["sequence"])
        _require(board.discussions("guest", bob.node_id, ANCHOR)[0]["resolved"],
                 "Conflict discussion was not explicitly resolved")
        _require(board.release_board("guest")[RELEASE]["done"][0]["task"] ==
                 task["task"], "Task board did not close the review task")
        _require(board.decisions("guest", node_id=joint.node_id)[0]["status"] ==
                 "approved", "Advisory approval was not recorded")

        history_store = LocalHistoryStore(folder / "history.r48.json")
        archive = history_store.save(graph)
        restored, pinned = history_store.load()
        _require(archive == pinned, "Saved history archive failed roundtrip")
        _require(tuple(node.node_id for node in restored.nodes()) ==
                 tuple(node.node_id for node in graph.nodes()),
                 "DAG ancestry or node IDs changed on reload")
        _require(ReviewNoteStore(board.notes.path).inspect()["head"] ==
                 final_note["digest"], "Notes HEAD lost on reopen")
        _require(TeamTaskStore(board.tasks.path).inspect()["head"] ==
                 approved["digest"], "Tasks HEAD lost on reopen")

        audit = LocalAuditLog(folder / "reviewed.audit.jsonl")
        event = workspace.append_audit(
            "alice", lease.token, audit, expected_head=None)
        evidence = reconcile_audit(
            audit, studio,
            known_revisions=tuple(node.revision for node in restored.nodes()),
            expected_head=event["digest"])
        _require(evidence.state == "aligned" and evidence.anchored,
                 "Canonical merge and immutable audit evidence diverged")

        path = folder / "jeanne-team.json"
        studio.save_as(path)
        reopened = AuthoringSession.open(path)
        snap = reopened.snapshot().to_dict()
        _require((snap["content"], snap["project"]) ==
                 (merged["content"], merged["project"]),
                 "Saved and reopened canonical pair diverged")
        _require(fingerprint_pair(snap["content"], snap["project"]) ==
                 joint.revision.digest,
                 "Saved game is not the verified reviewed merge")
        _require(history["bob_session"].snapshot().to_dict() ==
                 history["bob_data"], "Bob's independent editor was mutated")

        export = (_export_preview(path, folder) if run_export else
                  {"preflight": "not_run", "release_certified": False})
        gameplay = (_gameplay_gate(merged["content"], merged["project"], folder)
                    if run_gameplay else {"result": "not_run"})
        return {
            "schema": 1, "result": "passed",
            "scope": "local-two-author-vertical-not-release-certification",
            "conflict": CONFLICT, "choice": CHOICE,
            "root_digest": history["root"].revision.digest,
            "alice_digest": alice.revision.digest,
            "bob_digest": bob.revision.digest,
            "merged_digest": joint.revision.digest,
            "archive_sha256": archive,
            "nodes": len(graph), "notes": board.notes.inspect()["count"],
            "board_events": board.tasks.inspect()["count"],
            "audit": evidence.state, "undo": undo, "export": export,
            "gameplay": gameplay, "release_certified": False,
        }
    finally:
        # Never claim distributed locking: only the local lease is released.
        leases.release("alice", lease.token)


def run_gate(*, run_gameplay=True, run_export=True):
    """Run in an isolated disposable workspace; no user's project is written."""
    with TemporaryDirectory(prefix="drawtemp-r78c-") as directory:
        return _execute(Path(directory), run_gameplay=run_gameplay,
                        run_export=run_export)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-gameplay", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args(argv)
    import json
    report = run_gate(run_gameplay=not args.no_gameplay,
                      run_export=not args.no_export)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
