"""R38.4 project preflight: bounded headless gates and Studio review."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_graph import preview_graph
from drawtemp.sdk.r38_preflight import inspect_project
from drawtemp.sdk.reference import reference_project


def pair():
    content, project = reference_project()
    return {"content": content.to_dict(), "project": project.to_dict()}


def graph(mid):
    return {"schema_version": 1, "id": "gate_intro", "mission_id": mid,
            "entry": "enter",
            "nodes": [
                {"id": "enter", "kind": "event",
                 "params": {"kind": "interact", "object_id": "gate"}},
                {"id": "message", "kind": "action",
                 "params": {"kind": "message", "text": "Open gate"}},
            ],
            "edges": [{"from": "enter", "out": "next",
                       "to": "message", "in": "flow"}]}


class PreflightTests(unittest.TestCase):
    def test_valid_unsaved_snapshot_read_only_and_repeatable(self):
        source = pair()
        before = deepcopy(source)
        first = inspect_project(source)
        second = inspect_project(source)
        self.assertEqual(first, second)
        self.assertEqual(before, source)
        self.assertEqual(first["kind"], "drawtemp-r38-creator-preflight")
        self.assertTrue(first["passed"], first["issues"])
        self.assertTrue(first["ready_for_preview"], first["issues"])
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertTrue(first["asset_integrity_verified"])
        self.assertFalse(first["release_certified"])
        self.assertGreater(first["counts"]["references_scanned"], 0)

    def test_canonical_broken_door_rejected(self):
        raw = pair()
        raw["content"]["missions"][0]["objects"] = [
            {"id": "lever", "kind": "switch", "pos": [2, 4],
             "link": "missing_gate"}]
        report = inspect_project(raw)
        self.assertFalse(report["passed"])
        self.assertFalse(report["ready_for_preview"])
        self.assertFalse(report["complete"])
        self.assertIn("canonical_invalid",
                      [entry["code"] for entry in report["issues"]])
        self.assertEqual(len(report["issues"]), len(report["errors"]))

    def test_graph_drift_fails_even_when_both_documents_validate(self):
        content, project = reference_project()
        mid = next(iter(content.missions))
        session = AuthoringSession.new(content, project)
        session.apply(preview_graph(session, graph(mid)))
        original = inspect_project(session.snapshot())
        self.assertTrue(original["passed"], original["issues"])
        self.assertEqual(original["counts"]["graphs"], 1)
        def edit_native(c, p):
            mission = next(row for row in c["missions"] if row["id"] == mid)
            row = next(x for x in mission["triggers"] if x["id"] == "r31_gate_intro")
            row["actions"][0]["text"] = "Changed by native editor"
            return c, p
        session.apply(session.preview_pair(edit_native))
        report = inspect_project(session.snapshot())
        self.assertFalse(report["passed"])
        self.assertIn("graph_native_drift", {row["code"] for row in report["issues"]})
        self.assertFalse(report["release_certified"])

    def test_graph_cycle_fail_closed_through_canonical_rules(self):
        raw = pair()
        mission = raw["content"]["missions"][0]
        mission["triggers"] = [
            {"id": "first", "condition": "tick", "value": 1, "after": ["second"],
             "actions": [{"kind": "message", "text": "a"}]},
            {"id": "second", "condition": "tick", "value": 1, "after": ["first"],
             "actions": [{"kind": "message", "text": "b"}]},
        ]
        report = inspect_project(raw)
        self.assertFalse(report["passed"])
        self.assertIn("canonical_invalid", {x["code"] for x in report["issues"]})
        self.assertTrue(any("cyclic" in msg.lower() for msg in report["errors"]))

    def test_missing_asset_and_missing_license_do_not_claim_ready(self):
        raw = pair()
        raw["project"]["assets"] = {
            "version": 1,
            "entries": [{"id": "portrait-jeanne", "kind": "portrait",
                         "path": "art/jeanne.png"}],
            "bindings": {},
        }
        source = deepcopy(raw)
        unchecked = inspect_project(raw)
        self.assertTrue(unchecked["passed"], unchecked["issues"])
        self.assertFalse(unchecked["ready_for_preview"])
        self.assertFalse(unchecked["asset_integrity_verified"])
        self.assertTrue(any(x["code"] == "asset_unchecked"
                            for x in unchecked["issues"]))
        strict_unchecked = inspect_project(raw, require_licenses=True)
        self.assertFalse(strict_unchecked["passed"])
        self.assertFalse(strict_unchecked["ready_for_preview"])
        with TemporaryDirectory() as folder:
            root = Path(folder)
            missing = inspect_project(raw, asset_root=root)
            self.assertFalse(missing["passed"])
            self.assertIn("asset_file", {x["code"] for x in missing["issues"]})
            png = root / "art" / "jeanne.png"
            png.parent.mkdir(parents=True)
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 24)
            nonstrict = inspect_project(raw, asset_root=root)
            self.assertTrue(nonstrict["passed"], nonstrict["issues"])
            self.assertTrue(nonstrict["ready_for_preview"])
            self.assertFalse(nonstrict["rights_verified"])
            strict = inspect_project(raw, asset_root=root, require_licenses=True)
            self.assertFalse(strict["passed"])
            self.assertFalse(strict["ready_for_preview"])
            self.assertIn("asset_rights_invalid", {x["code"] for x in strict["issues"]})
        self.assertEqual(raw, source)

    def test_license_attestation_is_evidence_only_not_release(self):
        raw = pair()
        raw["project"]["assets"] = {
            "version": 1,
            "entries": [{"id": "portrait-jeanne", "kind": "portrait",
                         "path": "art/jeanne.png"}],
            "bindings": {},
        }
        with TemporaryDirectory() as folder:
            root = Path(folder)
            asset = root / "art" / "jeanne.png"
            asset.parent.mkdir()
            asset.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 24)
            evidence = root / "licenses" / "grant.txt"
            evidence.parent.mkdir()
            evidence.write_text("TEST DATA. NOT AN ACTUAL LICENSE.\n", encoding="utf-8")
            (root / "asset-licenses.json").write_text(json.dumps({
                "schema": 1, "assets": {"art/jeanne.png": {
                    "status": "approved", "rights_holder": "Synthetic fixture",
                    "license_id": "TEST-ONLY", "evidence_path": "licenses/grant.txt",
                    "sha256": sha256(asset.read_bytes()).hexdigest(),
                    "allow_modification": True, "allow_redistribution": True,
                }}
            }), encoding="utf-8")
            report = inspect_project(raw, asset_root=root, require_licenses=True)
            self.assertTrue(report["passed"], report["issues"])
            self.assertTrue(report["rights_verified"])
            self.assertTrue(report["ready_for_preview"])
            self.assertFalse(report["release_certified"])

    def test_opaque_invalid_extensions_and_malformed_json_fail_closed(self):
        raw = pair()
        raw["project"]["extensions"]["org.unknown.schema"] = {
            "schema_version": 2, "data": {},
        }
        report = inspect_project(raw)
        self.assertFalse(report["passed"])
        self.assertIn("canonical_invalid", {i["code"] for i in report["issues"]})
        raw = pair()
        raw["project"]["title"] = float("nan")
        bad = inspect_project(raw)
        self.assertFalse(bad["passed"])
        self.assertFalse(bad["complete"])
        self.assertIn("invalid_json", {i["code"] for i in bad["issues"]})

    def test_diagnostic_budget_never_reports_clean_after_limit(self):
        raw = pair()
        # Valid access around the bound is a smoke check; hostile input must
        # fail canonical validation rather than overflow the inspection.
        raw["project"]["story"]["entry_scenes"]["main"] = "does_not_exist"
        report = inspect_project(raw)
        self.assertFalse(report["ready_for_preview"])

@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class PreflightQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_studio_panel_reports_without_mutation(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r38_preflight_qt import PreflightDialog
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        with TemporaryDirectory() as folder:
            owner = StudioWindow(session, settings=QSettings(
                str(Path(folder) / "studio.ini"), QSettings.IniFormat))
            self.assertIn("r38_preflight", owner.commands)
            before = session.snapshot().to_dict()
            dialog = PreflightDialog(owner)
            self.assertIsNotNone(dialog.report)
            self.assertTrue(dialog.report["passed"], dialog.report["issues"])
            self.assertEqual(session.snapshot().to_dict(), before)
            dialog.reject()
            owner.close()


if __name__ == "__main__":
    unittest.main()
