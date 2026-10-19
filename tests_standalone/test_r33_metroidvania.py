"""R33.A state-space preflight, canonical extension and CT compatibility."""
import copy
import unittest

from drawtemp.sdk.reference import reference_project
from sporebound.metroidvania import analyze_metroidvania, validate_metroidvania
from sporebound.model import RuleError


def example():
    return {
        "version": 1,
        "rooms": ["village", "ruins", "citadel"],
        "start": "village", "goal": "citadel",
        "starting_capabilities": [],
        "pickups": [{"id": "boots", "room": "ruins", "grants": ["double_jump"]}],
        "links": [
            {"id": "visit", "source": "village", "destination": "ruins", "requires": []},
            {"id": "return", "source": "ruins", "destination": "village", "requires": []},
            {"id": "boss_gate", "source": "village", "destination": "citadel",
             "requires": ["double_jump"]},
        ],
    }


class R33ProgressionTests(unittest.TestCase):
    def test_gated_route_and_deterministic_witness(self):
        graph = example()
        first = analyze_metroidvania(graph, scene_ids=graph["rooms"])
        self.assertTrue(first["complete"])
        self.assertTrue(first["safe"])
        self.assertTrue(first["goal_reachable"])
        self.assertEqual([step["room"] for step in first["witness"]],
                         ["village", "ruins", "village", "citadel"])
        self.assertIn("double_jump", first["witness"][-1]["capabilities"])
        self.assertEqual(first, analyze_metroidvania(graph))
        self.assertEqual(graph, example())

    def test_one_way_trap_is_reported_even_if_goal_has_a_route(self):
        graph = example()
        graph["rooms"].append("pit")
        graph["links"].append({"id": "drop", "source": "village",
                               "destination": "pit", "requires": []})
        report = analyze_metroidvania(graph)
        self.assertTrue(report["goal_reachable"])
        self.assertFalse(report["safe"])
        self.assertIn("pit", [state["room"] for state in report["softlock_states"]])

    def test_ability_behind_its_own_gate_is_a_softlock(self):
        graph = example()
        graph["links"][0]["requires"] = ["double_jump"]
        graph["links"][1]["requires"] = ["double_jump"]
        report = analyze_metroidvania(graph)
        self.assertFalse(report["goal_reachable"])
        self.assertEqual(report["unreachable_rooms"], ["citadel", "ruins"])

    def test_budget_is_fail_closed(self):
        report = analyze_metroidvania(example(), state_budget=1)
        self.assertFalse(report["complete"])
        self.assertFalse(report["safe"])
        self.assertTrue(report["warnings"])
        with self.assertRaises(RuleError):
            analyze_metroidvania(example(), state_budget=True)

    def test_strict_schema_refs_and_duplicate_ids(self):
        graph = example()
        with self.assertRaises(RuleError):
            validate_metroidvania(graph, scene_ids=["village"])
        for changed in ("missing_room", "unknown_capability", "duplicate_link", "bad_version"):
            altered = copy.deepcopy(graph)
            if changed == "missing_room":
                altered["links"][0]["destination"] = "missing"
            elif changed == "unknown_capability":
                altered["links"][0]["requires"] = ["fly"]
            elif changed == "duplicate_link":
                altered["links"].append(altered["links"][0])
            else:
                altered["version"] = 2
            with self.subTest(changed=changed), self.assertRaises(RuleError):
                validate_metroidvania(altered)

    def test_legacy_gameproject_remains_unmodified(self):
        content, project = reference_project()
        old = copy.deepcopy(project.to_dict())
        project.validate(content)
        self.assertEqual(project.to_dict(), old)
        project.extensions["drawtemp.metroidvania"] = {
            "schema_version": 1, "data": example()}
        with self.assertRaises(RuleError):
            project.validate(content)
        project.extensions.clear()
        project.validate(content)
        self.assertEqual(project.to_dict(), old)


if __name__ == "__main__":
    unittest.main()
