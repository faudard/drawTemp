"""R26.B opt-in Qt Quick action preview, with gameplay owned by ActionRuntime.

Launch using: python -m drawtemp.player.action_app [--smoke] [--save-dir DIR]
The existing tactical Player entry point is untouched unless --action-demo
is explicitly selected.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from drawtemp.player.action_clock import ActionStepClock
from drawtemp.player.action_controller import ActionPlayerController, demo_scene
from drawtemp.render.iso_scene import scene_from_action


def create_bridge(controller, renderer):
    """A QObject adapter; imported lazily to preserve headless Python installs."""
    from PySide6.QtCore import QObject, Property, Signal, Slot

    class ActionBridge(QObject):
        stateChanged = Signal()

        def __init__(self, controller):
            super().__init__()
            self.controller = controller
            self.renderer = renderer
            self._clock = ActionStepClock()
            self._last_ns = time.monotonic_ns()
            self._pending_dodge = False
            self._pending_interact = False
            self._publish()

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        def _publish(self):
            hero = self.controller.runtime.hero
            from sporebound.action_runtime import SCALE
            target = (hero["pos"][0] / SCALE - .5,
                      hero["pos"][1] / SCALE - .5)
            self.renderer.replace_scene(
                scene_from_action(self.controller.runtime), follow_world=target)
            self.stateChanged.emit()

        def _resync(self):
            self._clock.reset()
            self._last_ns = time.monotonic_ns()
            self._pending_dodge = False
            self._pending_interact = False

        @Slot(int, int, bool, bool, bool, bool)
        def tick(self, dx, dy, attack, dodge, guard, interact):
            """One explicit logical tick for deterministic Qt test drivers."""
            try:
                self.controller.step(dx, dy, attack=attack, dodge=dodge,
                                     guard=guard, interact=interact)
            except Exception as exc:
                self.controller.message = "Action refusée : " + str(exc)
            self._resync()
            self._publish()

        @Slot(int, int, bool, bool, bool, bool)
        def pulse(self, dx, dy, attack, dodge, guard, interact):
            """Poll input at arbitrary UI FPS and step 60 Hz logical time."""
            now = time.monotonic_ns()
            elapsed = max(0, now - self._last_ns)
            self._last_ns = now
            if self.controller.paused or not self.controller.runtime.hero["alive"]:
                self._resync()
                return
            # Edge-triggered actions survive polls that produce zero logical
            # ticks, and are consumed once on the first successful tick.
            self._pending_dodge |= dodge
            self._pending_interact |= interact
            steps = self._clock.advance(elapsed)
            if not steps:
                return
            try:
                for _ in range(steps):
                    if not self.controller.runtime.hero["alive"]:
                        break
                    self.controller.step(
                        dx, dy, attack=attack, dodge=self._pending_dodge,
                        guard=guard, interact=self._pending_interact)
                    self._pending_dodge = False
                    self._pending_interact = False
            except Exception as exc:
                self.controller.message = "Action refusée : " + str(exc)
                self._resync()
            self._publish()

        @Slot()
        def pause(self):
            self.controller.toggle_pause()
            self._resync()
            self.stateChanged.emit()

        @Slot()
        def save(self):
            try:
                self.controller.save()
            except (OSError, ValueError) as exc:
                self.controller.message = str(exc)
            self._resync()
            self.stateChanged.emit()

        @Slot()
        def load(self):
            try:
                self.controller.load()
            except Exception as exc:
                self.controller.message = "Reprise refusée : " + str(exc)
            self._resync()
            self._publish()

        @Slot()
        def respawn(self):
            try:
                self.controller.respawn()
            except Exception as exc:
                self.controller.message = "Respawn refusé : " + str(exc)
            self._resync()
            self._publish()

    return ActionBridge(controller)


def main(argv=None):
    parser = argparse.ArgumentParser(description="R26 experimental Action Player preview")
    parser.add_argument("--smoke", action="store_true",
                        help="Instantiate offscreen UI and stop before gameplay")
    parser.add_argument("--save-dir", type=Path,
                        default=Path.home() / ".drawtemp" / "action-preview")
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print("Qt 6 unavailable: pip install '.[qt6]' — " + str(exc), file=sys.stderr)
        return 2

    app = QGuiApplication([sys.argv[0]])
    controller = ActionPlayerController(
        demo_scene(), save_path=args.save_dir / "action.json")
    # The exact same R3 projection/controller handles Studio, tactical Player
    # and this opt-in action Player. The Qt delegate is projection-specific.
    from drawtemp.render.qt_viewport import make_controller
    renderer = make_controller(scene_from_action(controller.runtime),
                               atlas_url="", projection_mode="top_down")
    bridge = create_bridge(controller, renderer)
    engine = QQmlApplicationEngine()
    renderer.attach_engine(engine)
    engine.rootContext().setContextProperty("renderer", renderer)
    engine.rootContext().setContextProperty("action", bridge)
    engine.setInitialProperties({"smokeMode": args.smoke})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("ActionPreview.qml"))))
    if not engine.rootObjects():
        print("R26 action preview QML failed to load", file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]
    if args.smoke:
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
