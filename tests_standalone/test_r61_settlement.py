"""R61.A settlement: deterministic jobs, zone saturation, conservation and reload."""
from copy import deepcopy
import unittest

from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.settlement_management import (
    EXTENSION, validate_settlement)
from sporebound.system_design import EXTENSION as SYSTEMS, SystemEconomy
from tests_standalone.test_r25_scene_router import scene_fixture


def economy_spec():
    return {
        "version": 1,
        "resources": [
            {"id": "grain", "initial": 10, "capacity": 50},
            {"id": "food", "initial": 1, "capacity": 50},
            {"id": "wood", "initial": 8, "capacity": 50},
            {"id": "plank", "initial": 0, "capacity": 50},
        ],
        "producers": [
            {"id": "farm", "inputs": {"grain": 1},
             "outputs": {"food": 2}, "interval": 2},
            {"id": "sawmill", "inputs": {"wood": 1},
             "outputs": {"plank": 1}, "interval": 1},
        ],
        "merchants": [], "quests": [],
    }


def settlement_spec():
    return {
        "version": 1,
        "zones": [{"id": "village", "scene": "arrival", "capacity": 2}],
        "buildings": [
            {"id": "mill", "zone": "village", "producer": "farm",
             "workers": 1, "cost": {}, "built": True},
            {"id": "workshop", "zone": "village", "producer": "sawmill",
             "workers": 1, "cost": {"wood": 2}, "built": False},
        ],
        "residents": [{"id": "ada"}, {"id": "bob"}],
        "needs": [{"resource": "food", "quantity": 1, "interval": 1}],
    }


def fixture():
    content, project = scene_fixture()
    project.extensions[SYSTEMS] = {
        "schema_version": 1, "data": economy_spec(), "references": []}
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": settlement_spec(), "references": []}
    project.validate(content)
    return content, project


def new_economy():
    return SystemEconomy(economy_spec(), {"arrival"},
                         settlement=settlement_spec())


