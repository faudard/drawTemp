"""2.5.3.3 class/talent graph and AI authoring contracts."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.class_ai_authoring import (
    ai_preview, delete_talent, job_graph, link_job, make_talent,
    parse_cells, save_talent, set_unit_ai, talent_graph, validate_route,
)
from sporebound.editor import Document
from sporebound.model import Content, RuleError


class ClassAIStudioTests(unittest.TestCase):
    def setUp(self):
        self.data = Content.load(DEFAULT_CONTENT).to_dict()
        self.before = deepcopy(self.data)

    def test_class_graph_uses_real_requires_and_is_deterministic(self):
        graph = job_graph(self.data)
        self.assertEqual(graph, job_graph(deepcopy(self.data)))
        self.assertEqual({node["id"] for node in graph["nodes"]},
                         set(self.data["jobs"]))
        self.assertIn({"from":"brave", "to":"field_medic"}, graph["edges"])
        levels = {n["id"]: n["depth"] for n in graph["nodes"]}
        self.assertLess(levels["brave"], levels["field_medic"])
        self.assertEqual(self.data, self.before)

    def test_class_link_respects_cycles_and_rejects_invalid_levels(self):
        linked = link_job(self.data, "field_medic", "bulwark", 3)
        self.assertEqual(linked["jobs"]["field_medic"]["requires"], "bulwark")
        self.assertEqual(linked["jobs"]["field_medic"]["requires_level"], 3)
        with self.assertRaises(RuleError):
            link_job(linked, "bulwark", "field_medic")
        with self.assertRaises(RuleError):
            link_job(self.data, "brave", "brave")
        with self.assertRaises(RuleError):
            link_job(self.data, "field_medic", "missing")
        with self.assertRaises(RuleError):
            link_job(self.data, "field_medic", "brave", True)
        self.assertEqual(self.data, self.before)

    def test_create_and_edit_multi_branch_talent_graph(self):
        a = make_talent(jp=2, bonuses={"attack":3}, skills=("flare",))
        first = save_talent(self.data, "brave", "lunge", a, creating=True)
        b = make_talent(jp=4, requires=("lunge",), exclusive="stances",
                        bonuses={"max_hp":10})
        second = save_talent(first, "brave", "bulwark_stance", b, creating=True)
        graph = talent_graph(second, "brave")
        self.assertEqual([e for e in graph["edges"]
                          if e["to"] == "bulwark_stance"],
                         [{"from":"lunge", "to":"bulwark_stance"}])
        self.assertEqual({node["id"] for node in graph["nodes"]},
                         {"lunge", "bulwark_stance"})
        self.assertEqual(second["jobs"]["brave"]["talents"]["lunge"]["jp"], 2)
        updated = save_talent(second, "brave", "bulwark_stance",
                              make_talent(jp=3, requires=("lunge",),
                                          exclusive="stances"))
        self.assertEqual(updated["jobs"]["brave"]["talents"]["bulwark_stance"]["jp"],3)
        self.assertEqual(self.data, self.before)

    def test_invalid_talent_dag_and_used_talent_refuse_without_mutation(self):
        first = save_talent(self.data, "brave", "base",
                            make_talent(jp=2), creating=True)
        second = save_talent(first, "brave", "higher",
                             make_talent(requires=("base",)), creating=True)
        with self.assertRaises(RuleError):
            delete_talent(second, "brave", "base")
        with self.assertRaises(RuleError):
            save_talent(second, "brave", "base",
                        make_talent(requires=("higher",)))
        with self.assertRaises(RuleError):
            save_talent(second, "brave", "higher",
                        make_talent(skills=("missing",)))
        with self.assertRaises(RuleError):
            save_talent(second, "brave", "higher",
                        make_talent(bonuses={"unknown":2}))
        self.assertEqual(first["jobs"]["brave"]["talents"]["base"]["requires"], [])
        self.assertEqual(self.data, self.before)

    def test_delete_talent_is_undoable_with_full_content_validation(self):
        doc = Document(Content.from_dict(self.data))
        doc.replace(save_talent(doc.data, "brave", "new_talent",
                                make_talent(jp=3), creating=True))
        self.assertIn("new_talent", doc.data["jobs"]["brave"]["talents"])
        doc.replace(delete_talent(doc.data, "brave", "new_talent"))
        self.assertNotIn("new_talent", doc.data["jobs"]["brave"]["talents"])
        doc.undo()
        self.assertIn("new_talent", doc.data["jobs"]["brave"]["talents"])
        doc.redo()
        self.assertNotIn("new_talent", doc.data["jobs"]["brave"]["talents"])

    def test_map_patrol_authoring_and_readonly_preview(self):
        route = parse_cells("2,1; 4,1; 5,1")
        valid = set_unit_ai(self.data, "garden", "grincheux",
                            roles=["protector", "leader"],route=route)
        self.assertEqual(valid["missions"][0]["units"][3]["patrol_route"],
                         tuple(tuple(point) for point in route))
        report = ai_preview(valid, "garden", "grincheux")
        self.assertEqual(report["mode"], "patrol")
        self.assertEqual(report["roles"], ["protector", "leader"])
        self.assertFalse(report["coordinated_active"])
        self.assertEqual(report["waypoints"], route)
        self.assertEqual(self.data, self.before)
        self.assertEqual(parse_cells(""), [])

    def test_invalid_patrol_waypoints_and_ruleset_rejected(self):
        for route in ("3,2; 4,2", "20,20; 1,1", "1,1; 1,1", "4,4", "1,0; -1,2"):
            with self.subTest(route=route), self.assertRaises(RuleError):
                set_unit_ai(self.data, "garden", "grincheux",
                            route=parse_cells(route))
        with self.assertRaises(RuleError):
            set_unit_ai(self.data, "garden", "grincheux",
                        behavior="coordinated", roles=["medic"])
        with self.assertRaises(RuleError):
            set_unit_ai(self.data, "garden", "grincheux",
                        roles=["medic", "medic"])
        self.assertEqual(self.data, self.before)


if __name__ == "__main__":
    unittest.main()
