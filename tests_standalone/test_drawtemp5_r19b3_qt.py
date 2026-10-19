"""R19.B3: shared Qt/Player renderer displays multiple distinct R7 packs."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.bestiary_r19 import export_role
from drawtemp.assets.characters import export_pack, starter_library
from tests_standalone.test_drawtemp5_r19b3_bestiary import paint_role

HAS_QT = importlib.util.find_spec("PySide6") is not None
HAS_PIL = importlib.util.find_spec("PIL") is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT and HAS_PIL, "Requires PySide6 and Pillow")
class R19B3MultiActorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication(["r19b3-qt"])

    def test_jeanne_and_wolf_use_the_same_atlas_delegate_without_replay_edits(self):
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "art"
            source.mkdir()
            paint_role(source, "wolf")
            export_role(source, root / "wolf-pack", "wolf")
            export_pack(starter_library()["jeanne"], ROOT, root / "jeanne-pack")
            scene = {
                "mission": "r19b3-studio-player", "width": 4, "height": 4,
                "revision": 42, "objects": [],
                "tiles": [
                    {"x": x, "y": y, "surface": "grass", "height": 0,
                     "feature": "", "blocked": False, "cover": 0,
                     "hazard": 0, "goal": False}
                    for x in range(4) for y in range(4)
                ],
                "actors": [
                    {"id": actor, "name": actor, "x": col, "y": 1,
                     "direction": "west", "team": team, "alive": True, "level": 0}
                    for actor, col, team in (
                        ("jeanne", 1, "player"), ("wolf", 2, "enemy"),
                        ("unmapped", 3, "enemy"))
                ],
            }
            renderer = make_controller(
                scene, character_pack=root / "jeanne-pack",
                character_packs={"wolf": root / "wolf-pack"})
            try:
                by_id = {row["id"]: row for row in renderer.items if row["kind"] == "actor"}
                self.assertTrue(by_id["jeanne"]["spriteReady"])
                self.assertTrue(by_id["wolf"]["spriteReady"])
                self.assertNotEqual(by_id["jeanne"]["imageUrl"], by_id["wolf"]["imageUrl"])
                self.assertNotIn("spriteReady", by_id["unmapped"])
                self.assertTrue(renderer.play_actor("wolf", "attack"))
                self.assertFalse(renderer.play_actor("unmapped", "attack"))
                self.assertEqual(renderer.characterId, "jeanne")
                self.assertEqual(renderer.characterOutfits, ["historical"])

                attack = {"kind": "attack", "actor": "wolf", "team": "enemy",
                          "start": [2, 1], "end": [1, 1], "duration_ms": 270}
                sample = renderer.visualClipFrame(attack, .5)
                self.assertEqual(sample["source"], "character_pack")
                self.assertEqual(sample["direction"], "west")
                self.assertEqual(sample["pose"], "attack")
                self.assertIn("wolf-pack", sample["imageUrl"])
                self.assertEqual(scene["revision"], 42)
                self.assertEqual(scene["actors"][1]["x"], 2)

                # No accidental pack collision or misidentified actor.
                with self.assertRaises(ValueError):
                    make_controller(scene, character_pack=root / "jeanne-pack",
                                    character_packs={"jeanne": root / "wolf-pack"})
                with self.assertRaises(ValueError):
                    make_controller(scene, character_pack=root / "jeanne-pack",
                                    character_packs={"jeanne": root / "jeanne-pack"})
            finally:
                renderer._sprite_timer.stop()

    def test_missing_optional_enemy_frame_does_not_repaint_as_jeanne(self):
        from drawtemp.assets.character_runtime import CharacterPack
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "art"
            source.mkdir()
            paint_role(source, "wolf")
            export_role(source, root / "wolf-pack", "wolf")
            wolf = CharacterPack(root / "wolf-pack")
            wolf._clips.pop(("default", "idle", "west"))
            scene = {
                "mission": "r19-missing", "width": 1, "height": 1,
                "revision": 1, "objects": [],
                "tiles": [{"x": 0, "y": 0, "surface": "grass",
                           "height": 0, "feature": "", "blocked": False,
                           "cover": 0, "hazard": 0, "goal": False}],
                "actors": [{"id": "wolf", "name": "wolf", "x": 0, "y": 0,
                            "team": "enemy", "alive": True, "level": 0,
                            "direction": "west"}],
            }
            renderer = make_controller(scene, character_packs={"wolf": wolf})
            try:
                row = next(row for row in renderer.items if row["kind"] == "actor")
                self.assertNotIn("spriteReady", row)
                self.assertEqual(renderer.visualClipFrame(
                    {"kind": "cast", "actor": "wolf", "start": [0, 0],
                     "end": [0, 0], "duration_ms": 290}, .5), {})
                self.assertEqual(scene["revision"], 1)
            finally:
                renderer._sprite_timer.stop()


if __name__ == "__main__":
    unittest.main()
