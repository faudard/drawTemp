"""R42.C2: R9 tactical trigger -> CT survival -> R5 once-only victory -> R9 aftermath.

No synthetic battle.result, no fake mission completion, no direct mutations
to Campaign flags in the tests. Every battle step is a real journaled command.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.r42_captain_slice import QUEST_MISSION, make_captain_slice
from drawtemp.sdk.r42_reachability import captain_slice_audit
from sporebound.game_session import GameSession
from sporebound.model import RuleError


class CaptainTacticalR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = make_captain_slice()

    def reach_quest(self):
        game = GameSession.new(self.content, self.project, 'main', seed=42)
        for choice in ('defend', 'rescue', 'trust', 'accept', 'alliance', 'finish'):
            while not game.narrative_line()['complete']:
                game.advance_narrative_line()
            game.choose_story_option(choice)
        self.assertIsNone(game.active_scene())
        self.assertIn(QUEST_MISSION, game.available_missions())
        return game

    def test_real_tactical_event_and_postvictory_story_are_replayable(self):
        game = self.reach_quest()
        before = game.recording()
        with self.assertRaises(RuleError):
            game.choose_tactical_story_option('acknowledge')
        self.assertEqual(game.recording(), before)

        battle = game.start_mission(QUEST_MISSION)
        self.assertIsNone(battle.result)
        self.assertEqual(game.mode, 'battle')
        self.assertEqual(game.tactical_story_pending, 'orders')
        self.assertEqual(game.tactical_scene()['id'], 'orders')
        self.assertIn('captain_orders', battle.fired)
        self.assertEqual(sum(e['kind'] == 'trigger' and
                             e.get('id') == 'captain_orders'
                             for e in battle.events), 1)
        self.assertFalse(game.progress.story_flags['r42_c_main_battle_orders'])

        # A pending dialogue is an explicit CT pause: no other action is legal.
        with self.assertRaises(RuleError):
            game.execute({'kind': 'end', 'facing': [0, 1]})
        self.assertFalse(game.progress.story_flags['r42_c_main_battle_orders'])
        game.advance_narrative_line()
        mid_dialogue = game.recording()
        restored = GameSession.from_recording(mid_dialogue,
                                              self.content, self.project)
        self.assertEqual(restored.recording(), mid_dialogue)
        self.assertEqual(restored.narrative_line()['index'], 1)
        self.assertEqual(restored.tactical_scene()['id'], 'orders')

        restored.choose_tactical_story_option('acknowledge')
        self.assertFalse(restored.tactical_story_pending)
        self.assertTrue(restored.progress.story_flags['r42_c_main_battle_orders'])
        self.assertEqual(sum(row['scene'] == 'orders' for row in
                             restored.progress.story_history), 1)
        with self.assertRaises(RuleError):
            restored.choose_tactical_story_option('acknowledge')
        before_battle = restored.recording()
        self.assertEqual(
            GameSession.from_recording(before_battle, self.content,
                                       self.project).recording(), before_battle)

        # This is a *genuine* command-driven Battle victory. No test assigns
        # battle.result, completed, reward_ledger or story_pending directly.
        commands = 0
        while restored.active_battle.result is None and commands < 80:
            restored.execute({'kind': 'end', 'facing': [0, 1]})
            commands += 1
        self.assertGreater(commands, 0)
        self.assertLess(commands, 80)
        self.assertEqual(restored.active_battle.result, 'victory')
        self.assertTrue(restored.finalized)
        self.assertEqual(restored.progress.completed.count(QUEST_MISSION), 1)
        self.assertTrue(restored.progress.story_flags['r42_c_main_quest_won'])
        self.assertEqual(restored.progress.flow_ledger.count(
            QUEST_MISSION + ':victory'), 1)
        self.assertEqual(restored.active_scene()['id'], 'quest_return')

        settlement = restored.recording()
        reloaded = GameSession.from_recording(settlement,
                                               self.content, self.project)
        self.assertEqual(reloaded.recording(), settlement)
        gold = reloaded.progress.gold
        xp = {k: v.xp for k, v in reloaded.progress.heroes.items()}
        reloaded._settle()  # Real settlement operation is idempotent.
        self.assertEqual(reloaded.progress.gold, gold)
        self.assertEqual({k: v.xp for k, v in reloaded.progress.heroes.items()},
                         xp)
        self.assertEqual(reloaded.recording(), settlement)
        self.assertEqual(reloaded.progress.story_history.count(
            {'scene': 'orders', 'choice': 'acknowledge'}), 1)

        reloaded.return_to_campaign()
        self.assertEqual(reloaded.mode, 'campaign')
        self.assertEqual(reloaded.active_scene()['id'], 'quest_return')
        while not reloaded.narrative_line()['complete']:
            reloaded.advance_narrative_line()
        reloaded.choose_story_option('report')
        self.assertTrue(reloaded.progress.story_flags['r42_c_main_captain_report'])
        self.assertIsNone(reloaded.active_scene())
        self.assertEqual(reloaded.progress.story_history.count(
            {'scene': 'quest_return', 'choice': 'report'}), 1)
        with self.assertRaises(RuleError):
            reloaded.choose_story_option('report')
        end = reloaded.recording()
        self.assertEqual(GameSession.from_recording(
            end, self.content, self.project).recording(), end)

    def test_quest_cannot_be_entered_without_conditional_unlock(self):
        game = GameSession.new(self.content, self.project, 'main')
        with self.assertRaises(RuleError):
            game.start_mission(QUEST_MISSION)
        self.assertEqual(game.progress.completed, [])
        self.assertFalse(game.progress.story_flags['r42_c_main_quest_won'])

    def test_audit_does_not_falsely_certify_external_battle_scenes(self):
        report = captain_slice_audit()
        self.assertTrue(report['passed'])
        self.assertEqual(report['dead_scenes'], [])
        self.assertEqual(report['dead_choices'], [])
        self.assertEqual(report['external_trigger_roots'],
                         ['orders', 'quest_return'])
        self.assertEqual(report['external_trigger_scenes_unverified'],
                         ['orders', 'quest_return'])
        self.assertFalse(report['tactical_replay_verified'])
        self.assertFalse(report['player_export_verified'])


if __name__ == '__main__':
    unittest.main()
