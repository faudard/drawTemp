"""Production-relevant tests for a village authored without hand-editing JSON."""
from collections import Counter, deque
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.fortified_village_3717a import MISSION_ID, build_village_document
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.iso_architecture import architecture_instances
from sporebound.iso_connections import bridge_axis, shoreline_mask
from sporebound.model import Content
from sporebound.storage import load_battle, save_battle


def traversable(board, start, goal):
    """Check geographic crossing without changing actual engine path rules."""
    queue, seen = deque([start]), {start}
    while queue:
        cell = queue.popleft()
        if cell == goal:
            return True
        for neighbor in board.neighbors(cell):
            if neighbor not in seen and not board.tile(neighbor).blocked:
                seen.add(neighbor)
                queue.append(neighbor)
    return False


class ReferenceVillageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Content.load(DEFAULT_CONTENT)
        cls.document = build_village_document(cls.base)
        cls.content = Content.from_dict(cls.document.data)
        cls.mission = cls.content.missions[MISSION_ID]

    def test_no_custom_schema_and_original_content_unchanged(self):
        self.assertNotIn(MISSION_ID, self.base.missions)
        self.assertIn(MISSION_ID, self.content.missions)
        self.assertEqual(
            set(self.content.missions) - set(self.base.missions), {MISSION_ID})
        self.assertEqual(self.mission.board.width, 26)
        self.assertEqual(self.mission.board.height, 20)
        self.assertTrue(self.document.dirty)

    def test_fortified_village_architecture_and_variants_are_real_stamps(self):
        board = self.mission.board
        instances = architecture_instances(board)
        counts = Counter(item.name for item in instances)
        self.assertGreaterEqual(counts['Maison'], 3)
        self.assertGreaterEqual(counts['Rempart'], 4)
        self.assertEqual(counts['Tour'], 1)
        self.assertEqual(counts['Ruines'], 1)
        self.assertEqual(counts['Pont'], 1)
        self.assertTrue(board.tile((21, 3)).blocked)
        self.assertFalse(board.tile((22, 13)).blocked)
        self.assertEqual(board.tile((7, 10)).feature, 'crate')
        self.assertEqual(board.tile((3, 8)).surface, 'cobble')
        self.assertEqual(board.tile((23, 9)).surface, 'cobble')

    def test_river_bridge_roads_and_gate_allow_a_crossing(self):
        board = self.mission.board
        self.assertTrue(board.tile((13, 8)).blocked)
        self.assertEqual(board.tile((13, 8)).surface, 'water')
        self.assertEqual(board.tile((13, 9)).surface, 'bridge')
        self.assertEqual(board.tile((13, 10)).surface, 'bridge')
        self.assertFalse(board.tile((13, 9)).blocked)
        self.assertEqual(bridge_axis(board, (13, 9)), 'x')
        self.assertTrue(shoreline_mask(board, (12, 8)))
        self.assertFalse(board.tile((19, 9)).blocked)
        self.assertTrue(board.tile((19, 6)).blocked)
        self.assertTrue(board.tile((19, 12)).blocked)
        self.assertTrue(traversable(board, (2, 10), (23, 9)))

    def test_existing_guided_interactions_and_playtest(self):
        mission = self.mission
        self.assertEqual({obj['id'] for obj in mission.objects},
                         {'east_gate', 'village_chest'})
        self.assertEqual(len(mission.triggers), 1)
        self.assertEqual(mission.triggers[0]['id'], 'crossed_valcroix_bridge')
        self.assertEqual(mission.objective, 'eliminate')
        battle = self.document.playtest(MISSION_ID, seed=7)
        self.assertEqual(battle.mission.id, MISSION_ID)
        self.assertEqual(len(battle.mission.units), 2)
        self.assertTrue(traversable(battle.board, (2, 10), (23, 9)))

    def test_save_reload_play_and_replay_have_identical_content(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'village.json'
            replay = Path(tmp) / 'battle.json'
            self.document.save(path)
            reopened = Content.load(path)
            self.assertEqual(reopened.to_dict(), self.content.to_dict())
            self.assertEqual(architecture_instances(
                reopened.missions[MISSION_ID].board),
                architecture_instances(self.mission.board))
            battle = self.document.playtest(MISSION_ID, seed=7)
            save_battle(replay, battle)
            self.assertEqual(load_battle(replay).digest(), battle.digest())

    def test_undo_redo_on_further_edit_keeps_fortification_intact(self):
        doc = build_village_document(self.base)
        first = doc.data
        doc.paint_many(MISSION_ID, [(10, 17)], 'feature:bush')
        self.assertEqual(Content.from_dict(doc.data).missions[
            MISSION_ID].board.tile((10, 17)).feature, 'bush')
        doc.undo()
        self.assertEqual(doc.data, first)
        doc.redo()
        self.assertEqual(Content.from_dict(doc.data).missions[
            MISSION_ID].board.tile((10, 17)).feature, 'bush')


if __name__ == '__main__':
    unittest.main()
