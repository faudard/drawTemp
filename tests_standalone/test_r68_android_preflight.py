"""R68.B2 only proves local preflight/staging contracts, not Android operation."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest
import zipfile

from drawtemp.quality import r68_android_preflight as r68

SHA = "a" * 40


class AndroidProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="r68b2-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "repo"
        self.root.mkdir()
        for relative in r68._REQUIRED_SOURCE:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# study stub\n", encoding="utf-8")
        (self.root / "drawtemp" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "sporebound" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "drawtemp" / "placeholder.png").write_bytes(b"artist rights not reviewed")

    def wheel(self, name):
        filename = f"{name}-6.8.3-6.8.3-cp311-cp311-android_aarch64.whl"
        path = self.home / filename
        with zipfile.ZipFile(path, "w") as out:
            out.writestr(f"{name}-6.8.3.dist-info/WHEEL",
                         "Wheel-Version: 1.0\nGenerator: r68-test\nRoot-Is-Purelib: false\nTag: cp311-cp311-android_aarch64\n")
            out.writestr(f"{name}/test.py", "# stub for metadata tests\n")
        return path, sha256(path.read_bytes()).hexdigest()

    def toolchain(self):
        sdk, ndk = self.home / "sdk", self.home / "ndk"
        for name in ("platforms/android-34/android.jar", "platform-tools/adb"):
            path = sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (sdk / "build-tools/35.0.0").mkdir(parents=True)
        ndk.mkdir()
        (ndk / "source.properties").write_text(
            "Pkg.Desc = Android NDK\nPkg.Revision = 26.1.10909125\n",
            encoding="utf-8")
        return sdk, ndk

    def supplied(self):
        pyside, ps_hash = self.wheel("PySide6")
        shiboken, sh_hash = self.wheel("shiboken6")
        sdk, ndk = self.toolchain()
        jdk = self.home / "jdk"
        (jdk / "bin").mkdir(parents=True)
        for name in ("java", "javac"):
            (jdk / "bin" / name).touch()
        (jdk / "release").write_text('JAVA_VERSION="17.0.13"\n', encoding="utf-8")
        return dict(pyside=pyside, shiboken=shiboken,
                    pyside_hash=ps_hash, shiboken_hash=sh_hash,
                    sdk=sdk, ndk=ndk, jdk=jdk, revision=SHA)

    def test_missing_toolchain_is_no_go(self):
        report = r68.inspect(self.root)
        self.assertTrue(report["blockers"])
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["candidate_stage_allowed"])
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["physical_device_verified"])

    def test_compatible_test_fixtures_only_allow_candidate_stage(self):
        with patch.object(r68.sys, "version_info", (3, 11, 9, "final", 0)):
            report = r68.inspect(self.root, **self.supplied())
        self.assertEqual(report["blockers"], [])
        self.assertTrue(report["candidate_stage_allowed"])
        self.assertFalse(report["build_success"])
        self.assertEqual(report["decision"], "NO-GO")
        self.assertEqual(report["evidence"]["android"]["ndk"], "26.1.10909125")

    def test_real_host_python_can_be_blocked(self):
        report = r68.inspect(self.root, **self.supplied())
        if r68.sys.version_info[:2] != (3, 11):
            self.assertIn("Python 3.11", " ".join(report["blockers"]))
        self.assertFalse(report["release_certified"])

    def test_wrong_wheel_abi_rejected(self):
        path, digest = self.wheel("PySide6")
        wrong = path.with_name(path.name.replace("cp311", "cp312"))
        path.rename(wrong)
        with self.assertRaisesRegex(r68.AndroidProbeError, "ABI"):
            r68._wheel(wrong, "PySide6", digest)

    def test_wrong_or_missing_digest_rejected(self):
        path, digest = self.wheel("PySide6")
        with self.assertRaises(r68.AndroidProbeError):
            r68._wheel(path, "PySide6", None)
        with self.assertRaisesRegex(r68.AndroidProbeError, "checksum"):
            r68._wheel(path, "PySide6", "0" * 64)
        self.assertEqual(r68._wheel(path, "PySide6", digest)["sha256"], digest)

    def test_wheel_archive_tag_mismatch_rejected(self):
        path, _ = self.wheel("shiboken6")
        with zipfile.ZipFile(path, "w") as out:
            out.writestr("shiboken6-6.8.3.dist-info/WHEEL",
                         "Wheel-Version: 1.0\nTag: cp312-cp312-android_aarch64\n")
        digest = sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(r68.AndroidProbeError, "metadata"):
            r68._wheel(path, "shiboken6", digest)

    def test_ndk_version_mismatch_rejected(self):
        sdk, ndk = self.toolchain()
        (ndk / "source.properties").write_text("Pkg.Revision = 28.2.13676358\n")
        with self.assertRaisesRegex(r68.AndroidProbeError, "NDK mismatch"):
            r68._android_install(sdk, ndk)

    def test_java_11_rejected(self):
        values = self.supplied()
        (values["jdk"] / "release").write_text('JAVA_VERSION="11.0.0"\n')
        with self.assertRaisesRegex(r68.AndroidProbeError, "JDK 17"):
            r68._jdk_install(values["jdk"])

    def test_absent_b1_files_rejected(self):
        (self.root / "drawtemp/player/r68_touch.py").unlink()
        with self.assertRaisesRegex(r68.AndroidProbeError, "R68.B1 prerequisites"):
            r68._source_inventory(self.root)

    def test_stage_is_new_outside_repo_and_drops_art(self):
        destination = self.home / "android-stage"
        report = r68.prepare_stage(self.root, destination, SHA)
        self.assertEqual(report["kind"], "drawtemp-r68-android-stage")
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["decision"], "NO-GO")
        self.assertTrue((destination / "main.py").is_file())
        self.assertFalse((destination / "drawtemp/placeholder.png").exists())
        launcher = (destination / "main.py").read_text()
        self.assertIn("QStandardPaths.AppDataLocation", launcher)
        self.assertIn("--touch-preview", launcher)
        for record in report["files"]:
            path = destination / record["path"]
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), record["sha256"])
        self.assertEqual(json.loads((destination / "r68-stage.json").read_text())["revision"], SHA)
        with self.assertRaisesRegex(r68.AndroidProbeError, "absent"):
            r68.prepare_stage(self.root, destination, SHA)

    def test_stage_inside_repo_is_rejected(self):
        with self.assertRaisesRegex(r68.AndroidProbeError, "outside"):
            r68.prepare_stage(self.root, self.root / "build" / "r68", SHA)
        self.assertFalse((self.root / "build").exists())

    def test_symlink_source_rejected(self):
        path = self.root / "drawtemp/player/hidden.json"
        try:
            path.symlink_to(self.root / "drawtemp/__init__.py")
        except (OSError, NotImplementedError):
            self.skipTest("No symlink permissions")
        with self.assertRaisesRegex(r68.AndroidProbeError, "Symlinks"):
            r68._source_inventory(self.root)

    def test_fails_closed_on_invalid_revision(self):
        with self.assertRaisesRegex(r68.AndroidProbeError, "exact"):
            r68.prepare_stage(self.root, self.home / "stage", "HEAD")
        with self.assertRaisesRegex(r68.AndroidProbeError, "Invalid source"):
            r68.inspect(self.root, revision="a" * 39)


if __name__ == "__main__":
    unittest.main()
