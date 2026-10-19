"""R23.A release ledger must be commit-pinned, cross-OS and fail closed."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest

from drawtemp.export.r15 import export_game
from drawtemp.export.templates import create_template
from scripts.r23_release_gate import PLATFORMS, aggregate, native_evidence

SHA = "a" * 40


class R23EvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="r23-native-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        content = create_template("blank", self.root / "project") / "game.json"
        runtime = self.root / "runtime"
        runtime.mkdir()
        native = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (runtime / native).write_bytes(b"frozen player stub")
        (runtime / "qt.dat").write_bytes(b"qt stub")
        self.bundle = export_game(content, runtime, self.root / "bundle")

    def proofs(self):
        return [native_evidence(self.bundle, revision=SHA, platform=platform)
                for platform in PLATFORMS]

    def test_native_probe_hashes_real_manifest_without_claiming_installer(self):
        result = native_evidence(self.bundle, revision=SHA, platform="Linux")
        self.assertEqual(result["revision"], SHA)
        self.assertEqual(len(result["manifest_sha256"]), 64)
        self.assertEqual(result["integrity"], "passed")
        self.assertEqual(result["clean_machine"], "not-asserted")
        self.assertEqual(result["smoke"], "not-asserted")

    def test_actual_manifest_tamper_prevents_report(self):
        target = self.bundle / "game" / "game.json"
        target.write_bytes(target.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            native_evidence(self.bundle, revision=SHA, platform="Linux")

    def test_matrix_remains_no_go_even_after_three_valid_builds(self):
        result = aggregate(self.proofs(), revision=SHA)
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["certified"])
        self.assertEqual(set(result["native_matrix"]), set(PLATFORMS))
        self.assertEqual(result["checks"]["R23.2"]["status"], "partial")
        self.assertEqual(result["checks"]["R23.10"]["status"], "blocked")
        self.assertEqual(len(result["checks"]), 12)

    def test_missing_or_duplicate_platform_prevents_aggregation(self):
        proofs = self.proofs()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            aggregate(proofs[:2], revision=SHA)
        proofs[-1]["platform"] = "Linux"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            aggregate(proofs, revision=SHA)

    def test_wrong_commit_prevents_aggregation(self):
        proofs = self.proofs()
        proofs[0]["revision"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "different commit"):
            aggregate(proofs, revision=SHA)

    def test_forged_external_certification_prevents_aggregation(self):
        proofs = self.proofs()
        proofs[0]["clean_machine"] = "passed"
        with self.assertRaisesRegex(ValueError, "Unverified"):
            aggregate(proofs, revision=SHA)

    def test_invalid_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, "commit SHA"):
            native_evidence(self.bundle, revision="master", platform="Linux")
        with self.assertRaisesRegex(ValueError, "commit SHA"):
            aggregate(self.proofs(), revision="local")

    def test_malformed_sha_or_file_count_rejected(self):
        proofs = self.proofs()
        proofs[1]["manifest_sha256"] = "fake"
        with self.assertRaisesRegex(ValueError, "integrity evidence"):
            aggregate(proofs, revision=SHA)
        proofs = self.proofs()
        proofs[1]["indexed_files"] = True
        with self.assertRaisesRegex(ValueError, "file count"):
            aggregate(proofs, revision=SHA)


if __name__ == "__main__":
    unittest.main()
