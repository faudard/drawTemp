"""R23.E: licensing is *not* approval; signatures are *not* self-certifying."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.export.r15 import export_game
from drawtemp.export.templates import create_template
from drawtemp.quality.r23e import (
    EvidenceError, asset_inventory, release_dossier,
    validate_external_evidence, verify_asset_inventory,
)
from scripts.r23e_verify_signature import (
    SignatureError, verify_linux, verify_macos, verify_windows,
)

REV = "a" * 40
PLATFORMS = ("Linux", "Windows", "macOS")


def rights(platform, *, declared=True):
    return {
        "schema": 1, "kind": "drawtemp-r23e-asset-inventory",
        "revision": REV, "platform": platform, "manifest_sha256": "c" * 64,
        "assets": [
            {"path": "game/assets/example.png", "sha256": "d" * 64,
             "license_declaration": "CC BY 4.0" if declared else None,
             "declaration_present": declared,
             "rights_holder_approved": "not-asserted",
             "attribution_approved": "not-asserted"},
        ],
        "license_warnings": [], "packaged_notices": declared,
        "evidence_kind": "machine-inventory-not-legal-approval",
        "legal_status": "blocked-pending-human-rights-review",
    }


def native():
    return {"kind": "drawtemp-r23d-assessment", "revision": REV,
            "decision": "NO-GO", "release_certified": False,
            "installer_matrix": {name: {} for name in PLATFORMS}}


class RightsReviewTests(unittest.TestCase):
    def test_real_blank_game_inventory_is_not_legal_approval(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = create_template("blank", base / "project")
            runtime = base / "runtime"
            runtime.mkdir()
            exe = runtime / ("DrawTempPlayer.exe" if os.name == "nt"
                             else "DrawTempPlayer")
            exe.write_bytes(b"native test fixture")
            exe.chmod(0o755)
            output = export_game(project / "game.json", runtime, base / "bundle")
            report = asset_inventory(output, revision=REV, platform="Linux")
            self.assertEqual(report["assets"], [])
            self.assertEqual(report["legal_status"],
                             "blocked-pending-human-rights-review")
            self.assertEqual(verify_asset_inventory(
                report, revision=REV, platform="Linux"), report)
            with self.assertRaisesRegex(EvidenceError, "mismatched"):
                verify_asset_inventory(report, revision=REV, platform="Windows")

    def test_inventory_rejects_license_claims_or_forged_legal_review(self):
        good = rights("Linux")
        self.assertEqual(verify_asset_inventory(
            good, revision=REV, platform="Linux"), good)
        cases = [
            {"legal_status": "approved"},
            {"evidence_kind": "signed-off"},
            {"manifest_sha256": "short"},
            {"assets": [dict(good["assets"][0], rights_holder_approved="yes")]},
            {"assets": [dict(good["assets"][0], declaration_present=False)]},
            {"assets": good["assets"] * 2},
        ]
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(EvidenceError):
                verify_asset_inventory(dict(good, **changed),
                                       revision=REV, platform="Linux")

    def test_complete_three_os_still_requires_legal_offline_human_signoff(self):
        result = release_dossier(revision=REV, r23d=native(),
                                 inventories=[rights(p) for p in PLATFORMS])
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["certified"])
        self.assertEqual(len(result["checks"]), 12)
        self.assertEqual(result["checks"]["R23.10"]["status"], "blocked")
        self.assertEqual(result["checks"]["R23.12"]["status"], "blocked")
        self.assertEqual(result["rights_matrix"]["Linux"]["asset_count"], 1)
        self.assertEqual(result["rights_matrix"]["Linux"]["missing_declarations"], 0)
        self.assertEqual(result["rights_matrix"]["Windows"]["rights_review"], "required")

    def test_missing_os_duplicate_os_and_different_revision_rejected(self):
        clean = [rights(p) for p in PLATFORMS]
        with self.assertRaisesRegex(EvidenceError, "Missing"):
            release_dossier(revision=REV, r23d=native(), inventories=clean[:-1])
        corrupt = deepcopy(clean)
        corrupt[2]["platform"] = "Windows"
        with self.assertRaisesRegex(EvidenceError, "Duplicate"):
            release_dossier(revision=REV, r23d=native(), inventories=corrupt)
        stale = deepcopy(clean)
        stale[2]["revision"] = "b" * 40
        with self.assertRaises(EvidenceError):
            release_dossier(revision=REV, r23d=native(), inventories=stale)
        with self.assertRaisesRegex(EvidenceError, "stale"):
            release_dossier(revision=REV, r23d=dict(native(), revision="b" * 40),
                            inventories=clean)

    def test_unreviewed_external_evidence_never_unblocks_release(self):
        item = {"kind": "offline_native_qa", "revision": REV, "platform": "Linux",
                "sha256": "e" * 64, "reference": "external QA case #4",
                "status": "submitted-unreviewed"}
        result = release_dossier(revision=REV, r23d=native(),
                                 inventories=[rights(p) for p in PLATFORMS],
                                 external=[item])
        self.assertEqual(result["external_submissions"], [item])
        self.assertEqual(result["checks"]["R23.1"]["status"], "partial")
        self.assertEqual(result["decision"], "NO-GO")
        for diff in ({"status": "approved"}, {"revision": "b" * 40},
                     {"sha256": "fake"}, {"platform": "Unknown"}):
            with self.subTest(diff=diff), self.assertRaises(EvidenceError):
                validate_external_evidence([dict(item, **diff)], revision=REV)
        with self.assertRaisesRegex(EvidenceError, "Duplicate"):
            validate_external_evidence([item, item], revision=REV)


class SignatureVerificationTests(unittest.TestCase):
    def test_invalid_publisher_or_wrong_os_cannot_validate(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "installer.exe"
            path.write_bytes(b"not-signed")
            digest = sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(SignatureError):
                verify_windows(path, expected_sha256=digest, revision=REV,
                               publisher_thumbprint="0" * 40)
            with self.assertRaises(SignatureError):
                verify_macos(path, expected_sha256=digest,
                             revision=REV, developer_team_id="TEAM123456")
            with self.assertRaises(SignatureError):
                verify_linux(path, path, path, expected_sha256=digest,
                             revision=REV, trusted_keyring_sha256=digest,
                             signing_key_fingerprint="a" * 40)

    @unittest.skipUnless(sys.platform == "linux", "Linux pinned-key unit test")
    def test_linux_signature_check_requires_pinned_key_and_real_gpgv_command(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            deb = root / "package.deb"
            keyring = root / "trusted.gpg"
            signature = root / "package.deb.asc"
            for path, blob in ((deb, b"deb"), (keyring, b"key"),
                               (signature, b"sig")):
                path.write_bytes(blob)
            digest = sha256(deb.read_bytes()).hexdigest()
            key_digest = sha256(keyring.read_bytes()).hexdigest()
            fpr = "a" * 40
            with self.assertRaisesRegex(SignatureError, "keyring"):
                verify_linux(deb, signature, keyring, expected_sha256=digest,
                             revision=REV, trusted_keyring_sha256="b" * 64,
                             signing_key_fingerprint=fpr)
            calls = []
            def simulated_shell(argv):
                calls.append(argv)
                if argv[0] == "gpg":
                    return "fpr:::::::::" + fpr + ":\n"
                return ""
            with patch("scripts.r23e_verify_signature._run",
                       side_effect=simulated_shell):
                report = verify_linux(
                    deb, signature, keyring, expected_sha256=digest,
                    revision=REV, trusted_keyring_sha256=key_digest,
                    signing_key_fingerprint=fpr)
            self.assertEqual([command[0] for command in calls],
                             ["gpg", "gpgv"])
            self.assertEqual(report["release_authorization"], "not-asserted")
            self.assertEqual(report["verification"], "os-trust-check-executed")
            self.assertEqual(report["manual_signoff"], "required")
            # The mocked command validates control flow only; it does NOT
            # certify any package or produce a real cryptographic signature.


if __name__ == "__main__":
    unittest.main()
