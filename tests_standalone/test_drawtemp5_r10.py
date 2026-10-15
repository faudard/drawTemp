"""R10 migration regression: canonical campaign documents, no parallel format."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest
from unittest.mock import patch

from drawtemp.core import Content
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.campaign_studio import CampaignStudio
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.campaign_graph import set_link


def _three_missions():
    content, project = reference_project()
    document = content.to_dict()
    forest = deepcopy(document["missions"][0])
    forest.update(id="r10_forest", name="La forêt", next_missions=[])
    castle = deepcopy(document["missions"][0])
    castle.update(id="r10_castle", name="Les remparts", next_missions=[])
    document["missions"].extend([forest, castle])
    content = Content.from_dict(document)
    project.story["scenes"][0]["choices"] = [
        {"id": "aid", "label": "Aider les villageois", "effects": [
            {"kind": "set_flag", "flag": "allegiance", "value": "aid"}]},
        {"id": "refuse", "label": "Refuser", "effects": [
            {"kind": "set_flag", "flag": "allegiance", "value": "refuse"}]},
    ]
    project.validate(content)
    return CampaignStudio.new(content, project)


class CampaignStudioTests(unittest.TestCase):
    def test_links_and_atomic_undo_redo(self):
        studio = _three_missions()
        base = studio.overview()
        self.assertEqual(base["graph"]["edges"], [])
        studio.link_missions(MISSION, "r10_forest")
        studio.link_missions("r10_forest", "r10_castle")
        self.assertEqual(studio.overview()["graph"]["edges"],
                         [(MISSION, "r10_forest"), ("r10_forest", "r10_castle")])
        studio.undo()
        self.assertEqual(studio.overview()["graph"]["edges"],
                         [(MISSION, "r10_forest")])
        studio.redo()
        self.assertEqual(len(studio.overview()["graph"]["edges"]), 2)

    def test_invalid_mutation_cannot_corrupt_pair(self):
        studio = _three_missions()
        before = studio.overview()
        with self.assertRaises(AuthoringError):
            studio.link_missions("no_such_mission", MISSION)
        self.assertEqual(studio.overview(), before)
        source_revision = studio.revision
        plan = studio.authoring.preview_pair(
            lambda content, project: (
                set_link(content, MISSION, "r10_castle"), project),
            kind="r10-stale-test", views=("workspace", "inspector"))
        studio.link_missions(MISSION, "r10_forest")
        with self.assertRaisesRegex(AuthoringError, "changed|stale"):
            studio.authoring.apply(plan)
        self.assertEqual(studio.revision, source_revision + 1)

    def test_world_and_siege_are_canonical(self):
        studio = _three_missions()
        studio.link_missions(MISSION, "r10_forest")
        studio.link_missions("r10_forest", "r10_castle")
        studio.initialize_world()
        studio.move_location("r10_forest", 300, 250, "Forêt")
        world = studio.overview()["world"]
        forest = next(node for node in world["nodes"]
                      if node["mission"] == "r10_forest")
        self.assertEqual((forest["x"], forest["y"], forest["region"]),
                         (300, 250, "Forêt"))
        studio.create_siege("castle_siege", "r10_forest")
        studio.add_siege_front("castle_siege", "walls", "r10_castle",
                               doctrine="assault")
        studio.set_siege_finale("castle_siege", "walls", {"approach": ["victory"]})
        siege = studio.overview()["sieges"][0]
        self.assertEqual(siege["fronts"]["walls"], "r10_castle")
        self.assertEqual(siege["campaign"]["final_front"], "walls")
        self.assertIsNotNone(studio.siege_timeline("castle_siege"))
        studio.undo()
        self.assertIsNone(studio.overview()["sieges"][0]["campaign"])
        studio.redo()
        self.assertEqual(studio.overview()["sieges"][0]["campaign"]["final_front"],
                         "walls")

    def test_two_story_decisions_three_missions_and_two_endings(self):
        studio = _three_missions()
        studio.link_missions(MISSION, "r10_forest")
        studio.link_missions("r10_forest", "r10_castle")
        studio.set_condition("ending", "alliance", "flag_eq", "allegiance", "aid")
        studio.set_condition("ending", "exile", "flag_eq", "allegiance", "refuse")
        studio.add_consequence("r10_castle", "victory", "gold", "", "20")
        studio.add_consequence("r10_forest", "victory", "set_flag",
                               "supplies_food", "3")
        for choice, ending in [("aid", "alliance"), ("refuse", "exile")]:
            studio.simulation_select(0)
            studio.simulation_choose(choice)
            for mission in [MISSION, "r10_forest", "r10_castle"]:
                self.assertIn(mission, [
                    action["id"] for action in studio.simulation_actions()
                    if action["kind"] == "mission"])
                studio.simulation_resolve(mission, "victory")
            result = studio.simulation_inspect()
            self.assertIn(ending, result["endings"])
            self.assertEqual(result["missions"]["completed"],
                             [MISSION, "r10_forest", "r10_castle"])
            self.assertEqual(result["variables"]["supplies_food"], 3)
            self.assertEqual(result["resources"]["gold"], 20 +
                             sum(row["reward"] for row in studio.overview()["missions"]))
            self.assertIn("r10_castle:victory", result["consequences"])
        self.assertEqual(studio.simulation_coverage()["endings_not_witnessed"], [])
        self.assertFalse(studio.simulation_inspect()["symbolic_only"] is False)
        self.assertEqual(studio.audit()["errors"], [])

    def test_authoring_changes_invalidate_sandbox_and_proof_is_explicit(self):
        studio = _three_missions()
        studio.simulation_choose("aid")
        studio.simulation_resolve(MISSION, "victory")
        candidate = studio.candidate_path(seed=17)
        self.assertEqual(candidate["steps"][0],
                         {"kind": "choice", "id": "aid"})
        self.assertEqual(candidate["steps"][1]["kind"], "mission")
        # A symbolic candidate must never call the tactical certifier itself.
        with patch("drawtemp.sdk.campaign_studio.certify_path",
                   return_value={"status": "CERTIFIED"}) as real_runner:
            report = studio.certify(candidate)
            self.assertEqual(report["status"], "CERTIFIED")
            real_runner.assert_called_once()
        studio.link_missions(MISSION, "r10_forest")
        self.assertEqual(studio.simulation_inspect()["node"], 0)

    def test_save_and_reload_both_canonical_documents(self):
        studio = _three_missions()
        studio.link_missions(MISSION, "r10_forest")
        studio.set_condition("ending", "alliance", "flag_eq",
                             "allegiance", "aid")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "r10_content.json"
            written = studio.save_as(path)
            self.assertEqual(len(written), 2)
            self.assertTrue(all(item.is_file() for item in written))
            reopened = CampaignStudio.open(path)
            self.assertEqual(reopened.overview()["graph"]["edges"],
                             [(MISSION, "r10_forest")])
            self.assertIn("alliance", reopened.overview()["flow"]["endings"])
            reopened.link_missions("r10_forest", "r10_castle")
            reopened.save()
            reloaded = CampaignStudio.open(path)
            self.assertEqual(len(reloaded.overview()["graph"]["edges"]), 2)

    def test_validated_export_uses_existing_source_bundle(self):
        studio = _three_missions()
        with patch("drawtemp.sdk.campaign_studio.export_game",
                   return_value="output.zip") as exporter:
            self.assertEqual(studio.export_source_bundle(".", "output.zip"),
                             "output.zip")
            content, project = exporter.call_args.args[:2]
            self.assertEqual(set(content.missions),
                             {MISSION, "r10_forest", "r10_castle"})
            self.assertEqual(project.campaign("main")["start_mission"], MISSION)

    def test_headless_sdk_never_imports_gui(self):
        code = """
import sys
class BanUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', '_tkinter', 'PySide6', 'PyQt6'):
            raise AssertionError('Unexpected UI import: ' + fullname)
sys.meta_path.insert(0, BanUI())
from drawtemp.sdk.campaign_studio import CampaignStudio
from drawtemp.sdk.reference import reference_project
content, project = reference_project()
assert CampaignStudio.new(content, project).overview()['campaigns']
"""
        subprocess.run([sys.executable, "-c", code], check=True,
                       capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
