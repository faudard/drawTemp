"""R49.A regression tests: command wiring, bounded metrics and honest gates."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.studio.r49_experience import (
    CORE_COMMANDS, OperationTimings, audit_command_bindings, measure_studio,
    resolve_shortcuts,
)
from drawtemp.studio.r18_navigation import WORKSPACES


class FakeAction:
    def __init__(self, text="Action"):
        self.label = text

    def text(self):
        return self.label

    def trigger(self):
        return None


class R49ContractsTests(unittest.TestCase):
    def test_shortcut_conflicts_keep_first_owner_and_do_not_mutate_settings(self):
        requested = {
            "save": "Ctrl+S",
            "playtest": " ctrl + s ",
            "palette": "Ctrl+Shift+P",
            "focus_resources": "",
        }
        before = requested.copy()
        effective, conflicts = resolve_shortcuts(requested)
        self.assertEqual(requested, before)
        self.assertEqual(effective["save"], "Ctrl+S")
        self.assertEqual(effective["playtest"], "")
        self.assertEqual(effective["palette"], "Ctrl+Shift+P")
        self.assertEqual(effective["focus_resources"], "")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((conflicts[0].key, conflicts[0].owner),
                         ("playtest", "save"))

    def test_shortcut_validation_is_fail_closed(self):
        for bad in ({None: "Ctrl+X"}, {"": "Ctrl+X"}, {"save": None}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                resolve_shortcuts(bad)

    def test_command_inventory_does_not_claim_execution_evidence(self):
        registered = {key: FakeAction() for key in CORE_COMMANDS}
        registered.update({"go_" + key: FakeAction() for key in WORKSPACES})
        audit = audit_command_bindings(registered, workspaces=WORKSPACES)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.registered, len(registered))
        self.assertNotIn("verified", audit.__dict__)
        registered["playtest"] = FakeAction(" ")
        del registered["go_maps"]
        registered["broken"] = object()
        audit = audit_command_bindings(registered, workspaces=WORKSPACES)
        self.assertFalse(audit.passed)
        problems = {(item.key, item.code) for item in audit.issues}
        self.assertIn(("playtest", "missing_label"), problems)
        self.assertIn(("go_maps", "missing"), problems)
        self.assertIn(("broken", "not_triggerable"), problems)

    def test_percentiles_nearest_rank_and_finite_bounded_history(self):
        timing = OperationTimings()
        for n in range(1, 101):
            timing.record("studio.refresh", n * 1_000_000)
        report = timing.summary()["studio.refresh"]
        self.assertEqual(report["count"], 100)
        self.assertEqual(report["p50_ms"], 50)
        self.assertEqual(report["p95_ms"], 95)
        self.assertEqual(report["p99_ms"], 99)
        self.assertEqual(report["max_ms"], 100)
        self.assertEqual(report["failures_observed"], 0)
        self.assertEqual(report["evidence"],
                         "local_process_observation_not_hardware_gate")
        for n in range(5):
            timing.record("studio.refresh", n * 1_000_000)
        small = OperationTimings(max_samples=2)
        small.record("studio.open", 1_000_000)
        small.record("studio.open", 2_000_000)
        small.record("studio.open", 3_000_000)
        self.assertEqual(small.summary()["studio.open"]["count"], 2)
        self.assertEqual(small.summary()["studio.open"]["p50_ms"], 2)

    def test_reject_unknown_operation_invalid_elapsed_and_failed_flag(self):
        timing = OperationTimings()
        for operation, elapsed in (("open /tmp/private", 12), ("studio.open", -1),
                                   ("studio.open", True), ("studio.open", 3.5)):
            with self.subTest(operation=operation, elapsed=elapsed):
                with self.assertRaises(ValueError):
                    timing.record(operation, elapsed)
        with self.assertRaises(ValueError):
            timing.record("studio.open", 0, failed=1)
        with self.assertRaises(ValueError):
            OperationTimings(max_samples=0)

    def test_timing_exception_is_not_swallowed_or_logged_with_sensitive_data(self):
        timing = OperationTimings()
        with self.assertRaisesRegex(RuntimeError, "private-file-name"):
            with timing.track("studio.open"):
                raise RuntimeError("private-file-name")
        summary = timing.summary()
        self.assertEqual(summary["studio.open"]["failures_observed"], 1)
        self.assertNotIn("private-file-name", str(summary))
        with self.assertRaises(ValueError):
            with timing.track("not.an.operation"):
                pass

    def test_decorator_preserves_method_return_value(self):
        class Example:
            def __init__(self):
                self.r49_timings = OperationTimings()

            @measure_studio("studio.navigate")
            def navigate(self, target):
                return target.upper()

        example = Example()
        self.assertEqual(example.navigate("maps"), "MAPS")
        self.assertEqual(example.r49_timings.summary()["studio.navigate"]["count"], 1)
        with self.assertRaises(ValueError):
            measure_studio("private-project-path")


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class R49StudioQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_studio_disables_colliding_persisted_shortcut_and_reports_metrics(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as temp:
            settings = QSettings(str(Path(temp) / "r49.ini"), QSettings.IniFormat)
            settings.setValue("shortcuts/playtest", "Ctrl+S")
            settings.sync()
            window = StudioWindow(settings=settings)
            self.addCleanup(window.deleteLater)
            self.assertTrue(window._r49_audit.passed, window._r49_audit.issues)
            self.assertEqual(window.commands["save"].shortcut().toString(),
                             "Ctrl+S")
            self.assertTrue(window.commands["playtest"].shortcut().isEmpty())
            self.assertTrue(window.commands["playtest"].isEnabled())
            messages = [window.problems.item(i).text()
                        for i in range(window.problems.count())]
            self.assertTrue(any("playtest" in text for text in messages))
            window.navigate("project")
            summary = window.r49_timings.summary()
            self.assertIn("studio.refresh", summary)
            self.assertIn("studio.navigate", summary)
            with patch("drawtemp.studio.qt_shell.QMessageBox.information") as show:
                window.open_r49_metrics()
                self.assertIn("localement", show.call_args.args[2])
            with patch.object(window, "_confirm_leave", return_value=True):
                window.close()


if __name__ == "__main__":
    unittest.main()
