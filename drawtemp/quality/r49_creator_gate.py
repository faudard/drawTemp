"""R49.C1 — reproducible headless Creator slice and fail-closed gate dossier.

This is *supporting* evidence, not a GUI author study, GPU benchmark or
installed native Player certification. It uses the R28 Creator factory,
R1 AuthoringSession, R2 typed inspector, R15 preflight/export and R30.F
CPU profiler. It never writes a new Content/GameProject schema.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import export_game, preflight, project_path, verify_bundle
from drawtemp.quality.r30_scale import collect_profile, validate_report
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.genre_workflow import create_genre_project, genre_preset
from drawtemp.studio.inspector_model import edit_properties
from drawtemp.studio.r49_first_scene import FirstSceneRequest, apply_first_scene
from drawtemp.studio.workspace_model import resources

SCHEMA = "drawtemp-r49c1-creator-slice-v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
EVIDENCE_KINDS = (
    "ci_linux", "ci_windows", "ci_macos",
    "author_guided", "author_unguided",
    "onscreen_linux", "onscreen_windows", "onscreen_macos",
    "native_player_linux", "native_player_windows", "native_player_macos",
    "accessibility_review", "hardware_profile", "licenses_review",
    "replay_save_review", "native_export_clean_machine",
)
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


class CreatorGateError(ValueError):
    """Invalid or insufficient evidence; never elevate to certification."""


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _index_evidence(evidence):
    if not isinstance(evidence, dict):
        raise CreatorGateError("Evidence mapping expected")
    if set(evidence) - set(EVIDENCE_KINDS):
        raise CreatorGateError("Unknown R49 evidence kind")
    indexed = {}
    for kind, location in sorted(evidence.items()):
        if not isinstance(location, (str, Path)):
            raise CreatorGateError("Evidence path expected")
        path = Path(location)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
            raise CreatorGateError("Evidence missing, linked or oversized: " + kind)
        indexed[kind] = {
            "sha256": _hash_file(path), "size_bytes": path.stat().st_size,
            "review_status": "not_independently_verified",
        }
    return indexed


def assemble_gate(*, revision, headless, preexport, runtime_bundle,
                  profile_available=False, evidence=None):
    """Compose evidence with a mandatory independent human release gate.

    Presence of an artifact is not proof of its truth. Neither CI nor an
    arbitrary JSON 'passed' field may turn this machine report into GO.
    """
    if not isinstance(revision, str) or not HEX40.fullmatch(revision):
        raise CreatorGateError("Exact lowercase Git commit SHA-40 required")
    if type(headless) is not bool or type(preexport) is not bool or type(profile_available) is not bool:
        raise CreatorGateError("Gate observations must be booleans")
    if runtime_bundle not in ("blocked", "preview_integrity_verified"):
        raise CreatorGateError("Unknown native bundle status")
    indexed = _index_evidence(evidence or {})
    missing = [kind for kind in EVIDENCE_KINDS if kind not in indexed]
    blockers = []
    if not headless:
        blockers.append("Headless creator roundtrip not verified")
    if not preexport:
        blockers.append("Canonical R15 preflight did not pass")
    if runtime_bundle != "preview_integrity_verified":
        blockers.append("Native Player preview bundle integrity not checked")
    if not profile_available:
        blockers.append("Canonical CPU profile missing")
    if missing:
        blockers.append("Required external evidence missing: " + ", ".join(missing))
    blockers.append("Independent creator, hardware and release review is required")
    return {
        "schema": "drawtemp-r49c1-gate-v1",
        "commit": revision,
        "status": "NO_GO",
        "automation": "supporting_evidence_only",
        "evidence": indexed,
        "missing_evidence": missing,
        "blockers": blockers,
        "release_certified": False,
        "independent_review_complete": False,
    }


def _source_pair_hashes(content_path):
    content = Path(content_path)
    project = project_path(content)
    return {"content_sha256": _hash_file(content),
            "project_sha256": _hash_file(project)}


def _author_canonical_project(folder, genre):
    """Author with public factories/typed UI contracts, never JSON editing."""
    project_dir = create_genre_project(genre, folder)
    content_path = project_dir / "game.json"
    session = AuthoringSession.open(content_path)
    baseline = session.snapshot().to_dict()
    catalog = resources(session.snapshot())
    maps = [item for item in catalog if item.family == "maps"]
    actors = [item for item in catalog if item.family == "actors"]
    if not maps or not actors:
        raise CreatorGateError("Starter must expose a map and an actor for this slice")
    # Two different resource families, one existing transactional editor.
    edit_properties(session, [maps[0]], {"name": "Carte du premier auteur"},
                    expected_revision=session.revision)
    edited_map = session.snapshot().revision
    edit_properties(session, [actors[0]], {"name": "Personnage du premier auteur"},
                    expected_revision=session.revision)
    apply_first_scene(session, FirstSceneRequest(
        mission_id=maps[0].resource_id,
        event_id="r49_intro_event", scene_id="r49_intro_scene",
        title="Premier scénario", speaker="Narrateur",
        dialogue="Bienvenue dans l'aventure.",
        action_message="La mission commence.", tick=1),
        expected_revision=session.revision)
    edited = session.snapshot().to_dict()
    if edited == baseline or session.revision != edited_map + 2:
        raise CreatorGateError("Canonical authoring did not update both documents")
    source_map = next(row for row in edited["content"]["missions"]
                      if row["id"] == maps[0].resource_id)
    if not any(row["id"] == "r49_intro_event" and
               row["actions"] == [{"kind": "message",
                                   "text": "La mission commence."}]
               for row in source_map["triggers"]):
        raise CreatorGateError("First tactical event/action was not persisted")
    scenes = edited["project"]["story"]["scenes"]
    if not any(row["id"] == "r49_intro_scene" for row in scenes):
        raise CreatorGateError("First narrative scene was not persisted")
    if edited["project"]["story"]["during_tactical_event"].get(
            maps[0].resource_id + "/r49_intro_event") != "r49_intro_scene":
        raise CreatorGateError("Canonical story/trigger reference not linked")
    session.undo()
    if session.snapshot().to_dict() == edited:
        raise CreatorGateError("Undo did not revert the authoring transaction")
    session.redo()
    if session.snapshot().to_dict() != edited:
        raise CreatorGateError("Redo did not restore the authored pair")
    if session.snapshot().revision < 5:
        raise CreatorGateError("Missing authoring/undo/redo history")
    session.save()
    reopened = AuthoringSession.open(content_path)
    if reopened.snapshot().to_dict() != edited:
        raise CreatorGateError("Saved pair does not match reopened canonical project")
    report = preflight(content_path)
    if not report["passed"]:
        raise CreatorGateError("R15 preflight failed: " + "; ".join(report["errors"]))
    return {
        "content_path": content_path, "resource_counts": {
            "maps": len(maps), "actors": len(actors),
            "scenes": sum(r.family == "scenes"
                          for r in resources(session.snapshot())),
        },
        "checks": {
            "r28_template_created": True,
            "r1_typed_edits": True,
            "r1_undo_redo": True,
            "r9_scene_trigger_action": True,
            "disk_save_reopen": True,
            "r15_preflight": True,
            "qt_gui_author_journey": False,
            "real_gameplay_action": False,
            "native_player_playtest": False,
            "external_author_test": False,
        },
        "preflight": {
            "passed": True, "mission_count": len(report["missions"]),
            "asset_count": len(report["assets"]),
            "warnings_count": len(report["warnings"]),
            "rights_attestations_checked": report["rights_attestations_checked"],
        },
    }


def run_creator_slice(output, *, revision, genre="srpg", runtime_dir=None,
                      profile_samples=0, evidence=None):
    """Publish only complete supporting evidence in a new output directory.

    Never overwrites an existing directory/symlink. Failed runs leave no
    complete public result. Native export is optional and always *preview*,
    even when its hash verification passes.
    """
    if not isinstance(revision, str) or not HEX40.fullmatch(revision):
        raise CreatorGateError("Commit SHA must be lowercase and complete")
    preset = genre_preset(genre)
    if preset.template is None:
        raise CreatorGateError("Requested genre is not yet supported: " + genre)
    if type(profile_samples) is not int or profile_samples not in (0, *range(3, 251)):
        raise CreatorGateError("Profile samples must be 0 or 3..250")
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise CreatorGateError("Existing destination may not be overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".r49c1-", dir=output.parent) as temp:
        stage = Path(temp) / "slice"
        stage.mkdir()
        authored = _author_canonical_project(stage / "project", genre)
        content_path = authored.pop("content_path")
        hash_before = _source_pair_hashes(content_path)
        bundle_state = "blocked"
        bundle_details = {"status": "blocked", "reason": "No native Player runtime provided"}
        if runtime_dir is not None:
            bundle = export_game(content_path, runtime_dir,
                                 stage / "bundle-preview",
                                 require_licenses=False, release=False)
            manifest = verify_bundle(bundle)
            bundle_state = "preview_integrity_verified"
            bundle_details = {
                "status": bundle_state, "verified_files": len(manifest["files"]),
                "release_candidate": False,
                "hardware_execution_verified": False,
                "license_review_completed": False,
            }
        profile = None
        if profile_samples:
            profile = validate_report(collect_profile(
                content_path=content_path, samples=profile_samples,
                warmups=1, synthetic_resources=1000))
            (stage / "profile.json").write_text(
                json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        if _source_pair_hashes(content_path) != hash_before:
            raise CreatorGateError("Verification unexpectedly mutated authored files")
        gate = assemble_gate(
            revision=revision, headless=True,
            preexport=authored["preflight"]["passed"],
            runtime_bundle=bundle_state,
            profile_available=profile is not None,
            evidence=evidence,
        )
        report = {
            "schema": SCHEMA,
            "revision": revision,
            "scope": "headless_contract_slice_not_onscreen_author_study",
            "genre": genre,
            "creator": authored,
            "canonical_pair": hash_before,
            "native_bundle": bundle_details,
            "cpu_profile": {
                "collected": profile is not None,
                "path": "profile.json" if profile is not None else None,
                "gpu_certified": False,
            },
            "gate": gate,
        }
        (stage / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(stage, output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="R49.C1 supporting Creator evidence (not release certification)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--genre", choices=("srpg", "narrative"), default="srpg")
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--profile-samples", type=int, default=0)
    parser.add_argument("--evidence", action="append", default=[], metavar="KIND=FILE")
    args = parser.parse_args(argv)
    indexed = {}
    for entry in args.evidence:
        key, separator, location = entry.partition("=")
        if not separator or not location or key in indexed:
            parser.error("Evidence entries must be unique KIND=FILE")
        indexed[key] = location
    try:
        report = run_creator_slice(
            args.output, revision=args.revision, genre=args.genre,
            runtime_dir=args.runtime_dir, profile_samples=args.profile_samples,
            evidence=indexed)
    except (CreatorGateError, ValueError, OSError) as exc:
        parser.exit(2, "R49.C1: " + str(exc) + "\n")
    print(json.dumps({"schema": report["schema"], "gate": report["gate"]["status"],
                      "output": str(args.output), "genre": report["genre"]},
                     ensure_ascii=False))
    return 0  # harness succeeded; gate status remains NO_GO


if __name__ == "__main__":
    raise SystemExit(main())
