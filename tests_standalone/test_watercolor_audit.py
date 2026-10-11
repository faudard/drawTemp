"""Optional-art audit tests: no Pillow or GUI dependency for geometry checks."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("watercolor_audit", ROOT / "scripts/audit_watercolor_pack.py")
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeCrop:
    def __init__(self, opaque, total):
        self.opaque, self.total = opaque, total

    def histogram(self):
        bins = [0] * 256
        bins[0] = self.total - self.opaque
        bins[255] = self.opaque
        return bins


class FakeImage:
    size = (4, 4)
    pixels = [
        [255, 255, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]

    def convert(self, mode):
        assert mode == "RGBA"
        return self

    def getchannel(self, channel):
        assert channel == "A"
        return self

    def crop(self, box):
        left, top, right, bottom = box
        alpha = [v for row in self.pixels[top:bottom] for v in row[left:right]]
        return FakeCrop(sum(v >= 128 for v in alpha), len(alpha))


class WatercolorAuditTests(unittest.TestCase):
    def test_each_canvas_border_is_measured_separately(self):
        self.assertEqual(audit.analyse_alpha(FakeImage()), {
            "top": 0.5, "right": 0., "bottom": 0., "left": 0.25})

    def test_tiny_frame_is_rejected(self):
        image = FakeImage()
        image.size = (1, 4)
        with self.assertRaisesRegex(ValueError, "at least 2x2"):
            audit.analyse_alpha(image)


if __name__ == "__main__":
    unittest.main()
