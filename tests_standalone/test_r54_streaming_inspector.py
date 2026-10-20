"""R54.B: no-JSON project authoring, inspect LOD, prefetch and R1 history."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.world_streaming_authoring import (
    apply_streaming, inspect_streaming, manifest_from_routes,
    prefetch_order, preview_streaming,
)
from sporebound.model import RuleError
from sporebound.world_streaming import EXTENSION
from tests_standalone.test_r54_world_streaming import fixture


class WorldStreamingInspectorTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()
        self.editor = AuthoringSession.new(self.content, self.project)
        self.canonical = self.editor.snapshot().to_dict()["project"]

    def test_generate_cells_from_existing_bidirectional_r25_links(self):
        spec = manifest_from_routes(self.canonical)
        self.assertEqual(spec["start"], "arrival")
        self.assertEqual([c["id"] for c in spec["cells"]],
                         ["arrival", "forest", "pass"])
        self.assertEqual(spec["cells"][1]["neighbors"], ["arrival", "pass"])
        self.assertEqual(spec["cells"][0]["entities"], [])
        self.assertEqual(spec["max_cache_bytes"], 4 * 1024 * 1024)
        self.assertNotIn("world_stream", self.editor.snapshot().to_dict())

    def test_generate_fail_closed_on_unpaired_portals(self):
        changed = deepcopy(self.canonical)
        changed["scene_routes"]["links"] = [
            link for link in changed["scene_routes"]["links"]
            if link["id"] != "back_forest"]
        spec = manifest_from_routes(changed)
        self.assertEqual([c["id"] for c in spec["cells"]],
                         ["arrival", "forest"])
        bad = deepcopy(changed)
        bad["scene_routes"] = {}
        with self.assertRaises(RuleError):
            manifest_from_routes(bad)

    def test_preview_undo_redo_and_revision_conflicts(self):
        snap = self.editor.snapshot()
        spec = manifest_from_routes(self.canonical)
        spec["cells"][0]["region"] = "village"
        preview = preview_streaming(self.editor, spec,
                                    expected_revision=snap.revision)
        self.assertEqual(self.editor.revision, 0)
        self.assertEqual(preview.report["cells"], 3)
        apply_streaming(self.editor, preview)
        self.assertEqual(self.editor.revision, 1)
        current = self.editor.snapshot().to_dict()["project"]
        self.assertEqual(current["extensions"][EXTENSION]["data"]["cells"][0]["region"],
                         "village")
        with self.assertRaises((RuleError, ValueError, AuthoringError)):
            preview_streaming(self.editor, spec,
                              expected_revision=snap.revision)
        self.editor.undo()
        previous = self.editor.snapshot().to_dict()["project"]
        self.assertEqual(previous["extensions"][EXTENSION],
                         self.canonical["extensions"][EXTENSION])
        self.editor.redo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], current)

    def test_invalid_draft_never_mutates_live_pair(self):
        spec = manifest_from_routes(self.canonical)
        invalid = [
            lambda data: data["cells"][0].update(region="../bad"),
            lambda data: data["cells"][1]["neighbors"].remove("pass"),
            lambda data: data["cells"][0].update(scene="missing"),
            lambda data: data.update(max_cache_bytes=1),
        ]
        before = self.editor.snapshot().to_dict()
        for modify in invalid:
            candidate = deepcopy(spec)
            modify(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(
                    (RuleError, AuthoringError)):
                preview_streaming(self.editor, candidate)
            self.assertEqual(self.editor.snapshot().to_dict(), before)

    def test_graph_lod_and_cache_telemetry_are_deterministic(self):
        spec = manifest_from_routes(self.canonical)
        report = inspect_streaming(spec, self.canonical,
                                   focus="pass", zoom=1.0)
        self.assertEqual(report["prefetch"], ["pass", "forest"])
        rows = {cell["id"]: cell for cell in report["cells"]}
        self.assertEqual(rows["pass"]["lod"], "detail")
        self.assertEqual(rows["forest"]["lod"], "overview")
        self.assertEqual(rows["arrival"]["lod"], "outline")
        self.assertEqual(rows["arrival"]["map_size"], [4, 4])
        self.assertEqual(rows["arrival"]["tile_preview"][1], "..#.")
        self.assertEqual(report["cache"]["resident_bytes"], 0)
        self.assertEqual(len(report["edges"]), 2)
        self.assertGreater(report["estimated_total_bytes"], 0)
        self.assertEqual(report, inspect_streaming(
            spec, self.canonical, focus="pass", zoom=1.0))
        zoomed = inspect_streaming(spec, self.canonical,
                                 focus="forest", zoom=2.0)
        self.assertTrue(all(row["lod"] == "detail"
                            for row in zoomed["cells"]))
        with self.assertRaises(RuleError):
            inspect_streaming(spec, self.canonical, zoom=True)

    def test_prefetch_is_bounded_and_readonly(self):
        spec = manifest_from_routes(self.canonical)
        copy = deepcopy(spec)
        self.assertEqual(prefetch_order(spec, "forest", radius=2, limit=2),
                         ["forest", "arrival"])
        self.assertEqual(prefetch_order(spec, "pass", radius=0), ["pass"])
        self.assertEqual(spec, copy)
        for radius, limit in ((-1, 2), (9, 8), (1, 0), (1, 9)):
            with self.subTest(radius=radius, limit=limit):
                with self.assertRaises(RuleError):
                    prefetch_order(spec, "forest", radius=radius, limit=limit)

    def test_reject_corrupt_telemetry(self):
        spec = manifest_from_routes(self.canonical)
        for data in (
            {"loaded": ["unknown"], "pending": 0, "resident_bytes": 0,
             "budget_bytes": spec["max_cache_bytes"]},
            {"loaded": [], "pending": 100, "resident_bytes": 0,
             "budget_bytes": spec["max_cache_bytes"]},
            {"loaded": [], "pending": 0,
             "resident_bytes": spec["max_cache_bytes"] + 1,
             "budget_bytes": spec["max_cache_bytes"]},
        ):
            with self.subTest(data=data), self.assertRaises(RuleError):
                inspect_streaming(spec, self.canonical, cache_stats=data)


if __name__ == "__main__":
    unittest.main()
