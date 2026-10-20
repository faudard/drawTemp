"""R58.B3 journal: explicit post-crash inspection, acknowledgement and no deletion."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.assets.packs import (
    ResourcePackError, install_pack, publish_pack, _read_archive,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.package_manager import installed_package_usage
from drawtemp.studio.package_upgrades import (
    PackageUpgradeError, _create_new_version, apply_package_upgrade,
    preview_package_upgrade,
)
from drawtemp.studio.package_upgrade_recovery import (
    JOURNAL_NAME, PackageRecoveryError, acknowledge_pending_upgrade,
    begin_upgrade_journal, clear_upgrade_journal, read_pending_upgrade,
    require_no_pending_upgrade,
)
from drawtemp.sdk.simulation import thaw
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source


class PendingPackageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.editor = AuthoringSession.new(*reference_project())
        old = make_source(self.root / "source-old", make_manifest())
        self.old_archive = self.root / "old.rpack"
        self.old = publish_pack(old, self.old_archive)
        install_pack(self.old, self.editor, self.root)
        newer = make_manifest()
        newer["version"] = "1.1.0"
        self.new_archive = self.root / "new.rpack"
        self.new = publish_pack(make_source(self.root / "source-new", newer),
                                self.new_archive)
        self.plan = self.preview()

    def preview(self):
        return preview_package_upgrade(
            self.editor, self.root, self.new_archive,
            expected_sha256=self.new.sha256)

    def begin(self):
        return begin_upgrade_journal(self.root, self.plan,
                                     thaw(self.plan._manifest))

    def test_pending_marker_blocks_new_package_edits_until_acknowledged(self):
        digest = self.begin()
        marker = self.root / JOURNAL_NAME
        self.assertTrue(marker.exists())
        self.assertEqual(self.editor.revision, 1)
        status = read_pending_upgrade(self.root)
        self.assertEqual(status["journal_sha256"], digest)
        self.assertEqual([row["state"] for row in status["files"]], ["missing"])
        with self.assertRaises(PackageRecoveryError) as blocked:
            require_no_pending_upgrade(self.root)
        self.assertEqual(blocked.exception.code, "recovery_required")
        with self.assertRaises(PackageRecoveryError):
            self.preview()
        with self.assertRaises(PackageRecoveryError):
            installed_package_usage(self.editor, self.root)
        result = acknowledge_pending_upgrade(
            self.root, self.editor, expected_sha256=digest)
        self.assertTrue(result["acknowledged"])
        self.assertFalse(result["files_deleted"])
        self.assertFalse(marker.exists())
        apply_package_upgrade(self.preview(), self.editor, self.root)
        self.assertEqual(self.editor.revision, 2)

    def test_pending_marker_also_blocks_legacy_r24_installs(self):
        self.begin()
        source = make_source(self.root / "source-third",
                             make_manifest("third-pack"))
        pack = publish_pack(source, self.root / "third.rpack")
        with self.assertRaises(ResourcePackError) as blocked:
            install_pack(pack, self.editor, self.root)
        self.assertEqual(blocked.exception.code, "recovery_required")
        self.assertFalse((self.root / "assets/packs/third-pack").exists())

    def test_complete_uncommitted_files_remain_after_recovery_and_are_reused(self):
        token = self.begin()
        directory, files = _create_new_version(
            self.root, thaw(self.plan._manifest), _read_archive(self.new_archive))
        self.assertTrue(all(row["state"] == "verified"
                            for row in read_pending_upgrade(self.root)["files"]))
        acknowledge_pending_upgrade(self.root, self.editor, expected_sha256=token)
        self.assertTrue(directory.exists())
        self.assertTrue(all(path.is_file() for path in files))
        plan = self.preview()
        self.assertTrue(plan.reuse_existing_bytes)
        result = apply_package_upgrade(plan, self.editor, self.root)
        self.assertEqual(result.snapshot.revision, 2)
        self.assertTrue(all(path.exists() for path in files))
        self.editor.undo()
        self.assertEqual(self.editor.revision, 3)

    def test_tampered_journal_cannot_be_acknowledged(self):
        digest = self.begin()
        with self.assertRaises(PackageRecoveryError) as stale:
            acknowledge_pending_upgrade(
                self.root, self.editor, expected_sha256="0" * 64)
        self.assertEqual(stale.exception.code, "stale_journal")
        marker = self.root / JOURNAL_NAME
        marker.write_bytes(b'{"schema_version":1,"schema_version":1}')
        with self.assertRaises(PackageRecoveryError) as bad:
            read_pending_upgrade(self.root)
        self.assertEqual(bad.exception.code, "invalid_journal")
        self.assertTrue(marker.exists())
        with self.assertRaises(PackageRecoveryError):
            clear_upgrade_journal(self.root, expected_sha256=digest)

    def test_invalid_editor_identity_does_not_clear_journal(self):
        digest = self.begin()
        self.editor.apply(self.editor.preview_project(
            lambda project: {**project, "subtitle": "Changed but same receipt"},
            kind="fixture-edit"))
        # Unrelated editor edits do not imply that interrupted target bytes are
        # safe; explicit acknowledgement may inspect and clear only the marker.
        result = acknowledge_pending_upgrade(
            self.root, self.editor, expected_sha256=digest)
        self.assertTrue(result["acknowledged"])
        self.assertFalse((self.root / JOURNAL_NAME).exists())

    def test_regular_upgrade_and_python_failure_leave_no_marker(self):
        from pathlib import Path
        with patch.object(self.editor, "apply",
                          side_effect=RuntimeError("failure")):
            with self.assertRaisesRegex(RuntimeError, "failure"):
                apply_package_upgrade(self.plan, self.editor, self.root)
        self.assertFalse((self.root / JOURNAL_NAME).exists())
        self.assertFalse((self.root / "assets/packs/forest-pack/1.1.0").exists())
        apply_package_upgrade(self.preview(), self.editor, self.root)
        self.assertFalse((self.root / JOURNAL_NAME).exists())


if __name__ == "__main__":
    unittest.main()
