"""R10.11: three linked playable missions, two decisions and persisted consequences.

These tests intentionally author through public commands, not hand-made
mission/story JSON. Symbolic routes and real replay certification are separate.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from drawtemp.sdk.campaign_studio import CampaignStudio
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.player.qt_app import build_controller
from drawtemp.sdk.authoring import AuthoringError


FOREST = "r10_forest_e2e"
CASTLE = "r10_castle_e2e"


def guided_campaign():
    content, project = reference_project()
    studio = CampaignStudio.new(content, project)
    studio.create_mission(FOREST, "La forêt des secours", after=MISSION)
    studio.create_mission(CASTLE, "Les portes du château", after=FOREST)
    studio.set_mission_reward(FOREST, 5)
    studio.set_mission_reward(CASTLE, 10)

    studio.create_scene(
        "r10_decision", "Le choix du village",
        "La route est dangereuse. Aider les habitants ou avancer ?",
        speaker="Jeanne")
    studio.add_story_choice("r10_decision", "aid", "Protéger les habitants")
    studio.add_story_choice_effect(
        "r10_decision", "aid", "set_flag", "allegiance", "aid")
    studio.add_story_choice("r10_decision", "refuse", "Continuer la marche")
    studio.add_story_choice_effect(
        "r10_decision", "refuse", "set_flag", "allegiance", "refuse")
    studio.remove_story_choice("r10_decision", "continue")
    studio.set_entry_scene("r10_decision")
    studio.add_consequence(FOREST, "victory", "set_flag", "supplies_food", "3")
    studio.add_consequence(CASTLE, "victory", "gold", "", "7")

    for ending, value in [("alliance", "aid"), ("exil", "refuse")]:
        studio.set_condition("ending", ending, "flag_eq", "allegiance", value)
        studio.append_condition(
            "ending", ending, "completed_mission", CASTLE, "")
    return studio


def route(studio, choice):
    studio.simulation_select(0)
    studio.simulation_choose(choice)
    for mission in (MISSION, FOREST, CASTLE):
        offered = studio.simulation_actions()
        if not any(x["kind"] == "mission" and x["id"] == mission and
                   x["outcome"] == "victory" for x in offered):
            raise AssertionError("Mission is unavailable in authored route: " + mission)
        studio.simulation_resolve(mission, "victory")
    return studio.candidate_path(seed=17)


class R10EndToEndTests(unittest.TestCase):
    def test_story_links_world_saves_and_symbolic_endings(self):
        studio = guided_campaign()
        overview = studio.overview()
        self.assertEqual(overview["graph"]["edges"],
                         [(MISSION, FOREST), (FOREST, CASTLE)])
        self.assertEqual(overview["entry_scene"], "r10_decision")
        self.assertEqual(overview["flow"]["endings"]["alliance"]["all"][1],
                         {"completed_mission": CASTLE})
        self.assertEqual(next(m for m in overview["missions"] if m["id"] == FOREST)["reward"], 5)

        for choice, ending in (("aid", "alliance"), ("refuse", "exil")):
            candidate = route(studio, choice)
            self.assertEqual(len(candidate["steps"]), 4)
            preview = studio.simulation_inspect()
            self.assertEqual(preview["endings"], [ending])
            self.assertEqual(preview["resources"]["gold"], 22)
            self.assertEqual(preview["resources"]["supplies"]["supplies_food"], 3)
            self.assertEqual(preview["missions"]["completed"],
                             [MISSION, FOREST, CASTLE])
            self.assertTrue(preview["symbolic_only"])
        self.assertEqual(studio.simulation_coverage()["endings_not_witnessed"], [])
        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "campaign.json"
            studio.save_as(content_path)
            reread = CampaignStudio.open(content_path)
            self.assertEqual(reread.overview()["graph"]["edges"], overview["graph"]["edges"])
            self.assertEqual(reread.overview()["flow"]["endings"], overview["flow"]["endings"])
            self.assertIn("aid", [c["id"] for c in reread.overview()["scenes"][-1]["choices"]])
            self.assertEqual(
                route(reread, "aid")["expect"]["endings"], ["alliance"])

    def test_invalid_new_mission_and_choice_roll_back_single_revision(self):
        studio = guided_campaign()
        revision = studio.revision
        with self.assertRaises(AuthoringError):
            studio.create_mission(FOREST, "Duplicate", after=CASTLE)
        with self.assertRaises(AuthoringError):
            studio.add_story_choice("r10_decision", "aid", "Duplicate")
        with self.assertRaises(AuthoringError):
            studio.remove_story_choice("r10_decision", "missing")
        self.assertEqual(studio.revision, revision)
        studio.undo()
        self.assertNotIn("exil", studio.overview()["flow"]["endings"])
        studio.redo()
        self.assertIn("exil", studio.overview()["flow"]["endings"])

    def test_player_loads_authored_pair_and_separates_save_directories(self):
        studio = guided_campaign()
        with TemporaryDirectory() as root:
            first = Path(root) / "first" / "content.json"
            second = Path(root) / "second" / "content.json"
            first.parent.mkdir()
            second.parent.mkdir()
            studio.save_as(first)
            pair = studio.authoring.snapshot().to_dict()
            from drawtemp.core import Content, GameProject
            copied = CampaignStudio.new(pair["content"], pair["project"])
            copied.save_as(second)
            one = build_controller(content_path=first)
            two = build_controller(content_path=second)
            self.assertIn(FOREST, one.content.missions)
            self.assertEqual(one.project.story["entry_scenes"]["main"], "r10_decision")
            self.assertNotEqual(one.save_dir, two.save_dir)
            self.assertFalse(one.save_dir.exists())
            self.assertFalse(two.save_dir.exists())
            explicit = build_controller(
                content_path=first, project_path=first.with_suffix(".game.json"),
                campaign_id="main", save_dir=Path(root) / "custom")
            self.assertEqual(explicit.save_dir, Path(root) / "custom")
            with self.assertRaisesRegex(ValueError, "requires"):
                build_controller(project_path=first.with_suffix(".game.json"))
            with self.assertRaisesRegex(ValueError, "Unknown campaign"):
                build_controller(content_path=first, campaign_id="other")

    @unittest.skipUnless(os.environ.get("DRAWTEMP_R10_FULL_GATE") == "1",
                         "Full Battle replay certification runs in the dedicated R10 gate")
    def test_two_endings_with_real_tactical_replay(self):
        studio = guided_campaign()
        with TemporaryDirectory() as directory:
            studio.save_as(Path(directory) / "r10.json")
            reopened = CampaignStudio.open(Path(directory) / "r10.json")
            reports = []
            for choice, ending in (("aid", "alliance"), ("refuse", "exil")):
                plan = route(reopened, choice)
                report = reopened.certify(plan, max_commands=1600)
                self.assertEqual(report["status"], "CERTIFIED")
                self.assertEqual(report["observed"]["endings"], [ending])
                self.assertEqual(report["observed"]["completed"],
                                 [MISSION, FOREST, CASTLE])
                self.assertTrue(report["evidence"]["checkpoints_replayed"])
                self.assertTrue(report["evidence"]["uninterrupted_equal_resumed"])
                self.assertEqual(report["evidence"]["tactical_battles"], 3)
                reports.append(report)
            self.assertEqual({e for report in reports
                              for e in report["observed"]["endings"]},
                             {"alliance", "exil"})


if __name__ == "__main__":
    unittest.main()
