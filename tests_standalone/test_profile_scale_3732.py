"""Contract tests for 3.7.32 Performance & Scale instrumentation (headless)."""
import unittest

from scripts.profile_scale_3732 import (
    make_event_graph, make_story_graph, make_workspace, measure_headless,
    percentiles,
)
from sporebound.event_graph import build_event_graph
from sporebound.story_graph import build_story_tree
from sporebound.studio_index4 import StudioIndex


class PerformanceScaleTests(unittest.TestCase):
    def test_tail_statistics_interpolate_without_dropping_spikes(self):
        stats = percentiles([1, 2, 3, 4, 100])
        self.assertEqual(stats["samples"], 5)
        self.assertEqual(stats["p50_ms"], 3)
        self.assertEqual(stats["max_ms"], 100)
        self.assertGreater(stats["p99_ms"], stats["p95_ms"])
        with self.assertRaises(ValueError):
            percentiles([])

    def test_workspace_index_is_derived_from_validated_documents(self):
        content, project = make_workspace(4)
        index = StudioIndex(content, project)
        for n in range(4):
            self.assertIn("mission:scale_%03d" % n, index.nodes)
        self.assertTrue(index.search("performance"))

    def test_event_and_story_graphs_use_canonical_projections(self):
        authored, mission = make_event_graph(8)
        events = build_event_graph(authored, mission)
        self.assertEqual(events["drawn_events"], 8)
        self.assertFalse(events["truncated"])
        story, root = make_story_graph(15)
        graph = build_story_tree(story, root)
        self.assertEqual(len(graph["nodes"]), 15)
        self.assertFalse(graph["truncated"])

    def test_headless_matrix_reports_latency_and_memory_without_mutation(self):
        measures = measure_headless(samples=2, resources=4, events=5,
                                   short_saves=2, long_saves=3)
        self.assertEqual(len(measures), 6)
        for row in measures:
            for key in ("p50_ms", "p95_ms", "p99_ms", "rss_bytes",
                        "python_traced_peak_bytes", "samples"):
                self.assertIn(key, row)
            self.assertGreaterEqual(row["p99_ms"], row["p95_ms"])
            self.assertEqual(row["samples"], 2)


if __name__ == "__main__":
    unittest.main()
