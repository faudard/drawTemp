"""Tk renderer and audio orchestration are importable without a GUI."""
import unittest
from unittest.mock import Mock

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.tk_renderer import CanvasRenderer
from sporebound.audio_stage import AudioStage


class RendererTests(unittest.TestCase):
    def test_fake_canvas_consumes_frame_without_mutating_battle(self):
        battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=13)
        digest = battle.digest()
        canvas = Mock()
        renderer = CanvasRenderer(canvas)
        renderer.draw(battle_frame(battle, (0, 0)), Camera())
        self.assertEqual(canvas.create_rectangle.call_count > 0, True)
        self.assertEqual(canvas.create_oval.call_count > 0, True)
        self.assertEqual(battle.digest(), digest)

    def test_no_audio_is_nonfatal(self):
        stage = AudioStage()
        self.assertFalse(stage.cue('attack'))
        battle = Battle(Content.load(DEFAULT_CONTENT), 'garden', seed=13)
        stage.observe(battle)
        stage.observe(battle)
        self.assertEqual(stage._seen[battle.battle_id], len(battle.events))
        stage.close()


if __name__ == '__main__':
    unittest.main()
