"""Synthetic git history proves R17 auditor distinguishes stacked merges."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.audit_r17_merge_ledger import PRSpec, audit, markdown


@unittest.skipUnless(shutil.which("git"), "git required")
class R17MergeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("branch", "-M", "master")
        self.git("config", "user.name", "R17 Test")
        self.git("config", "user.email", "r17@example.invalid")
        self.write("base.txt", "baseline\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        proc = subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        return proc.stdout.strip()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit(self, path, content):
        self.write(path, content)
        self.git("add", path)
        self.git("commit", "-qm", path)

    def test_direct_merge_is_proved_but_stacked_branch_merge_is_not(self):
        self.git("checkout", "-qb", "integrated")
        self.commit("feature/merged.py", "class Merged: pass\n")
        self.git("checkout", "-q", "master")
        self.git("merge", "--no-ff", "-qm", "merge integrated", "integrated")
        integrated_sha = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "stacked")
        self.commit("feature/unreleased.py", "class Unreleased: pass\n")
        stacked_sha = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "master")
        result = audit(self.root, "master", (
            PRSpec(10, "R7", integrated_sha, (
                ("feature/merged.py", "class Merged"),)),
            PRSpec(11, "R9", stacked_sha, (
                ("feature/unreleased.py", "class Unreleased"),)),
        ))
        self.assertEqual(result["rows"][0]["integration"], "ancestor-and-probes")
        self.assertEqual(result["rows"][1]["integration"], "not-an-ancestor")
        self.assertEqual(result["rows"][1]["missing_paths"],
                         ["feature/unreleased.py"])
        self.assertIn("#11", markdown(result))
        self.assertEqual(result["head"], integrated_sha)

    def test_present_file_is_not_proof_of_merged_commit(self):
        self.git("checkout", "-qb", "foreign")
        self.commit("feature/shared.py", "class Feature: pass\n")
        unrelated = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "master")
        # Same symbol, different *tree*: two commits made in the same second
        # with identical parent/message/file could otherwise have identical
        # Git object IDs, making "foreign" indistinguishable from master.
        self.commit("feature/shared.py", "class Feature: pass\n# independent implementation\n")
        report = audit(self.root, "master", (
            PRSpec(12, "R9", unrelated,
                   (("feature/shared.py", "class Feature"),)),))
        self.assertEqual(report["rows"][0]["integration"], "not-an-ancestor")
        self.assertEqual(report["rows"][0]["missing_paths"], [])

    def test_shallow_or_unreachable_commit_must_not_pass(self):
        self.commit("feature/present.py", "a = 1\n")
        report = audit(self.root, "master", (
            PRSpec(13, "R9", "f" * 40, (("feature/present.py", "a = 1"),)),
        ))
        self.assertEqual(report["rows"][0]["integration"], "history-unavailable")
        self.assertEqual(report["rows"][0]["ancestor_of_ref"], "unknown")

    def test_missing_symbol_is_not_false_green(self):
        self.commit("feature/exists.py", "def different(): pass\n")
        sha = self.git("rev-parse", "HEAD")
        report = audit(self.root, "master", (
            PRSpec(14, "R7", sha, (("feature/exists.py", "class Expected"),)),
        ))
        self.assertEqual(report["rows"][0]["integration"],
                         "ancestor-with-missing-probes")
        self.assertEqual(len(report["rows"][0]["missing_symbols"]), 1)


if __name__ == "__main__":
    unittest.main()
