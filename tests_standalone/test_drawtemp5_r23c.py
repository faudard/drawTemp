"""R23.C real portable preview packaging and hostile-archive regressions."""
from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
import unittest
import zipfile

from drawtemp.export.r15 import export_game
from drawtemp.export.r23c import (
    ReleaseError, install_preview, package_preview, remove_preview,
    verify_portable,
)
from drawtemp.export.templates import create_template

REV = "3" * 40


class PortableReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="r23c-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        project = create_template("blank", self.root / "source")
        game_runtime = self.root / "player-runtime"
        game_runtime.mkdir()
        player = game_runtime / ("DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer")
        player.write_bytes(b"Player fixture, not a real native binary")
        player.chmod(0o755)
        self.game = export_game(project / "game.json", game_runtime, self.root / "Jeanne")
        self.studio = self.root / "studio-runtime"
        self.studio.mkdir()
        self.studio_name = "DrawTempStudio.exe" if os.name == "nt" else "DrawTempStudio"
        exe = self.studio / self.studio_name
        exe.write_bytes(b"Studio fixture, not a real native binary")
        exe.chmod(0o755)
        (self.studio / "support.dat").write_bytes(b"Qt support fixture")

    def package(self, *, platform=None):
        platform = platform or ("Windows" if os.name == "nt" else "Linux")
        archive = self.root / ("portable.zip" if platform == "Windows" else "portable.tar.gz")
        result = package_preview(self.game, self.studio, archive,
                                 revision=REV, platform=platform)
        self.assertEqual(result["certification"], "preview-NO-GO")
        return archive, result

    def test_publish_install_verify_remove_preserves_historical_bundle(self):
        platform = "Windows" if os.name == "nt" else "Linux"
        archive, result = self.package(platform=platform)
        self.assertEqual(sha256(archive.read_bytes()).hexdigest(), result["sha256"])
        self.assertEqual((archive.with_name(archive.name + ".sha256")).read_text(
            encoding="ascii").strip(), result["sha256"] + "  " + archive.name)
        original = (self.game / "manifest.json").read_bytes()
        installed = self.root / "installed"
        install_preview(archive, installed, expected_sha256=result["sha256"],
                        revision=REV, platform=platform)
        release = verify_portable(installed, revision=REV, platform=platform)
        self.assertEqual(release["kind"], "drawtemp-r23c-portable-preview")
        self.assertEqual(release["certification"], "preview-NO-GO")
        self.assertTrue((installed / "Jeanne/game/game.game.json").is_file())
        self.assertTrue((installed / "Studio" / self.studio_name).is_file())
        self.assertEqual(original, (installed / "Jeanne/manifest.json").read_bytes())
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            install_preview(archive, installed, expected_sha256=result["sha256"])
        self.assertEqual(remove_preview(installed), installed)
        self.assertFalse(installed.exists())

    def test_archive_digest_is_mandatory_and_failure_does_not_create_install(self):
        archive, result = self.package()
        with self.assertRaisesRegex(ReleaseError, "SHA-256"):
            install_preview(archive, self.root / "install", expected_sha256="0" * 64)
        with self.assertRaisesRegex(ReleaseError, "SHA-256"):
            install_preview(archive, self.root / "install", expected_sha256="invalid")
        self.assertFalse((self.root / "install").exists())

    def test_wrong_revision_platform_and_missing_studio_fail_closed(self):
        archive, result = self.package()
        with self.assertRaisesRegex(ReleaseError, "revision"):
            install_preview(archive, self.root / "wrong", expected_sha256=result["sha256"],
                            revision="9" * 40)
        self.assertFalse((self.root / "wrong").exists())
        with self.assertRaisesRegex(ReleaseError, "platform"):
            install_preview(archive, self.root / "wrong", expected_sha256=result["sha256"],
                            platform="macOS")
        self.assertFalse((self.root / "wrong").exists())
        (self.studio / self.studio_name).unlink()
        with self.assertRaisesRegex(ReleaseError, "Studio native executable"):
            package_preview(self.game, self.studio, self.root / "missing.tar.gz",
                            platform="Linux", revision=REV)

    def test_installed_integrity_change_blocks_uninstall(self):
        archive, info = self.package()
        target = self.root / "install"
        install_preview(archive, target, expected_sha256=info["sha256"])
        (target / "Studio/support.dat").write_bytes(b"tampered")
        with self.assertRaisesRegex(ReleaseError, "integrity mismatch"):
            verify_portable(target)
        with self.assertRaises(ReleaseError):
            remove_preview(target)
        self.assertTrue(target.exists())

    def test_symlinked_studio_runtime_outside_project_is_rejected(self):
        rogue = self.root / "outside.txt"
        rogue.write_bytes(b"evil")
        link = self.studio / "rogue.txt"
        try:
            link.symlink_to(rogue)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("Host does not permit symbolic links: " + str(exc))
        with self.assertRaisesRegex(ReleaseError, "escapes runtime"):
            package_preview(self.game, self.studio, self.root / "outside.tar.gz",
                            platform="Linux", revision=REV)

    def test_tar_symlink_is_rejected_without_touching_destination(self):
        if os.name == "nt":
            self.skipTest("POSIX tar evil symlink case")
        archive = self.root / "evil.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("DrawTemp/escape")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../elsewhere"
            tf.addfile(info)
        with self.assertRaisesRegex(ReleaseError, "link or special"):
            install_preview(archive, self.root / "evil-install",
                            expected_sha256=sha256(archive.read_bytes()).hexdigest())
        self.assertFalse((self.root / "evil-install").exists())

    def test_tar_parent_traversal_and_duplicate_members_are_rejected(self):
        if os.name == "nt":
            self.skipTest("POSIX tar evil entries case")
        for names, message in (
            (["DrawTemp/../outside"], "Unsafe"),
            (["DrawTemp/one", "DrawTemp/one"], "Duplicate"),
        ):
            with self.subTest(names=names):
                archive = self.root / ("evil-" + str(len(names)) + ".tar.gz")
                with tarfile.open(archive, "w:gz") as tf:
                    for name in names:
                        payload = b"evil"
                        info = tarfile.TarInfo(name)
                        info.size = len(payload)
                        tf.addfile(info, io.BytesIO(payload))
                with self.assertRaisesRegex(ReleaseError, message):
                    install_preview(archive, self.root / "no-install",
                                    expected_sha256=sha256(archive.read_bytes()).hexdigest())
                self.assertFalse((self.root / "no-install").exists())

    def test_zip_traversal_and_duplicate_members_are_rejected(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as tf:
            tf.writestr("DrawTemp/../escape", b"evil")
        with self.assertRaisesRegex(ReleaseError, "Unsafe"):
            install_preview(archive, self.root / "no-install",
                            expected_sha256=sha256(archive.read_bytes()).hexdigest())
        self.assertFalse((self.root / "no-install").exists())

    def test_broken_install_symlink_is_never_overwritten(self):
        archive, report = self.package()
        target = self.root / "broken-link"
        try:
            target.symlink_to(self.root / "nothing", target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("Host does not permit symbolic links: " + str(exc))
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            install_preview(archive, target, expected_sha256=report["sha256"])
        self.assertTrue(target.is_symlink())

    def test_uninstall_is_scoped_to_verified_distribution(self):
        unsafe = self.root / "existing"
        unsafe.mkdir()
        (unsafe / "valuable.txt").write_text("keep")
        with self.assertRaises(ReleaseError):
            remove_preview(unsafe)
        self.assertEqual((unsafe / "valuable.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
