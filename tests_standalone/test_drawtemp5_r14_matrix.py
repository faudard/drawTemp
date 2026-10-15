"""R14 matrix must fail closed under stale, forged or truncated CI artifacts."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r14 import evidence_report
from drawtemp.quality.r14_matrix import (
    PINNED_QT, REQUIRED_PROBES, REQUIRED_RUNNERS, inspect_matrix,
)

SHA = "a" * 40


def source(directory, os_name, *, revision=SHA):
    folder = Path(directory) / os_name
    folder.mkdir(exist_ok=True)
    report = evidence_report({}, revision=revision)
    report["environment"].update(runner=os_name, python="3.12.7", qt=PINNED_QT)
    probes = {}
    for name in REQUIRED_PROBES:
        filename = name + ".log"
        (folder / filename).write_text("Ran 1 test in 0.001s\nOK\n", encoding="utf-8")
        probes[name] = {
            "status": "pass", "exit_code": 0,
            "command": ["python", "-m", "unittest", name], "log": filename,
        }
    report["probes"] = probes
    return folder / "r14-report.json", report


class MatrixCertificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sources = [source(self.temp.name, os_name) for os_name in REQUIRED_RUNNERS]

    def inspect(self, sources=None, **kwargs):
        return inspect_matrix(self.sources if sources is None else sources,
                              expected_revision=SHA, **kwargs)

    def test_valid_unique_three_host_evidence(self):
        reports, problems = self.inspect()
        self.assertEqual(set(reports), set(REQUIRED_RUNNERS))
        self.assertEqual(problems, [])

    def test_missing_or_duplicate_host_never_passes(self):
        self.assertTrue(self.inspect(self.sources[:-1])[1])
        self.assertTrue(self.inspect(self.sources + [self.sources[0]])[1])

    def test_mixed_revision_and_untrusted_revision_rejected(self):
        self.sources[1][1]["revision"] = "b" * 40
        self.assertTrue(any("same immutable commit" in p for p in self.inspect()[1]))
        self.sources[1][1]["revision"] = "local"
        self.assertTrue(any("immutable 40-digit" in p for p in self.inspect()[1]))

    def test_wrong_python_or_qt_cannot_certify(self):
        self.sources[0][1]["environment"]["qt"] = "not checked here"
        self.assertTrue(any("PySide6" in p for p in self.inspect()[1]))
        self.sources[0][1]["environment"]["qt"] = PINNED_QT
        self.sources[0][1]["environment"]["python"] = "3.11.0"
        self.assertTrue(any("Python" in p for p in self.inspect()[1]))

    def test_missing_log_and_skipped_probe_are_rejected(self):
        self.sources[0][1]["probes"]["qt"]["exit_code"] = 0
        self.sources[0][1]["probes"]["qt"]["status"] = "blocked"
        self.assertTrue(any("qt did not exit" in p for p in self.inspect()[1]))
        self.sources[0][1]["probes"]["qt"]["status"] = "pass"
        (self.sources[0][0].parent / "qt.log").unlink()
        self.assertTrue(any("missing/empty/unsafe log" in p for p in self.inspect()[1]))

    def test_unsafe_log_path_is_rejected(self):
        self.sources[0][1]["probes"]["qt"]["log"] = "../qt.log"
        self.assertTrue(any("unsafe log" in p for p in self.inspect()[1]))

    def test_invalid_schema_is_not_accepted(self):
        self.sources[0][1]["checks"] = {}
        self.assertTrue(any("invalid report" in p for p in self.inspect()[1]))


if __name__ == "__main__":
    unittest.main()
