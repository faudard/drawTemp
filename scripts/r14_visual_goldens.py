"""R14.5 real Qt scene screenshots, candidate review and golden comparison.

Usage:
  python scripts/r14_visual_goldens.py capture --output r14-goldens
  python scripts/r14_visual_goldens.py capture --output r14-goldens --require-approved
  python scripts/r14_visual_goldens.py approve --capture r14-goldens --reviewer <person>

No capture is silently promoted to an approved baseline. Running with
--require-approved is intentionally fail-closed until human reviewed assets exist.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

from drawtemp.quality.r14_goldens import (
    EXPECTED, approve_candidates, case_id, digest, evaluate_capture,
    html_report, profile_id, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDENS = ROOT / "tests_standalone/goldens/r14"


def render_frame(args):
    """Private child process: QT_SCALE_FACTOR set before any Qt imports."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    expected_dpi = args.dpi
    if os.environ.get("QT_SCALE_FACTOR") != str(expected_dpi):
        raise RuntimeError("DPI must be fixed in a fresh child Qt process")
    app = QApplication.instance() or QApplication(["drawtemp-r14-goldens"])
    screen = app.primaryScreen()
    if screen is None or abs(screen.devicePixelRatio() - expected_dpi) > 0.1:
        raise RuntimeError("Qt platform ignored required devicePixelRatio")
    target = args.target
    if target == "studio":
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.studio.map_authoring import MapStudio
        window = MapWindow(MapStudio.reference())
        window.resize(1120, 720)
        window.renderer.camera.zoom = args.zoom
        window.renderer.center_scene()
        window.show()
        QTest.qWait(350)
        if window.viewport.rootObject() is None:
            raise RuntimeError("Studio IsoViewport failed to load")
        image = window.viewport.grabFramebuffer()
        window.hide()
        window.deleteLater()
    else:
        from drawtemp.player.qt_app import build_controller, create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.sdk.reference import MISSION
        with TemporaryDirectory() as save_dir:
            controller = build_controller(save_dir=save_dir, reference=True)
            controller.new_game()
            controller.choose("enter")
            controller.start_mission(MISSION)
            if controller.state()["screen"] not in ("battle", "result"):
                raise RuntimeError("Expected real reference battle for Player visual golden")
            renderer = make_controller(scene_for_player(controller))
            renderer.camera.zoom = args.zoom
            renderer.center_scene()
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": False})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(ROOT / "drawtemp/player/Main.qml")))
            if not engine.rootObjects():
                raise RuntimeError("Player Main.qml failed to instantiate")
            window = engine.rootObjects()[0]
            window.setWidth(1024)
            window.setHeight(680)
            window.show()
            QTest.qWait(350)
            image = window.grabWindow()
            window.hide()
            window.close()
            engine.deleteLater()

    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise RuntimeError("Qt produced a null/empty frame; never fake a golden")
    args.png.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(args.png), "PNG"):
        raise RuntimeError("Failed to save real Qt frame")
    meta = {
        "target": target, "dpi": args.dpi, "zoom": args.zoom,
        "width": image.width(), "height": image.height(),
        "qt_screen_dpr": screen.devicePixelRatio(),
        "qt_image_dpr": image.devicePixelRatio(),
        "sha256": digest(args.png), "capture_status": "captured",
        "capture_backend": os.environ.get("QT_QUICK_BACKEND"),
        "capture_platform": os.environ.get("QT_QPA_PLATFORM"),
    }
    write_json(args.meta, meta)
    return 0


def capture_suite(args):
    from importlib.metadata import version
    qt = version("PySide6")
    os_name = platform.system().lower()
    profile = profile_id(os_name, qt)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": 1, "profile": profile, "os": os_name, "qt": qt,
        "backend": "software", "revision": os.environ.get("GITHUB_SHA", "local"),
        "capture_complete": False, "release_certified": False,
        "tolerance": {"max_channel_delta": 12, "max_changed_fraction": 0.001},
        "cases": {},
    }
    for target, dpi, zoom in EXPECTED:
        key = case_id(target, dpi, zoom)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software", QT_SCALE_FACTOR=str(dpi),
                   QT_ENABLE_HIGHDPI_SCALING="1")
        png = output / "actual" / (key + ".png")
        metadata = output / "metadata" / (key + ".json")
        command = [
            sys.executable, str(Path(__file__).resolve()), "_frame",
            "--target", target, "--dpi", str(dpi), "--zoom", str(zoom),
            "--png", str(png), "--meta", str(metadata),
        ]
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True,
                text=True, timeout=75, check=False)
            (output / "logs").mkdir(exist_ok=True)
            (output / "logs" / (key + ".log")).write_text(
                completed.stdout + "\n" + completed.stderr,
                encoding="utf-8", errors="replace")
            if completed.returncode != 0:
                raise RuntimeError(f"Qt child exit={completed.returncode}; see logs/{key}.log")
            data = json.loads(metadata.read_text(encoding="utf-8"))
            if (data["target"], data["dpi"], data["zoom"]) != (target, dpi, zoom) or \
                    data.get("capture_backend") != "software" or \
                    data.get("capture_platform") != "offscreen" or \
                    abs(data["qt_screen_dpr"] - dpi) > 0.1 or \
                    data["sha256"] != digest(png):
                raise ValueError("Wrong environment, case or PNG SHA-256")
            report["cases"][key] = data
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            report["cases"][key] = {
                "target": target, "dpi": dpi, "zoom": zoom,
                "capture_status": "fail", "comparison": "fail", "reason": str(exc),
            }
    report["capture_complete"] = all(
        row.get("capture_status") == "captured" for row in report["cases"].values())
    if report["capture_complete"]:
        try:
            evaluate_capture(output, args.goldens, report)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            report["comparison"] = "fail"
            report["error"] = "Baseline integrity or comparison error: " + str(exc)
    else:
        report["comparison"] = "fail"
    write_json(output / "r14-visual.json", report)
    html_report(output, report)
    print(json.dumps({
        "profile": profile, "capture_complete": report["capture_complete"],
        "comparison": report["comparison"], "report": str(output / "index.html"),
        "goldens_reviewed": report.get("goldens_reviewed", False),
    }, ensure_ascii=False))
    if not report["capture_complete"] or report["comparison"] == "fail":
        return 1
    if args.require_approved and report["comparison"] != "pass":
        return 2
    # Missing human-reviewed baselines do not masquerade as a successful
    # comparison; capture-only CI is a green infrastructure job, not R14.5 pass.
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    captures = sub.add_parser("capture", help="Record 12 real candidate frames; compare only if approved")
    captures.add_argument("--output", type=Path, required=True)
    captures.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    captures.add_argument("--require-approved", action="store_true",
                          help="Fail when any golden is unapproved or changes beyond tolerance")
    approval = sub.add_parser("approve", help="Manual, separate baseline promotion for a reviewed PR")
    approval.add_argument("--capture", type=Path, required=True)
    approval.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    approval.add_argument("--reviewer", required=True)
    frame = sub.add_parser("_frame", help=argparse.SUPPRESS)
    frame.add_argument("--target", choices=("studio", "player"), required=True)
    frame.add_argument("--dpi", type=int, choices=(1, 2), required=True)
    frame.add_argument("--zoom", type=float, choices=(0.75, 1.0, 1.5), required=True)
    frame.add_argument("--png", type=Path, required=True)
    frame.add_argument("--meta", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "_frame":
        return render_frame(args)
    if args.command == "capture":
        return capture_suite(args)
    approved = approve_candidates(args.capture, args.goldens, reviewer=args.reviewer)
    print("Reviewed golden manifest: " + str(approved))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
