"""R26.B opt-in Qt Quick action preview, with gameplay owned by ActionRuntime.

Launch using: python -m drawtemp.player.action_app [--smoke] [--save-dir DIR]
The existing tactical Player entry point is untouched unless --action-demo
is explicitly selected.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from drawtemp.player.action_controller import ActionPlayerController, demo_scene


def create_bridge(controller):
    """A QObject adapter; imported lazily to preserve headless Python installs."""
    from PySide6.QtCore import QObject, Property, Signal, Slot

    class ActionBridge(QObject):
        stateChanged = Signal()

        def __init__(self, controller):
            super().__init__()
            self.controller = controller

        @Property("QVariantMap", notify=stateChanged)
        def view(self):
            return self.controller.state()

        @Slot(int, int, bool, bool, bool, bool)
        def tick(self, dx, dy, attack, dodge, guard, interact):
            try:
                self.controller.step(dx, dy, attack=attack, dodge=dodge,
                                     guard=guard, interact=interact)
            except Exception as exc:
                # A rejected command never changes authoritative game state.
                self.controller.message = "Action refusée : " + str(exc)
            self.stateChanged.emit()

        @Slot()
        def pause(self):
            self.controller.toggle_pause()
            self.stateChanged.emit()

        @Slot()
        def save(self):
            try:
                self.controller.save()
            except (OSError, ValueError) as exc:
                self.controller.message = str(exc)
            self.stateChanged.emit()

        @Slot()
        def load(self):
            try:
                self.controller.load()
            except Exception as exc:
                self.controller.message = "Reprise refusée : " + str(exc)
            self.stateChanged.emit()

        @Slot()
        def respawn(self):
            try:
                self.controller.respawn()
            except (OSError, ValueError, Exception) as exc:
                self.controller.message = "Respawn refusé : " + str(exc)
            self.stateChanged.emit()

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
    bridge = create_bridge(controller)
    engine = QQmlApplicationEngine()
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
