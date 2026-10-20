"""R36.C2 export-preflight provenance tests, exercising canonical R15 rights."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import preflight
from drawtemp.quality.r36_release import audit_r36_rights
from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
from tests_standalone.test_r36_animation_graph import authored, graph
from tests_standalone.test_drawtemp5_r4_assets import rgba_png


def project_with_graph():
    session = authored()
    editor = AnimationControllerAuthoring(session)
    editor.apply(editor.preview(graph()))
    return session.snapshot().to_dict()


def fixture(root):
    """Write a real R1-valid Content+GameProject pair and three physical PNGs."""
    root = Path(root)
    snapshot = project_with_graph()
    contents = snapshot["content"]
    project = snapshot["project"]
    content_path = root / "game.json"
    content_path.write_text(json.dumps(contents), encoding="utf-8")
    game_path = root / "game.game.json"
    game_path.write_text(json.dumps(project), encoding="utf-8")
    folder = root / "art"
    folder.mkdir()
    for asset in ("s_idle", "s_attack", "s_hit"):
        (folder / (asset + ".png")).write_bytes(rgba_png(16, 32))
    return content_path, project


def approve_assets(root):
    root = Path(root)
    (root / "licenses").mkdir()
    (root / "licenses/rights.txt").write_text(
        "Fixture artist confirms licensed modification and redistribution.",
        encoding="utf-8")
    rights = {}
    for asset in ("s_idle", "s_attack", "s_hit"):
        relative = "art/" + asset + ".png"
        digest = sha256((root / relative).read_bytes()).hexdigest()
        rights[relative] = {
            "status": "approved", "rights_holder": "R36 test fixture",
            "license_id": "CC0-1.0", "evidence_path": "licenses/rights.txt",
            "sha256": digest, "allow_modification": True,
            "allow_redistribution": True,
        }
    (root / "asset-licenses.json").write_text(
        json.dumps({"schema": 1, "assets": rights}), encoding="utf-8")


class R36ReleaseRightsTests(unittest.TestCase):
    def test_existing_preview_unchanged_but_release_fails_without_evidence(self):
        with TemporaryDirectory() as directory:
            path, project = fixture(directory)
            report = audit_r36_rights(project, directory)
            self.assertTrue(report["enabled"])
            self.assertEqual(report["sprites"], ["s_attack", "s_hit", "s_idle"])
            self.assertEqual(len(report["files"]), 3)
            self.assertTrue(report["warnings"])
            self.assertFalse(report["release_ready"])
            self.assertTrue(preflight(path)["passed"])
            strict = preflight(path, require_licenses=True)
            self.assertFalse(strict["passed"])
            self.assertFalse(strict["r36_animation"]["release_ready"])

    def test_strict_release_checks_real_r15_attestations_and_sha256(self):
        with TemporaryDirectory() as directory:
            path, project = fixture(directory)
            approve_assets(directory)
            result = preflight(path, require_licenses=True)
            self.assertTrue(result["passed"], result["errors"])
            self.assertTrue(result["rights_attestations_checked"])
            self.assertTrue(result["r36_animation"]["release_ready"])
            self.assertTrue(result["r36_animation"]["rights_attestations_checked"])
            self.assertEqual(len(result["r36_animation"]["files"]), 3)
            original = (Path(directory) / "art/s_hit.png")
            original.write_bytes(rgba_png(18, 32))
            broken = preflight(path, require_licenses=True)
            self.assertFalse(broken["passed"])
            self.assertIn("SHA-256", str(broken["errors"]))

    def test_r4_atlas_annotation_source_hash_must_match_png(self):
        with TemporaryDirectory() as directory:
            path, project = fixture(directory)
            approve_assets(directory)
            first = next(x for x in project["assets"]["entries"]
                         if x["id"] == "s_idle")
            first["region"] = [0, 0, 16, 32]
            (Path(directory) / "game.game.json").write_text(
                json.dumps(project), encoding="utf-8")
            annotation = {
                "pivot": [8, 30], "footprint": [1, 1],
                "direction": "south", "pose": "idle",
                "license": "CC0-1.0",
                "source_sha256": "0" * 64,
            }
            folder = Path(directory) / ".drawtemp"
            folder.mkdir()
            (folder / "r4-annotations.json").write_text(json.dumps({
                "version": 1, "sprites": {"s_idle": annotation}
            }), encoding="utf-8")
            strict = preflight(path, require_licenses=True)
            self.assertFalse(strict["passed"])
            self.assertIn("R4 annotation source hash", str(strict["errors"]))
            annotation["source_sha256"] = sha256(
                (Path(directory) / "art/s_idle.png").read_bytes()).hexdigest()
            (folder / "r4-annotations.json").write_text(
                json.dumps({"version": 1, "sprites": {"s_idle": annotation}}),
                encoding="utf-8")
            self.assertTrue(preflight(path, require_licenses=True)["passed"])
            annotation["license"] = "CC-BY-4.0"
            (folder / "r4-annotations.json").write_text(
                json.dumps({"version": 1, "sprites": {"s_idle": annotation}}),
                encoding="utf-8")
            mismatch = preflight(path, require_licenses=True)
            self.assertFalse(mismatch["passed"])
            self.assertIn("license differs", str(mismatch["errors"]))
            annotation["license"] = "UNVERIFIED"
            (folder / "r4-annotations.json").write_text(
                json.dumps({"version": 1, "sprites": {"s_idle": annotation}}),
                encoding="utf-8")
            failed = preflight(path, require_licenses=True)
            self.assertFalse(failed["passed"])
            self.assertIn("unverified", str(failed["errors"]))

    def test_multiple_atlas_regions_are_hashed_as_one_physical_file(self):
        with TemporaryDirectory() as directory:
            _, project = fixture(directory)
            entries = project["assets"]["entries"]
            idle = next(row for row in entries if row["id"] == "s_idle")
            hit = next(row for row in entries if row["id"] == "s_hit")
            idle["region"] = [0, 0, 8, 32]
            hit["region"] = [8, 0, 8, 32]
            hit["path"] = idle["path"]
            result = audit_r36_rights(project, directory)
            self.assertEqual(len(result["files"]), 2)
            self.assertFalse(result["errors"])

    def test_legacy_projects_do_not_invent_r36_asset_requirements(self):
        with TemporaryDirectory() as directory:
            snapshot = project_with_graph()
            project = deepcopy(snapshot["project"])
            project["extensions"].pop("org.drawtemp.animation")
            result = audit_r36_rights(project, directory, require_licenses=True)
            self.assertFalse(result["enabled"])
            self.assertTrue(result["release_ready"])
            self.assertEqual(result["files"], [])


if __name__ == "__main__":
    unittest.main()
