"""R49.C1: real canonical authoring slice and conservative release gate."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import preflight, project_path, verify_bundle
from drawtemp.quality.r49_creator_gate import (
    CreatorGateError, EVIDENCE_KINDS, HEX40, SCHEMA,
    _index_evidence, assemble_gate, run_creator_slice,
)
from drawtemp.sdk.authoring import AuthoringSession


REVISION = "a" * 40


class CreatorSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_canonical_template_authoring_undo_save_and_preflight(self):
        target = self.root / "vs49"
        report = run_creator_slice(target, revision=REVISION, genre="srpg")
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["revision"], REVISION)
        self.assertEqual(report["scope"],
                         "headless_contract_slice_not_onscreen_author_study")
        self.assertEqual(report["gate"]["status"], "NO_GO")
        self.assertFalse(report["gate"]["release_certified"])
        self.assertFalse(report["creator"]["checks"]["real_gameplay_action"])
        self.assertTrue(report["creator"]["checks"]["r1_undo_redo"])
        self.assertTrue(report["creator"]["checks"]["disk_save_reopen"])
        self.assertTrue(report["creator"]["preflight"]["passed"])
        self.assertGreater(report["creator"]["resource_counts"]["maps"], 0)
        self.assertGreater(report["creator"]["resource_counts"]["actors"], 0)
        content = target / "project" / "game.json"
        game = project_path(content)
        self.assertTrue(content.is_file())
        self.assertTrue(game.is_file())
        opened = AuthoringSession.open(content)
        snapshot = opened.snapshot().to_dict()
        self.assertEqual(snapshot["content"]["missions"][0]["name"],
                         "Carte du premier auteur")
        self.assertTrue(any(
            row["name"] == "Personnage du premier auteur"
            for mission in snapshot["content"]["missions"]
            for row in mission["units"]))
        self.assertTrue(preflight(content)["passed"])
        self.assertEqual(
            sha256(content.read_bytes()).hexdigest(),
            report["canonical_pair"]["content_sha256"])
        self.assertEqual(
            sha256(game.read_bytes()).hexdigest(),
            report["canonical_pair"]["project_sha256"])
        self.assertEqual(
            json.loads((target / "report.json").read_text(encoding="utf-8")),
            report)
        self.assertFalse((target / "bundle-preview").exists())
        self.assertFalse(report["cpu_profile"]["collected"])
        self.assertIn("native_player_playtest",
                      report["creator"]["checks"])
        self.assertTrue(report["gate"]["missing_evidence"])

    def test_existing_destination_refused_without_modifying_data(self):
        path = self.root / "existing"
        path.mkdir()
        sentinel = path / "important.txt"
        sentinel.write_text("protected", encoding="utf-8")
        with self.assertRaises(CreatorGateError):
            run_creator_slice(path, revision=REVISION)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "protected")
        with self.assertRaises(CreatorGateError):
            run_creator_slice(self.root / "invalid_sha", revision="f" * 39)
        self.assertFalse((self.root / "invalid_sha").exists())

    def test_unavailable_genre_fails_before_writing(self):
        for kind in ("action_adventure", "classic_rpg", "hybrid"):
            with self.subTest(kind=kind), self.assertRaises(CreatorGateError):
                run_creator_slice(self.root / kind, revision=REVISION, genre=kind)
            self.assertFalse((self.root / kind).exists())
        with self.assertRaises(CreatorGateError):
            run_creator_slice(self.root / "bad", revision=REVISION,
                              profile_samples=2)
        self.assertFalse((self.root / "bad").exists())

    def test_mock_native_player_package_is_preview_only(self):
        # Identical to the R15 integrity unit tests: not a real executable.
        runtime = self.root / "fake-runtime"
        runtime.mkdir()
        filename = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (runtime / filename).write_bytes(b"NOT AN EXECUTABLE: integrity test only")
        result = run_creator_slice(self.root / "packaged", revision=REVISION,
                                   runtime_dir=runtime)
        info = result["native_bundle"]
        self.assertEqual(info["status"], "preview_integrity_verified")
        self.assertFalse(info["release_candidate"])
        self.assertFalse(info["hardware_execution_verified"])
        self.assertEqual(result["gate"]["status"], "NO_GO")
        manifest = verify_bundle(self.root / "packaged" / "bundle-preview")
        self.assertFalse(manifest["release_candidate"])
        self.assertEqual(manifest["certification"], "R14 not certified")

    def test_missing_native_runtime_fails_without_published_output(self):
        target = self.root / "no-runtime"
        with self.assertRaises((FileNotFoundError, OSError, ValueError)):
            run_creator_slice(target, revision=REVISION,
                              runtime_dir=self.root / "missing-player")
        self.assertFalse(target.exists())


class CreatorGatePolicyTests(unittest.TestCase):
    def test_mandatory_matrix_never_claims_certification(self):
        gate = assemble_gate(revision=REVISION, headless=True,
                             preexport=True,
                             runtime_bundle="preview_integrity_verified",
                             profile_available=True)
        self.assertEqual(gate["status"], "NO_GO")
        self.assertFalse(gate["release_certified"])
        self.assertEqual(gate["missing_evidence"], list(EVIDENCE_KINDS))
        self.assertIn("Independent creator", " ".join(gate["blockers"]))

    def test_files_are_hashed_not_trusted_as_attestations(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {}
            for kind in EVIDENCE_KINDS:
                path = root / (kind + ".txt")
                path.write_text('{"claimed_certification": "GO"}', encoding="utf-8")
                files[kind] = path
            gate = assemble_gate(revision=REVISION, headless=True,
                                 preexport=True,
                                 runtime_bundle="preview_integrity_verified",
                                 profile_available=True, evidence=files)
            self.assertEqual(gate["missing_evidence"], [])
            self.assertEqual(gate["status"], "NO_GO")
            self.assertFalse(gate["release_certified"])
            self.assertTrue(all(
                x["review_status"] == "not_independently_verified"
                for x in gate["evidence"].values()))
            selected = next(iter(files))
            self.assertEqual(
                gate["evidence"][selected]["sha256"],
                sha256(files[selected].read_bytes()).hexdigest())

    def test_invalid_paths_unknown_keys_and_incomplete_sha_fail_closed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "evidence.txt"
            valid.write_text("real bytes", encoding="utf-8")
            with self.assertRaises(CreatorGateError):
                _index_evidence({"unknown": valid})
            with self.assertRaises(CreatorGateError):
                _index_evidence({"ci_linux": root / "not-there"})
            with self.assertRaises(CreatorGateError):
                assemble_gate(revision="123", headless=True,
                              preexport=True, runtime_bundle="blocked")
            with self.assertRaises(CreatorGateError):
                assemble_gate(revision=REVISION, headless="yes",
                              preexport=True, runtime_bundle="blocked")
            with self.assertRaises(CreatorGateError):
                assemble_gate(revision=REVISION, headless=True,
                              preexport=True, runtime_bundle="certified")
            link = root / "linked.txt"
            try:
                link.symlink_to(valid)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(CreatorGateError):
                _index_evidence({"ci_linux": link})

    def test_all_validation_booleans_matter(self):
        gate = assemble_gate(revision=REVISION, headless=False,
                             preexport=False, runtime_bundle="blocked")
        self.assertEqual(gate["status"], "NO_GO")
        self.assertTrue(any("Headless" in reason for reason in gate["blockers"]))
        self.assertTrue(any("R15 preflight" in reason for reason in gate["blockers"]))


if __name__ == "__main__":
    unittest.main()
