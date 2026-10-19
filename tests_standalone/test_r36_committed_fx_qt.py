"""R36.B Qt offscreen smoke for the R3 action Player + cosmetic overlay.

No GPU performance claim: this checks QML instantiation only.
"""
from __future__ import annotations

import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QSG_RHI_BACKEND", "software")

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Optional Qt6 installation required")
class CommittedFxQtTests(unittest.TestCase):
    def test_action_player_qml_instantiates_with_fx_overlay(self):
        from drawtemp.player.action_app import main
        self.assertEqual(main(["--smoke"]), 0)


if __name__ == "__main__":
    unittest.main()
