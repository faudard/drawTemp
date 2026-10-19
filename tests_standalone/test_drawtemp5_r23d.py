"""R23.D test contracts and Linux real Debian package structure."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.quality.r23d_release import CHECKS, native_assessment
from scripts.r23d_native_installer import (
    InstallerError, build_deb, package_installer, sha256_file,
)

REV = "b" * 40


def success(platform):
    return {
        "schema": 1, "kind": "drawtemp-r23d-clean-install",
        "revision": REV, "platform": platform,
        "format": {"Windows": "inno-setup", "Linux": "deb",
                   "macOS": "dmg"}[platform],
        "installer_sha256": "a" * 64, "signed": False,
        "notarized": False, "runner": "hosted-ephemeral-offscreen",
        "checks": {key: "passed" for key in CHECKS},
    }


class R23DReleaseGateTests(unittest.TestCase):
    def matrix(self):
        return [success(osname) for osname in ("Linux", "Windows", "macOS")]

    def test_green_ci_installers_not_false_release_certificate(self):
        result = native_assessment(self.matrix(), revision=REV)
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["release_certified"])
        self.assertEqual(set(result["installer_matrix"]),
                         {"Linux", "Windows", "macOS"})
        self.assertEqual(result["gates"]["R23.1"]["status"], "partial")
        self.assertEqual(result["gates"]["R23.10"]["status"], "blocked")

    def test_missing_duplicate_mismatched_revision_and_false_signing(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            native_assessment(self.matrix()[:2], revision=REV)
        for key, replacement, expression in (
            ("platform", "Linux", "duplicate"),
            ("revision", "1" * 40, "mismatched"),
            ("signed", True, "cannot claim"),
            ("notarized", True, "cannot claim"),
            ("runner", "physical-clean-PC", "cannot claim"),
        ):
            matrix = self.matrix()
            matrix[2][key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(
                    ValueError, expression):
                native_assessment(matrix, revision=REV)

    def test_skipped_uninstall_or_studio_smoke_blocks(self):
        for key in CHECKS:
            matrix = self.matrix()
            matrix[1]["checks"][key] = "skipped"
            with self.subTest(check=key), self.assertRaisesRegex(
                    ValueError, "Incomplete native"):
                native_assessment(matrix, revision=REV)

    def test_optional_upstream_must_match_exact_commit(self):
        upstream = {
            "kind": "drawtemp-r23c-release-assessment", "revision": REV,
            "decision": "NO-GO", "certified": False,
            "platform_evidence": {"Linux": {}, "Windows": {}, "macOS": {}},
        }
        self.assertEqual(native_assessment(
            self.matrix(), revision=REV, r23c=upstream)["r23c"], "linked-same-sha")
        broken = dict(upstream, revision="f" * 40)
        with self.assertRaisesRegex(ValueError, "R23.C"):
            native_assessment(self.matrix(), revision=REV, r23c=broken)

    def test_output_not_overwritten_and_digest_is_attached(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            output = Path(folder) / "DrawTempStudio-5.5-preview-Windows.exe"
            with patch("scripts.r23d_native_installer.verify_portable",
                       return_value={"certification": "preview-NO-GO"}), patch(
                       "scripts.r23d_native_installer.build_windows",
                       side_effect=lambda a, b: b.write_bytes(b"installer fixture")):
                receipt = package_installer(source, output, revision=REV,
                                            platform="Windows")
                self.assertFalse(receipt["signed"])
                self.assertEqual(sha256_file(output), receipt["sha256"])
                self.assertEqual(output.with_name(output.name + ".sha256")
                                 .read_text().split()[0], receipt["sha256"])
                with self.assertRaisesRegex(InstallerError, "already exists"):
                    package_installer(source, output, revision=REV,
                                      platform="Windows")


@unittest.skipUnless(sys.platform == "linux" and shutil.which("dpkg-deb"),
                     "Debian packaging requires dpkg-deb on Linux")
class DebianArtifactTests(unittest.TestCase):
    def test_real_deb_contains_native_binaries_launchers_and_desktop(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "portable"
            for rel in ("Studio/DrawTempStudio", "Jeanne/Player/DrawTempPlayer"):
                executable = source / rel
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"fixture")
                executable.chmod(0o755)
            (source / "release.json").write_text('{"preview":true}\n')
            output = root / "preview.deb"
            build_deb(source, output, architecture="amd64")
            self.assertTrue(output.is_file())
            tree = subprocess.check_output(["dpkg-deb", "--contents", output],
                                           text=True)
            control = subprocess.check_output(["dpkg-deb", "--field", output],
                                              text=True)
            self.assertIn("opt/drawtemp-studio-preview/Jeanne/Player/DrawTempPlayer",
                          tree)
            self.assertIn("usr/bin/drawtemp-studio-preview", tree)
            self.assertIn("usr/share/applications/drawtemp-studio-preview.desktop",
                          tree)
            self.assertIn("Package: drawtemp-studio-preview", control)
            self.assertIn("Depends: libegl1, libopengl0", control)
            self.assertNotIn("home/", tree)


if __name__ == "__main__":
    unittest.main()
