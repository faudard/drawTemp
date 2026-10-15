"""R4.B Qt smoke: real shared QML viewport uses atlas, not a new painter."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.reference import MISSION
from tests_standalone.test_drawtemp5_r4_runtime import imported_jeanne


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt6 extra not installed")
class R4QtRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_r3_controller_and_qml_show_real_animated_jeanne(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from drawtemp.assets.runtime import PresentationAssets
        from drawtemp.render.iso_scene import scene_from_mission
        from drawtemp.render.qt_viewport import make_controller

        with tempfile.TemporaryDirectory() as tmp:
            _, project_path, content, project = imported_jeanne(tmp)
            scene = scene_from_mission(content.missions[MISSION])
            renderer = make_controller(
                scene, assets=PresentationAssets.for_project(project, project_path))
            self.assertTrue(renderer.animatedAssets)
            actor = next(row for row in renderer.items
                         if row["kind"] == "actor" and row["id"] == "jeanne")
            self.assertTrue(actor["imageUrl"].startswith("file:"))
            self.assertEqual(actor["assetId"], "jeanne.south.idle.0")
            renderer.advanceVisual(120)
            next_actor = next(row for row in renderer.items
                              if row["kind"] == "actor" and row["id"] == "jeanne")
            self.assertEqual(next_actor["assetId"], "jeanne.south.idle.1")
            self.assertEqual(renderer.scene, scene)
            viewport = QQuickWidget()
            try:
                viewport.rootContext().setContextProperty("renderer", renderer)
                viewport.setResizeMode(QQuickWidget.SizeRootObjectToView)
                viewport.setSource(QUrl.fromLocalFile(str(
                    Path(__file__).resolve().parents[1] /
                    "drawtemp/render/IsoViewport.qml")))
                self.assertNotEqual(viewport.status(), QQuickWidget.Error,
                                    "\n".join(str(e) for e in viewport.errors()))
                self.assertIsNotNone(viewport.rootObject())
                viewport.show()
                self.app.processEvents()
            finally:
                viewport.hide()
                viewport.deleteLater()

    def test_studio_embeds_browser_and_uses_same_resource(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow

        with tempfile.TemporaryDirectory() as tmp:
            _, project_path, content, project = imported_jeanne(tmp)
            studio = MapStudio(AuthoringSession.new(content, project), MISSION)
            window = MapWindow(studio, project_path=project_path)
            try:
                self.assertIsNotNone(window.asset_browser_dock)
                self.assertEqual(window.asset_browser.items.count(), 4)
                self.assertTrue(window.renderer.animatedAssets)
                actor = next(row for row in window.renderer.items
                             if row["kind"] == "actor" and row["id"] == "jeanne")
                self.assertEqual(actor["assetId"], "jeanne.south.idle.0")
                self.assertIsNotNone(window.viewport.rootObject())
            finally:
                window.hide()
                window.deleteLater()

    def test_player_runs_with_same_imported_project_without_studio(self):
        with tempfile.TemporaryDirectory() as tmp:
            content_path, project_path, _, _ = imported_jeanne(tmp)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       QT_QUICK_BACKEND="software")
            process = subprocess.run(
                [sys.executable, "-m", "drawtemp.player.qt_app",
                 "--content", str(content_path), "--project", str(project_path),
                 "--save-dir", str(Path(tmp) / "saves"), "--smoke"],
                env=env, cwd=Path(__file__).resolve().parents[1],
                capture_output=True, text=True, timeout=35)
            self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
