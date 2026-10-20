"""R80.A2: executable historical-format regression; deliberately NOT 12.0 certification.

Anchors four repository content documents to the exact Git blobs in the R16
merge commit dated 2026-10-15. They have not changed on this feature branch.
The v0 envelope is a documented, *derived* compatibility case, not a claim
that a separately archived v0 customer project exists.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HISTORICAL_COMMIT = "7829988c587b7761e2ec07944b343fef59a06943"
# SHA-1 values are Git blob object identities, not user-supplied attestations.
PINNED = {
    "core.json": "cff5763c18c5bc34feefa35db8ba4f971bbb6851",
    "core.game.json": "3d8d9751d0573b44dd75bd965df5e360b18e2053",
    "jeanne.json": "5246292a14b66bc9a4a3ed011c34468dc192662e",
    "jeanne.game.json": "e252012b7b46799a85b712c4243e4bc7d4775287",
}
ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = ("content_v0_to_v1_migration", "content_v1_project_v1_roundtrip",
             "unknown_schema_rejection", "legacy_jeanne_ct_replay",
             "session_v1_save_restore", "session_store_v2_recovery",
             "migration_rollback")


class HistoricalRegressionError(ValueError):
    """An observed historical-format incompatibility or failed invariant."""


def _assert(condition, message):
    if not condition:
        raise HistoricalRegressionError(message)


def _git_blob(raw):
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def load_pinned_sources(source_root=None):
    """Reject drift before parsing anything; no network and no file writes."""
    root = Path(source_root) if source_root is not None else ROOT
    directory = root / "sporebound" / "content"
    pinned = {}
    for name, expected in PINNED.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise HistoricalRegressionError("Missing/linked historical fixture " + name)
        with path.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        _assert(len(raw) <= 4 * 1024 * 1024, "Oversized historical fixture " + name)
        _assert(_git_blob(raw) == expected, "Historical fixture drift: " + name)
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys,
                              parse_constant=_reject_constant)
        except (UnicodeError, ValueError, TypeError) as exc:
            raise HistoricalRegressionError("Unreadable pinned source " + name) from exc
        _assert(type(data) is dict, "Historical fixture must be a JSON object")
        pinned[name] = (raw, data)
    return pinned


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoricalRegressionError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise HistoricalRegressionError("Nonfinite number: " + value)


def run_historical_regressions(*, source_root=None):
    """Run real Core/SDK migration, replay and save validators on R16 data.

    Temporary targets are freshly created. Originals are only read; no
    verification updates a checked-in fixture, rewrites a save or grants
    publication permission.
    """
    from drawtemp.core import Content, GameProject, GameSession
    from drawtemp.sdk.content_migration import (
        MigrationError as EnvelopeError, commit_pair, preview_pair, preview_documents)
    from drawtemp.sdk.legacy_migration import (
        MigrationError as LegacyError, migrate_project, rollback_project)
    from drawtemp.sdk.reference import MISSION, reference_project
    from drawtemp.sdk.replay import ReplayCommand, ReplayError, verify_recording, verify_sequence
    from sporebound.persistence import SessionStore

    sources = load_pinned_sources(source_root)
    observations = {}
    for stem in ("core", "jeanne"):
        content = Content.from_dict(deepcopy(sources[stem + ".json"][1]))
        project = GameProject.from_dict(deepcopy(sources[stem + ".game.json"][1]), content)
        canonical_content = content.to_dict()
        canonical_project = project.to_dict()
        _assert(Content.from_dict(canonical_content).to_dict() == canonical_content,
                "Content v1 canonical round trip drift: " + stem)
        _assert(GameProject.from_dict(canonical_project, content).to_dict() ==
                canonical_project, "GameProject v1 canonical round trip drift: " + stem)
        observations[stem] = {
            "content_git_blob": PINNED[stem + ".json"],
            "project_git_blob": PINNED[stem + ".game.json"],
            "content_sha256": sha256(sources[stem + ".json"][0]).hexdigest(),
            "project_sha256": sha256(sources[stem + ".game.json"][0]).hexdigest(),
        }

    data = deepcopy(sources["core.json"][1])
    project_data = deepcopy(sources["core.game.json"][1])
    # Historical v0 *envelope* support has no claim of older gameplay schemas.
    data.pop("version")
    project_data["version"] = 0
    cv, pv, changes, result_c, result_p = preview_documents(data, project_data)
    _assert((cv, pv) == (0, 0) and len(changes) == 2,
            "Expected only explicit v0 envelope migration")
    _assert(result_c["version"] == 1 and result_p["version"] == 1,
            "v0 migrated into unsupported schema")

    for label, doc in (("content", data), ("project", project_data)):
        broken = deepcopy(doc)
        broken["version"] = 99
        try:
            if label == "content":
                preview_documents(broken, project_data)
            else:
                preview_documents(data, broken)
        except EnvelopeError as exc:
            _assert(exc.code == "unsupported_version",
                    "Unknown schema produced wrong rejection")
        else:
            raise HistoricalRegressionError("Unknown " + label + " schema accepted")

    with TemporaryDirectory(prefix="drawtemp-r80a2-") as temp:
        folder = Path(temp)
        v0_path = folder / "v0" / "legacy.json"
        v0_path.parent.mkdir()
        v0_project = v0_path.with_suffix(".game.json")
        v0_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        v0_project.write_text(json.dumps(project_data, ensure_ascii=False),
                              encoding="utf-8")
        v0_originals = (v0_path.read_bytes(), v0_project.read_bytes())
        plan = preview_pair(v0_path)
        converted_path = folder / "converted" / "core.json"
        converted_path.parent.mkdir()
        commit_pair(plan, converted_path)
        converted_game = converted_path.with_suffix(".game.json")
        _assert((v0_path.read_bytes(), v0_project.read_bytes()) == v0_originals,
                "Envelope migration changed historical source")
        expected_content = Content.from_dict(sources["core.json"][1])
        expected_project = GameProject.from_dict(
            sources["core.game.json"][1], expected_content)
        converted_content = Content.load(converted_path)
        _assert(converted_content.to_dict() == expected_content.to_dict(),
                "Content envelope normalization differs from canonical v1")
        _assert(GameProject.load(converted_game, converted_content).to_dict() ==
                expected_project.to_dict(),
                "Project envelope normalization differs from canonical v1")
        # Explicit stale approval must fail before any new destination appears.
        v0_path.write_bytes(v0_originals[0] + b" ")
        stale_target = folder / "stale.json"
        try:
            commit_pair(plan, stale_target)
        except EnvelopeError as exc:
            _assert(exc.code == "stale_preview", "Wrong stale approval rejection")
        else:
            raise HistoricalRegressionError("Stale migration preview was accepted")
        _assert(not stale_target.exists(), "Stale migration published a project")

        # Actual checked-in historical R16 content, byte-preserved through
        # the existing reversible migration contract (not a schema bump).
        historical = folder / "historical" / "core.json"
        historical.parent.mkdir()
        historical_manifest = historical.with_suffix(".game.json")
        historical.write_bytes(sources["core.json"][0])
        historical_manifest.write_bytes(sources["core.game.json"][0])
        original_pair = (historical.read_bytes(), historical_manifest.read_bytes())
        bundle = folder / "migration-bundle"
        migrate_project(historical, bundle)
        restore = folder / "rolled-back"
        rollback_project(bundle, restore)
        _assert(((restore / "core.json").read_bytes(),
                 (restore / "core.game.json").read_bytes()) == original_pair,
                "R16 rollback was not byte-identical")
        _assert((historical.read_bytes(), historical_manifest.read_bytes()) == original_pair,
                "R16 migration modified source")
        try:
            rollback_project(bundle, restore)
        except LegacyError:
            pass
        else:
            raise HistoricalRegressionError("Existing rollback target overwritten")
        # Tamper with a disposable migration bundle, never a checked-in fixture.
        (bundle / "originals" / "core.json").write_bytes(b"{}")
        corrupted_target = folder / "corrupted-rollback"
        try:
            rollback_project(bundle, corrupted_target)
        except LegacyError:
            pass
        else:
            raise HistoricalRegressionError("Tampered backup was restored")
        _assert(not corrupted_target.exists(), "Corrupt rollback published files")

        # Real Jeanne canonical CT trace, validated at each checkpoint by
        # SDK replay and GameSession.from_recording (no synthetic replay API).
        jeanne_content, jeanne_project = reference_project()
        initial = GameSession.new(jeanne_content, jeanne_project, "main", seed=17)
        commands = (
            ReplayCommand("choose_story_option", ("enter",)),
            ReplayCommand("start_mission", (MISSION,)),
            ReplayCommand("execute", ({"kind": "interact", "unit": "jeanne",
                                       "object": "lever"},)),
            ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
        )
        trace = verify_sequence(jeanne_content, jeanne_project, "main", commands, seed=17)
        _assert(trace.verified and len(trace.checkpoints) == len(commands) + 1,
                "Jeanne replay missing verified checkpoints")
        _assert(trace.checkpoints[-1].mode == "battle" and
                trace.checkpoints[-1].tactical_digest is not None,
                "Jeanne tactical state disappeared")
        initial_snapshot = deepcopy(initial.recording())
        _assert(verify_recording(initial_snapshot, jeanne_content, jeanne_project)
                .recording() == initial_snapshot, "Jeanne v1 replay round-trip mismatch")
        first_digest = initial_snapshot["digest"]

        # R16 supported game_session v1 -> SessionStore v2 migration leaves
        # primary and exact previous-generation v1 bytes accessible.
        v1 = folder / "save-v1.json"
        initial.save(v1)
        old_bytes = v1.read_bytes()
        store = SessionStore(v1)
        migrated = store.migrate_v1(jeanne_content, jeanne_project,
                                    expected_campaign_id="main")
        _assert(migrated.sequence == 1 and not migrated.migrated_from_v1,
                "V2 checkpoint migration failed")
        _assert(store.backup.read_bytes() == old_bytes,
                "V1 backup not byte-for-byte preserved")
        restored = store.load_with_status(jeanne_content, jeanne_project)
        _assert(restored.source == "primary" and
                restored.session.recording()["digest"] == first_digest,
                "V2 recovery changed GameSession progress/identity")
        # Repeated loads must not apply a reward or any command.
        _assert(store.load(jeanne_content, jeanne_project).recording() ==
                store.load(jeanne_content, jeanne_project).recording(),
                "Repeated loads mutated campaign state")
        v2_bytes = v1.read_bytes()
        v1.write_text('{"version":999}', encoding="utf-8")
        recovered = store.load_with_status(jeanne_content, jeanne_project)
        _assert(recovered.source == "backup" and recovered.migrated_from_v1 and
                recovered.session.recording()["digest"] == first_digest,
                "V1 backup recovery diverged")
        _assert(v1.read_bytes() != v2_bytes, "Backup load silently overwrote damaged primary")
        store.backup.write_bytes(b"tampered")
        try:
            store.load(jeanne_content, jeanne_project)
        except Exception as exc:
            from drawtemp.core import RuleError
            _assert(isinstance(exc, RuleError),
                    "Unexpected corrupt-checkpoint exception")
        else:
            raise HistoricalRegressionError("Double-corrupt checkpoint was accepted")
        _assert((historical.read_bytes(), historical_manifest.read_bytes()) == original_pair,
                "Historical fixture bytes changed")

    return {
        "kind": "drawtemp-r80a2-executed-regressions",
        "schema": 1,
        "historical_commit": HISTORICAL_COMMIT,
        "checked": list(SUPPORTED),
        "pinned_sources": observations,
        "jeanne_replay_checkpoints": len(trace.checkpoints),
        "session_format_migration": "game_session_v1 -> session_checkpoint_v2",
        "result": "passed",
        "release_certified": False,
        "tag_allowed": False,
        "exclusions": [
            "No archived 5.x-11.x user-authored saves or separately archived v0 project",
            "No proof of no duplicate rewards after completed combat (load-only invariant checked)",
            "No long-session fault-injection certification",
            "No multi-mode runtime replay certification",
            "No external creator, physical GPU, clean-machine or license approval",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_historical_regressions()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2,
                                          ensure_ascii=False) + "\n", encoding="utf-8")
    except (HistoricalRegressionError, OSError, ValueError, AssertionError) as exc:
        print("R80.A2 compatibility gate blocked: " + str(exc), file=sys.stderr)
        return 2
    print("R80.A2 historical regression checks passed (12.0 release remains NO-GO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
