"""R17.12 real authored Jeanne -> Player save/replay -> R15 export contract."""
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import ExportError, export_game, preflight, verify_bundle
from drawtemp.quality.r17_cross_workshop import (
    ASSET_ID, CINEMATIC_ID, EVENT_ID, MISSION, PAGE_ID, STORY_ID,
    author_project, inspect_export, verify_gameplay,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.events import EventStudio
from drawtemp.studio.rpg_database import DatabaseEditor
from sporebound.cinematics import triggered_tactical_cinematics


class R1712CrossWorkshopTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def new_project(self):
        evidence = author_project(self.root / "authored")
        content = Path(evidence["content_path"])
        self.assertTrue(content.is_file())
        self.assertTrue(content.with_suffix(".game.json").is_file())
        self.assertEqual(evidence["content_sha256"],
                         sha256(content.read_bytes()).hexdigest())
        return evidence, content

    def runtime_fixture(self):
        # Validates the R15 copying/manifest contract only; this is NOT
        # an executable Player. Native proof lives in separate-runner CI.
        runtime = self.root / "fake-native-for-hash-test"
        runtime.mkdir()
        executable = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (runtime / executable).write_bytes(b"test fixture: not a real executable")
        return runtime

    def test_all_workshops_share_one_authoring_revision_and_disk_documents(self):
        proof, content = self.new_project()
        editor = AuthoringSession.open(content)
        pair = editor.snapshot().to_dict()
        mission = next(row for row in pair["content"]["missions"]
                       if row["id"] == MISSION)
        self.assertGreaterEqual(proof["authoring_revision"], 10)
        self.assertEqual(mission["name"], "R17.12 — Le passage du château")
        self.assertIn(proof["house_id"], {row["id"] for row in mission["structures"]})
        self.assertTrue(any(row["structure_id"] == proof["house_id"] and
                            row["level"] == 1 for row in mission["interior_floors"]))
        self.assertEqual(pair["content"]["jobs"]["r8_lancier"]["name"], "Lancier")
        self.assertEqual(DatabaseEditor(editor).detail(
            "equipment", "r8_spear")["slot"], "weapon")
        self.assertEqual(pair["project"]["campaigns"][0]["name"],
                         "Le passage du château")
        self.assertEqual(pair["project"]["title"], "R17.12 — Jeanne E2E")
        self.assertTrue(any(row["id"] == EVENT_ID
                            for row in mission["triggers"]))
        self.assertEqual(EventStudio(editor).event_pages(
            MISSION, EVENT_ID)[1]["id"], PAGE_ID)
        self.assertIn(CINEMATIC_ID,
                      json.dumps(pair["project"]["cinematics"]))
        asset = pair["project"]["assets"]["entries"][0]
        self.assertEqual(asset["id"], ASSET_ID)
        physical = content.parent / proof["asset_path"]
        self.assertGreater(physical.stat().st_size, 24)
        self.assertEqual(physical.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(proof["asset_sha256"],
                         sha256(physical.read_bytes()).hexdigest())
        report = preflight(content)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["assets"], [proof["asset_path"]])
        self.assertTrue(any("license" in warning.lower()
                            for warning in report["warnings"]))
        self.assertFalse(editor.snapshot().dirty)

    def test_real_player_event_cinematic_and_save_replayed_across_restart(self):
        proof, content = self.new_project()
        playback = verify_gameplay(content, self.root / "saves")
        self.assertTrue(playback["replay_verified"])
        self.assertEqual(playback["trigger_count"], 1)
        self.assertEqual(playback["active_mission"], MISSION)
        from drawtemp.player.qt_app import build_controller
        fresh = build_controller(content_path=content,
                                 save_dir=self.root / "saves", campaign_id="main")
        fresh.load(1)
        battle = fresh.session._session.active_battle
        clips, _ = triggered_tactical_cinematics(fresh.project, battle)
        self.assertIn(CINEMATIC_ID, [clip["id"] for clip in clips])
        save = self.root / "saves" / "slot_1.json"
        self.assertEqual(sha256(save.read_bytes()).hexdigest(),
                         playback["save_sha256"])

    def test_export_includes_only_authored_documents_and_physical_assets(self):
        proof, content = self.new_project()
        assert verify_gameplay(content, self.root / "saves")
        before = (content.read_bytes(), content.with_suffix(".game.json").read_bytes())
        target = self.root / "exported"
        export_game(content, self.runtime_fixture(), target)
        result = inspect_export(content, target)
        self.assertFalse(result["release_certified"])
        self.assertEqual(result["asset_files"], [proof["asset_path"]])
        self.assertEqual(sha256((target / "game" / proof["asset_path"]).read_bytes()).hexdigest(),
                         proof["asset_sha256"])
        self.assertEqual((content.read_bytes(),
                          content.with_suffix(".game.json").read_bytes()), before)
        self.assertEqual(verify_bundle(target)["content"], "game/" + content.name)
        self.assertFalse((target / "game" / "asset-licenses.json").exists())

        published = target / "game" / proof["asset_path"]
        published.write_bytes(published.read_bytes() + b"R1712-tamper")
        with self.assertRaisesRegex(ExportError, "integrity"):
            verify_bundle(target)
        self.assertEqual(sha256((content.parent / proof["asset_path"]).read_bytes()).hexdigest(),
                         proof["asset_sha256"])

    def test_export_refuses_missing_asset_without_creating_bundle(self):
        proof, content = self.new_project()
        (content.parent / proof["asset_path"]).unlink()
        report = preflight(content)
        self.assertFalse(report["passed"])
        output = self.root / "refused"
        with self.assertRaisesRegex(ExportError, "Pre-export validation"):
            export_game(content, self.runtime_fixture(), output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
