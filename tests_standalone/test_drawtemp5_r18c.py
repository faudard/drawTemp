"""R18.C: tactical target acknowledgement is UI-only, replay-safe and Qt-ready."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import MISSION, reference_project


class TargetConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        content, project = reference_project()
        self.player = PlayerController(
            content, project, "main", self.temporary.name)
        self.player.new_game()
        self.player.choose("enter")
        self.player.start_mission(MISSION)

    def _player_turn_and_reachable(self):
        for _ in range(100):
            battle = self.player.session._session.active_battle
            if battle.result:
                self.skipTest("Reference encounter ended before player activation")
            if battle.deploying:
                self.player.command("deploy")
            elif battle.active is not None and battle.active.team == "enemy":
                self.player.advance_enemy()
            else:
                break
        battle = self.player.session._session.active_battle
        if battle.active is None or battle.active.team != "player":
            self.skipTest("No active player in reference encounter")
        moves = sorted(
            point for point in battle.reachable() if point != battle.active.pos)
        if not moves:
            self.skipTest("No legal movement destination")
        return moves[0]

    def test_request_and_cancel_never_advance_combat_or_save(self):
        cell = self._player_turn_and_reachable()
        self.player.select_cell(*cell)
        original = self.player.session.recording()
        snapshot = self.player.session.snapshot()
        previous = self.player.state()["battle"]
        candidate = self.player.request_target("move")
        pending = candidate["pending_target"]
        self.assertEqual(pending["cell"], list(cell))
        self.assertEqual(pending["kind"], "move")
        self.assertTrue(pending["valid"])
        self.assertIn("Coût", pending["details"])
        self.assertEqual(self.player.session.recording(), original)
        self.assertEqual(self.player.session.snapshot(), snapshot)
        self.assertEqual(self.player.state()["battle"], previous)
        self.assertEqual(self.player.cancel_target()["pending_target"], {})
        self.assertEqual(self.player.session.recording(), original)

    def test_cancel_on_new_selection_and_invalid_commands(self):
        cell = self._player_turn_and_reachable()
        self.player.select_cell(*cell)
        self.player.request_target("move")
        self.player.select_cell(0, 0)
        self.assertEqual(self.player.state()["pending_target"], {})
        with self.assertRaisesRegex(ValueError, "Aucune action"):
            self.player.confirm_target()
        with self.assertRaises(ValueError):
            self.player.request_target("unknown")
        with self.assertRaises(ValueError):
            self.player.request_target("skill", "invalid_skill")

    def test_rejects_stale_action_without_engine_command(self):
        cell = self._player_turn_and_reachable()
        self.player.select_cell(*cell)
        self.player.request_target("move")
        before = self.player.session.recording()
        # Simulate another owner advancing the actual canonical simulation.
        self.player.session.execute(
            {"kind": "move", "cell": list(cell)},
            expected_revision=self.player.session.snapshot().revision)
        updated = self.player.session.recording()
        self.assertNotEqual(before, updated)
        self.assertFalse(self.player.state()["pending_target"]["valid"])
        with self.assertRaisesRegex(ValueError, "modifié"):
            self.player.confirm_target()
        self.assertEqual(self.player.session.recording(), updated)
        self.assertEqual(self.player.state()["pending_target"], {})

    def test_confirmation_is_one_canonical_action_and_staging_not_saved(self):
        cell = self._player_turn_and_reachable()
        self.player.select_cell(*cell)
        self.player.request_target("move")
        before = self.player.session.snapshot().revision
        previous_recording = self.player.session.recording()
        self.player.save(1)
        saved_file = Path(self.temporary.name) / "slot_1.json"
        original_bytes = saved_file.read_bytes()
        resumed = PlayerController(
            self.player.content, self.player.project, "main",
            self.temporary.name)
        self.assertEqual(resumed.load(1)["pending_target"], {})
        self.assertEqual(saved_file.read_bytes(), original_bytes)
        self.assertEqual(resumed.session.recording(), previous_recording)
        self.player.confirm_target()
        self.assertEqual(self.player.state()["pending_target"], {})
        self.assertEqual(self.player.session.snapshot().revision, before + 1)
        self.assertNotEqual(self.player.session.recording(), previous_recording)
        self.assertEqual(saved_file.read_bytes(), original_bytes)

    def test_return_to_title_clears_pending_without_changing_save(self):
        cell = self._player_turn_and_reachable()
        self.player.select_cell(*cell)
        self.player.request_target("move")
        original = self.player.session.recording()
        self.player.title()
        self.assertEqual(self.player.state()["screen"], "title")
        self.assertEqual(self.player.state()["pending_target"], {})
        self.assertEqual(self.player.session.recording(), original)

    def test_request_attack_is_not_derived_from_inspected_skill(self):
        self._player_turn_and_reachable()
        self.player.inspected_skill = "not_the_attack"
        battle = self.player.session.snapshot().battle
        active = next(unit for unit in battle["units"]
                      if unit["id"] == battle["active"])
        self.player.select_cell(*active["pos"])
        # Engine may reject attacking own cell; the preview must still use
        # 'attack' rather than the unrelated highlighted skill.
        canonical = self.player.session.tactical_presentation(
            self.player.selected, "attack",
            expected_revision=self.player.session.snapshot().revision)
        from drawtemp.sdk.simulation import thaw
        focus = thaw(canonical)["focus"]
        try:
            view = self.player.request_target("attack")
        except ValueError:
            self.assertFalse(focus["can_target"])
        else:
            self.assertTrue(focus["can_target"])
            self.assertEqual(view["pending_target"]["kind"], "attack")


class QtQmlContractTests(unittest.TestCase):
    def test_ui_identifiers_and_input_contract_present(self):
        text = (Path(__file__).resolve().parents[1] /
                "drawtemp" / "player" / "Main.qml").read_text(encoding="utf-8")
        for value in (
            'objectName: "r18TargetConfirmation"',
            'objectName: "r18ConfirmTarget"',
            'objectName: "r18CancelTarget"',
            'player.requestTarget("move", "")',
            'player.requestTarget("attack", "")',
            'player.confirmTarget()',
            'player.cancelTarget()',
        ):
            with self.subTest(value=value):
                self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
