"""R1.E: deterministic replay, fault injection and SDK thread certification."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import threading
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.core import Content, GameProject, GameSession
from drawtemp.sdk import (
    AuthoringSession, PlayerSlotStore, ReplayCommand, SDK_FEATURES,
    Simulation, SdkWorkQueue, WorkQueueError,
    CertificationError, certify_trace,
)
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.game_session import digest
from sporebound.model import RuleError


def jeanne_trace():
    return (
        ReplayCommand("choose_story_option", ("enter",)),
        ReplayCommand("start_mission", (MISSION,)),
        ReplayCommand("execute", ({"kind": "interact", "unit": "jeanne",
                                   "object": "lever"},)),
        ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
    )


def hold_for_cancel(content, project):
    """This transform is intentionally external code, not UI state."""
    content["missions"][0]["name"] = "Updated from worker"
    return content, project


class CertificationTraceTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_multiple_seeds_have_equal_continuous_replay_and_disk_state(self):
        for seed in (1, 17, 221):
            with self.subTest(seed=seed):
                trace = jeanne_trace()
                original_command = deepcopy(trace[2].args[0])
                result = certify_trace(self.content, self.project, "main",
                                       trace, seed=seed)
                self.assertTrue(result.verified)
                self.assertEqual(result.seed, seed)
                self.assertEqual(len(result.steps), len(trace) + 1)
                self.assertEqual(result.steps[0].mode, "campaign")
                self.assertEqual(result.steps[-1].mode, "battle")
                self.assertEqual(result.steps[-1].session_sha256,
                                 result.final_sha256)
                self.assertEqual(len(result.steps[-1].rng_sha256), 64)
                self.assertEqual(len(result.steps[-1].ct_sha256), 64)
                self.assertEqual(len(result.steps[-1].events_sha256), 64)
                self.assertEqual(trace[2].args[0], original_command)

    def test_multifront_timeline_and_focus_survive_every_disk_resume(self):
        root = Path(__file__).resolve().parents[1] / "sporebound" / "content"
        content = Content.load(root / "core.json")
        project = GameProject.load(root / "core.game.json", content)
        session = GameSession.new(content, project, "main", seed=17)
        session.progress.unlocked.append("hold")
        initial = session.recording()
        commands = (
            ReplayCommand("start_fronts",
                          ({"garden": "garden", "defense": "hold"}, "garden"),
                          {"specs": {"garden": {"strength": 8, "opposition": 8},
                                     "defense": {"strength": 9, "opposition": 11,
                                                 "doctrine": "assault"}}}),
            ReplayCommand("set_doctrine", ("defense", "assault")),
            ReplayCommand("advance_fronts"),
            ReplayCommand("switch_front", ("defense",)),
            ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
        )
        before = deepcopy(initial)
        report = certify_trace(content, project, "main", commands, initial=initial)
        self.assertEqual(len(report.steps), 6)
        self.assertEqual(report.steps[-1].mode, "fronts")
        self.assertTrue(all(s.fronts_sha256 for s in report.steps[1:]))
        self.assertTrue(all(s.tactical_sha256 for s in report.steps[1:]))
        self.assertEqual(initial, before)

    def test_recomputed_outer_hash_does_not_hide_tampered_inner_replay(self):
        sim = Simulation.new(self.content, self.project, "main")
        sim.choose_story_option("enter")
        sim.start_mission(MISSION)
        sim.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
        valid = sim.recording()
        original = deepcopy(valid)
        tampered = deepcopy(valid)
        tampered["tactical"]["commands"][-1]["object"] = "gate"
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                       if k != "digest"})
        with self.assertRaises(CertificationError) as caught:
            certify_trace(self.content, self.project, "main", (),
                          initial=tampered)
        self.assertEqual(caught.exception.code, "invalid_start")
        self.assertEqual(valid, original)

    def test_budget_unknown_command_and_wrong_checkpoint_seed(self):
        with self.assertRaises(CertificationError) as bad:
            certify_trace(self.content, self.project, "main",
                          (ReplayCommand("__class__"),))
        self.assertEqual(bad.exception.code, "invalid_command")
        with self.assertRaises(CertificationError) as bad:
            certify_trace(self.content, self.project, "main",
                          jeanne_trace(), max_commands=3)
        self.assertEqual(bad.exception.code, "invalid_budget")
        start = GameSession.new(self.content, self.project, "main", seed=3)
        with self.assertRaises(CertificationError) as bad:
            certify_trace(self.content, self.project, "main", (),
                          initial=start.recording(), seed=17)
        self.assertEqual(bad.exception.code, "wrong_start")


class PlayerFailureTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "slot_1.json"
        self.store = PlayerSlotStore(self.path, self.content, self.project,
                                     campaign_id="main")
        self.sim = Simulation.new(self.content, self.project, "main")
        self.store.save(self.sim)
        self.sim.choose_story_option("enter")
        self.store.save(self.sim)
        self.assertTrue(self.store.backup.exists())

    def test_backup_write_failure_preserves_last_two_generations(self):
        before_primary = self.path.read_bytes()
        before_backup = self.store.backup.read_bytes()
        self.sim.start_mission(MISSION)
        with patch("drawtemp.sdk.slots.write_bytes",
                   side_effect=OSError("injected backup I/O fault")):
            with self.assertRaises(OSError):
                self.store.save(self.sim)
        self.assertEqual(self.path.read_bytes(), before_primary)
        self.assertEqual(self.store.backup.read_bytes(), before_backup)
        self.assertEqual(self.store.inspect().primary, "valid")
        self.assertEqual(self.store.inspect().backup, "valid")
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_unverified_save_and_stale_writer_lock_fail_closed(self):
        before_primary = self.path.read_bytes()
        before_backup = self.store.backup.read_bytes()
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text('{"pid":0}', encoding="utf-8")
        try:
            with self.assertRaises(RuleError):
                self.store.save(self.sim)
            self.assertEqual(self.path.read_bytes(), before_primary)
            self.assertEqual(self.store.backup.read_bytes(), before_backup)
        finally:
            lock.unlink()
        # Reject a directly mutated domain session, never promote it to backup.
        self.sim._session.campaign_id = "unknown_campaign"
        with self.assertRaises(RuleError):
            self.store.save(self.sim)
        self.assertEqual(self.path.read_bytes(), before_primary)
        self.assertEqual(self.store.backup.read_bytes(), before_backup)

    def test_corrupt_primary_keeps_valid_backup_and_requires_explicit_restore(self):
        original_backup = self.store.backup.read_bytes()
        invalid_bytes = b'{"version":1,"broken":'
        self.path.write_bytes(invalid_bytes)
        before_live = self.sim.recording()
        with self.assertRaises(Exception):
            self.store.load()
        with self.assertRaises(Exception):
            self.store.save(self.sim)
        self.assertEqual(self.store.backup.read_bytes(), original_backup)
        self.assertEqual(self.sim.recording(), before_live)
        recovered = self.store.restore_backup()
        self.assertEqual(self.path.read_bytes(), original_backup)
        self.assertEqual(recovered.recording()["campaign_id"], "main")
        self.assertEqual(self.store.damaged.read_bytes(), invalid_bytes)

    def test_foreign_project_and_symlinks_cannot_be_recovered(self):
        other = deepcopy(self.project)
        other.title += " incompatible"
        foreign = PlayerSlotStore(self.path, self.content, other,
                                  campaign_id="main")
        original = self.path.read_bytes()
        with self.assertRaises(Exception):
            foreign.load()
        self.assertEqual(self.path.read_bytes(), original)
        if sys.platform != "win32":
            self.store.backup.unlink()
            self.store.backup.symlink_to(self.path)
            with self.assertRaises(Exception):
                self.store.restore_backup()
            self.assertEqual(self.path.read_bytes(), original)


class SDKWorkerBoundaryTests(unittest.TestCase):
    def test_background_result_is_immutable_until_owner_accepts(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        before = studio.snapshot()
        with SdkWorkQueue(max_workers=1) as queue:
            ticket = queue.submit_authoring(studio, hold_for_cancel)
            from tests_standalone.test_drawtemp5_r1_workers import wait_for
            result = wait_for(queue, ticket)
            self.assertTrue(result.ready, result.message)
            self.assertEqual(studio.snapshot(), before)
            changed = studio.apply(result.payload)
            self.assertEqual(changed.snapshot.revision, 1)
            self.assertEqual(studio.undo().snapshot.revision, 2)

    def test_public_sdk_exports_threading_and_certification_without_ui(self):
        import subprocess
        program = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "_tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise RuntimeError(fullname)
sys.meta_path.insert(0, Block())
from drawtemp.sdk import certify_trace, SdkWorkQueue, PlayerSlotStore
from drawtemp.sdk import SDK_FEATURES, capabilities
assert 'certification.v1' in SDK_FEATURES
assert 'workers.v1' in SDK_FEATURES
"""
        subprocess.run([sys.executable, "-c", program], check=True,
                       capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
