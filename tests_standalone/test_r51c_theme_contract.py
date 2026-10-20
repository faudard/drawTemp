"""R51.C: verify that Studio and Player wire the exact shared QML resources.

These are static contract checks only. Physical accessibility and GPU still
require qualified human and device tests before a release is considered GO.
"""
from pathlib import Path
import unittest

from drawtemp.studio.r51_layout_draft import editor_sample, new_layout
from drawtemp.quality.r51_ui import ui_export_audit


class R51CThemeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1]
        cls.node = (cls.root / "drawtemp/player/R51Node.qml").read_text(encoding="utf-8")
        cls.layout = (cls.root / "drawtemp/player/R51Layout.qml").read_text(encoding="utf-8")
        cls.player = (cls.root / "drawtemp/player/Main.qml").read_text(encoding="utf-8")
        cls.studio = (cls.root / "drawtemp/studio/r51_designer_qt.py").read_text(
            encoding="utf-8")
        cls.packaging = (cls.root / "pyproject.toml").read_text(encoding="utf-8")

    def test_shared_qml_component_used_by_studio_player_and_wheel(self):
        self.assertIn('"R51Layout.qml"', self.studio)
        self.assertIn("R51Layout {", self.player)
        self.assertIn("R51Node {", self.layout)
        self.assertIn('"player/*.qml"', self.packaging)
        self.assertIn("Text.PlainText", self.node)
        self.assertNotIn("eval(", self.node)
        self.assertNotIn("Qt.createQmlObject", self.node)

    def test_preferences_flow_and_focus_accessible_contrast(self):
        self.assertIn("property bool highContrast: false", self.layout)
        self.assertIn("property real textScale: 1.0", self.layout)
        self.assertIn("highContrast: canvas.highContrast", self.layout)
        self.assertIn("textScale: canvas.textScale", self.layout)
        self.assertGreaterEqual(self.node.count("highContrast: nodeItem.highContrast"), 2)
        self.assertGreaterEqual(self.node.count("textScale: nodeItem.textScale"), 2)
        self.assertGreaterEqual(self.player.count("highContrast: root.highContrast"), 2)
        self.assertGreaterEqual(self.player.count("textScale: root.textScale"), 2)
        self.assertIn("self.contrast_preview = QCheckBox", self.studio)
        self.assertIn("self.scale_preview = QSpinBox", self.studio)
        self.assertIn('setProperty("highContrast"', self.studio)
        self.assertIn('setProperty("textScale"', self.studio)
        self.assertIn("ui_export_audit", self.studio)
        self.assertIn("Export bloqué", self.studio)
        self.assertIn("Accessible.description", self.node)
        self.assertIn("Math.max(44", self.node)
        self.assertIn("parent.activeFocus", self.node)
        self.assertIn("onFocusMove", self.layout)

    def test_editor_samples_are_still_explicitly_not_live_game_state(self):
        data = editor_sample(new_layout("MENU"), 1280)
        self.assertIs(data["sample"], True)
        self.assertEqual(data["kind"], "MENU")
        self.assertFalse(ui_export_audit({"title": "legacy"})["present"])


if __name__ == "__main__":
    unittest.main()
