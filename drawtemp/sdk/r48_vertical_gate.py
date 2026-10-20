"""R48.C1: deterministic, two-author Jeanne collaboration vertical slice.

Reuses real R1 authoring, R30 semantic merge, R48 graph/archive/notes/audit,
and canonical GameSession combat/replay. This is an executable regression gate,
not a certification of online collaboration, OS crash durability, export, or Qt.
All writes are confined to a temporary directory.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.core import Content, GameProject, GameSession
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.audit_reconciliation import reconcile_audit
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.migration import comparable, fingerprint
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.project_history import HistoryReviewController, RevisionGraph
from drawtemp.sdk.project_history_store import LocalHistoryStore
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.review_notes import ReviewNoteStore
from sporebound.ai import choose_command

CONFLICT = "/project/story/scenes/arrival/title"
ANCHOR = "/project/story/scenes/arrival"
TILE = (1, 4)
SEED = 17


def _alice_pair(content, project):
    """Map tile and mission authoring plus an intentionally contested title."""
    updated_content, updated_project = deepcopy(content), deepcopy(project)
    mission = next(row for row in updated_content["missions"] if row["id"] == MISSION)
    mission["name"] = "Village — route d'Alice"
    matches = [tile for tile in mission["board"]["tiles"]
               if tile["pos"] == list(TILE)]
    if len(matches) != 1 or matches[0]["surface"] != "cobble":
        raise AssertionError("R48.C reference terrain fixture drifted")
    matches[0]["surface"] = "grass"
    scene = updated_project["story"]["scenes"][0]
    scene["title"] = "Le village — version Alice"
    return updated_content, updated_project


def _bob_pair(content, project):
    """Independent narrative edit plus deliberate same-scene-title conflict."""
    updated_content, updated_project = deepcopy(content), deepcopy(project)
    scene = updated_project["story"]["scenes"][0]
    scene["title"] = "La lisière — version Bob"
    scene["text"] = "Jeanne prépare le groupe avant d'ouvrir la porte."
    updated_project["subtitle"] = "Chroniques de la lisière"
    return updated_content, updated_project


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _gameplay_gate(content_dict, project_dict, folder):
    """Run real story, tactical lever, save/load and canonical deterministic replay."""
    content = Content.from_dict(content_dict)
    project = GameProject.from_dict(project_dict, content)
    game = GameSession.new(content, project, "main", seed=SEED)
    _assert(game.active_scene() is not None, "Expected starting story scene")
    game.choose_story_option("enter")
    game.start_mission(MISSION)
    _assert(game.active_battle.board.tile((3, 4)).blocked,
            "Reference door was not initially blocked")
    game.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
    _assert(not game.active_battle.board.tile((3, 4)).blocked,
            "Reference door did not open after lever")
    turns = 0
    for turns in range(1, 701):
        if game.active_battle.result:
            break
        game.execute(choose_command(game.active_battle))
    _assert(game.active_battle.result == "victory",
            "Merged Jeanne mission did not reach deterministic victory")
    saved = folder / "player-replay.json"
    game.save(saved)
    original_bytes = saved.read_bytes()
    loaded = GameSession.load(saved, content, project)
    replayed = GameSession.from_recording(game.recording(), content, project)
    expected = comparable(game.recording())
    _assert(comparable(loaded.recording()) == expected, "Game save/load diverged")
    _assert(comparable(replayed.recording()) == expected, "Replay diverged")
    _assert(saved.read_bytes() == original_bytes, "Replay source was changed by loading")
    return {"result": "victory", "seed": SEED, "turns": turns,
            "replay_sha256": fingerprint(expected)}


def run_gate(*, run_gameplay=True):
    """Return deterministic digests and gate outcome without persistent user files."""
    content, project = reference_project()
    base_session = AuthoringSession.new(content, project)
    base = base_session.snapshot().to_dict()
    graph = RevisionGraph()
    root = graph.add(make_revision(base["content"], base["project"],
                                   author="baseline"), label="jeanne-root")
    alice_session = AuthoringSession.new(content, project)
    alice_session.apply(alice_session.preview_pair(
        _alice_pair, kind="r48c-map-and-dialogue"))
    alice_data = alice_session.snapshot().to_dict()
    alice = graph.add(make_revision(
        alice_data["content"], alice_data["project"], author="alice",
        parents=(root.revision.digest,)),
        parents=(root.node_id,), label="Alice: carte et scène")

    bob_session = AuthoringSession.new(content, project)
    bob_session.apply(bob_session.preview_pair(
        _bob_pair, kind="r48c-story-and-dialogue"))
    bob_data = bob_session.snapshot().to_dict()
    bob = graph.add(make_revision(
        bob_data["content"], bob_data["project"], author="bob",
        parents=(root.revision.digest,)),
        parents=(root.node_id,), label="Bob: dialogue")

    before = alice_session.snapshot().to_dict()
    reviewer = HistoryReviewController(alice_session, graph)
    review = reviewer.compare_history(alice.node_id, bob.node_id)
    _assert([row.path for row in review.conflicts] == [CONFLICT],
            "Expected exactly one explicit semantic title conflict")
    try:
        reviewer.apply(review, {})
    except ValueError:
        pass
    else:
        raise AssertionError("Unresolved conflict was silently applied")
    _assert(alice_session.snapshot().to_dict() == before,
            "Invalid review modified the editor")
    transition = reviewer.apply(review, {CONFLICT: "incoming"})
    merged = transition.snapshot.to_dict()
    _assert(merged["project"]["story"]["scenes"][0]["title"] ==
            "La lisière — version Bob", "Explicit incoming choice was ignored")
    _assert(merged["project"]["story"]["scenes"][0]["text"] ==
            "Jeanne prépare le groupe avant d'ouvrir la porte.",
            "Independent dialogue change was lost")
    _assert(merged["content"]["missions"][0]["name"] ==
            "Village — route d'Alice", "Local mission changes were lost")
    _assert(next(tile for tile in merged["content"]["missions"][0]["board"]["tiles"]
                 if tile["pos"] == list(TILE))["surface"] == "grass",
            "Local terrain tile was lost")

    merged_revision = make_revision(
        merged["content"], merged["project"], author="alice+bob",
        parents=(alice.revision.digest, bob.revision.digest))
    joint = graph.add(merged_revision,
                      parents=(alice.node_id, bob.node_id),
                      label="Reviewed two-author merge")

    with TemporaryDirectory(prefix="drawtemp-r48c-") as temporary:
        folder = Path(temporary)
        history = LocalHistoryStore(folder / "history.r48.json")
        archive_digest = history.save(graph)
        restored, read_digest = history.load()
        _assert(archive_digest == read_digest, "History archive digest changed")
        _assert([node.node_id for node in graph.nodes()] ==
                [node.node_id for node in restored.nodes()],
                "History node identity drifted after reload")

        source = folder / "jeanne.json"
        alice_session.save_as(source)
        current_pair = AuthoringSession.open(source).snapshot().to_dict()
        _assert(current_pair["content"] == merged["content"] and
                current_pair["project"] == merged["project"],
                "Canonical two-document save/reload diverged")
        _assert(base_session.snapshot().to_dict() == base,
                "Original reference session was mutated")

        notes = ReviewNoteStore(folder / "review.jsonl")
        initial = notes.append(bob, expected_head=None,
                               anchor=ANCHOR, author="alice",
                               text="Texte relu lors de la fusion")
        notes.append(bob, expected_head=initial["digest"],
                     anchor=ANCHOR, author="bob",
                     text="", kind="resolve", thread=initial["sequence"])
        _assert(notes.threads(node_id=bob.node_id)[0]["resolved"],
                "Reviewed scene discussion was not resolved")

        audit = LocalAuditLog(folder / "authoring.audit.jsonl")
        event = audit.append(expected_head=None, actor="alice", operation="merge",
                             resource="scene:arrival",
                             before=alice.revision.digest, after=joint.revision.digest)
        report = reconcile_audit(
            audit, alice_session,
            known_revisions=tuple(node.revision for node in restored.nodes()),
            expected_head=event["digest"])
        _assert(report.state == "aligned" and report.anchored,
                "Merged archive and advisory audit did not reconcile")
        gameplay = (_gameplay_gate(merged["content"], merged["project"], folder)
                    if run_gameplay else {"result": "not_run"})
    return {
        "schema": 1, "result": "passed", "conflict": CONFLICT,
        "base_digest": root.revision.digest,
        "alice_digest": alice.revision.digest,
        "bob_digest": bob.revision.digest,
        "merged_digest": merged_revision.digest,
        "archive_sha256": archive_digest, "nodes": len(graph),
        "notes": 2, "audit": "aligned", "gameplay": gameplay,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-gameplay", action="store_true",
                        help="Only validate the authoring, archive, review and audit gates")
    args = parser.parse_args()
    import json
    print(json.dumps(run_gate(run_gameplay=not args.no_gameplay),
                     indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
