"""R55.B typed connection contracts independent of the Qt canvas."""
from copy import deepcopy
import unittest

from drawtemp.studio.system_design_graph import edit_link, links
from sporebound.model import RuleError
from tests_standalone.test_r55_system_design import system_spec


class R55GraphLinksTests(unittest.TestCase):
    SCENES = {"arrival", "outpost"}

    def test_add_replace_remove_recipe_ports_immutable_source(self):
        original = system_spec()
        source = ("resources", "ore")
        target = ("producers", "jeweler")
        changed = edit_link(original, source, target, quantity=3,
                            scenes=self.SCENES)
        self.assertNotIn("ore", original["producers"][1]["inputs"])
        self.assertEqual(changed["producers"][1]["inputs"]["ore"], 3)
        self.assertIn((source, target, 3), links(changed))
        changed = edit_link(changed, source, target, quantity=5,
                            scenes=self.SCENES)
        self.assertEqual(changed["producers"][1]["inputs"]["ore"], 5)
        removed = edit_link(changed, source, target, remove=True,
                            scenes=self.SCENES)
        self.assertEqual(removed, original)

    def test_cyclic_or_invalid_connection_never_mutates_original(self):
        original = system_spec()
        baseline = deepcopy(original)
        cases = [
            (("resources", "gem"), ("producers", "smelter"), 1),
            (("resources", "ingot"), ("resources", "ore"), 1),
            (("producers", "smelter"), ("merchants", "trader"), 1),
            (("resources", "missing"), ("producers", "smelter"), 1),
            (("resources", "ore"), ("producers", "smelter"), True),
            (("resources", "ore"), ("producers", "smelter"), 1001),
            (("resources", "ore"), ("producers", "smelter"), 0),
        ]
        for source, target, quantity in cases:
            with self.subTest(source=source, target=target, quantity=quantity):
                with self.assertRaises((RuleError, ValueError)):
                    edit_link(original, source, target, quantity=quantity,
                              scenes=self.SCENES)
                self.assertEqual(original, baseline)

    def test_resource_bindings_for_merchant_and_quest(self):
        original = system_spec()
        for category, ident in (("merchants", "trader"), ("quests", "delivery")):
            updated = edit_link(original, ("resources", "gem"),
                                (category, ident), scenes=self.SCENES)
            row = updated[category][0]
            self.assertEqual(row["resource"], "gem")
            self.assertEqual(original[category][0]["resource"], "ingot")
            self.assertIn((("resources", "gem"), (category, ident), None),
                          links(updated))
            with self.assertRaises(RuleError):
                edit_link(updated, ("resources", "gem"),
                          (category, ident), remove=True, scenes=self.SCENES)

    def test_mandatory_last_input_and_output_cannot_be_removed(self):
        original = system_spec()
        for source, target in (
            (("resources", "ore"), ("producers", "smelter")),
            (("producers", "smelter"), ("resources", "ingot")),
        ):
            with self.subTest(source=source, target=target):
                with self.assertRaises(RuleError):
                    edit_link(original, source, target, remove=True,
                              scenes=self.SCENES)
        self.assertEqual(original, system_spec())

    def test_order_is_stable_and_duplicate_free(self):
        spec = system_spec()
        self.assertEqual(links(spec), links(deepcopy(spec)))
        self.assertEqual(len(links(spec)), 6)
        self.assertEqual(len(set(links(spec))), 6)


if __name__ == "__main__":
    unittest.main()
