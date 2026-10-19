"""R40.A reference starters: canonical authoring, isolation and honest release scope."""
from __future__ import annotations

from copy import deepcopy
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from drawtemp.core import GameSession
from drawtemp.export.r15 import ExportError, preflight
from drawtemp.export.templates import TEMPLATES
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.r40_starters import (
    STARTER_KINDS, create_starter_pair, starter_catalog,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.project_wizard import ProjectSpec, create_project, project_preview
from sporebound.game_modes import resolve_scene_profile
from sporebound.metroidvania import analyze_metroidvania
from sporebound.roguelite import EXTENSION as ROGUELITE_EXTENSION


class R40StarterTests(unittest.TestCase):
    def test_all_four_distinct_and_explicitly_not_certified(self):
        self.assertEqual(len(STARTER_KINDS), 4)
        self.assertTrue(set(STARTER_KINDS).issubset(TEMPLATES))
        catalog = starter_catalog()
        self.assertEqual({x["genre"] for x in catalog},
                         {"srpg", "action-adventure", "metroidvania", "roguelite"})
        self.assertEqual({x["id"] for x in catalog}, set(STARTER_KINDS))
        self.assertTrue(all(x["canonical_pair"] for x in catalog))
        self.assertTrue(all(not x["release_8_0_certified"] and
                            not x["player_export_certified"] and
                            not x["human_ux_certified"] for x in catalog))

    def test_canonical_pairs_are_detached_and_preserve_legacy_ct(self):
        old_content, old_project = reference_project()
        original = deepcopy(old_content.to_dict())
        historical_project = deepcopy(old_project.to_dict())
        for kind in STARTER_KINDS:
            with self.subTest(kind=kind):
                content, project = create_starter_pair(kind)
                self.assertEqual(content.to_dict(), original)
                self.assertEqual(set(content.missions), set(old_content.missions))
                project.validate(content)
                self.assertEqual(resolve_scene_profile(
                    project.game_modes, next(iter(content.missions)))["combat"],
                    "TACTICAL_CT")
        self.assertEqual(old_project.to_dict(), historical_project)

    def test_action_starter_uses_existing_exploration_and_profile_contracts(self):
        content, project = create_starter_pair("r40-adventure")
        self.assertEqual(set(project.exploration),
                         {"arrival", "r40_ruins", "r40_citadel"})
        self.assertEqual(resolve_scene_profile(
            project.game_modes, "r40_ruins")["combat"], "ACTION_REALTIME")
        self.assertFalse(project.scene_routes)
        self.assertFalse(project.assets)
        project.validate(content)

    def test_metroidvania_reachability_and_fail_closed_gate(self):
        content, project = create_starter_pair("r40-metroidvania")
        graph = project.extensions["drawtemp.metroidvania"]["data"]
        report = analyze_metroidvania(graph, scene_ids=project.exploration)
        self.assertTrue(report["complete"])
        self.assertTrue(report["safe"])
        self.assertTrue(report["goal_reachable"])
        self.assertIn("double_jump", report["witness"][-1]["capabilities"])
        copy_project = deepcopy(project)
        copy_project.extensions["drawtemp.metroidvania"]["data"]["links"][0]["requires"] = ["fly"]
        with self.assertRaises((ValueError, TypeError)):
            copy_project.validate(content)
        project.validate(content)

    def test_roguelite_uses_real_session_and_keeps_meta_separate_from_ct(self):
        content, project = create_starter_pair("r40-roguelite")
        self.assertIn(ROGUELITE_EXTENSION, project.extensions)
        game = GameSession.new(content, project, "main", seed=19)
        before_gold = game.progress.gold
        initial = game.roguelite_state()
        self.assertEqual(initial["status"], "active")
        for room in initial["layout"]["route"][1:]:
            game.roguelite_move(room)
        self.assertEqual(game.roguelite_state()["status"], "won")
        self.assertEqual(game.roguelite_state()["meta"]["coins"], 7)
        self.assertEqual(game.progress.gold, before_gold)
        self.assertEqual(
            GameSession.from_recording(game.recording(), content, project)
            .roguelite_state(), game.roguelite_state())

    def test_existing_wizard_creates_four_canonical_editable_projects(self):
        with TemporaryDirectory() as root:
            for kind in STARTER_KINDS:
                with self.subTest(kind=kind):
                    destination = Path(root) / kind
                    spec = ProjectSpec(kind, destination, title="Mon jeu", language="fr")
                    preview = project_preview(spec)
                    self.assertTrue(preview["passed"], preview["errors"])
                    self.assertFalse(destination.exists())
                    path = create_project(spec)
                    self.assertEqual(path, destination / "game.json")
                    snap = AuthoringSession.open(path).snapshot().to_dict()
                    self.assertEqual(snap["project"]["title"], "Mon jeu")
                    self.assertGreater(len(snap["content"]["missions"]), 0)
                    self.assertTrue(preflight(path)["passed"])
                    self.assertFalse(project_preview(spec)["passed"])
                    with self.assertRaises(ExportError):
                        create_project(spec)

    def test_unknown_starter_rejected_without_disk_write(self):
        for invalid in ("missing", "", 12, None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                create_starter_pair(invalid)
        with TemporaryDirectory() as root:
            destination = Path(root) / "invalid"
            self.assertFalse(project_preview(
                ProjectSpec("r40-not-found", destination))["passed"])
            self.assertFalse(destination.exists())


@unittest.skipUnless(find_spec("PySide6"), "PySide6 is not installed")
class R40CreatorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_starters_are_available_in_existing_creator_dialog(self):
        from drawtemp.studio.r15_creator import CreatorDialog
        dialog = CreatorDialog()
        try:
            options = [dialog.template.itemText(i)
                       for i in range(dialog.template.count())]
            for kind in STARTER_KINDS:
                self.assertIn(kind, options)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
