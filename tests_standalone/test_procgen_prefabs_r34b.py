"""R34.B: canonical references, door sockets, determinism and explicit refusal."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from drawtemp.sdk.procgen import ProcGenError, ProcGenRecipe
from drawtemp.sdk.procgen_prefabs import (
    demo_library, generate_with_prefabs, preview_seeds,
    validate_library, verify_with_prefabs,
)


class PrefabGenerationTests(unittest.TestCase):
    def setUp(self):
        self.recipe = ProcGenRecipe(seed=17, rooms=10, branches=3,
                                    locked_goal=True, encounter_budget=5)
        self.library = demo_library()

    def test_determinism_reachability_and_matching_100_seeds(self):
        first = preview_seeds(self.recipe, self.library, list(range(100)), biome="ruins")
        again = preview_seeds(self.recipe, deepcopy(self.library),
                              list(range(100)), biome="ruins")
        self.assertEqual(first, again)
        self.assertTrue(all(x["passed"] for x in first), first)
        self.assertEqual(len({x["digest"] for x in first}), 100)
        for seed in range(100):
            recipe = {**self.recipe.to_dict(), "seed": seed}
            layout = generate_with_prefabs(recipe, self.library, biome="ruins")
            self.assertTrue(verify_with_prefabs(recipe, self.library, layout, biome="ruins"))
            self.assertEqual(layout["route"][0], 0)
            self.assertEqual(layout["rooms"][layout["route"][-1]]["role"], "exit")
            self.assertTrue(any(r["role"] == "goal" for r in layout["rooms"]))
            for room in layout["rooms"]:
                self.assertEqual(len(room["doors"]), len(room["neighbors"]))
                for door in room["doors"]:
                    back = next(d for d in layout["rooms"][door["to"]]["doors"]
                                if d["to"] == room["id"])
                    self.assertEqual(door["kind"], back["kind"])

    def test_library_order_never_changes_output_or_registry(self):
        lib = deepcopy(self.library)
        a = generate_with_prefabs(self.recipe, lib, biome="ruins")
        lib["prefabs"].reverse()
        b = generate_with_prefabs(self.recipe, lib, biome="ruins")
        self.assertEqual(a, b)
        self.assertEqual(self.library["prefabs"][0]["id"], "entry")
        tampered = deepcopy(a)
        tampered["rooms"][0]["prefab_id"] = "forged"
        with self.assertRaises(ProcGenError) as exc:
            verify_with_prefabs(self.recipe, lib, tampered, biome="ruins")
        self.assertEqual(exc.exception.code, "invalid_generation")

    def test_incompatible_doors_and_missing_role_fail_explicitly(self):
        bad = deepcopy(self.library)
        goal = next(x for x in bad["prefabs"] if x["id"] == "boss")
        goal["ports"] = ["stone", "stone"]
        with self.assertRaises(ProcGenError) as exc:
            generate_with_prefabs(self.recipe, bad, biome="ruins")
        self.assertEqual(exc.exception.code, "unsatisfiable_prefabs")
        no_key = deepcopy(self.library)
        no_key["prefabs"] = [p for p in no_key["prefabs"] if p["id"] != "keyroom"]
        with self.assertRaises(ProcGenError) as exc:
            generate_with_prefabs(self.recipe, no_key, biome="ruins")
        self.assertEqual(exc.exception.code, "unsatisfiable_prefabs")
        with self.assertRaises(ProcGenError) as exc:
            generate_with_prefabs(self.recipe, self.library, biome="ruins", search_budget=1)
        self.assertEqual(exc.exception.code, "search_budget_exhausted")
        rejected = preview_seeds(self.recipe, bad, [17, 18], biome="ruins")
        self.assertFalse(any(row["passed"] for row in rejected))
        self.assertEqual([row["seed"] for row in rejected], [17, 18])
        self.assertTrue(all(row["error_code"] == "unsatisfiable_prefabs"
                            for row in rejected))

    def test_strict_schema_validation_rejects_untrusted_fields_and_types(self):
        for mutation in (
            lambda x: x.update({"extra": "not accepted"}),
            lambda x: x.update({"schema_version": 2}),
            lambda x: x["prefabs"][0].update({"roles": [["entry"]]}),
            lambda x: x["prefabs"][0].update({"biomes": [["ruins"]]}),
            lambda x: x["prefabs"][0].update({"ports": [{"arch": True}]}),
            lambda x: x["prefabs"][0].update({"roles": ["entry", "entry"]}),
            lambda x: x["prefabs"][0].update({"tags": ["invalid tag"]}),
            lambda x: x["prefabs"].append(deepcopy(x["prefabs"][0])),
        ):
            bad = deepcopy(self.library)
            mutation(bad)
            with self.subTest(bad=bad), self.assertRaises(ProcGenError):
                validate_library(bad)
        with self.assertRaises(ProcGenError):
            preview_seeds(self.recipe, self.library, list(range(501)), biome="ruins")
        with self.assertRaises(ProcGenError):
            generate_with_prefabs(self.recipe, self.library, biome="bad/path")

    def test_real_canonical_asset_and_content_refs(self):
        from sporebound.assets import AssetRegistry

        registry = AssetRegistry({
            "version": 1, "entries": [
                {"id": "ruins_tile", "kind": "sprite", "path": "art/ruins.png"},
            ], "bindings": {},
        })
        content = SimpleNamespace(missions={"castle_room": object()})
        project = SimpleNamespace(asset_registry=lambda: registry)
        library = deepcopy(self.library)
        for prefab in library["prefabs"]:
            prefab.update(asset_id="ruins_tile", mission_id="castle_room")
        original = deepcopy(library)
        generated = generate_with_prefabs(self.recipe, library, biome="ruins",
                                          content=content, project=project)
        self.assertEqual(original, library)
        self.assertEqual(registry.require_reference("ruins_tile")["kind"], "sprite")
        self.assertTrue(all(r["mission_id"] == "castle_room" for r in generated["rooms"]))
        self.assertTrue(all(r["asset_id"] == "ruins_tile" for r in generated["rooms"]))
        for wrong in ("missing", "Castle_Room"):
            bad = deepcopy(library)
            bad["prefabs"][0]["mission_id"] = wrong
            with self.assertRaises(ProcGenError) as exc:
                generate_with_prefabs(self.recipe, bad, biome="ruins",
                                      content=content, project=project)
            self.assertEqual(exc.exception.code, "unknown_reference")
        library["prefabs"][0]["asset_id"] = "missing"
        with self.assertRaises(ProcGenError) as exc:
            validate_library(library, content=content, project=project)
        self.assertEqual(exc.exception.code, "unknown_reference")


if __name__ == "__main__":
    unittest.main()