class R61SettlementTests(unittest.TestCase):
    def test_project_only_accepts_typed_settlement_bound_to_r55(self):
        content, project = fixture()
        self.assertEqual(GameProject.from_dict(
            project.to_dict(), content).to_dict(), project.to_dict())
        for mutator in (
                lambda s: s["buildings"].append(deepcopy(s["buildings"][0])),
                lambda s: s["buildings"][0].update(workers=True),
                lambda s: s["buildings"][0].update(producer="unknown"),
                lambda s: s["buildings"][0].update(zone=[]),
                lambda s: s["needs"][0].update(resource=[]),
                lambda s: s["zones"][0].update(capacity=0),
                lambda s: s["buildings"][1].update(built=True, zone="missing"),
                lambda s: s["residents"].append({"id": "ada"}),
                lambda s: s["needs"][0].update(quantity=-1),
                lambda s: s.update(version=2),
                lambda s: s.update(scripts=["import os"]),
        ):
            with self.subTest(mutator=mutator), self.assertRaises(RuleError):
                changed = deepcopy(settlement_spec())
                mutator(changed)
                validate_settlement(changed, economy_spec(), {"arrival"})
        project.extensions.pop(SYSTEMS)
        with self.assertRaises(RuleError):
            project.validate(content)

    def test_workforce_shortage_recovery_and_tick_partitioning(self):
        a, b = new_economy(), new_economy()
        a.advance(3)
        for _ in range(3):
            b.advance(1)
        self.assertEqual(a.snapshot(), b.snapshot())
        self.assertEqual(a.stocks["food"], 0)
        self.assertEqual(a.settlement_state()["shortages"]["food"], 2)
        self.assertEqual(a.stocks["grain"], 10)  # no ghost production
        for runtime in (a, b):
            self.assertTrue(runtime.settlement_assign("ada", "mill", "job1"))
            runtime.advance(1)
        self.assertEqual(a.snapshot(), b.snapshot())
        self.assertEqual(a.settlement_state()["shortages"]["food"], 0)
        self.assertEqual(a.stocks["food"], 1)
        self.assertEqual(a.stocks["grain"], 9)

    def test_atomic_zone_costs_and_concurrent_workers(self):
        sim = new_economy()
        before = sim.snapshot()
        with self.assertRaises(RuleError):
            sim.settlement_assign("bob", "workshop", "early")
        self.assertEqual(sim.snapshot(), before)
        self.assertTrue(sim.settlement_build("workshop", "build1"))
        self.assertEqual(sim.stocks["wood"], 6)
        self.assertFalse(sim.settlement_build("workshop", "build1"))
        self.assertTrue(sim.settlement_assign("ada", "workshop", "job1"))
        before = sim.snapshot()
        with self.assertRaises(RuleError):
            sim.settlement_assign("bob", "workshop", "job2")
        with self.assertRaises(RuleError):
            sim.settlement_assign("ada", "mill", "job1")
        with self.assertRaises(RuleError):
            sim.settlement_build("mill", "build2")
        self.assertEqual(sim.snapshot(), before)
        sim.advance(2)
        self.assertEqual(sim.stocks["plank"], 2)
        self.assertEqual(sim.stocks["wood"], 4)
        self.assertEqual(sim.stocks["grain"], 10)
        self.assertTrue(sim.settlement_assign("ada", None, "leave"))
        self.assertTrue(sim.settlement_assign("bob", "workshop", "job3"))
        self.assertFalse(sim.settlement_assign("bob", "workshop", "noop"))
        before = sim.snapshot()
        with self.assertRaises(RuleError):
            sim.settlement_build("workshop", "job3")  # shared receipt namespace
        self.assertEqual(sim.snapshot(), before)

    def test_stock_conservation_and_saturation(self):
        spec = settlement_spec()
        spec["zones"][0]["capacity"] = 1
        sim = SystemEconomy(economy_spec(), {"arrival"}, settlement=spec)
        before = sim.snapshot()
        with self.assertRaises(RuleError):
            sim.settlement_build("workshop", "build")
        self.assertEqual(sim.snapshot(), before)
        spec = economy_spec()
        spec["resources"][3]["capacity"] = 1
        sim = SystemEconomy(spec, {"arrival"}, settlement=settlement_spec())
        sim.settlement_build("workshop", "build")
        sim.settlement_assign("ada", "workshop", "job")
        sim.advance(6)
        self.assertEqual(sim.stocks["plank"], 1)
        self.assertEqual(sim.stocks["wood"], 5)  # 8 - 2 for build - 1 for production
        self.assertGreater(sim.settlement_state()["shortages"]["food"], 0)

    def test_save_replay_rejects_tampering_and_old_shapes_unchanged(self):
        sim = new_economy()
        sim.settlement_assign("ada", "mill", "job1")
        sim.advance(4)
        sim.settlement_build("workshop", "build1")
        sim.settlement_assign("bob", "workshop", "job2")
        sim.advance(2)
        before = sim.snapshot()
        clone = new_economy()
        clone.restore(deepcopy(before))
        self.assertEqual(clone.snapshot(), before)
        for mutate in (
                lambda x: x["stocks"].update(food=42),
                lambda x: x["settlement"]["built"].clear(),
                lambda x: x["settlement"]["shortages"].update(food=99),
                lambda x: x["journal"].append(deepcopy(x["journal"][1])),
                lambda x: x["journal"][0].update(resident="evil"),
                lambda x: x["tick"].__class__ and x.update(tick=True),
        ):
            forged = deepcopy(before)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                clone.restore(forged)
            self.assertEqual(clone.snapshot(), before)
        legacy = SystemEconomy(economy_spec(), {"arrival"})
        self.assertNotIn("settlement", legacy.snapshot())
        legacy.advance(2)
        unchanged = SystemEconomy(economy_spec(), {"arrival"})
        unchanged.restore(legacy.snapshot())
        self.assertEqual(unchanged.snapshot(), legacy.snapshot())

    def test_game_session_save_restore_and_legacy_isolation(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=61)
        session.system_advance(3)
        self.assertEqual(session.settlement_state()["shortages"]["food"], 2)
        self.assertTrue(session.settlement_assign("ada", "mill", "job1"))
        session.system_advance(2)
        session.settlement_build("workshop", "build1")
        session.settlement_assign("bob", "workshop", "job2")
        session.system_advance(2)
        recording = session.recording()
        restored = GameSession.from_recording(recording, content, project)
        self.assertEqual(restored.recording(), recording)
        self.assertEqual(restored.settlement_state(), session.settlement_state())
        tampered = deepcopy(recording)
        tampered["systems"]["settlement"]["assignments"]["ada"] = "workshop"
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(tampered, content, project)
        # Opt-out creates no extra checkpoint fields or R61 session API.
        project.extensions.pop(EXTENSION)
        project.validate(content)
        old = GameSession.new(content, project, "main")
        self.assertNotIn("settlement", old.recording()["systems"])
        with self.assertRaises(RuleError):
            old.settlement_state()


if __name__ == "__main__":
    unittest.main()
