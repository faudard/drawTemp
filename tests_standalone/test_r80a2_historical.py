"""R80.A2: executable historic R16 snapshots; no 12.0 release authorization."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.quality.r80_cross_revision import run_cross_revision
from drawtemp.quality.r80_historical import (
    HISTORICAL_COMMIT, PINNED, ROOT, SUPPORTED, HistoricalRegressionError,
    _git_blob, load_pinned_sources, main, run_historical_regressions,
)


class R80A2HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)

    def copy_sources(self):
        directory = self.scratch / "sporebound" / "content"
        directory.mkdir(parents=True)
        source = ROOT / "sporebound" / "content"
        for name in PINNED:
            shutil.copyfile(source / name, directory / name)
        return directory

    def test_real_r16_pins_and_read_only_snapshot(self):
        source = ROOT / "sporebound" / "content"
        originals = {name: (source / name).read_bytes() for name in PINNED}
        data = load_pinned_sources()
        self.assertEqual(set(data), set(PINNED))
        self.assertEqual(len(HISTORICAL_COMMIT), 40)
        self.assertEqual({name: _git_blob(raw) for name, (raw, _) in data},
                         PINNED)
        self.assertEqual(originals, {name: (source / name).read_bytes()
                                     for name in PINNED})
        self.assertEqual(data["core.json"][1]["version"], 1)
        self.assertEqual(data["jeanne.game.json"][1]["version"], 1)

    def test_complete_runtime_matrix(self):
        report = run_historical_regressions()
        self.assertEqual(report["result"], "passed")
        self.assertEqual(report["historical_commit"], HISTORICAL_COMMIT)
        self.assertEqual(report["checked"], list(SUPPORTED))
        self.assertEqual(report["session_format_migration"],
                         "game_session_v1 -> session_checkpoint_v2")
        self.assertEqual(report["jeanne_replay_checkpoints"], 5)
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["tag_allowed"])
        self.assertIn("No multi-mode runtime replay certification",
                      report["exclusions"])

    def test_corrupt_historical_bytes_block_before_runtime(self):
        directory = self.copy_sources()
        source = directory / "core.json"
        source.write_bytes(source.read_bytes() + b" ")
        with self.assertRaisesRegex(HistoricalRegressionError, "drift"):
            load_pinned_sources(self.scratch)
        with self.assertRaisesRegex(HistoricalRegressionError, "drift"):
            run_historical_regressions(source_root=self.scratch)

    def test_missing_historical_file_blocks(self):
        directory = self.copy_sources()
        (directory / "core.game.json").unlink()
        with self.assertRaisesRegex(HistoricalRegressionError, "Missing/linked"):
            load_pinned_sources(self.scratch)

    def test_symlink_historical_source_blocks(self):
        directory = self.copy_sources()
        source = directory / "core.json"
        target = directory / "core-copy.json"
        shutil.copyfile(source, target)
        source.unlink()
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported")
        with self.assertRaisesRegex(HistoricalRegressionError, "Missing/linked"):
            load_pinned_sources(self.scratch)

    def test_blob_identity_is_bound_to_payload_and_length(self):
        self.assertNotEqual(_git_blob(b"abc"), _git_blob(b"abc "))
        self.assertNotEqual(_git_blob(b"abc"), _git_blob(b"abd"))

    def test_fake_v11_history_is_not_counted(self):
        self.assertNotIn("multi_mode_replay", SUPPORTED)
        self.assertNotIn("long_session_fault_recovery", SUPPORTED)
        self.assertNotIn("sdk_abi_change_review", SUPPORTED)
        with patch.dict(PINNED, {"core.json": "0" * 40}):
            with self.assertRaisesRegex(HistoricalRegressionError, "drift"):
                load_pinned_sources()

    def test_cross_revision_refuses_unverified_checkout(self):
        fake = self.scratch / "fake-r16"
        fake.mkdir()
        with self.assertRaisesRegex(HistoricalRegressionError,
                                    "authenticate historical Git checkout"):
            run_cross_revision(fake)

    def test_cross_revision_refuses_symlink_directory(self):
        real = self.scratch / "real"
        real.mkdir()
        alias = self.scratch / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks unsupported")
        with self.assertRaisesRegex(HistoricalRegressionError, "real directory"):
            run_cross_revision(alias)

    def test_cli_produces_explicit_unreleased_report(self):
        output = self.scratch / "output" / "r80a2.json"
        self.assertEqual(main(["--report", str(output)]), 0)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["result"], "passed")
        self.assertFalse(result["tag_allowed"])
        self.assertEqual(len(result["pinned_sources"]), 2)


if __name__ == "__main__":
    unittest.main()
