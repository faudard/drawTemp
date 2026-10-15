"""R14.5 explicit golden comparison tests (no self-updating baselines)."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.visual import compare_png

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt 6 is provided by the R14 matrix")
class VisualRegressionContractTests(unittest.TestCase):
    def test_exact_rgba_pixels_independent_of_png_encoding(self):
        from PySide6.QtGui import QImage, QColor
        with TemporaryDirectory() as folder:
            base = Path(folder) / "golden.png"
            actual = Path(folder) / "actual.png"
            a = QImage(12, 10, QImage.Format_RGBA8888)
            a.fill(QColor("#263c45"))
            self.assertTrue(a.save(str(base)))
            self.assertTrue(a.save(str(actual)))
            result = compare_png(actual, base, max_channel_delta=0,
                                 max_changed_fraction=0)
            self.assertTrue(result["passed"])
            self.assertEqual(result["changed_pixels"], 0)
            self.assertEqual(result["pixels"], 120)

    def test_tolerance_diff_and_failure_artifact(self):
        from PySide6.QtGui import QImage, QColor
        with TemporaryDirectory() as folder:
            base = Path(folder) / "golden.png"
            actual = Path(folder) / "actual.png"
            diff = Path(folder) / "diff.png"
            a = QImage(20, 20, QImage.Format_RGBA8888)
            a.fill(QColor("#264052"))
            self.assertTrue(a.save(str(base)))
            a.setPixelColor(7, 9, QColor("#e00000"))
            self.assertTrue(a.save(str(actual)))
            changed = compare_png(actual, base, max_channel_delta=12,
                                  max_changed_fraction=0, diff_path=diff)
            self.assertFalse(changed["passed"])
            self.assertEqual(changed["changed_pixels"], 1)
            self.assertAlmostEqual(changed["changed_fraction"], 1 / 400)
            self.assertTrue(diff.is_file())
            tolerated = compare_png(actual, base, max_channel_delta=12,
                                   max_changed_fraction=0.003)
            self.assertTrue(tolerated["passed"])
            self.assertRaises(ValueError, compare_png, actual, base,
                              max_channel_delta=256)

    def test_baseline_absence_and_dimension_mismatch_block(self):
        from PySide6.QtGui import QImage, QColor
        with TemporaryDirectory() as folder:
            golden = Path(folder) / "not-reviewed.png"
            actual = Path(folder) / "actual.png"
            sample = QImage(8, 8, QImage.Format_RGBA8888)
            sample.fill(QColor("#aaaaaa"))
            self.assertTrue(sample.save(str(actual)))
            with self.assertRaises(FileNotFoundError):
                compare_png(actual, golden)
            self.assertFalse(golden.exists(), "Never bootstrap a baseline from an actual")
            other = QImage(5, 8, QImage.Format_RGBA8888)
            other.fill(QColor("#aaaaaa"))
            self.assertTrue(other.save(str(golden)))
            with self.assertRaisesRegex(ValueError, "dimensions"):
                compare_png(actual, golden)


if __name__ == "__main__":
    unittest.main()
