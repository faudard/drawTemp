"""R19.B3 bestiary import: eight roles, no fake mirrors, canonical R7 runtime."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.bestiary_r19 import (
    ROLE_ACTIONS, SIZE, audit_role, audit_roster, export_role, role_recipe,
)
from drawtemp.assets.character_runtime import CharacterPack
from drawtemp.assets.characters import DIRECTIONS, validate

HAS_PIL = importlib.util.find_spec("PIL") is not None


def paint_role(root, role):
    """Real RGBA directional test fixtures; never bundled as release art."""
    from PIL import Image, ImageDraw
    side = SIZE[role]
    for a, action in enumerate(ROLE_ACTIONS[role]):
        for d, direction in enumerate(DIRECTIONS):
            for phase in range(2):
                canvas = Image.new("RGBA", (side, side))
                brush = ImageDraw.Draw(canvas)
                c = ((32 + a * 31 + d * 4) % 255,
                     (49 + d * 41 + phase * 17) % 255,
                     (79 + phase * 73 + a * 9) % 255, 255)
                x = (d + 1) * side // 12 + phase * 3
                brush.polygon([
                    (x, side // 6), (x + side // 4, side // 5),
                    (x + side // 3, side // 2 + phase * 3),
                    (x + side // 8, side * 4 // 5)], fill=c)
                brush.rectangle((10 + phase, side * 4 // 5,
                                 side // 2 + d, side - 3), fill=c)
                location = root / role / direction / f"{action}_{phase}.png"
                location.parent.mkdir(parents=True, exist_ok=True)
                canvas.save(location)


@unittest.skipUnless(HAS_PIL, "Pillow is needed for source pixel certification")
class BestiaryR19Tests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name) / "authored"
        self.root.mkdir()

    def test_eight_role_recipes_are_r7_v1_and_require_all_cardinal_views(self):
        self.assertEqual(len(ROLE_ACTIONS), 8)
        self.assertEqual(set(ROLE_ACTIONS),
                         {"wolf", "bandit", "archer", "spearman", "knight",
                          "healer", "officer", "boss"})
        for role in ROLE_ACTIONS:
            recipe = role_recipe(role)
            self.assertEqual(validate(recipe), recipe)
            self.assertEqual(recipe["pivot"], [SIZE[role] // 2, SIZE[role] - 1])
            for action in ROLE_ACTIONS[role]:
                clip = recipe["variants"]["default"]["clips"][action]
                self.assertEqual(set(clip["directions"]), set(DIRECTIONS))
                self.assertEqual(len(clip["directions"]["south"]), 2)
        with self.assertRaises(ValueError):
            role_recipe("invented")

    def test_existing_single_view_or_absent_assets_are_blocked(self):
        report = audit_roster(self.root)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(set(report["roles"]), set(ROLE_ACTIONS))
        self.assertEqual(report["roles"]["wolf"]["status"], "blocked")
        self.assertEqual(report["redistribution_rights"], "not_assessed")
        self.assertTrue(any(x["code"] == "missing_or_invalid_frame"
                            for x in report["roles"]["wolf"]["issues"]))

    def test_verified_wolf_exports_to_existing_r7_runtime_without_edits(self):
        paint_role(self.root, "wolf")
        source = self.root / "wolf/south/attack_0.png"
        original = sha256(source.read_bytes()).hexdigest()
        report = audit_role(self.root, "wolf")
        self.assertEqual(report["status"], "candidate_ready", report["issues"])
        self.assertEqual(report["human_art_approval"], "not_assessed")
        self.assertEqual(report["expected_frames"], 40)
        target = Path(self.work.name) / "published-wolf"
        exported = export_role(self.root, target, "wolf")
        self.assertEqual(exported["status"], "candidate_ready")
        self.assertEqual(sha256(source.read_bytes()).hexdigest(), original)
        pack = CharacterPack(target)
        self.assertEqual(pack.character_id, "wolf")
        self.assertEqual(pack.variants, ("default",))
        for action in ROLE_ACTIONS["wolf"]:
            for direction in DIRECTIONS:
                first = pack.sample(variant="default", action=action,
                                    direction=direction, elapsed_ms=0)
                last = pack.sample(variant="default", action=action,
                                   direction=direction,
                                   elapsed_ms=pack.duration("default", action, direction) // 2)
                self.assertTrue(first["spriteReady"])
                self.assertNotEqual(first["spriteRegion"], last["spriteRegion"])
                self.assertEqual(first["spritePivot"], [32, 63])
        proof = json.loads((target / "bestiary-provenance.json").read_text())
        self.assertEqual(len(proof["source_sha256"]), 40)
        self.assertFalse(proof["redistribution_approved"])
        self.assertEqual(proof["human_art_approval"], "pending")
        with self.assertRaises(ValueError):
            export_role(self.root, target, "wolf")

    def test_relabelled_and_exact_mirrored_views_are_rejected(self):
        from PIL import Image, ImageOps
        paint_role(self.root, "wolf")
        for phase in range(2):
            south = self.root / f"wolf/south/attack_{phase}.png"
            north = self.root / f"wolf/north/attack_{phase}.png"
            north.write_bytes(south.read_bytes())
        report = audit_role(self.root, "wolf")
        self.assertIn("recycled_direction", {x["code"] for x in report["issues"]})
        paint_role(self.root, "wolf")
        for phase in range(2):
            south = self.root / f"wolf/south/attack_{phase}.png"
            north = self.root / f"wolf/north/attack_{phase}.png"
            with Image.open(south) as frame:
                ImageOps.mirror(frame).save(north)
        report = audit_role(self.root, "wolf")
        self.assertEqual(report["status"], "blocked")
        self.assertIn("mirrored_direction", {x["code"] for x in report["issues"]})

    def test_static_recycled_action_and_wrong_dimensions_block(self):
        from PIL import Image
        paint_role(self.root, "wolf")
        same = self.root / "wolf/east/idle_0.png"
        (self.root / "wolf/east/idle_1.png").write_bytes(same.read_bytes())
        for phase in range(2):
            path = self.root / f"wolf/west/hit_{phase}.png"
            path.write_bytes((self.root / f"wolf/west/attack_{phase}.png").read_bytes())
        Image.new("RGBA", (32, 32), (70, 70, 70, 255)).save(
            self.root / "wolf/north/death_1.png")
        issues = {x["code"] for x in audit_role(self.root, "wolf")["issues"]}
        self.assertTrue({"static_animation", "recycled_action",
                         "missing_or_invalid_frame"} <= issues)

    def test_symlink_and_blank_frames_fail_closed(self):
        from PIL import Image
        paint_role(self.root, "wolf")
        path = self.root / "wolf/east/walk_1.png"
        Image.new("RGBA", (64, 64)).save(path)
        self.assertEqual(audit_role(self.root, "wolf")["status"], "blocked")
        self.assertIn("missing_or_invalid_frame",
                      {x["code"] for x in audit_role(self.root, "wolf")["issues"]})
        try:
            path.unlink()
            path.symlink_to(self.root / "wolf/south/walk_0.png")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this host")
        self.assertIn("missing_or_invalid_frame",
                      {x["code"] for x in audit_role(self.root, "wolf")["issues"]})

    def test_boss_size_and_healer_r7_required_attack(self):
        self.assertEqual(SIZE["boss"], 128)
        self.assertIn("attack", ROLE_ACTIONS["healer"])
        self.assertIn("magic", ROLE_ACTIONS["healer"])
        paint_role(self.root, "boss")
        self.assertEqual(audit_role(self.root, "boss")["status"], "candidate_ready")


if __name__ == "__main__":
    unittest.main()
