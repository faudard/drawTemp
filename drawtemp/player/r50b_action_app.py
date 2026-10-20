"""R50.B opt-in Qt Quick Player using canonical GameSession persistence.

Usage:
  python -m drawtemp.player.r50b_action_app --content PROJECT/game.json --new
  python -m drawtemp.player.r50b_action_app --content PROJECT/game.json
  python -m drawtemp.player.r50b_action_app --content PROJECT/game.json --smoke

The older --action-demo remains a separate diagnostic, never used as a
source of truth for these R50.B slots. Frozen/native releases are forbidden.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from drawtemp.player.action_app import create_bridge
from drawtemp.player.r50b_action_controller import (
    R50BActionController, load_authored_action_pair,
)
from drawtemp.render.iso_scene import scene_from_action


def _default_profile(content_path):
    token = sha256(str(content_path.resolve()).encode("utf-8")).hexdigest()[:20]
    return Path.home() / ".drawtemp" / "r50b-action" / token / "profile.json"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="R50.B Qt graphical Player — canonical GameSession slot")
    parser.add_argument("--content", required=True, type=Path,
                        help="Authored canonical game.json with paired game.game.json")
    parser.add_argument("--profile", type=Path, default=None,
                        help="Explicit isolated Player profile path")
    parser.add_argument("--campaign", default=None, help="Campaign ID")
    parser.add_argument("--slot", type=int, default=1, help="Save slot (default: 1)")
    parser.add_argument("--new", action="store_true",
                        help="Create a new game; refuse overwriting an existing slot")
    parser.add_argument("--smoke", action="store_true",
                        help="Load R50.B QML offscreen with a temporary profile only")
    options = parser.parse_args(argv)
    if getattr(sys, "frozen", False):
        print("R50.B Qt prototype is not a verified native Player bundle",
              file=sys.stderr)
        return 2
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError as exc:
        print("R50.B Qt prototype requires .[qt6]: " + str(exc),
              file=sys.stderr)
        return 2

    try:
        content, project = load_authored_action_pair(options.content)
    except (OSError, ValueError) as exc:
        print("Invalid authored R50.B project: " + str(exc), file=sys.stderr)
        return 1
    temp = TemporaryDirectory(prefix="drawtemp-r50b-smoke-") if options.smoke else None
    try:
        profile = ((Path(temp.name) / "profile.json") if temp is not None
                   else (options.profile or _default_profile(options.content)))
        controller = R50BActionController(
            content, project, profile, campaign=options.campaign,
            slot=options.slot, new=options.smoke or options.new)
        app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
        from drawtemp.render.qt_viewport import make_controller
        renderer = make_controller(
            scene_from_action(controller.runtime),
            atlas_url="", projection_mode="top_down")
        bridge = create_bridge(controller, renderer)
        engine = QQmlApplicationEngine()
        renderer.attach_engine(engine)
        engine.rootContext().setContextProperty("renderer", renderer)
        engine.rootContext().setContextProperty("action", bridge)
        engine.setInitialProperties({"smokeMode": options.smoke})
        qml = Path(__file__).with_name("R50BActionPlayer.qml")
        engine.load(QUrl.fromLocalFile(str(qml)))
        if not engine.rootObjects():
            print("R50.B canonical Player QML failed to load", file=sys.stderr)
            return 1
        if options.smoke:
            QTimer.singleShot(0, app.quit)
        return app.exec()
    except (OSError, ValueError) as exc:
        print("R50.B Player refused to open the slot: " + str(exc),
              file=sys.stderr)
        return 1
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
