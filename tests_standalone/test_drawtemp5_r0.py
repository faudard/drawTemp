"""Migration must detect real divergence and remain executable without UI imports."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.migration import run_gate
from drawtemp.sdk.session import SessionAdapter
from scripts.audit_drawtemp5 import inventory

ROOT = Path(__file__).resolve().parents[1]


class MigrationFoundationTests(unittest.TestCase):
    def test_reference_matches_frozen_baseline_and_is_repeatable(self):
        expected = json.loads((ROOT / 'docs/drawtemp5/reference-baseline.json').read_text())
        self.assertEqual(run_gate(), expected)
        self.assertEqual(run_gate(), expected)

    def test_harness_detects_adapter_regression(self):
        class BrokenAdapter(SessionAdapter):
            def execute(self, command):
                pass
        with self.assertRaisesRegex(AssertionError, 'lever'):
            run_gate(BrokenAdapter)

    def test_gate_rejects_a_valid_but_stale_candidate_save(self):
        # A self-consistent older checkpoint is more dangerous than broken JSON:
        # both readers can open it, but the lever/mission state has been lost.
        from drawtemp.core import GameSession
        from drawtemp.sdk.reference import reference_project

        class StaleSaveAdapter(SessionAdapter):
            def save(self, path):
                content, project = reference_project()
                return GameSession.new(content, project, "main", seed=17).save(path)

        with self.assertRaisesRegex(AssertionError, "candidate save differs"):
            run_gate(StaleSaveAdapter)

    def test_gate_rejects_corrupted_candidate_save(self):
        class CorruptSaveAdapter(SessionAdapter):
            def save(self, path):
                Path(path).write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(AssertionError, "candidate save cannot be loaded"):
            run_gate(CorruptSaveAdapter)

    def test_gate_rejects_broken_adapter_loader_even_for_legacy_save(self):
        from drawtemp.core import GameSession

        class StaleLoadAdapter(SessionAdapter):
            @classmethod
            def load(cls, path, content, project):
                return cls(GameSession.new(content, project, "main", seed=17))

        with self.assertRaisesRegex(AssertionError, "legacy save differs"):
            run_gate(StaleLoadAdapter)

    def test_cli_rejects_reference_drift_and_keeps_diagnostic_report(self):
        expected = json.loads((ROOT / "docs/drawtemp5/reference-baseline.json").read_text())
        expected["trace"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / "modified-baseline.json"
            report = Path(folder) / "observed.json"
            baseline.write_text(json.dumps(expected), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "drawtemp.sdk.migration",
                 "--verify-baseline", str(baseline), "--report", str(report)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("R0 frozen baseline mismatch", result.stderr)
            self.assertEqual(json.loads(report.read_text())["result"], "victory")
            self.assertNotEqual(json.loads(report.read_text()), expected)

    def test_snapshot_does_not_expose_mutable_session(self):
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
        adapter = SessionAdapter.new(content, project, 'main')
        first = adapter.snapshot()
        first['progress']['gold'] = 99999
        self.assertNotEqual(first, adapter.snapshot())

    def test_no_graphics_imports_at_runtime(self):
        code = '''
import sys
class BlockUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', '_tkinter', 'PySide6', 'PyQt6', 'PyQt5'):
            raise AssertionError('Forbidden UI dependency: ' + fullname)
sys.meta_path.insert(0, BlockUI())
from drawtemp.sdk.migration import run_gate
assert run_gate()['result'] == 'victory'
'''
        subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True,
                       capture_output=True, text=True)

    def test_transitive_audit_gate(self):
        self.assertEqual(inventory()['headless_violations'], [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'drawtemp/core').mkdir(parents=True)
            (root / 'drawtemp/core/__init__.py').write_text('from sporebound.bridge import run\n')
            (root / 'sporebound').mkdir()
            (root / 'sporebound/bridge.py').write_text('from . import gui\n')
            (root / 'sporebound/gui.py').write_text('import tkinter\n')
            self.assertTrue(inventory(root)['headless_violations'])


if __name__ == '__main__':
    unittest.main()
