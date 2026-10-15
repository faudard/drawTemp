"""Qt 6 R4 browser smoke: real widget navigation, thumbnails and bookmarks."""
import os
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.atlas import DirectionalLayout, plan_directional_import
from sporebound.assets import AssetRegistry
from tests_standalone.test_drawtemp5_r4_assets import rgba_png


class R4QtBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            raise unittest.SkipTest("PySide6 optional Qt 6 extra not installed")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_browser_displays_atlas_animation_group_and_search_favorite(self):
        from drawtemp.assets.qt_browser import AssetBrowser, MIME_ASSET_ID
        self.assertEqual(MIME_ASSET_ID, "application/x-drawtemp-asset-id")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.png"
            source.write_bytes(rgba_png(256, 128))
            plan = plan_directional_import(
                AssetRegistry(), source, "jeanne",
                DirectionalLayout((64, 64), {"idle": (0,), "attack": (1,)},
                                  pivot=(32, 60)), license_id="CC0-1.0")
            plan.copy_into(root)
            widget = AssetBrowser(AssetRegistry(plan.manifest), root)
            self.addCleanup(widget.close)
            self.assertEqual(widget.items.count(), 8)
            self.assertFalse(widget.preview.pixmap().isNull())
            widget.search.setText("attack")
            self.assertEqual(widget.items.count(), 4)
            self.assertEqual(len(widget._frames), 1)
            chosen = widget.items.currentItem()
            self.assertIsNotNone(chosen)
            mime = widget.items.mimeData([chosen])
            self.assertTrue(mime.hasFormat(MIME_ASSET_ID))
            self.assertEqual(bytes(mime.data(MIME_ASSET_ID)).decode(),
                             chosen.data(0x0100))
            widget.favorite.click()
            widget.filter.setCurrentText("favorites")
            self.assertEqual(widget.items.count(), 1)
            self.assertIn(widget.items.currentItem().data(0x0100), widget.preferences.favorites)
            widget.clock.stop()


if __name__ == "__main__":
    unittest.main()
