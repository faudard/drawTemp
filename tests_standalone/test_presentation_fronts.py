"""Regression: finished tactical sectors unlock campaign return."""
from pathlib import Path
import unittest
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.presentation import strategy_frame

class FinalFrontTests(unittest.TestCase):
    def test_completed_sector_is_visible_and_can_exit(self):
        content = Content.load(DEFAULT_CONTENT)
        project = GameProject.load(Path(DEFAULT_CONTENT).with_suffix('.game.json'), content)
        game = GameSession.new(content, project, 'main')
        game.progress.unlocked.append('escape')
        game.start_fronts({'garden': 'garden', 'escape': 'escape'}, 'garden')
        with self.assertRaises(RuleError):
            game.return_to_campaign()
        game.fronts.battles['garden'].result = 'victory'
        rows = {row.id: row.status for row in strategy_frame(game.fronts).fronts}
        self.assertEqual(rows['garden'], 'victory')
        game.fronts.timeline.fronts['escape']['status'] = 'victory'
        game.return_to_campaign()
        self.assertEqual(game.mode, 'campaign')
