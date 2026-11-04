"""Headless proof that Studio visual goldens need a separate human approval."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

from scripts.studio_visual_goldens import (
    EXPECTED, PROFILE, approve, image_diff, load_reference, review,
)


@unittest.skipUnless(Image is not None, "Pillow is optional outside visual CI")
class StudioVisualGoldenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "candidates"
        self.refs = Path(self.tmp.name) / "approved"
        self.folder.mkdir()
        frames = []
        for i, name in enumerate(EXPECTED):
            picture = Image.new("RGB", (1280, 850), (235, 235, 235))
            draw = ImageDraw.Draw(picture)
            draw.rectangle((150, 120, 1080, 680), fill=(63 + i, 140, 93))
            draw.text((200, 300), name, fill="white")
            dest = self.folder / (name + ".png")
            picture.save(dest)
            frames.append({
                "name": name, "file": name + ".png",
                "image_sha256": sha256(dest.read_bytes()).hexdigest(),
                "canvas_items": 160, "map_luma_stddev": 20.0,
                "projection": "iso" if "iso" in name else "2d",
                "playtest": name.endswith("playtest"),
            })
        (self.folder / "manifest.json").write_text(json.dumps({
            "schema": "drawtemp-studio-pr-visual-v1",
            "capture": "real Tk window via X11 ImageGrab",
            "mission": "fortified_village_3717a",
            "frames": frames,
        }), encoding="utf-8")

    def test_missing_reference_is_review_required_never_pass(self):
        self.assertEqual(review(self.folder, self.refs), 0)
        r = json.loads((self.folder / "visual-review.json").read_text())
        self.assertEqual(r["result"], "review_required")
        self.assertFalse(r["reference_approved"])
        self.assertTrue((self.folder / "index.html").is_file())
        self.assertFalse((self.refs / PROFILE / "manifest.json").exists())
        self.assertEqual(review(self.folder, self.refs, require_approved=True), 1)

    def test_approval_requires_review_and_all_four_images(self):
        with self.assertRaises(ValueError):
            approve(self.folder, self.refs, reviewer="")
        manifest = approve(self.folder, self.refs, reviewer="Human reviewer")
        self.assertTrue(manifest.is_file())
        self.assertEqual(load_reference(self.refs)["reviewer"], "Human reviewer")
        with self.assertRaises(FileExistsError):
            approve(self.folder, self.refs, reviewer="Someone else")
        self.assertEqual(review(self.folder, self.refs), 0)
        report = json.loads((self.folder / "visual-review.json").read_text())
        self.assertEqual(report["result"], "pass")
        self.assertTrue((self.folder / "comparisons" /
                         (EXPECTED[0] + ".png")).is_file())

    def test_pixel_regression_produces_before_after_diff_and_fails(self):
        approve(self.folder, self.refs, reviewer="Human reviewer")
        path = self.folder / (EXPECTED[0] + ".png")
        with Image.open(path) as pic:
            altered = pic.copy()
        ImageDraw.Draw(altered).rectangle((300, 300, 600, 600), fill="#ff0033")
        altered.save(path)
        manifest_path = self.folder / "manifest.json"
        data = json.loads(manifest_path.read_text())
        data["frames"][0]["image_sha256"] = sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(data))
        self.assertEqual(review(self.folder, self.refs), 1)
        report = json.loads((self.folder / "visual-review.json").read_text())
        self.assertEqual(report["result"], "fail")
        self.assertFalse(report["cases"][EXPECTED[0]]["metrics"]["passed"])
        self.assertTrue((self.folder / "diff" /
                         (EXPECTED[0] + ".png")).is_file())
        self.assertTrue((self.folder / "comparisons" /
                         (EXPECTED[0] + ".png")).is_file())
        self.assertEqual(
            Image.open(self.folder / "comparisons" / (EXPECTED[0] + ".png")).size,
            (3840, 902))

    def test_corrupted_approved_png_is_rejected(self):
        approve(self.folder, self.refs, reviewer="Human reviewer")
        path = self.refs / PROFILE / (EXPECTED[0] + ".png")
        path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            load_reference(self.refs)

    def test_incomplete_candidate_cannot_be_approved(self):
        (self.folder / (EXPECTED[3] + ".png")).unlink()
        with self.assertRaises(FileNotFoundError):
            approve(self.folder, self.refs, reviewer="Human reviewer")
        self.assertFalse((self.refs / PROFILE / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
