"""R1.D integration: migration, replay, Player persistence and public SDK."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject, GameSession
from drawtemp.player.controller import PlayerController
from drawtemp.sdk import (
    SDK_API_VERSION, SDK_API_STATUS, AuthoringSession, MigrationError,
    ReplayCommand, ReplayError, PlayerSlotStore, Simulation, SlotError,
    capabilities, preview_documents, preview_pair, commit_pair,
    verify_recording, verify_sequence,
)
from drawtemp.sdk.reference import MISSION, reference_project


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def source(self, root):
        source = Path(root) / "legacy.json"
        data = self.content.to_dict()
        project = self.project.to_dict()
        data.pop("version")
        project["version"] = 0
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        source.with_suffix(".game.json").write_text(
            json.dumps(project, ensure_ascii=False), encoding="utf-8")
        return source

    def test_preview_and_explicit_export_preserve_original_bytes(self):
        with TemporaryDirectory() as root:
            source = self.source(root)
            original = (source.read_bytes(), source.with_suffix(".game.json").read_bytes())
            plan = preview_pair(source)
            self.assertEqual(plan.content_version, 0)
            self.assertEqual(plan.project_version, 0)
            self.assertEqual(len(plan.changes), 2)
            with self.assertRaises(TypeError):
                plan.content["version"] = 9
            self.assertEqual((source.read_bytes(), source.with_suffix(".game.json").read_bytes()),
                             original)
            target = Path(root) / "imported.json"
            paths = commit_pair(plan, target)
            self.assertTrue(all(path.exists() for path in paths))
            self.assertEqual((source.read_bytes(), source.with_suffix(".game.json").read_bytes()),
                             original)
            authoring = AuthoringSession.open(target)
            imported = authoring.snapshot().to_dict()
            c = Content.from_dict(imported["content"])
            p = GameProject.from_dict(imported["project"], c)
            sim = Simulation.new(c, p, "main", seed=17)
            sim.choose_story_option("enter")
            sim.start_mission(MISSION)
            sim.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
            self.assertEqual(sim.simulate(max_steps=700).battle["result"], "victory")
            with self.assertRaises(MigrationError) as error:
                commit_pair(plan, target)
            self.assertEqual(error.exception.code, "publish_failed")

    def test_stale_preview_blocks_output_and_preserves_source(self):
        with TemporaryDirectory() as root:
            source = self.source(root)
            plan = preview_pair(source)
            source.write_bytes(source.read_bytes() + b" ")
            target = Path(root) / "new.json"
            with self.assertRaises(MigrationError) as error:
                commit_pair(plan, target)
            self.assertEqual(error.exception.code, "stale_preview")
            self.assertFalse(target.exists())

    def test_invalid_future_and_malformed_legacy_fail_closed(self):
        data, project = self.content.to_dict(), self.project.to_dict()
        data["version"] = 2
        with self.assertRaises(MigrationError) as error:
            preview_documents(data, project)
        self.assertEqual(error.exception.code, "unsupported_version")
        data["version"] = 0
        data["missions"] = []
        with self.assertRaises(MigrationError):
            preview_documents(data, project)
        self.assertEqual(self.content.to_dict()["version"], 1)

    def test_same_source_destination_and_bad_extensions_rejected(self):
        with TemporaryDirectory() as root:
            source = self.source(root)
            plan = preview_pair(source)
            with self.assertRaises(MigrationError):
                commit_pair(plan, source)
            with self.assertRaises(MigrationError):
                commit_pair(plan, Path(root) / "wrong.game.json")
            self.assertTrue(source.is_file())


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_jeanne_trace_verifies_every_stage_and_does_not_touch_input(self):
        steps = (
            ReplayCommand("choose_story_option", ("enter",)),
            ReplayCommand("start_mission", (MISSION,)),
            ReplayCommand("execute", ({"kind": "interact", "unit": "jeanne",
                                       "object": "lever"},)),
            ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
        )
        original = deepcopy(steps[2].args[0])
        report = verify_sequence(self.content, self.project, "main", steps)
        self.assertTrue(report.verified)
        self.assertEqual(len(report.checkpoints), len(steps) + 1)
        self.assertEqual(report.checkpoints[0].mode, "campaign")
        self.assertEqual(report.checkpoints[-1].mode, "battle")
        self.assertEqual(report.final_digest, report.checkpoints[-1].session_digest)
        self.assertEqual(original, steps[2].args[0])

    def test_checkpoint_corruption_is_rejected_even_with_valid_envelope(self):
        session = GameSession.new(self.content, self.project, "main")
        recorded = session.recording()
        verified = verify_recording(recorded, self.content, self.project)
        self.assertEqual(verified.recording(), recorded)
        changed = deepcopy(recorded)
        changed["progress"]["gold"] = 999999
        with self.assertRaises(ReplayError) as error:
            verify_recording(changed, self.content, self.project)
        self.assertEqual(error.exception.code, "invalid_recording")
        self.assertEqual(recorded["progress"]["gold"], session.progress.gold)

    def test_multifront_journal_with_focus_and_doctrine(self):
        root = Path(__file__).resolve().parents[1] / "sporebound" / "content"
        content = Content.load(root / "core.json")
        project = GameProject.load(root / "core.game.json", content)
        seed_session = GameSession.new(content, project, "main", seed=17)
        seed_session.progress.unlocked.append("hold")
        starting = seed_session.recording()
        report = verify_sequence(
            content, project, "main", (
                ReplayCommand("start_fronts", (
                    {"garden": "garden", "defense": "hold"}, "garden"), {
                    "specs": {"garden": {"strength": 8, "opposition": 8},
                              "defense": {"strength": 9, "opposition": 11,
                                          "doctrine": "assault"}},
                }),
                ReplayCommand("set_doctrine", ("defense", "assault")),
                ReplayCommand("advance_fronts"),
                ReplayCommand("switch_front", ("defense",)),
                ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
            ), initial=starting, seed=17)
        self.assertTrue(report.verified)
        self.assertEqual(len(report.checkpoints), 6)
        self.assertTrue(all(step.mode == "fronts" for step in report.checkpoints[1:]))
        self.assertTrue(all(step.tactical_digest for step in report.checkpoints[1:]))

    def test_operation_allowlist_and_budget(self):
        with self.assertRaises(ReplayError) as error:
            verify_sequence(self.content, self.project, "main",
                            (ReplayCommand("__class__"),))
        self.assertEqual(error.exception.code, "invalid_command")
        with self.assertRaises(ReplayError):
            verify_sequence(self.content, self.project, "main",
                            (ReplayCommand("start_mission", (MISSION,)),),
                            max_commands=0)


class PlayerSlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.content, self.project = reference_project()
        self.controller = PlayerController(self.content, self.project, "main",
                                           self.tmp.name)

    def test_verified_backup_and_explicit_restore_of_corrupt_slot(self):
        self.controller.new_game()
        self.controller.save(1)
        self.controller.choose("enter")
        self.controller.save(1)
        primary = Path(self.tmp.name) / "slot_1.json"
        backup = primary.with_suffix(".json.bak")
        self.assertEqual(self.controller.inspect_slot(1).primary, "valid")
        self.assertTrue(self.controller.inspect_slot(1).recoverable)
        self.assertNotEqual(primary.read_bytes(), backup.read_bytes())
        damaged = b'{"broken":'
        primary.write_bytes(damaged)
        self.assertEqual(self.controller.inspect_slot(1).primary, "invalid")
        before = self.controller.session.recording()
        with self.assertRaises(Exception):
            self.controller.load(1)
        self.assertEqual(self.controller.session.recording(), before)
        with self.assertRaises(Exception):
            self.controller.save(1)  # bad primary must NOT be rotated to backup
        self.assertNotEqual(backup.read_bytes(), damaged)
        self.controller.restore_backup(1)
        self.assertEqual(primary.read_bytes(), backup.read_bytes())
        self.assertEqual(primary.with_suffix(".json.damaged").read_bytes(), damaged)
        self.assertEqual(self.controller.state()["screen"], "dialogue")

    def test_save_load_and_recovery_keep_game_session_v1_layout(self):
        self.controller.new_game()
        self.controller.save(1)
        raw = json.loads((Path(self.tmp.name) / "slot_1.json").read_text())
        self.assertEqual(raw["kind"], "game_session")
        self.assertEqual(raw["version"], 1)
        self.assertEqual(raw["digest"], self.controller.session.recording()["digest"])
        self.controller.choose("enter")
        self.controller.load(1)
        self.assertEqual(self.controller.state()["screen"], "dialogue")

    def test_foreign_campaign_or_symlink_cannot_overwrite_slot(self):
        self.controller.new_game()
        with TemporaryDirectory() as other:
            target = Path(other) / "slot_1.json"
            store = PlayerSlotStore(target, self.content, self.project,
                                    campaign_id="not-the-campaign")
            with self.assertRaises(SlotError) as error:
                store.save(self.controller.session)
            self.assertEqual(error.exception.code, "wrong_campaign")
            if sys.platform != "win32":
                target.symlink_to(Path(other) / "missing.json")
                with self.assertRaises(SlotError) as error:
                    PlayerSlotStore(target, self.content, self.project,
                                    campaign_id="main").save(self.controller.session)
                self.assertEqual(error.exception.code, "unsafe_path")


class PublicAPITests(unittest.TestCase):
    def test_capabilities_version_and_lazy_imports(self):
        self.assertEqual(SDK_API_VERSION[0], 1)
        self.assertEqual(SDK_API_STATUS, "provisional")
        self.assertEqual(capabilities()["game_session_schema"], 1)
        self.assertEqual(capabilities()["content_schema"], 1)
        self.assertIn("replay.v1", capabilities()["features"])

    def test_public_sdk_is_headless_without_qt_or_tk(self):
        program = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "_tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from drawtemp.sdk import Simulation, AuthoringSession, PlayerSlotStore, preview_pair
from drawtemp.sdk import verify_sequence, capabilities
assert capabilities()["api_version"] == [1, 0]
"""
        subprocess.run([sys.executable, "-c", program], check=True,
                       capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
