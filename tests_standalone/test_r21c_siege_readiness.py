"""R21.C regression: real ram, gate, lever, and offscreen front state.

The preview runs the existing interaction on a detached Battle. Every committed
result is executed by Battle / MultiFrontSession and checked by replay digest.
"""
from copy import deepcopy
import json
import unittest

from examples.siege_fronts import SIEGE_LINKS
from examples.siege_scenarios import siege_content
from sporebound.command_center import handle
from sporebound.engine import Battle
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError
from sporebound.siege_readiness_r21 import (
    siege_front_readiness, siege_operation_preview,
)


def ram_battle(*, near_gate=False, blocked=False):
    data = siege_content().to_dict()
    mission = next(m for m in data["missions"] if m["id"] == "castle_ram")
    mission["deployment"] = []
    captain = next(u for u in mission["units"] if u["id"] == "captain")
    captain["pos"] = [6, 3] if near_gate else [2, 3]
    captain["ct"] = 100
    ram = next(o for o in mission["objects"] if o["id"] == "ram")
    if near_gate:
        ram["pos"] = [7, 3]
    if blocked:
        mission["units"].append({
            "id": "roadblock", "name": "Roadblock", "team": "enemy",
            "pos": [4, 3]})
    return Battle(Content.from_dict(data), "castle_ram", seed=13)


def linked_siege():
    data = siege_content().to_dict()
    walls = next(m for m in data["missions"] if m["id"] == "castle_ramparts")
    lever = next(o for o in walls["objects"] if o["id"] == "portcullis_lever")
    # The same valid authored switch is adjacent to the captain solely to
    # keep a headless causal-link regression short. The link itself is real.
    lever["pos"] = [2, 3]
    captain = next(u for u in walls["units"] if u["id"] == "captain")
    captain["ct"] = 100
    return MultiFrontSession(
        Content.from_dict(data),
        {"walls": "castle_ramparts", "gate": "castle_ram",
         "courtyard": "castle_courtyard"},
        "walls", seed=19, links=deepcopy(SIEGE_LINKS[:1]))


def infrastructure(view, front, object_id):
    row = next(f for f in view["fronts"] if f["id"] == front)
    return next(o for o in row["infrastructure"] if o["id"] == object_id)


class SiegePreparationTests(unittest.TestCase):
    def test_ram_advance_preview_matches_exact_committed_step_and_replay(self):
        battle = ram_battle()
        before = battle.digest()
        report = siege_operation_preview(battle, "ram")
        self.assertTrue(report["ready"])
        self.assertEqual(report["phase"], "advance")
        self.assertEqual(report["position"], [3, 3])
        self.assertEqual(report["next_position"], [4, 3])
        self.assertEqual(report["gate_hp"], 4)
        self.assertEqual(report["gate_hp_after"], 4)
        self.assertEqual(report, siege_operation_preview(battle, "ram"))
        self.assertEqual(battle.digest(), before)
        json.dumps(report, sort_keys=True)
        battle.execute({"kind": "interact", "object": "ram"})
        moved = next(o for o in battle.mission.objects if o["id"] == "ram")
        self.assertEqual(moved["pos"], report["next_position"])
        self.assertTrue(any(event["kind"] == "ram_advanced"
                            for event in battle.events))
        self.assertEqual(
            Battle.replay(battle.recording()).digest(), battle.digest())

    def test_ram_strike_and_gate_hp_preview_use_canonical_damage(self):
        battle = ram_battle(near_gate=True)
        report = siege_operation_preview(battle, "ram")
        self.assertTrue(report["ready"])
        self.assertEqual(report["phase"], "strike")
        self.assertEqual(report["gate_hp"], 4)
        self.assertEqual(report["gate_hp_after"], 3)
        battle.execute({"kind": "interact", "object": "ram"})
        gate = next(o for o in battle.mission.objects if o["id"] == "main_gate")
        self.assertEqual(gate["hp"], report["gate_hp_after"])
        self.assertEqual(
            Battle.replay(battle.recording()).digest(), battle.digest())

    def test_blocked_ram_path_is_reported_and_rejected_without_state_loss(self):
        battle = ram_battle(blocked=True)
        before = battle.digest()
        count = len(battle.commands)
        report = siege_operation_preview(battle, "ram")
        self.assertFalse(report["ready"])
        self.assertIn("blocked", report["reason"].lower())
        self.assertEqual(battle.digest(), before)
        with self.assertRaises(RuleError):
            battle.execute({"kind": "interact", "object": "ram"})
        self.assertEqual(len(battle.commands), count)
        self.assertEqual(battle.digest(), before)

    def test_invalid_object_id_and_deployment_are_never_reported_as_ready(self):
        battle = ram_battle()
        before = battle.digest()
        with self.assertRaises(RuleError):
            siege_operation_preview(battle, "unknown")
        with self.assertRaises(RuleError):
            siege_operation_preview(battle, "")
        self.assertEqual(battle.digest(), before)
        deployed = Battle(siege_content(), "castle_ram", seed=13)
        self.assertTrue(deployed.deploying)
        preview = siege_operation_preview(deployed, "ram")
        self.assertFalse(preview["ready"])
        self.assertEqual(preview["phase"], "unavailable")


class CrossFrontPreparationTests(unittest.TestCase):
    def test_real_lever_opens_unloaded_gate_and_reduces_courtyard_opposition(self):
        session = linked_siege()
        session.execute({"kind": "start_battle"})
        before = session.digest()
        prior = siege_front_readiness(session)
        self.assertFalse(infrastructure(prior, "gate", "main_gate")["open"])
        self.assertFalse(next(row for row in prior["causal_links"]
                              if row["id"] == "raise_herse")["applied"])
        self.assertFalse(next(row for row in prior["fronts"]
                              if row["id"] == "gate")["materialized"])
        lever = siege_operation_preview(session.active, "portcullis_lever")
        self.assertEqual(lever["phase"], "open")
        self.assertTrue(lever["ready"])
        self.assertEqual(session.digest(), before)

        session.execute({"kind": "interact", "object": "portcullis_lever"})
        current = siege_front_readiness(session)
        self.assertTrue(infrastructure(current, "gate", "main_gate")["open"])
        self.assertTrue(next(row for row in current["causal_links"]
                             if row["id"] == "raise_herse")["applied"])
        self.assertEqual(next(row for row in current["fronts"]
                              if row["id"] == "courtyard")["opposition"], 7)
        self.assertEqual(session.applied_links, {"raise_herse"})
        self.assertEqual(session.front_overrides["gate"]["main_gate"]["open"], True)
        self.assertFalse(next(row for row in current["fronts"]
                              if row["id"] == "gate")["materialized"])
        replay = MultiFrontSession.replay(session.recording())
        self.assertEqual(replay.digest(), session.digest())
        self.assertEqual(siege_front_readiness(replay), current)

    def test_command_center_siege_is_read_only_and_returns_json(self):
        session = linked_siege()
        original = session.digest()
        same, response, quit_requested = handle(session, "siege")
        self.assertIs(same, session)
        self.assertFalse(quit_requested)
        data = json.loads(response)
        self.assertEqual(data, siege_front_readiness(session))
        self.assertEqual(original, session.digest())


if __name__ == "__main__":
    unittest.main()
