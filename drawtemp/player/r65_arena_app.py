"""R65.C standalone opt-in Qt Quick arena over the existing R3 renderer.

Run: python -m drawtemp.player.r65_arena_app
     python -m drawtemp.player.r65_arena_app --smoke
     python -m drawtemp.player.r65_arena_app --content game.json \
          --project game.game.json --preset arena

R65 v3 checkpoint only; not a canonical R50/GameSession slot.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from drawtemp.player.action_clock import ActionStepClock
from drawtemp.player.r65_arena_controller import ActionArenaController
from sporebound.action_arena_r65 import arena_demo
from sporebound.action_combat_catalog_r65 import preset_from_project
from drawtemp.render.iso_scene import scene_from_action


def create_bridge(controller, renderer, *, now_ns=None):
    from PySide6.QtCore import QObject, Property, Signal, Slot

    class ArenaBridge(QObject):
        stateChanged = Signal()

        def __init__(self):
            super().__init__()
            self.controller = controller
            self.renderer = renderer
            self.clock = ActionStepClock(hz=60)
            self._now = now_ns or time.monotonic_ns
            self._last_ns = self._now()
            self._queued_dodge = False
            self._queued_parry = False
            self._queued_interact = False
            self.publish()

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        def reset_clock(self):
            self.clock.reset()
            self._last_ns = self._now()
            self._queued_dodge = False
            self._queued_parry = False
            self._queued_interact = False

        def publish(self):
            from sporebound.action_runtime import SCALE
            hero = self.controller.runtime.hero
            target = (hero["pos"][0] / SCALE - .5,
                      hero["pos"][1] / SCALE - .5)
            self.renderer.replace_scene(
                scene_from_action(self.controller.runtime),
                follow_world=target)
            self.stateChanged.emit()

        @Slot(int, int, bool, bool, bool, bool, bool, bool)
        def pulse(self, dx, dy, attack, dodge, guard, interact, fire, parry):
            now = self._now()
            elapsed = max(0, now - self._last_ns)
            self._last_ns = now
            if self.controller.paused or not self.controller.runtime.hero["alive"]:
                self.reset_clock()
                return
            self._queued_dodge |= bool(dodge)
            self._queued_parry |= bool(parry)
            self._queued_interact |= bool(interact)
            steps = self.clock.advance(elapsed)
            for _ in range(steps):
                if not self.controller.runtime.hero["alive"] or (
                        self.controller.runtime.snapshot()["arena"]["victory"]):
                    break
                try:
                    self.controller.step(
                        dx, dy, attack=attack, dodge=self._queued_dodge,
                        guard=guard, interact=self._queued_interact,
                        fire=fire, parry=self._queued_parry)
                except Exception as exc:
                    self.controller.message = "Tick refusé : " + str(exc)
                    self.reset_clock()
                    break
                self._queued_dodge = False
                self._queued_parry = False
                self._queued_interact = False
            if steps:
                self.publish()

        @Slot()
        def pause(self):
            self.controller.toggle_pause()
            self.reset_clock()
            self.publish()

        @Slot()
        def save(self):
            try:
                self.controller.save()
            except Exception as exc:
                self.controller.message = "Sauvegarde refusée : " + str(exc)
            self.reset_clock()
            self.publish()

        @Slot()
        def load(self):
            try:
                self.controller.load()
            except Exception as exc:
                self.controller.message = "Chargement refusé : " + str(exc)
            self.reset_clock()
            self.publish()

        @Slot()
        def restart(self):
            try:
                self.controller.respawn()
            except Exception as exc:
                self.controller.message = "Reprise refusée : " + str(exc)
            self.reset_clock()
            self.publish()

    return ArenaBridge()


def main(argv=None):
    parser = argparse.ArgumentParser(description="R65.C isolated action arena")
    parser.add_argument("--smoke", action="store_true",
                        help="Open Qt offscreen and quit before any gameplay")
    parser.add_argument("--save-dir", type=Path,
                        default=Path.home() / ".drawtemp" / "r65-arena")
    parser.add_argument("--content", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--preset", default=None)
    args = parser.parse_args(argv)
    if bool(args.content) != bool(args.project):
        parser.error("--content and --project are required together")
    if args.preset and not args.project:
        parser.error("--preset requires --content/--project")

    scene, default_preset, setup = arena_demo()
    preset = default_preset
    if args.project:
        from sporebound.model import Content
        from sporebound.game_project import GameProject
        try:
            project = GameProject.load(args.project, Content.load(args.content))
            preset = preset_from_project(project, args.preset)
        except Exception as exc:
            print("R65 preset rejected: " + str(exc), file=sys.stderr)
            return 2
    try:
        controller = ActionArenaController(
            scene, preset, setup,
            save_path=args.save_dir / "arena-v3.json")
    except Exception as exc:
        print("R65 arena rejected: " + str(exc), file=sys.stderr)
        return 2
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print("R65 arena Qt requires PySide6: " + str(exc), file=sys.stderr)
        return 2

    from drawtemp.render.qt_viewport import make_controller
    app = QGuiApplication([sys.argv[0]])
    renderer = make_controller(
        scene_from_action(controller.runtime),
        atlas_url="", projection_mode="top_down")
    bridge = create_bridge(controller, renderer)
    engine = QQmlApplicationEngine()
    renderer.attach_engine(engine)
    engine.rootContext().setContextProperty("renderer", renderer)
    engine.rootContext().setContextProperty("arena", bridge)
    engine.setInitialProperties({"smokeMode": args.smoke})
    engine.load(QUrl.fromLocalFile(str(
        Path(__file__).with_name("R65Arena.qml"))))
    if not engine.rootObjects():
        print("R65 arena QML failed to load", file=sys.stderr)
        return 1
    if args.smoke:
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
