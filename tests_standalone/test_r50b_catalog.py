"""R50.B real authoring journey with blocked unsupported genres."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r50b_catalog import (
    CatalogError, REQUIRED_GENRES, STARTERS,
    catalog, create_starter, preview_starter, starter,
)


class R50BCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_catalog_is_explicit_about_available_and_blocked(self):
        report = catalog()
        rows = {e["id"]: e for e in report["entries"]}
        self.assertEqual(set(REQUIRED_GENRES), {
            "srpg", "action_adventure", "classic_rpg",
            "metroidvania", "roguelite",
        })
        self.assertTrue(set(REQUIRED_GENRES) <= set(rows))
        self.assertTrue(rows["srpg"]["can_create"])
        self.assertTrue(rows["narrative_prototype"]["can_create"])
        self.assertFalse(rows["narrative_hybrid"]["can_create"])
        self.assertFalse(rows["classic_rpg"]["can_create"])
        self.assertEqual(set(report["missing_creation_genres"]),
                         set(REQUIRED_GENRES) - {"srpg"})
        self.assertFalse(report["release_9_0_ready"])
        self.assertFalse(report["native_player_verified"])
        self.assertFalse(report["export_pc_verified"])
        with self.assertRaises(CatalogError):
            starter("made_up_genre")

    def test_blocked_modes_cannot_mutate_disk_or_masquerade_as_ct(self):
        for entry in STARTERS:
            if entry.minigame is not None:
                continue
            target = self.root / entry.key
            preview = preview_starter(entry.key, target)
            self.assertFalse(preview["can_create"])
            self.assertEqual(preview["will_write"], [])
            with self.subTest(genre=entry.key), self.assertRaises(CatalogError):
                create_starter(entry.key, target)
            self.assertFalse(target.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_preview_and_existing_project_are_non_destructive(self):
        dest = self.root / "duel"
        before = set(self.root.iterdir())
        result = preview_starter("srpg", dest)
        self.assertTrue(result["can_create"])
        self.assertEqual(set(self.root.iterdir()), before)
        dest.mkdir()
        marker = dest / "keep.txt"
        marker.write_text("do not overwrite", encoding="utf-8")
        self.assertFalse(preview_starter("srpg", dest)["can_create"])
        with self.assertRaises(CatalogError):
            create_starter("srpg", dest)
        self.assertEqual(marker.read_text(encoding="utf-8"), "do not overwrite")
        with self.assertRaises(CatalogError):
            preview_starter("srpg", self.root / "nonexistent" / "project")

    def test_real_studio_edit_save_and_headless_session_roundtrip(self):
        digests = {}
        for key in ("srpg", "narrative_prototype"):
            with self.subTest(starter=key):
                result = create_starter(key, self.root / key)
                self.assertEqual(result["status"], "headless-pass")
                self.assertFalse(result["release_9_0_ready"])
                self.assertFalse(result["proof"]["native_player_tested"])
                self.assertFalse(result["proof"]["standalone_export_tested"])
                self.assertTrue(result["proof"]["transactional_edit"])
                self.assertTrue(result["proof"]["undo_redo"])
                self.assertTrue(result["proof"]["saved_and_reopened"])
                self.assertTrue(result["proof"]["gamesession_checkpoint_roundtrip"])
                path = Path(result["content_path"])
                self.assertTrue(path.is_file())
                self.assertTrue(path.with_name("game.game.json").is_file())
                opened = AuthoringSession.open(path)
                self.assertFalse(opened.snapshot().dirty)
                self.assertTrue(
                    opened.snapshot().to_dict()["project"]["subtitle"].endswith(
                        "Atelier R50.B"))
                digests[key] = result["proof"]["checkpoint_digest"]
        self.assertNotEqual(digests["srpg"], digests["narrative_prototype"])

    def test_failure_cleans_staged_work_not_user_directory(self):
        output = self.root / "failure"
        with patch("drawtemp.studio.r50b_catalog._authoring_rehearsal",
                   side_effect=CatalogError("Injected stop")):
            with self.assertRaisesRegex(CatalogError, "Injected stop"):
                create_starter("srpg", output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(CatalogError):
            create_starter("srpg", "")
        self.assertFalse((self.root / "game.json").exists())


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class R50BQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_qt_disables_unavailable_genres_and_routes_existing_project(self):
        from drawtemp.studio.r50b_catalog_qt import R50CatalogWidget
        with TemporaryDirectory() as temp:
            gallery = R50CatalogWidget()
            self.assertEqual(gallery.genre.count(), len(STARTERS))
            for key in ("action_adventure", "classic_rpg",
                        "metroidvania", "roguelite", "narrative_hybrid"):
                gallery.genre.setCurrentIndex(gallery.genre.findData(key))
                self.assertFalse(gallery.create_button.isEnabled())
            gallery.parent_folder.setText(temp)
            gallery.genre.setCurrentIndex(gallery.genre.findData("srpg"))
            self.assertTrue(gallery.create_button.isEnabled())
            gallery.create()
            paths = []
            gallery.openRequested.connect(paths.append)
            gallery.open_created()
            self.assertEqual(len(paths), 1)
            self.assertTrue(Path(paths[0]).is_file())
            self.assertFalse(gallery.open_button.isEnabled()
                             and gallery.genre.currentData() != "srpg")
            gallery.close()


if __name__ == "__main__":
    unittest.main()
