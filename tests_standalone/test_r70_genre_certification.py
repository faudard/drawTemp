"""R70.A headless regression and release-report tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r70_genre_certification import (
    LEGACY_GENRES, NEW_GENRES, PLATFORMS, SEEDS,
    audit_seeded_replay, build_ledger, main, required_evidence,
)

REV = "a" * 40
DIGEST = "b" * 64


def trace(seed):
    value = sha256(str(seed).encode("utf-8")).hexdigest()
    return {"tick_digests": [value, DIGEST], "restored_digest": DIGEST,
            "peak_agents": 8, "world_cells": 1024}


class GenreCertificationTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "records").mkdir()
        (self.root / "artifacts").mkdir()

    def add(self, name="first", slot=None, revision=REV, outcome="passed"):
        slot = slot or required_evidence()[0]
        payload = (name + " evidence").encode("utf-8")
        (self.root / "artifacts" / (name + ".log")).write_bytes(payload)
        record = dict(zip(("requirement", "scope", "platform", "genre", "seed"), slot))
        record.update({"kind": "drawtemp-r70-evidence", "schema": 1,
                       "revision": revision, "outcome": outcome,
                       "artifact": "artifacts/" + name + ".log",
                       "sha256": sha256(payload).hexdigest()})
        (self.root / "records" / (name + ".json")).write_text(json.dumps(record), encoding="utf-8")
        return record

    def test_required_matrix_has_all_three_genres_and_platforms(self):
        matrix = set(required_evidence())
        self.assertEqual(len(matrix), len(required_evidence()))
        self.assertEqual({s[3] for s in matrix if s[1] == "seeded_replay"}, set(NEW_GENRES))
        self.assertEqual({s[4] for s in matrix if s[1] == "seeded_replay"}, set(SEEDS))
        self.assertEqual({s[3] for s in matrix if s[1] == "replay"}, set(LEGACY_GENRES))
        self.assertEqual({s[2] for s in matrix if s[1] == "physical_gpu"}, set(PLATFORMS))
        self.assertIn(("R60", "upstream_gate", "agnostic", "agnostic", -1), matrix)
        self.assertNotIn(("R67", "upstream_gate", "agnostic", "agnostic", -1), matrix)

    def test_empty_and_reported_claims_are_not_release_approval(self):
        empty = build_ledger(REV, self.root)
        self.assertEqual(empty["decision"], "NO-GO")
        self.assertFalse(empty["tag_allowed"])
        self.assertEqual(empty["reported_slots"], 0)
        self.assertEqual(len(empty["missing"]), empty["expected_slots"])
        self.add()
        reported = build_ledger(REV, self.root)
        self.assertEqual(reported["reported_slots"], 1)
        self.assertFalse(reported["release_certified"])
        self.assertEqual(reported["invalid"], [])

    def test_duplicate_wrong_commit_and_failed_claims(self):
        self.add()
        self.add("second")
        report = build_ledger(REV, self.root)
        self.assertEqual(report["reported_slots"], 1)
        self.assertIn("Duplicate evidence slot", report["invalid"][0]["reason"])
        (self.root / "records" / "second.json").unlink()
        self.add("second", slot=required_evidence()[1], revision="c" * 40)
        report = build_ledger(REV, self.root)
        self.assertIn("different commit", report["invalid"][0]["reason"])
        (self.root / "records" / "second.json").unlink()
        self.add("second", slot=required_evidence()[1], outcome="failed")
        self.assertTrue(any("failing evidence" in b for b in build_ledger(REV, self.root)["blockers"]))

    def test_tamper_unsafe_paths_and_duplicate_json_fields(self):
        record = self.add()
        path = self.root / "records" / "first.json"
        (self.root / "artifacts" / "first.log").write_text("tampered")
        self.assertIn("checksum mismatch", build_ledger(REV, self.root)["invalid"][0]["reason"])
        record["artifact"] = "artifacts/../secrets.log"
        path.write_text(json.dumps(record))
        self.assertIn("traversal", build_ledger(REV, self.root)["invalid"][0]["reason"])
        record["artifact"] = "artifacts/first.log"
        path.write_text(json.dumps(record)[:-1] + ', "schema": 1}')
        self.assertIn("Duplicate JSON object key", build_ledger(REV, self.root)["invalid"][0]["reason"])

    def test_bad_slot_types_and_revision_are_rejected(self):
        for revision in ("master", "A" * 40, "a" * 39):
            with self.subTest(revision=revision):
                with self.assertRaises(ValueError):
                    build_ledger(revision, self.root)
        row = self.add()
        row["seed"] = True
        (self.root / "records" / "first.json").write_text(json.dumps(row))
        self.assertIn("Unsupported evidence slot", build_ledger(REV, self.root)["invalid"][0]["reason"])

    def test_symlinked_artifact_and_record_blocked(self):
        self.add()
        path = self.root / "artifacts" / "first.log"
        target = self.root / "other.log"
        target.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        self.assertIn("Linked evidence", build_ledger(REV, self.root)["invalid"][0]["reason"])

    def test_deterministic_replay_and_budgets(self):
        result = audit_seeded_replay(trace, max_agents=12, max_world_cells=2000)
        self.assertEqual([x["seed"] for x in result["cases"]], list(SEEDS))
        self.assertFalse(result["release_certified"])
        with self.assertRaisesRegex(ValueError, "budget"):
            audit_seeded_replay(trace, max_agents=7, max_world_cells=2000)
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_seeded_replay(trace, seeds=[1, 1], max_agents=12, max_world_cells=2000)

    def test_restored_replay_or_second_run_divergence_blocks(self):
        def mismatched(seed):
            sample = trace(seed)
            sample["restored_digest"] = "0" * 64
            return sample
        with self.assertRaisesRegex(ValueError, "Disk-restored"):
            audit_seeded_replay(mismatched, max_agents=12, max_world_cells=2000)
        calls = []
        def divergent(seed):
            calls.append(seed)
            sample = trace(seed)
            if len(calls) == 2:
                sample["tick_digests"] = ["f" * 64, DIGEST]
            return sample
        with self.assertRaisesRegex(ValueError, "Non-deterministic"):
            audit_seeded_replay(divergent, max_agents=12, max_world_cells=2000)

    def test_cli_is_report_only(self):
        target = self.root / "out.json"
        args = ["--revision", REV, "--evidence-dir", str(self.root), "--output", str(target)]
        self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(target.read_text())["decision"], "NO-GO")
        self.assertEqual(main(args + ["--enforce"]), 1)


if __name__ == "__main__":
    unittest.main()
