"""R51.C — export capabilities and fail-closed authored-UI rights.

Approved asset metadata in this suite is synthetic test evidence ONLY,
never a real redistribution license for the Jeanne art or a release GO.
"""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import ExportError, export_game, preflight, verify_bundle
from drawtemp.export.templates import create_template
from drawtemp.quality.r51_ui import ui_export_audit
from drawtemp.studio.r51_layout_draft import new_layout, edit_layout


class R51CExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = create_template("jeanne", self.root / "project")
        self.content = self.folder / "game.json"
        self.project_path = self.folder / "game.game.json"
        self.original = json.loads(self.project_path.read_text(encoding="utf-8"))
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        name = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (self.runtime / name).write_bytes(b"fixture binary, not a certified runtime")
        self.assets = preflight(self.content)["assets"]
        self.assertTrue(self.assets, "Rights gate fixture requires physical assets")

    def write_ui(self, layouts):
        project = deepcopy(self.original)
        project.setdefault("extensions", {})["org.drawtemp.ui"] = {
            "schema_version": 1, "data": {"version": 1, "layouts": layouts}}
        self.project_path.write_text(json.dumps(project, ensure_ascii=False),
                                     encoding="utf-8")
        return project

    def approve_synthetic_rights(self):
        folder = self.folder / "licenses"
        folder.mkdir(exist_ok=True)
        (folder / "fixture-grant.txt").write_text(
            "Synthetic provenance fixture, NOT A REAL LICENSE\n", encoding="utf-8")
        entries = {
            name: {
                "status": "approved", "rights_holder": "TEST-ONLY",
                "license_id": "TEST-ONLY",
                "evidence_path": "licenses/fixture-grant.txt",
                "sha256": sha256((self.folder / name).read_bytes()).hexdigest(),
                "allow_modification": True, "allow_redistribution": True,
            } for name in self.assets
        }
        (self.folder / "asset-licenses.json").write_text(
            json.dumps({"schema": 1, "assets": entries}), encoding="utf-8")

    def test_legacy_preview_export_still_accepts_warnings(self):
        result = preflight(self.content)
        self.assertTrue(result["passed"], result["errors"])
        self.assertNotIn("ui", result)
        self.assertTrue(result["warnings"])
        target = self.root / "legacy-preview"
        export_game(self.content, self.runtime, target)
        self.assertNotIn("ui", verify_bundle(target))

    def test_opt_in_ui_demands_rights_even_for_preview(self):
        self.write_ui({"menu": new_layout("MENU")})
        result = preflight(self.content)
        self.assertFalse(result["passed"])
        self.assertIn("ui", result)
        self.assertTrue(any("asset-licenses.json" in item
                            for item in result["errors"]))
        self.assertFalse(result["rights_attestations_checked"])
        with self.assertRaisesRegex(ExportError, "Pre-export"):
            export_game(self.content, self.runtime, self.root / "blocked")
        self.assertFalse((self.root / "blocked").exists())

    def test_supported_screens_strict_preview_bundle_is_attested(self):
        project = self.write_ui({
            "menu": new_layout("MENU"),
            "combat": new_layout("HUD_CT"),
        })
        audit = ui_export_audit(project)
        self.assertFalse(audit["errors"])
        self.assertEqual(len(audit["sha256"]), 64)
        self.approve_synthetic_rights()
        report = preflight(self.content)
        self.assertTrue(report["passed"], report["errors"])
        self.assertTrue(report["rights_attestations_checked"])
        self.assertEqual(audit, report["ui"])
        target = self.root / "ui-preview"
        export_game(self.content, self.runtime, target)
        verified = verify_bundle(target)
        self.assertEqual(verified["ui"]["sha256"], audit["sha256"])
        self.assertEqual(verified["ui"]["screens"], audit["screens"])
        self.assertTrue(verified["ui"]["strict_asset_rights"])
        self.assertFalse(verified["release_candidate"])
        with self.assertRaisesRegex(ExportError, "preview"):
            verify_bundle(target, require_release=True)

        manifest = target / "manifest.json"
        original = json.loads(manifest.read_text(encoding="utf-8"))
        for altered in (
            dict(original, ui=dict(original["ui"], sha256="0" * 64)),
            {key: val for key, val in original.items() if key != "ui"},
        ):
            manifest.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ExportError):
                verify_bundle(target)
        manifest.write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(verify_bundle(target)["ui"]["sha256"],
                         audit["sha256"])

    def test_unsupported_screens_are_no_go_even_with_license(self):
        for kind in ("DIALOGUE", "INVENTORY", "HUD_ACTION"):
            with self.subTest(kind=kind):
                self.write_ui({"unsupported": new_layout(kind)})
                result = preflight(self.content)
                self.assertFalse(result["passed"])
                self.assertTrue(any("Studio-preview only" in msg
                                    for msg in result["errors"]), result)
        self.approve_synthetic_rights()
        self.write_ui({"unsupported": new_layout("DIALOGUE")})
        strict = preflight(self.content)
        self.assertFalse(strict["passed"])
        self.assertFalse(strict["rights_attestations_checked"])
        self.assertTrue(any("Studio-preview only" in msg
                            for msg in strict["errors"]))

    def test_unimplemented_actions_and_title_bindings_block_export(self):
        layout = new_layout("MENU")
        layout["root"]["children"][0]["action"] = "combat.end_turn"
        self.write_ui({"menu": layout})
        audit = ui_export_audit(json.loads(self.project_path.read_text()))
        self.assertTrue(any("unsupported Player intent" in msg
                            for msg in audit["errors"]))
        self.assertTrue(any("lacks menu.new_game" in msg
                            for msg in audit["errors"]))
        layout = new_layout("MENU")
        layout["root"]["children"][0] = {
            "id": "main_action", "type": "text",
            "binding": {"path": "session.campaign_id", "type": "str"}}
        layout["focus_order"] = ["continue_action"]
        self.write_ui({"menu": layout})
        audit = ui_export_audit(json.loads(self.project_path.read_text()))
        self.assertTrue(any("GameSession bindings" in msg
                            for msg in audit["errors"]))

    def test_preview_bundle_rejects_pending_attestations(self):
        self.write_ui({"menu": new_layout("MENU")})
        self.approve_synthetic_rights()
        rights_path = self.folder / "asset-licenses.json"
        rights = json.loads(rights_path.read_text())
        rights["assets"][self.assets[0]]["status"] = "pending"
        rights_path.write_text(json.dumps(rights))
        report = preflight(self.content)
        self.assertFalse(report["passed"])
        self.assertTrue(any("Pending" in e for e in report["errors"]))
        with self.assertRaises(ExportError):
            export_game(self.content, self.runtime, self.root / "pending")
        self.assertFalse((self.root / "pending").exists())

    def test_ui_hash_independent_of_json_key_order(self):
        project = self.write_ui({"menu": new_layout("MENU")})
        audit1 = ui_export_audit(project)
        project["extensions"]["org.drawtemp.ui"]["data"]["layouts"] = {
            "menu": deepcopy(new_layout("MENU"))}
        audit2 = ui_export_audit(project)
        self.assertEqual(audit1["sha256"], audit2["sha256"])


if __name__ == "__main__":
    unittest.main()
