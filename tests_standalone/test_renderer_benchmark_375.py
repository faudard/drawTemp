"""Renderer prototype workload is reproducible without GUI dependencies."""
import unittest
from scripts.benchmark_renderers_375 import positions, quantile


class RendererBenchmarkContractTests(unittest.TestCase):
    def test_identical_layout_per_backend(self):
        self.assertEqual(positions(20, 0, 1), positions(20, 0, 1))
        self.assertNotEqual(positions(20, 0, 1), positions(20, 1, 1))
        for scale in (1, 2):
            values = positions(200, 100, scale)
            self.assertEqual(len(values), 200)
            for x, y in values:
                self.assertTrue(0 <= x <= 800 - 64 * scale)
                self.assertTrue(0 <= y <= 600 - 64 * scale)

    def test_percentile_monotonicity(self):
        samples = [13, 1, 3, 20, 7]
        self.assertEqual(quantile(samples, 0), 1)
        self.assertEqual(quantile(samples, 1), 20)
        self.assertGreaterEqual(quantile(samples, 0.95), quantile(samples, 0.50))


if __name__ == "__main__":
    unittest.main()
