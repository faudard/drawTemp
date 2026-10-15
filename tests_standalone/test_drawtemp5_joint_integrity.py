"""Consolidated DrawTemp 5 integration contract (R1/R3/R4/R5/R8-R12).

Unlike per-lot unit tests, all editors below operate on *one* canonical
AuthoringSession, whose two documents must remain loadable by the Player.
This is a headless gate, NOT certification of QML/real-GPU parity or packaging.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.catalog import AssetIndex
from drawtemp.cinematics import CinematicDocument
from drawtemp.core import Content, GameProject
from drawtemp.player.controller import PlayerController
from drawtemp.render.iso_scene import fingerprint, scene_from_mission
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.campaign_studio import CampaignStudio
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.rpg_database import DatabaseEditor, lancer_example
from sporebound.event_composer import action, condition


class JointIntegrityTests(unittest.TestCase):
    def _authored_project(self):
        content, project = reference_project()
        shared = AuthoringSession.new(content, project)
        maps = MapStudio(shared, MISSION)
        database = DatabaseEditor(shared)
        events = EventStudio(shared)
        campaigns = CampaignStudio(shared, "main")

        # R5 -> R8 -> R9 -> R10: each edit must share one history and schema.
        maps.create("joint_village", "Village intégré", 12, 12)
        maps.paint([(3, 3), (3, 4)], "surface:stone")
        maps.structure("Maison", (5, 5))
        self.assertEqual(maps.sample((3, 3)), "stone")
        lancer_example(shared)
        self.assertTrue(database.detail("skills", "r8_guard_ally"))
        events.create(MISSION, "joint_lever",
                      condition("interact", object_id="lever"),
                      [action("message", text="La porte est ouverte")])
        self.assertEqual(events.event(MISSION, "joint_lever")["id"], "joint_lever")
        campaigns.link_missions(MISSION, "joint_village")
        self.assertIn((MISSION, "joint_village"),
                      campaigns.overview()["graph"]["edges"])

        # R11 must not replace the other workspaces' changes with its own
        # detached project copy. Commit clips through the shared SDK transaction.
        current = shared.snapshot().to_dict()
        authored_content = Content.from_dict(current["content"])
        authored_project = GameProject.from_dict(current["project"], authored_content)
        cinematic = CinematicDocument(authored_project, authored_content)
        clip_id = cinematic.add_jeanne_intro()
        self.assertTrue(cinematic.sample(clip_id, 2700)[0])
        shared.apply(shared.preview_project(
            lambda data: {**data, "cinematics": cinematic.clips},
            kind="joint-r11-cinematic"))
        self.assertEqual(shared.snapshot().to_dict()["project"]["cinematics"][0]["id"],
                         clip_id)

        return shared

    def test_one_document_roundtrips_into_player_and_renderer(self):
        authoring = self._authored_project()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "joint.json"
            authoring.save_as(target)
            reopened = AuthoringSession.open(target)
            actual = reopened.snapshot().to_dict()
            self.assertEqual(actual["content"], authoring.snapshot().to_dict()["content"])
            self.assertEqual(actual["project"], authoring.snapshot().to_dict()["project"])

            content = Content.from_dict(actual["content"])
            project = GameProject.from_dict(actual["project"], content)
            # R4 registry is owned by the same GameProject; no parallel manifest.
            self.assertEqual(AssetIndex(project.asset_registry()).registry.to_dict(),
                             project.asset_registry().to_dict())
            self.assertIn("r8_guard_ally", content.skills)
            self.assertIn("joint_village", content.missions)
            self.assertEqual(project.cinematics[0]["id"], "jeanne_intro")

            # R12 consumes this authored pair, without opening the Studio.
            player = PlayerController(content, project, "main", root / "saves")
            player.new_game()
            player.choose("enter")
            player.start_mission(MISSION)
            state = player.state()
            self.assertIn(state["screen"], ("battle", "result"))
            self.assertEqual(state["battle"]["mission_id"], MISSION)

            # R3 sees the exact mission and R1 runtime snapshot used by R12.
            scene = scene_from_mission(content.missions[MISSION], player.session.snapshot())
            self.assertEqual(scene["revision"], state["revision"])
            self.assertEqual(scene["mission"], state["battle"]["mission_id"])
            before = {**scene, "revision": 0}
            first_fingerprint = fingerprint(before)
            self.assertGreater(len(scene["tiles"]), 0)

            player.save(1)
            restored = PlayerController(content, project, "main", root / "saves")
            restored.load(1)
            self.assertEqual(restored.state()["battle"], state["battle"])
            after = scene_from_mission(content.missions[MISSION],
                                       restored.session.snapshot())
            self.assertEqual(fingerprint({**after, "revision": 0}), first_fingerprint)

    def test_stale_cross_editor_preview_is_rejected_without_data_loss(self):
        shared = AuthoringSession.new(*reference_project())
        database = DatabaseEditor(shared)
        maps = MapStudio(shared, MISSION)
        planned = database.preview_many((
            ("jobs", "create", "joint_guardian", "", {"name": "Guardian"}),))
        maps.paint([(4, 3)], "surface:stone")
        from drawtemp.sdk.authoring import AuthoringError
        with self.assertRaises(AuthoringError) as caught:
            database.commit(planned)
        self.assertEqual(caught.exception.code, "stale_revision")
        self.assertFalse(any(row.id == "joint_guardian"
                             for row in database.entries("jobs")))


if __name__ == "__main__":
    unittest.main()
