"""R21.D integration gates: deployment, convoy, siege, focus, checkpoint.

Scenarios execute the production commands against authored content, then
reconstruct from the exact multi-front operation journal.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_fronts import siege_session
from examples.siege_r21d_journey import demonstrate
from sporebound.command_center import handle
from sporebound.fronts import MultiFrontSession
from sporebound.model import RuleError
from sporebound.siege_journey_r21 import (
    deployment_choices, siege_journey_snapshot,
)


class JourneyProjectionTests(unittest.TestCase):
    def test_deployment_options_use_actual_occupied_zone_and_footprints(self):
        session = siege_session(focused="gate", seed=41)
        battle = session.active
        first = battle.digest()
        original = session.digest()
        view = siege_journey_snapshot(session)
        self.assertEqual(view["phase"], "deployment")
        self.assertEqual(view["focused"], "gate")
        captain = next(row for row in view["deployment"]
                       if row["unit"] == "captain")
        self.assertEqual(captain["current"], [1, 3])
        self.assertGreater(captain["valid_count"], 0)
        self.assertEqual(captain["certainty"], "legal_now")
        self.assertEqual(view, siege_journey_snapshot(session))
        self.assertEqual(battle.digest(), first)
        self.assertEqual(session.digest(), original)
        self.assertEqual(json.loads(json.dumps(view)), view)

        # Restrict display without restricting legal deployment itself.
        narrow = deployment_choices(battle, max_cells=1)
        self.assertEqual(len(next(row for row in narrow
                                  if row["unit"] == "captain")["cells"]), 1)
        self.assertTrue(next(row for row in narrow
                             if row["unit"] == "captain")["truncated"])
        for bad in (0, 33, 2.5, True):
            with self.subTest(bad=bad), self.assertRaises(RuleError):
                siege_journey_snapshot(session, max_deploy_cells=bad)
        self.assertEqual(session.digest(), original)

    def test_unfinished_turn_prevents_focus_and_is_visible(self):
        session = siege_session(focused="supplies", seed=17)
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "supply_cache"})
        before = session.digest()
        view = siege_journey_snapshot(session)
        targets = [row for row in view["focus_choices"]
                   if row["front"] != "supplies"]
        self.assertTrue(targets)
        self.assertTrue(all(not row["ready"] for row in targets))
        self.assertTrue(all(row["reason"] for row in targets))
        self.assertEqual(session.digest(), before)
        session.execute({"kind": "end"})
        view = siege_journey_snapshot(session)
        self.assertTrue(next(row for row in view["focus_choices"]
                             if row["front"] == "gate")["ready"])

    def test_command_center_journey_is_read_only_and_json_serializable(self):
        session = siege_session(focused="gate", seed=7)
        original = session.digest()
        same, response, quitting = handle(session, "journey")
        self.assertIs(same, session)
        self.assertFalse(quitting)
        self.assertEqual(json.loads(response), siege_journey_snapshot(session))
        self.assertEqual(session.digest(), original)


class JourneyPlaybackTests(unittest.TestCase):
    def test_real_supply_sabotage_convoy_deployment_and_ram(self):
        session = demonstrate(seed=23)
        report = siege_journey_snapshot(session)
        self.assertEqual(report["turn"], 1)
        self.assertEqual(report["focused"], "gate")
        self.assertEqual(report["phase"], "tactical")
        self.assertIn("throne", report["blocked_reinforcements"])
        self.assertTrue(any(row["id"] == "cut_supply_route"
                            and row["applied"] for row in report["causal_links"]))
        self.assertTrue(any(entry["kind"] == "unit_deployed"
                            and entry["unit"] == "captain"
                            for entry in session.active.events))
        self.assertTrue(any(entry["kind"] == "ram_advanced"
                            for entry in session.active.events))
        ram = next(o for o in session.active.mission.objects
                   if o["id"] == "ram")
        self.assertEqual(ram["pos"], [4, 3])
        self.assertEqual(session.logistics.reserves["player"], 2)
        self.assertEqual(session.digest(),
                         MultiFrontSession.replay(session.recording()).digest())

    def test_verified_file_checkpoint_roundtrip_and_resume_next_front(self):
        session = demonstrate(seed=7)
        original = session.digest()
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "siege-r21d.json"
            current, message, quitting = handle(session,
                                                  "save " + str(destination))
            self.assertIs(current, session)
            self.assertIn("Verified", message)
            self.assertFalse(quitting)
            self.assertTrue(destination.is_file())
            restored, _, quitting = handle(session,
                                            "load " + str(destination))
            self.assertFalse(quitting)
            self.assertEqual(restored.digest(), original)
            self.assertEqual(siege_journey_snapshot(restored),
                             siege_journey_snapshot(session))
            self.assertEqual(restored.recording(), session.recording())

            # Continue two distinct authenticated sessions independently.
            session.switch("walls")
            restored.switch("walls")
            self.assertEqual(session.digest(), restored.digest())
            session.execute({"kind": "start_battle"})
            restored.execute({"kind": "start_battle"})
            self.assertEqual(session.digest(), restored.digest())
            session.advance()
            restored.advance()
            self.assertEqual(session.digest(), restored.digest())
            self.assertEqual(
                MultiFrontSession.replay(restored.recording()).digest(),
                restored.digest())

    def test_tampered_checkpoint_does_not_replace_live_session(self):
        session = demonstrate(seed=11)
        before = session.digest()
        original_history = deepcopy(session.history)
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "siege-checkpoint.json"
            handle(session, "save " + str(destination))
            recording = json.loads(destination.read_text(encoding="utf-8"))
            recording["digest"] = "tampered"
            destination.write_text(json.dumps(recording), encoding="utf-8")
            with self.assertRaises(RuleError):
                handle(session, "load " + str(destination))
        self.assertEqual(session.digest(), before)
        self.assertEqual(session.history, original_history)


if __name__ == "__main__":
    unittest.main()
