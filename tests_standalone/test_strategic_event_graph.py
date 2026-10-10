"""2.5.4.5 strategic graph regression: authored predicates, real events and replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_scenarios import siege_content
from sporebound import strategic_events as graph
from sporebound.game_project import GameProject
from sporebound.fronts import MultiFrontSession
from sporebound.model import RuleError
from sporebound.siege_authoring import (add_front, make_session, new_blueprint,
                                         remove_front, replace_siege,
                                         load_siege_slot, save_siege_slot)


class StrategicGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = siege_content()

    def blueprint(self):
        bp = new_blueprint("castle_events", "main", "castle_supply", front="supplies")
        bp = add_front(bp, "gate", "castle_ram", strength=10, opposition=14)
        bp = add_front(bp, "walls", "castle_ramparts", strength=8, opposition=12)
        return bp

    def project(self, bp):
        return replace_siege(GameProject.default(self.content),
                             self.content, bp)

    def graph(self):
        return [
            {"id": "resource_seen",
             "when": {"battle_event": {"front": "supplies", "kind": "interact",
                                       "value": "supply_cache"}},
             "effects": [{"kind": "block_reinforcements", "front": "walls"}]},
            {"id": "timed_pressure",
             "when": {"all": [
                 {"turn_at_least": 2},
                 {"front_status": {"front": "gate", "status": "active"}}]},
             "effects": [{"kind": "reduce_opposition", "front": "walls", "amount": 2}]},
            {"id": "follow_up",
             "when": {"all": [
                 {"fired": "timed_pressure"},
                 {"not": {"front_status": {"front": "gate", "status": "defeat"}}}]},
             "effects": [{"kind": "set_doctrine", "front": "gate", "doctrine": "delay"},
                         {"kind": "signal", "text": "Le ravitaillement ennemi faiblit."}]},
        ]

    def configured(self):
        bp = self.blueprint()
        for node in self.graph():
            bp = graph.upsert(bp, self.content, node)
        return bp

    def test_optional_manifest_and_legacy_save_unchanged(self):
        plain = self.blueprint()
        self.assertNotIn("event_graph", plain)
        session = make_session(plain, self.content)
        self.assertNotIn("event_graph", session.state())
        self.assertNotIn("event_graph", session.recording())
        self.assertEqual(session.recording()["version"], 2)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())
        bp = self.configured()
        restored = self.project(bp)
        self.assertEqual(restored.sieges[0]["event_graph"], self.graph())
        self.assertNotIn("event_graph", graph.remove(
            graph.remove(
                graph.remove(bp, self.content, "follow_up"),
                self.content, "timed_pressure"),
            self.content, "resource_seen"))

    def test_real_objectives_not_fake_and_one_shot_firing(self):
        bp = self.configured()
        before = deepcopy(bp)
        session = make_session(bp, self.content, seed=7)
        self.assertEqual(session.recording()["version"], 6)
        self.assertNotIn("resource_seen", session.fired_graph)
        # A strategic clock alone cannot authenticate an object interaction.
        session.advance()
        self.assertNotIn("resource_seen", session.fired_graph)
        self.assertEqual(session.timeline.turn, 1)
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "supply_cache"})
        self.assertIn("resource_seen", session.fired_graph)
        self.assertIn("walls", session.blocked_reinforcements)
        session.advance()
        self.assertEqual(session.fired_graph, {"resource_seen", "timed_pressure",
                                               "follow_up"})
        self.assertEqual(session.timeline.fronts["gate"]["doctrine"], "delay")
        self.assertEqual(sum(e["kind"] == "strategic_event_fired"
                             for e in session.timeline.events), 3)
        for _ in range(3):
            session.advance()
        self.assertEqual(sum(e["kind"] == "strategic_event_fired"
                             for e in session.timeline.events), 3)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())
        self.assertEqual(bp, before)

    def test_order_does_not_depend_on_storage_order(self):
        bp = self.configured()
        first = make_session(bp, self.content)
        shuffled = deepcopy(bp)
        shuffled["event_graph"].reverse()
        second = make_session(shuffled, self.content)
        first.advance()
        first.advance()
        second.advance()
        second.advance()
        self.assertEqual(first.timeline.fronts, second.timeline.fronts)
        self.assertEqual(first.fired_graph, second.fired_graph)

    def test_invalid_condition_action_cycles_and_limits_are_atomic(self):
        bp = self.configured()
        fixed = deepcopy(bp)
        variants = [
            {"id": "no_logic", "when": {"run_python": "pass"},
             "effects": [{"kind": "signal", "text": "x"}]},
            {"id": "bad_front", "when": {"front_status": {
                "front": "missing", "status": "victory"}},
             "effects": [{"kind": "signal", "text": "x"}]},
            {"id": "fake_proof", "when": {"battle_event": {
                "front": "supplies", "kind": "interact", "value": "fake"}},
             "effects": [{"kind": "signal", "text": "x"}]},
            {"id": "auto_boss", "when": {"turn_at_least": 1},
             "effects": [{"kind": "reduce_opposition", "front": "walls",
                          "amount": -1}]},
            {"id": "missing_dependency", "when": {"fired": "unknown"},
             "effects": [{"kind": "signal", "text": "x"}]},
            {"id": "self_cycle", "when": {"fired": "self_cycle"},
             "effects": [{"kind": "signal", "text": "x"}]},
            {"id": "unbounded", "when": {"all": [
                {"turn_at_least": 1} for _ in range(9)]},
             "effects": [{"kind": "signal", "text": "x"}]},
        ]
        for variant in variants:
            with self.subTest(node=variant["id"]), self.assertRaises(RuleError):
                graph.upsert(bp, self.content, variant)
            self.assertEqual(bp, fixed)
        cycled = graph.upsert(bp, self.content, {
            "id": "node_a", "when": {"turn_at_least": 0},
            "effects": [{"kind": "signal", "text": "a"}]})
        cycled = graph.upsert(cycled, self.content, {
            "id": "node_b", "when": {"fired": "node_a"},
            "effects": [{"kind": "signal", "text": "b"}]})
        with self.assertRaises(RuleError):
            graph.upsert(cycled, self.content, {
                "id": "node_a", "when": {"fired": "node_b"},
                "effects": [{"kind": "signal", "text": "a"}]})
        with self.assertRaises(RuleError):
            graph.remove(bp, self.content, "timed_pressure")
        with self.assertRaises(RuleError):
            remove_front(bp, "walls")
        self.assertEqual(bp, fixed)

    def test_preview_project_and_checkpoint_exact_identity(self):
        bp = self.configured()
        projection = graph.preview(bp, self.content, turns=3)
        self.assertEqual(projection[2]["fired"],
                         ["follow_up", "timed_pressure"])
        self.assertTrue(all("resource_seen" not in item["fired"]
                            for item in projection))
        project = self.project(bp)
        session = make_session(bp, self.content, seed=4)
        session.advance()
        session.advance()
        with TemporaryDirectory() as directory:
            dest = Path(directory) / "castle.game.json"
            project.save(dest, self.content)
            reloaded = GameProject.load(dest, self.content)
            self.assertEqual(reloaded.sieges[0], bp)
            save_siege_slot(dest, bp, 1, session)
            loaded = load_siege_slot(dest, bp, 1, self.content)
            self.assertEqual(loaded.digest(), session.digest())
            changed = deepcopy(bp)
            changed["event_graph"][0]["effects"][0]["front"] = "gate"
            with self.assertRaises(RuleError):
                load_siege_slot(dest, changed, 1, self.content)

    def test_effect_targets_unopened_front_and_keeps_tactical_boss_locked(self):
        bp = self.blueprint()
        bp["event_graph"] = [
            {"id": "breach_help",
             "when": {"turn_at_least": 1},
             "effects": [{"kind": "open_door", "front": "gate",
                          "object": "main_gate"}]},
        ]
        session = make_session(bp, self.content)
        self.assertNotIn("gate", session.battles)
        session.advance()
        self.assertTrue(session.front_overrides["gate"]["main_gate"]["open"])
        session.switch("gate")
        door = next(o for o in session.active.mission.objects
                    if o["id"] == "main_gate")
        self.assertTrue(door["open"])
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())


if __name__ == "__main__":
    unittest.main()
