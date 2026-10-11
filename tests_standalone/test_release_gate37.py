"""3.7 release: authored export, independent Player checkpoints, motion, Jeanne slice."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from sporebound.ai import choose_command
from sporebound.game_export4 import export_game
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.presentation import battle_frame
from sporebound.studio_release_gate import verify_game_bundle
from sporebound.visual_motion import MotionDirector
from sporebound.workspace import create_campaign, duplicate_mission

ROOT = Path(__file__).resolve().parents[1]


class StudioReleaseTests(unittest.TestCase):
    def test_studio_authoring_export_run_and_resume_without_hand_written_json(self):
        content = Content.load(ROOT / "sporebound/content/core.json")
        project = GameProject.default(content)
        # The same validated authoring APIs used by the Studio workspace.
        authored = duplicate_mission(content.to_dict(), project, "garden",
                                     "release_garden", "Mission de réception")
        content = Content.from_dict(authored)
        project = create_campaign(project, content, "release", "Campagne de réception",
                                  "release_garden")
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive = export_game(content, project, root, root / "release.zip")
            report = verify_game_bundle(archive)
            self.assertTrue(report["verified"])
            self.assertEqual(report["campaigns"], 2)
            self.assertGreaterEqual(report["missions"], 2)
            unpacked = root / "installed"
            unpacked.mkdir()
            with ZipFile(archive) as zip_file:
                zip_file.extractall(unpacked)
            # Load exactly the exported documents, not their authoring objects.
            packed_content = Content.load(unpacked / "game/content.json")
            packed_project = GameProject.load(unpacked / "game/project.game.json",
                                              packed_content)
            profile = unpacked / "saves/profile.json"
            player = PlayerController(packed_content, packed_project, profile)
            player.new_game("release", 1)
            player.start_mission("release_garden")
            checkpoint = player.session.recording()
            resumed = PlayerController(packed_content, packed_project, profile)
            resumed.load_game("release", 1)
            self.assertEqual(resumed.session.recording(), checkpoint)
            self.assertEqual(resumed.session.active_battle.mission.id,
                             "release_garden")
            self.assertNotIn("saves/", "\n".join(ZipFile(archive).namelist()))

    def test_tampered_export_is_rejected_before_player_save_creation(self):
        content = Content.load(ROOT / "sporebound/content/core.json")
        project = GameProject.default(content)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            original = export_game(content, project, root, root / "good.zip")
            corrupted = root / "tampered.zip"
            with ZipFile(original) as src, ZipFile(corrupted, "w", ZIP_DEFLATED) as dst:
                for name in src.namelist():
                    data = src.read(name)
                    if name == "game/content.json":
                        data += b"\n "
                    dst.writestr(name, data)
            with self.assertRaisesRegex(RuleError, "Corrupt export member"):
                verify_game_bundle(corrupted)
            self.assertFalse((root / "saves").exists())

    def test_cosmetic_motion_never_changes_tactical_digest(self):
        content = Content.load(ROOT / "sporebound/content/core.json")
        project = GameProject.default(content)
        session = GameSession.new(content, project, "main", seed=5)
        session.start_mission("garden")
        battle = session.active_battle
        director = MotionDirector(duration_ms=200)
        original = battle.digest()
        first = battle_frame(battle)
        director.observe(first, 1000)
        self.assertEqual(battle.digest(), original)
        session.execute(choose_command(battle))
        updated = battle_frame(battle)
        new_digest = battle.digest()
        director.observe(updated, 1100)
        director.poses(1190)
        finished = director.poses(1301)
        self.assertEqual(battle.digest(), new_digest)
        for actor in updated.actors:
            self.assertEqual((finished[actor.id].x, finished[actor.id].y),
                             actor.pos)


class JeanneFullSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(ROOT / "sporebound/content/jeanne.json")
        cls.project = GameProject.load(ROOT / "sporebound/content/jeanne.game.json",
                                       cls.content)

    def visit(self, session, hotspot):
        from collections import deque
        stage = session.exploration_state()
        point = next(x for x in stage["interactions"] if x["id"] == hotspot)
        target = tuple(point["pos"])
        blocked = {tuple(cell) for cell in stage["blocked"]}
        start = tuple(stage["position"])
        queue = deque([(start, ())])
        visited = {start}
        while queue:
            cell, path = queue.popleft()
            if abs(cell[0] - target[0]) + abs(cell[1] - target[1]) <= 1:
                for dx, dy in path:
                    session.explore_move(dx, dy)
                session.explore_interact(hotspot)
                return
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                step = (cell[0] + dx, cell[1] + dy)
                if (0 <= step[0] < stage["width"] and
                        0 <= step[1] < stage["height"] and
                        step not in blocked and step not in visited):
                    visited.add(step)
                    queue.append((step, (*path, (dx, dy))))
        self.fail("Unreachable story hotspot: " + hotspot)

    def win(self, session, mission, limit=850):
        self.assertEqual(session.available_missions(), [mission])
        session.start_mission(mission)
        for _ in range(limit):
            if session.active_battle.result is not None:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(session.active_battle.result, "victory", mission)
        self.assertIn(mission, session.progress.completed)
        session.return_to_campaign()

    def test_fields_to_vaucouleurs_continuous_with_checkpoint(self):
        session = GameSession.new(self.content, self.project, "jeanne", seed=17)
        self.assertEqual(session.active_scene()["id"], "sc_p0_champs")
        for hotspot in ("ble", "medaillon", "chene"):
            self.visit(session, hotspot)
        session.choose_story_option("ecouter")
        session.choose_story_option("repondre")
        session.choose_story_option("souvenir")
        self.win(session, "p0_01_lame")
        session.choose_story_option("courir")
        self.win(session, "p0_02_incendie")
        for hotspot in ("maison", "grange", "carrefour"):
            self.visit(session, hotspot)
        session.choose_story_option("secourir")
        self.win(session, "p0_03a_secours")
        session.choose_story_option("partir")
        self.win(session, "p0_04_fuite")
        session.choose_story_option("promesse")
        self.assertEqual(session.active_scene()["id"], "sc_a1_camp")
        session.choose_story_option("engager_etienne")
        self.assertTrue(session.progress.story_flags["recruited_etienne"])
        self.win(session, "a1_01_route")
        session.choose_story_option("tenir_passage")
        self.win(session, "a1_02_pont")
        session.choose_story_option("ravitailler")
        self.win(session, "a1_03_hospice")
        session.choose_story_option("prendre_archives")
        with TemporaryDirectory() as folder:
            save = Path(folder) / "player.json"
            session.save(save)
            restored = GameSession.load(save, self.content, self.project)
            self.assertEqual(restored.progress, session.progress)
            self.assertEqual(restored.available_missions(), ["a1_04a_archives"])
            session = restored
            self.win(session, "a1_04a_archives")
            session.choose_story_option("avancer_vaucouleurs")
            self.win(session, "a1_05_vaucouleurs")
            self.assertEqual(session.active_scene()["id"], "sc_a1_fin")
            session.choose_story_option("preuve_officielle")
            self.assertTrue(session.progress.story_flags["acte1_complete"])
            self.assertEqual(session.progress.story_flags["acte2_appui"], "archives")
            self.assertEqual(session.available_missions(), [])
            self.assertEqual(len(session.progress.completed), 9)
            session.save(save)
            self.assertEqual(GameSession.load(save, self.content, self.project).progress,
                             session.progress)


if __name__ == "__main__":
    unittest.main()
