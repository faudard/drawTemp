"""R34.A headless contract tests (no Qt, external assets or filesystem writes)."""
from copy import deepcopy
import json
import unittest

from drawtemp.sdk.procgen import (
    ALGORITHM, ProcGenError, ProcGenRecipe, generate, generate_batch, verify,
)


class ProceduralGeneratorTests(unittest.TestCase):
    def recipe(self, **changes):
        return ProcGenRecipe.from_dict({"seed": 451, **changes})

    def test_strict_schema_and_seed_roundtrip(self):
        recipe = self.recipe(rooms=12, branches=3, locked_goal=True)
        self.assertEqual(ProcGenRecipe.from_dict(json.loads(json.dumps(recipe.to_dict()))), recipe)
        self.assertEqual(recipe.algorithm, ALGORITHM)
        for changed in ({"extra": 1}, {"seed": True}, {"seed": -1},
                        {"seed": 2**63}, {"rooms": 65}, {"rooms": 3, "branches": 1},
                        {"locked_goal": 1}, {"algorithm": "future-version"},
                        {"schema_version": 2}, {"locked_goal": True, "branches": 0},
                        {"encounter_budget": 257}, {"rooms": 4, "loot_budget": 45}):
            with self.subTest(changed=changed), self.assertRaises(ProcGenError):
                ProcGenRecipe.from_dict({**recipe.to_dict(), **changed})
        with self.assertRaises(ProcGenError):
            ProcGenRecipe.from_dict(["not", "a", "mapping"])

    def test_reproducible_100_seeds_both_unlocked_and_locked(self):
        for locked in (False, True):
            recipe = self.recipe(rooms=16, branches=4, locked_goal=locked,
                                 encounter_budget=80, loot_budget=60)
            first = generate_batch(recipe, list(range(100)))
            second = generate_batch(recipe.to_dict(), list(range(100)))
            self.assertEqual(first, second)
            self.assertEqual(len({row["digest"] for row in first}), 100)
            for seed, row in enumerate(first):
                with self.subTest(seed=seed, locked=locked):
                    self.assertEqual(row["recipe"]["seed"], seed)
                    self.assertEqual(verify({**recipe.to_dict(), "seed": seed}, row), row["route"])
                    self.assertEqual(sum(x["encounters"] for x in row["rooms"]), 80)
                    self.assertEqual(sum(x["loot"] for x in row["rooms"]), 60)
                    self.assertIn(next(x["id"] for x in row["rooms"] if x["role"] == "goal"), row["route"])
                    self.assertEqual(row["route"][0], 0)
                    self.assertEqual(row["route"][-1], row["recipe"]["rooms"] - row["recipe"]["branches"] - 1)
                    self.assertLessEqual(max(len(x["neighbors"]) for x in row["rooms"]), 4)
                    if locked:
                        self.assertTrue(row["locks"])
                        self.assertEqual(sum("goal_key" in x["keys"] for x in row["rooms"]), 1)

    def test_generated_objects_detached_and_integrity_check(self):
        recipe = self.recipe(locked_goal=True)
        first = generate(recipe)
        first_copy = deepcopy(first)
        self.assertEqual(verify(recipe, first), first["route"])
        first["rooms"][0]["neighbors"].clear()
        with self.assertRaises(ProcGenError) as caught:
            verify(recipe, first)
        self.assertEqual(caught.exception.code, "invalid_generation")
        self.assertEqual(generate(recipe), first_copy)
        tampered = deepcopy(first_copy)
        tampered["digest"] = "0" * 64
        with self.assertRaises(ProcGenError):
            verify(recipe, tampered)
        with self.assertRaises(ProcGenError):
            verify({**recipe.to_dict(), "seed": 15}, first_copy)

    def test_budget_and_batch_rejection(self):
        recipe = self.recipe()
        for seeds in ([], list(range(501)), [1, True], [-1], [2**63], tuple(range(2))):
            with self.subTest(seeds_len=len(seeds)), self.assertRaises(ProcGenError):
                generate_batch(recipe, seeds)
        for bad in ({"seed": 5, "rooms": 64, "branches": 61, "locked_goal": True},
                    {"seed": 0, "rooms": 3, "encounter_budget": 17}):
            with self.assertRaises(ProcGenError):
                generate(bad)

    def test_different_seeds_and_optional_lock(self):
        recipe = self.recipe(rooms=10, branches=2, locked_goal=False)
        a = generate(recipe)
        b = generate({**recipe.to_dict(), "seed": recipe.seed + 1})
        self.assertNotEqual(a["digest"], b["digest"])
        self.assertEqual(a["locks"], [])
        self.assertEqual([x["role"] for x in a["rooms"]].count("key"), 0)


if __name__ == "__main__":
    unittest.main()
