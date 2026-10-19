"""R28.E three independent R15 project creations and conservative release gates."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r28e_minigames import (
    MINIGAMES, MiniGameError, audit_minigame, certification_matrix,
    create_minigame, create_portfolio, preview_minigame,
)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content


class MiniGameCreationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_three_projects_have_independent_canonical_documents_and_real_roundtrips(self):
        projects = {}
        for spec in MINIGAMES:
            with self.subTest(game=spec.key):
                directory = create_minigame(spec.key, self.root / spec.key)
                self.assertEqual(directory, self.root / spec.key)
                path = directory / "game.json"
                manifest = directory / "game.game.json"
                self.assertTrue(path.is_file())
                self.assertTrue(manifest.is_file())
                self.assertTrue(preflight(path)["passed"])
                result = audit_minigame(path, spec.key)
                self.assertTrue(result["game_session_roundtrip"])
                self.assertTrue(result["author_documents_unchanged"])
                self.assertFalse(result["r28_release_certified"])
                self.assertFalse(result["native_player_verified"])
                data = AuthoringSession.open(path).snapshot().to_dict()
                self.assertEqual(data["project"]["title"], spec.label)
                projects[spec.key] = data
        self.assertEqual(len(projects), 3)
        self.assertEqual(
            len({game["project"]["title"] for game in projects.values()}), 3)
        self.assertEqual(
            len({game["content"]["missions"][0]["name"]
                 for game in projects.values()}), 3)
        self.assertEqual(
            projects["choix_village"]["project"]["game_modes"]["default"]["preset"],
            "narrative")
        self.assertNotIn("game_modes", projects["duel_tactique"]["project"])

    def test_narrative_game_has_two_meaningful_branches_without_ct_corruption(self):
        path = create_minigame("choix_village", self.root / "narrative") / "game.json"
        studio = AuthoringSession.open(path)
        data = studio.snapshot().to_dict()
        content = Content.from_dict(data["content"])
        project = GameProject.from_dict(data["project"], content)
        self.assertEqual(
            {choice["id"] for choice in project.story["scenes"][0]["choices"]},
            {"enter", "observe"})
        flags = set()
        for chosen in ("enter", "observe"):
            game = GameSession.new(content, project, "main", seed=28)
            game.choose_story_option(chosen)
            active = "r28_helped" if chosen == "enter" else "r28_observed"
            self.assertTrue(game.progress.story_flags[active])
            flags.add(active)
            record = game.recording()
            self.assertEqual(
                GameSession.from_recording(record, content, project).recording(),
                record)
        self.assertEqual(flags, {"r28_helped", "r28_observed"})
        self.assertEqual(
            project.game_modes["scenes"][next(iter(content.missions))]["preset"],
            "srpg")

    def test_preview_is_read_only_and_creation_never_overwrites_or_leaks_partial(self):
        before = set(self.root.iterdir())
        result = preview_minigame("duel_tactique", self.root / "safe")
        self.assertTrue(result["no_overwrite"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(set(self.root.iterdir()), before)
        with self.assertRaises(MiniGameError):
            preview_minigame("fiction", self.root / "missing")
        existing = self.root / "already"
        existing.mkdir()
        with self.assertRaises(MiniGameError):
            create_minigame("duel_tactique", existing)
        self.assertFalse((existing / "game.json").exists())
        with self.assertRaises(MiniGameError):
            create_minigame("duel_tactique", self.root / "absent" / "project")
        created = create_minigame("duel_tactique", self.root / "safe")
        data = (created / "game.json").read_bytes()
        with self.assertRaises(MiniGameError):
            create_minigame("duel_tactique", created)
        self.assertEqual((created / "game.json").read_bytes(), data)

    def test_portfolio_creates_three_games_and_matrix_must_remain_no_go(self):
        target = self.root / "portfolio"
        result = create_portfolio(target)
        self.assertEqual(result, target)
        matrix = certification_matrix(target)
        self.assertEqual(matrix["kind"], "r28e-certification-matrix")
        self.assertTrue(matrix["three_independent_documents"])
        self.assertEqual(set(matrix["mode_coverage"]), {"srpg", "narrative"})
        self.assertIn("action", matrix["missing_mode_coverage"])
        self.assertFalse(matrix["release_6_4_go"])
        self.assertFalse(matrix["r28_10_three_genres_certified"])
        self.assertEqual(len(matrix["projects"]), 3)
        self.assertTrue(all(row["passed"] for row in matrix["projects"]))
        self.assertEqual(
            len({row["checkpoint_digest"] for row in matrix["projects"]}), 3)
        # Poison just one built pair: certification must refuse the portfolio.
        project_path = target / "choix_village" / "game.game.json"
        old = project_path.read_text(encoding="utf-8")
        project_path.write_text(old.replace("Le choix du village", "Projet altéré"),
                                encoding="utf-8")
        poisoned = certification_matrix(target)
        self.assertFalse(poisoned["three_independent_documents"])
        self.assertFalse(poisoned["release_6_4_go"])
        self.assertFalse(next(row for row in poisoned["projects"]
                              if row["minigame"] == "choix_village")["passed"])

    def test_failed_portfolio_never_erases_existing_directory(self):
        folder = self.root / "portfolio"
        folder.mkdir()
        marker = folder / "user_notes.txt"
        marker.write_text("do not touch", encoding="utf-8")
        with self.assertRaises(MiniGameError):
            create_portfolio(folder)
        self.assertEqual(marker.read_text(encoding="utf-8"), "do not touch")
        self.assertEqual([p.name for p in folder.iterdir()], ["user_notes.txt"])


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class MiniGameQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_gallery_creates_all_via_ui_and_displays_true_no_go(self):
        from drawtemp.studio.r28e_minigames_qt import MiniGameGallery
        gallery = MiniGameGallery()
        gallery.parent_path.setText(str(self.root))
        gallery.preview()
        self.assertIn("no_overwrite", gallery.report.toPlainText())
        self.assertFalse((self.root / "duel_tactique").exists())
        gallery.create_three()
        self.assertIn("created_portfolio", gallery.report.toPlainText())
        target = self.root / "DrawTemp_R28_MiniGames"
        self.assertTrue(target.is_dir())
        for spec in MINIGAMES:
            self.assertTrue((target / spec.key / "game.json").is_file())
        gallery.certify()
        matrix = json.loads(gallery.report.toPlainText())
        self.assertFalse(matrix["release_6_4_go"])
        self.assertTrue(matrix["three_independent_documents"])
        paths = []
        gallery.openRequested.connect(paths.append)
        gallery.open_selected()
        self.assertEqual(paths, [str(target / "duel_tactique" / "game.json")])
        gallery.close()

    def test_gallery_does_not_overwrite_and_shell_adopts_session(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        source, project = reference_project()
        session = AuthoringSession.new(source, project)
        settings = QSettings(str(self.root / "test.ini"), QSettings.IniFormat)
        shell = StudioWindow(session, settings=settings)
        shell.navigate("minigames")
        page = shell.pages["minigames"]
        self.assertIs(page, shell.workspace_tabs.currentWidget())
        self.assertIn("go_minigames", shell.commands)
        page.parent_path.setText(str(self.root))
        page.create_selected()
        self.assertTrue(page.open_button.isEnabled(), page.report.toPlainText())
        path = self.root / "duel_tactique" / "game.json"
        page.open_selected()
        self.assertEqual(shell.content_path, path)
        self.assertIsNot(shell.session, session)
        self.assertEqual(
            shell.session.snapshot().to_dict()["project"]["title"],
            "Duel de l'écuyer")
        self.assertFalse(shell.session.snapshot().dirty)
        shell.close()


if __name__ == "__main__":
    unittest.main()
