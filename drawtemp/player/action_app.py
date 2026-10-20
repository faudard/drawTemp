"""R26.B opt-in Qt Quick action preview, with gameplay owned by ActionRuntime.

Launch using: python -m drawtemp.player.action_app [--smoke] [--save-dir DIR]
The existing tactical Player entry point is untouched unless --action-demo
is explicitly selected.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from drawtemp.player.action_clock import ActionStepClock
from drawtemp.player.action_controller import ActionPlayerController, demo_scene
from drawtemp.render.iso_scene import scene_from_action
from drawtemp.render.r36_frame_budget import R36FrameBudget


def create_bridge(controller, renderer, *, profiling=False):
    """A QObject adapter; imported lazily to preserve headless Python installs."""
    from PySide6.QtCore import QObject, Property, Signal, Slot

    class ActionBridge(QObject):
        stateChanged = Signal()

        def __init__(self, controller):
            super().__init__()
            self.controller = controller
            self.renderer = renderer
            self.telemetry = R36FrameBudget() if profiling else None
            self._last_profile_tick = -1
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
            scene = scene_from_action(
                self.controller.runtime,
                animation_frames=(self.controller.animation.frames()
                                  if self.controller.animation is not None else None))
            # Pure optical diagnostic: geometry is the authored R26 wall grid.
            # Lighting cannot alter the committed rules engine or collision.
            from drawtemp.render.cell_lighting import project_cell_lighting
            lights = self.controller.state()["vfx"]["lights"]
            if lights:
                scene["light_cells"] = project_cell_lighting(
                    self.controller.scene, lights)
            submit_start_ns = time.perf_counter_ns() if self.telemetry else None
            self.renderer.replace_scene(scene, follow_world=target)
            if self.telemetry is not None:
                view = self.controller.state()
                tick = self.controller.runtime.tick
                if tick < self._last_profile_tick:
                    self.telemetry.reset()
                self._last_profile_tick = tick
                items = self.renderer.items
                self.telemetry.record(
                    tick=tick, duration_ns=time.perf_counter_ns() - submit_start_ns,
                    items=len(items),
                    actors=sum(1 for row in items if row["kind"] == "actor"),
                    particles=len(view["vfx"]["particles"]),
                    lights=len(view["vfx"]["lights"]),
                    fx=min(96, len(view["fx"]) + len(view["animation_cues"])),
                )
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

        @Slot()
        def settle(self):
            """R50.B only: commit action victory and real CT start."""
            try:
                self.controller.settle()
            except Exception as exc:
                self.controller.message = "Victoire non validée : " + str(exc)
            self._resync()
            self._publish()

        @Slot()
        def returnFromCt(self):
            """R50.B only: abandon CT with no tactical loot and return."""
            try:
                self.controller.return_from_ct()
            except Exception as exc:
                self.controller.message = "Retour CT refusé : " + str(exc)
            self._resync()
            self._publish()

    return ActionBridge(controller)


def main(argv=None):
    parser = argparse.ArgumentParser(description="R26 experimental Action Player preview")
    parser.add_argument("--smoke", action="store_true",
                        help="Instantiate offscreen UI and stop before gameplay")
    parser.add_argument("--save-dir", type=Path,
                        default=Path.home() / ".drawtemp" / "action-preview")
    parser.add_argument("--content", type=Path,
                        help="Canonical Content JSON for --animation-project")
    parser.add_argument("--animation-project", type=Path,
                        help="Validated GameProject JSON containing R28/R36 animation assets")
    parser.add_argument("--profile-r36", type=Path,
                        help="Write opt-in CPU render-submit telemetry at Player exit")
    parser.add_argument("--hero-controller",
                        help="Existing R36 Animation Controller bound to the action hero")
    args = parser.parse_args(argv)
    if any((args.content, args.animation_project, args.hero_controller)) and not all(
            (args.content, args.animation_project, args.hero_controller)):
        parser.error("--content, --animation-project and --hero-controller are required together")
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print("Qt 6 unavailable: pip install '.[qt6]' — " + str(exc), file=sys.stderr)
        return 2

    app = QGuiApplication([sys.argv[0]])
    animation_project = None
    if args.animation_project is not None:
        from sporebound.model import Content
        from sporebound.game_project import GameProject
        try:
            animation_project = GameProject.load(
                args.animation_project, Content.load(args.content))
        except (OSError, ValueError, TypeError) as exc:
            print("R36 animation project rejected: " + str(exc), file=sys.stderr)
            return 2
    try:
        controller = ActionPlayerController(
            demo_scene(), save_path=args.save_dir / "action.json",
            animation_project=animation_project,
            animation_bindings=({"hero": args.hero_controller}
                                if args.hero_controller else None))
    except (ValueError, TypeError) as exc:
        print("R36 hero binding rejected: " + str(exc), file=sys.stderr)
        return 2
    # The exact same R3 projection/controller handles Studio, tactical Player
    # and this opt-in action Player. The Qt delegate is projection-specific.
    from drawtemp.render.qt_viewport import make_controller
    # The R4 resolver/atlas is also the only R36 image path. Missing user
    # assets become per-actor placeholder diagnostics, not gameplay failure.
    assets = None
    if animation_project is not None:
        from drawtemp.assets.r36_runtime import R36PresentationAssets
        try:
            assets = R36PresentationAssets.for_project(
                animation_project, args.animation_project)
        except (OSError, RuntimeError, ValueError) as exc:
            print("R36 asset resolver rejected: " + str(exc), file=sys.stderr)
            return 2
    renderer = make_controller(scene_from_action(controller.runtime),
                               atlas_url="", projection_mode="top_down",
                               assets=assets)
    bridge = create_bridge(controller, renderer,
                           profiling=args.profile_r36 is not None)
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
    code = app.exec()
    if args.profile_r36 is not None and bridge.telemetry is not None:
        args.profile_r36.write_text(
            json.dumps(bridge.telemetry.report(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
