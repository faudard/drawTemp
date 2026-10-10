"""Regression tests for headless audio authoring and playback dispatch."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.audio_authoring import (
    bind_sound, import_sound, remove_sound, suggested_slots,
)
from sporebound.audio_stage import AudioStage
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class AudioAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)

    def _source(self, root, name="score.ogg"):
        source = root / name
        if name.lower().endswith(".ogg"):
            source.write_bytes(b"OggS" + b"audio-test")
        else:
            source.write_bytes(b"RIFF" + b"\x00" * 4 + b"WAVE" + b"data")
        return source

    def test_import_bind_unbind_and_roundtrip(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            src = self._source(root)
            updated = import_sound(self.project, self.content, src, root, "score")
            self.assertEqual(updated.assets["entries"][0], {
                "id": "score", "kind": "sound", "path": "assets/audio/score.ogg"})
            self.assertEqual(
                (root / "assets/audio/score.ogg").read_bytes(), src.read_bytes())
            self.assertFalse(self.project.assets)
            updated = bind_sound(updated, self.content, "title", "score")
            updated = bind_sound(updated, self.content, "mission_garden", "score")
            updated = bind_sound(updated, self.content, "music_scene_oath", "score")
            updated = bind_sound(updated, self.content, "scene_enter_oath", "score")
            path = root / "my.game.json"
            updated.save(path, self.content)
            restored = GameProject.load(path, self.content)
            self.assertEqual(restored.to_dict(), updated.to_dict())
            with self.assertRaises(RuleError):
                remove_sound(restored, self.content, "score")
            for slot in ("title", "mission_garden", "music_scene_oath", "scene_enter_oath"):
                restored = bind_sound(restored, self.content, slot)
            restored = remove_sound(restored, self.content, "score")
            self.assertEqual(restored.assets["entries"], [])
            self.assertTrue((root / "assets/audio/score.ogg").is_file())

    def test_refuses_unsafe_inputs_without_modifying_project(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = self._source(root, "hit.wav")
            for name in ("../escape", "impossible/name", "bad id"):
                with self.subTest(name=name), self.assertRaises(RuleError):
                    import_sound(self.project, self.content, source, root, name)
            corrupt = root / "broken.wav"
            corrupt.write_bytes(b"not-wav")
            with self.assertRaises(RuleError):
                import_sound(self.project, self.content, corrupt, root, "bad")
            updated = import_sound(self.project, self.content, source, root, "hit")
            with self.assertRaises(RuleError):
                import_sound(updated, self.content, source, root, "HIT")
            original = root / "assets/audio/hit.wav"
            with self.assertRaises(RuleError):
                import_sound(self.project, self.content, source, root, "hit")
            self.assertEqual(original.read_bytes(), source.read_bytes())
            with self.assertRaises(RuleError):
                bind_sound(updated, self.content, "battle", "unknown")
            with self.assertRaises(RuleError):
                bind_sound(updated, self.content, "../slot", "hit")

    def test_refuses_audio_directory_symlink_escape(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "game"
            root.mkdir()
            (root / "assets").mkdir()
            outside = Path(folder) / "outside"
            outside.mkdir()
            try:
                (root / "assets/audio").symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(RuleError):
                import_sound(self.project, self.content, self._source(root), root, "score")
            self.assertEqual(list(outside.iterdir()), [])

    def test_suggestions_derive_from_content_and_story(self):
        self.project.story = {
            "scenes": [{"id": "arrival", "title": "Arrivée", "speaker": "",
                        "text": "Bienvenue", "choices": [
                            {"id": "continue", "label": "Suite", "effects": []}]}],
            "entry_scenes": {}, "after_mission": {}
        }
        self.project.validate(self.content)
        music, effects = suggested_slots(self.content, self.project)
        self.assertIn("title", music)
        self.assertIn("mission_garden", music)
        self.assertIn("music_scene_arrival", music)
        self.assertIn("scene_enter_arrival", effects)


class AudioDispatchTests(unittest.TestCase):
    def test_plays_specific_music_else_falls_back_and_stops(self):
        content = Content.load(DEFAULT_CONTENT)
        project = GameProject.default(content)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "theme.wav"
            source.write_bytes(b"RIFF" + b"\x00" * 4 + b"WAVE")
            project = import_sound(project, content, source, root, "theme")
            project = bind_sound(project, content, "battle", "theme")
            stage = AudioStage(project.asset_registry(), root)
            mixer = Mock()
            stage._mixer = mixer
            self.assertEqual(stage.music_for("mission_garden", "battle"), "battle")
            mixer.music.load.assert_called_once()
            self.assertEqual(stage.music_for("mission_garden", "battle"), "battle")
            self.assertEqual(mixer.music.load.call_count, 1)
            self.assertTrue(stage.preview_asset("theme"))
            mixer.Sound.assert_called_once()
            stage.stop()
            mixer.stop.assert_called_once()
            self.assertIsNone(stage.music_for("missing"))
            self.assertFalse(stage.preview_asset("unknown"))
            stage.close()


if __name__ == "__main__":
    unittest.main()
