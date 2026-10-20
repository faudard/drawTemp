"""R68.B1 headless touch and lifecycle tests; no mobile certification implied."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.r68_touch import PortableActionDriver, TouchInput

W, H = 800, 480


def point(ident, x, y):
    return {"id": ident, "x": x, "y": y}


def button(ident, name):
    positions = {"interact": (.67, .59), "attack": (.84, .63),
                 "guard": (.67, .83), "dodge": (.85, .86)}
    x, y = positions[name]
    return point(ident, x * W, y * H)


class FakeController:
    def __init__(self):
        self.runtime = type("Runtime", (), {
            "hero": {"alive": True}, "tick": 0
        })()
        self.paused = False
        self.commands = []

    def step(self, dx, dy, *, attack, dodge, guard, interact):
        if self.paused:
            raise AssertionError("paused controller was stepped")
        self.runtime.tick += 1
        self.commands.append((dx, dy, attack, dodge, guard, interact))


class FakeTime:
    value = 0

    def now(self):
        return self.value

    def advance(self, nanoseconds):
        self.value += nanoseconds


class TouchInputTests(unittest.TestCase):
    def test_neutral_and_diagonal_direction(self):
        touch = TouchInput()
        touch.update([point(1, .20 * W, .75 * H)], W, H)
        self.assertEqual((touch.dx, touch.dy), (0, 0))
        touch.update([point(1, .20 * W + 45, .75 * H - 45)], W, H)
        self.assertEqual((touch.dx, touch.dy), (1, -1))
        touch.update([point(1, .20 * W - 45, .75 * H + 45)], W, H)
        self.assertEqual((touch.dx, touch.dy), (-1, 1))

    def test_multitouch_hold_and_action_edges(self):
        touch = TouchInput()
        touch.update([point(1, .20 * W + 50, .75 * H),
                      button(2, "attack"), button(3, "dodge"),
                      button(4, "guard"), button(5, "interact")], W, H)
        self.assertEqual((touch.dx, touch.dy), (1, 0))
        self.assertTrue(touch.attack)
        self.assertTrue(touch.guard)
        self.assertEqual(touch.consume_edges(), (True, True))
        self.assertEqual(touch.consume_edges(), (False, False))
        touch.update([button(2, "attack"), button(3, "dodge"),
                      button(4, "guard"), button(5, "interact")], W, H)
        self.assertEqual(touch.consume_edges(), (False, False))
        touch.update([], W, H)
        self.assertFalse(touch.attack)
        touch.update([button(3, "dodge")], W, H)
        self.assertEqual(touch.consume_edges(), (True, False))

    def test_offscreen_pointer_and_cancel_are_inert(self):
        touch = TouchInput()
        touch.update([point(1, -100, 400), point(2, 7000, 9999)], W, H)
        self.assertEqual((touch.dx, touch.dy), (0, 0))
        touch.update([button(1, "attack")], W, H)
        touch.reset()
        self.assertFalse(touch.attack)
        self.assertEqual(touch.consume_edges(), (False, False))

    def test_conflicting_directions_are_bounded(self):
        touch = TouchInput()
        touch.update([point(1, .20 * W - 60, .75 * H),
                      point(2, .20 * W + 60, .75 * H)], W, H)
        self.assertEqual((touch.dx, touch.dy), (0, 0))

    def test_untrusted_touch_records_fail_without_state_mutation(self):
        touch = TouchInput()
        touch.update([button(1, "attack")], W, H)
        invalid = [
            ([], True, H), ([], W, 0), ("not-a-list", W, H),
            ([point(1, 20, 200)] * 2, W, H),
            ([{"id": True, "x": 1, "y": 2}], W, H),
            ([{"id": 1, "x": float("nan"), "y": 2}], W, H),
            ([{"id": 1, "x": float("inf"), "y": 2}], W, H),
            ([{"id": 1, "x": 10 ** 1000, "y": 2}], W, H),
            ([], 100_000, H),
            ([{"id": 1, "x": 1, "y": 1, "extra": 3}], W, H),
            ([point(n, 1, 1) for n in range(11)], W, H),
        ]
        for points, width, height in invalid:
            with self.subTest(points=points), self.assertRaises(ValueError):
                touch.update(points, width, height)
            self.assertTrue(touch.attack)
        self.assertEqual(touch.consume_edges(), (False, False))


class PortableActionDriverTests(unittest.TestCase):
    def make_driver(self):
        clock = FakeTime()
        controller = FakeController()
        return clock, controller, PortableActionDriver(controller, now_ns=clock.now)

    def test_touch_and_keyboard_feed_same_step(self):
        clock, controller, driver = self.make_driver()
        driver.update_touch([point(1, .20 * W + 50, .75 * H),
                             button(2, "attack")], W, H)
        clock.advance(20_000_000)
        self.assertEqual(driver.pulse(0, 0), 1)
        self.assertEqual(controller.commands[0], (1, 0, True, False, False, False))
        clock.advance(20_000_000)
        driver.pulse(0, -1, guard=True)
        self.assertEqual(controller.commands[1][:3], (1, -1, True))
        self.assertTrue(controller.commands[1][4])

    def test_tap_survives_zero_tick_poll_once(self):
        clock, controller, driver = self.make_driver()
        driver.update_touch([button(1, "dodge"), button(2, "interact")], W, H)
        clock.advance(2_000_000)
        self.assertEqual(driver.pulse(0, 0), 0)
        driver.update_touch([], W, H)
        clock.advance(20_000_000)
        self.assertEqual(driver.pulse(0, 0), 1)
        self.assertEqual(controller.commands[0][3:], (True, False, True))
        clock.advance(20_000_000)
        driver.pulse(0, 0)
        self.assertFalse(controller.commands[1][3])
        self.assertFalse(controller.commands[1][5])

    def test_background_time_not_caught_up_and_inputs_cleared(self):
        clock, controller, driver = self.make_driver()
        clock.advance(20_000_000)
        driver.pulse(0, 0)
        self.assertEqual(controller.runtime.tick, 1)
        driver.update_touch([button(3, "attack"), button(4, "dodge")], W, H)
        driver.set_active(False)
        clock.advance(15_000_000_000)
        self.assertEqual(driver.pulse(0, 0), 0)
        self.assertEqual(controller.runtime.tick, 1)
        driver.set_active(True)
        self.assertEqual(driver.pulse(0, 0), 0)
        clock.advance(20_000_000)
        self.assertEqual(driver.pulse(0, 0), 1)
        self.assertEqual(controller.commands[-1], (0, 0, False, False, False, False))

    def test_manual_pause_retained_across_platform_suspend(self):
        clock, controller, driver = self.make_driver()
        controller.paused = True
        driver.set_active(False)
        clock.advance(3_000_000_000)
        driver.set_active(True)
        clock.advance(20_000_000)
        self.assertEqual(driver.pulse(1, 1), 0)
        self.assertTrue(controller.paused)
        controller.paused = False
        clock.advance(20_000_000)
        driver.pulse(1, 0)
        self.assertEqual(controller.commands[-1][0:2], (1, 0))

    def test_framerate_independence_and_no_burst_after_stall(self):
        results = []
        for fps in (30, 60, 120):
            clock, controller, driver = self.make_driver()
            for frame in range(1, fps + 1):
                clock.value = frame * 1_000_000_000 // fps
                driver.pulse(1, 0)
            results.append(controller.runtime.tick)
        self.assertEqual(results, [60, 60, 60])
        clock, controller, driver = self.make_driver()
        clock.advance(60_000_000_000)
        driver.pulse(1, 0)
        self.assertEqual(controller.runtime.tick, 6)  # R26 catch-up cap.

    def test_defeated_controller_is_not_stepped(self):
        clock, controller, driver = self.make_driver()
        controller.runtime.hero["alive"] = False
        clock.advance(20_000_000)
        self.assertEqual(driver.pulse(0, 0, attack=True), 0)
        self.assertEqual(controller.commands, [])

    def test_bad_lifecycle_flag_is_refused(self):
        _, _, driver = self.make_driver()
        with self.assertRaises(ValueError):
            driver.set_active(1)
        self.assertTrue(driver.active)


class IntegrationGuards(unittest.TestCase):
    def test_spike_remains_opt_in_and_qml_is_packaged(self):
        root = Path(__file__).resolve().parents[1]
        action = (root / "drawtemp/player/action_app.py").read_text(encoding="utf-8")
        qml = (root / "drawtemp/player/ActionPreview.qml").read_text(encoding="utf-8")
        overlay = (root / "drawtemp/player/MobileTouchOverlay.qml").read_text(encoding="utf-8")
        package = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("--touch-preview", action)
        self.assertIn("setPlatformActive", action)
        self.assertIn("MobileTouchOverlay", qml)
        self.assertIn("MultiPointTouchArea", overlay)
        self.assertIn('"player/*.qml"', package)

    def test_real_r26_controller_save_replay_roundtrip(self):
        from drawtemp.player.action_controller import ActionPlayerController, demo_scene
        with TemporaryDirectory() as temp:
            path = Path(temp) / "action.json"
            controller = ActionPlayerController(demo_scene(), save_path=path)
            clock = FakeTime()
            driver = PortableActionDriver(controller, now_ns=clock.now)
            driver.update_touch([point(1, .20 * W + 50, .75 * H)], W, H)
            clock.advance(50_000_000)
            self.assertEqual(driver.pulse(0, 0), 3)
            controller.save()
            checkpoint = controller.runtime.digest()
            clock.advance(50_000_000)
            driver.pulse(0, 1)
            self.assertNotEqual(checkpoint, controller.runtime.digest())
            driver.set_active(False)
            controller.load()
            driver.reset()
            self.assertEqual(controller.runtime.digest(), checkpoint)
            driver.set_active(True)
            clock.advance(20_000_000)
            driver.pulse(0, 0)
            self.assertEqual(controller.runtime.tick, 4)


if __name__ == "__main__":
    unittest.main()
