"""3.7.32C: value-based Workspace index invalidation and lookup parity."""
from copy import deepcopy
import unittest

from scripts.profile_scale_3732 import make_workspace
from sporebound.model import RuleError
from sporebound.studio_index4 import StudioIndex, WorkspaceModelCache, fold


class WorkspaceModelCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content, cls.project = make_workspace(8)

    def setUp(self):
        self.raw = deepcopy(self.content.to_dict())
        self.project = type(self.project).from_dict(
            deepcopy(self.project.to_dict()), self.content)
        self.cache = WorkspaceModelCache()

    def test_value_equal_dicts_reuse_model_without_revalidation(self):
        first = self.cache.get(self.raw, self.project)
        self.assertEqual(self.cache.builds, 1)
        self.assertIs(self.cache.get(deepcopy(self.raw), self.project), first)
        self.assertEqual(self.cache.builds, 1)
        self.cache.invalidate()
        self.assertIsNot(self.cache.get(self.raw, self.project), first)
        self.assertEqual(self.cache.builds, 2)

    def test_in_place_content_and_project_mutations_refresh_view(self):
        initial = self.cache.get(self.raw, self.project)
        target = next(row for row in self.raw["missions"]
                      if row["id"] == "scale_002")
        target["name"] = "La nouvelle place"
        changed = self.cache.get(self.raw, self.project)
        self.assertIsNot(changed, initial)
        self.assertEqual(changed.nodes["mission:scale_002"].label,
                         "La nouvelle place")
        self.assertTrue(changed.search("nouvelle place"))
        self.project.title = "Autre royaume"
        renamed = self.cache.get(self.raw, self.project)
        self.assertEqual(renamed.nodes["game:settings"].label, "Autre royaume")
        self.assertEqual(self.cache.builds, 3)

    def test_invalid_edit_never_overwrites_previous_valid_cache(self):
        valid = self.cache.get(self.raw, self.project)
        broken = deepcopy(self.raw)
        target = next(row for row in broken["missions"]
                      if row["id"] == "scale_002")
        target["next_missions"] = ["does_not_exist"]
        with self.assertRaises(RuleError):
            self.cache.get(broken, self.project)
        self.assertIs(self.cache.get(self.raw, self.project), valid)
        self.assertEqual(self.cache.builds, 1)

    def test_search_and_reference_indexes_match_legacy_full_scans(self):
        index = StudioIndex(self.content, self.project)
        for query in ("", "scale", "performance", "campaign", "MISSING"):
            terms = [fold(part) for part in query.split()]
            expected = tuple(node for _, node in sorted(index.nodes.items())
                             if all(term in fold(' '.join(
                                 (node.key, node.label, node.summary)))
                                    for term in terms))
            self.assertEqual(index.search(query), expected)
        for key in [*index.nodes, "not_present"]:
            self.assertEqual(index.outgoing(key), tuple(
                edge for edge in index.references if edge.source == key))
            self.assertEqual(index.incoming(key), tuple(
                edge for edge in index.references if edge.target == key))


if __name__ == "__main__":
    unittest.main()
