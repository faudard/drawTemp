"""R17.6: fail-closed technical asset rights gate for standalone releases.

The approved records in these tests are synthetic data, NOT legal approval
of any artwork or a certification of Jeanne's production asset pack.
"""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import (
    ExportError, export_game, preflight, verify_bundle,
)
from drawtemp.export.templates import create_template


class R17AssetRightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = create_template("jeanne", self.root / "creator-project")
        self.content = self.project / "game.json"
        self.assets = preflight(self.content)["assets"]
        self.assertTrue(self.assets)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        binary = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (self.runtime / binary).write_bytes(b"synthetic test runtime, not executable")

    def write_rights(self, entries=None):
        if entries is None:
            entries = self.valid_rights()
        path = self.project / "asset-licenses.json"
        path.write_text(json.dumps({"schema": 1, "assets": entries}, indent=2),
                        encoding="utf-8")
        return path

    def valid_rights(self):
        evidence = self.project / "licenses" / "fixture-grant.txt"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            "TEST FIXTURE ONLY. This is not an actual copyright license.\n",
            encoding="utf-8")
        return {
            rel: {
                "status": "approved",
                "rights_holder": "Synthetic test fixture",
                "license_id": "TEST-ONLY",
                "evidence_path": "licenses/fixture-grant.txt",
                "sha256": sha256((self.project / rel).read_bytes()).hexdigest(),
                "allow_modification": True,
                "allow_redistribution": True,
            } for rel in self.assets
        }

    def test_jeanne_template_is_preview_not_licensed_release(self):
        preview = preflight(self.content)
        self.assertTrue(preview["passed"], preview["errors"])
        self.assertFalse(preview["rights_attestations_checked"])
        self.assertTrue(any("asset-licenses.json" in w for w in preview["warnings"]))
        strict = preflight(self.content, require_licenses=True)
        self.assertFalse(strict["passed"])
        self.assertTrue(any("asset-licenses.json" in e for e in strict["errors"]))
        bundle = self.root / "preview"
        export_game(self.content, self.runtime, bundle)
        self.assertFalse(verify_bundle(bundle)["release_candidate"])
        with self.assertRaisesRegex(ExportError, "preview"):
            verify_bundle(bundle, require_release=True)

    def test_valid_synthetic_attestations_bind_to_files_and_ship_evidence(self):
        self.write_rights()
        report = preflight(self.content, require_licenses=True)
        self.assertTrue(report["passed"], report["errors"])
        self.assertTrue(report["rights_attestations_checked"])
        self.assertEqual(report["rights_evidence"], ["licenses/fixture-grant.txt"])
        bundle = self.root / "strict-preview"
        export_game(self.content, self.runtime, bundle, require_licenses=True)
        manifest = verify_bundle(bundle)
        self.assertTrue(manifest["rights_attestations_checked"])
        self.assertFalse(manifest["release_candidate"])  # R14 still unverified
        self.assertIn("game/licenses/fixture-grant.txt",
                      {f["path"] for f in manifest["files"]})
        with self.assertRaisesRegex(ExportError, "preview"):
            verify_bundle(bundle, require_release=True)
        proof = bundle / "game/licenses/fixture-grant.txt"
        proof.write_bytes(proof.read_bytes() + b"altered")
        with self.assertRaisesRegex(ExportError, "integrity"):
            verify_bundle(bundle)

    def test_release_requires_both_rights_and_r14(self):
        with self.assertRaisesRegex(ExportError, "rights and R14"):
            export_game(self.content, self.runtime, self.root / "bad-release",
                        release=True)
        self.write_rights()
        with self.assertRaisesRegex(ExportError, "rights and R14"):
            export_game(self.content, self.runtime, self.root / "no-r14",
                        release=True, require_licenses=True)
        self.assertFalse((self.root / "bad-release").exists())

    def test_legacy_plain_strings_cannot_grant_redistribution(self):
        path = self.project / "asset-licenses.json"
        path.write_text(json.dumps({p: "CC-BY" for p in self.assets}),
                        encoding="utf-8")
        self.assertFalse(preflight(self.content, require_licenses=True)["passed"])
        self.assertTrue(preflight(self.content)["passed"])

    def test_pending_rights_missing_evidence_and_stale_digest_fail(self):
        base = self.valid_rights()
        first = self.assets[0]
        for change, fragment in (
            ({"status": "pending"}, "Pending"),
            ({"allow_redistribution": False}, "Pending"),
            ({"allow_modification": False}, "Pending"),
            ({"sha256": "0" * 64}, "SHA-256"),
            ({"evidence_path": "licenses/not-found.txt"}, "evidence"),
            ({"evidence_path": "../escape.txt"}, "evidence"),
        ):
            with self.subTest(change=change):
                copy = deepcopy(base)
                copy[first].update(change)
                self.write_rights(copy)
                result = preflight(self.content, require_licenses=True)
                self.assertFalse(result["passed"], change)
                self.assertTrue(any(fragment.lower() in msg.lower()
                                    for msg in result["errors"]), result["errors"])

    def test_unknown_and_case_colliding_rights_are_rejected(self):
        base = self.valid_rights()
        base["licenses/unknown.png"] = deepcopy(next(iter(base.values())))
        self.write_rights(base)
        self.assertFalse(preflight(self.content, require_licenses=True)["passed"])
        base = self.valid_rights()
        rel = self.assets[0]
        base[rel.upper()] = deepcopy(base[rel])
        self.write_rights(base)
        strict = preflight(self.content, require_licenses=True)
        self.assertFalse(strict["passed"])
        self.assertTrue(any("Duplicate" in e for e in strict["errors"]))

    def test_rights_index_is_hashed_into_export_manifest(self):
        self.write_rights()
        bundle = self.root / "hashed"
        export_game(self.content, self.runtime, bundle, require_licenses=True)
        index = bundle / "game/asset-licenses.json"
        index.write_bytes(index.read_bytes() + b" ")
        with self.assertRaisesRegex(ExportError, "integrity"):
            verify_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
