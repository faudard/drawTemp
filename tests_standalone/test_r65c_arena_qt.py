"""R65.C optional actual Qt Quick viewport smoke and fixed clock checks."""
import importlib.util
import os
import unittest
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from drawtemp.player.action_clock import ActionStepClock
from sporebound.action_arena_r65 import arena_demo

_HAS_QT = importlib.util.find_spec("PySide6") is not None


class R65ArenaClockTests(unittest.TestCase):
    def test_display_polling_30_60_120_keeps_60_simulation_ticks(self):
        # Logical R65 combat rate remains 60; only polling period varies.
        for fps in (30, 60, 120):
            clock = ActionStepClock(hz=60)
            steps = 0
            # Integer-nanosecond total: exact for one second.
            last = 0
            for index in range(1, fps + 1):
                now = 1_000_000_000 * index // fps
                steps += clock.advance(now - last)
                last = now
            self.assertEqual(steps, 60, "display FPS must not change combat steps")

    def test_arena_demo_is_valid_and_original(self):
        scene, preset, setup = arena_demo()
        self.assertEqual(len(scene["enemies"]), 3)
        self.assertEqual(len(preset["boss_patterns"]), 2)
        self.assertEqual(set(setup["flankers"]),
                         {"scout_left", "scout_right"})


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class R65ArenaQtTests(unittest.TestCase):
    def test_offscreen_qml_loads_real_shared_renderer(self):
        from drawtemp.player.r65_arena_app import main
        with TemporaryDirectory() as temp:
            result = main(["--smoke", "--save-dir", temp])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
