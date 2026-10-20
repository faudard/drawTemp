#!/usr/bin/env python3
"""R36.C2 actual Studio timeline / Action Player screenshot candidate matrix.

Requires Qt 6.8.3; reuses the R14.5 reviewed-baseline format and pixel diff
implementation but keeps R36 approvals in a separate directory. Captures are
never automatically approved or treated as GPU certification.
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
DEFAULT_GOLDENS = ROOT / "tests_standalone/goldens/r36"
KIND = "r36-animation-visual-candidates"


def make_reference_session(root):
    """Build small independently authored R28/R36 art inside the capture sandbox."""
    from PySide6.QtGui import QImage, QColor
    from drawtemp.sdk.authoring import AuthoringSession
    from drawtemp.sdk.reference import reference_project
    from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
    from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring
    from drawtemp.studio.r28d_workflow import AnimationHitboxStudio

    root = Path(root)
    art = root / "art"
    art.mkdir(parents=True, exist_ok=True)
    specs = [
        ("idle", "#4b91d2"),
        ("attack", "#e8b755"),
        ("hit", "#c76569"),
    ]
    session = AuthoringSession.new(*reference_project())
    editor = AnimationHitboxStudio(session)
    for asset, color in specs:
        image = QImage(32, 40, QImage.Format_ARGB32)
        image.fill(QColor(color))
        if not image.save(str(art / (asset + ".png")), "PNG"):
            raise RuntimeError("Could not create reference R28 PNG")
        editor.apply(editor.preview_sprite("r36_s_" + asset, "art/" + asset + ".png"))
    editor.apply(editor.preview_animation(
        "r36_idle", [{"sprite": "r36_s_idle", "duration_ms": 120}], loop=True))
    editor.apply(editor.preview_animation(
        "r36_attack", [{"sprite": "r36_s_attack", "duration_ms": 90},
                       {"sprite": "r36_s_hit", "duration_ms": 90}], loop=False))
    graph = {
        "schema_version": 1, "id": "r36_demo", "initial": "idle",
        "states": [{"id": "idle", "animation": "r36_idle"},
                   {"id": "attack", "animation": "r36_attack"}],
        "transitions": [
            {"source": "idle", "target": "attack", "on": "attack", "priority": 20},
            {"source": "attack", "target": "idle", "on": "finished", "priority": 10},
        ],
    }
    controller = AnimationControllerAuthoring(session)
    controller.apply(controller.preview(graph))
    markers = AnimationTimelineAuthoring(session)
    markers.apply(markers.preview({
        "schema_version": 1, "id": "r36_demo_timeline", "controller_id": "r36_demo",
        "tracks": [{"state": "attack", "markers": [
            {"id": "impact_glow", "at_ms": 40, "cue": "glow"},
            {"id": "strike", "at_ms": 90, "cue": "spark"},
        ]}],
    }))
    content_path = root / "reference.json"
    session.save_as(content_path)
    return session, content_path.with_suffix(".game.json")


def render_frame(args):
    """Called only as a child so Qt DPI/backend cannot leak between captures."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest

    if os.environ.get("QT_SCALE_FACTOR") != str(args.dpi):
        raise RuntimeError("R36 capture DPI must be fixed before importing Qt")
    if (os.environ.get("QT_QPA_PLATFORM") != "offscreen" or
            os.environ.get("QT_QUICK_BACKEND") != "software"):
        raise RuntimeError("R36 reference capture requires software/offscreen profile")
    app = QApplication.instance() or QApplication(["r36-capture"])
    screen = app.primaryScreen()
    if screen is None or abs(screen.devicePixelRatio() - args.dpi) > .1:
        raise RuntimeError("Qt screen did not adopt expected DPI")
    with TemporaryDirectory() as folder:
        session, project_file = make_reference_session(folder)
        if args.target == "studio":
            from drawtemp.studio.animation_timeline_qt import AnimationTimelinePanel
            widget = AnimationTimelinePanel(session)
            widget.states.setCurrentIndex(widget.states.findData("attack"))
            widget.at_ms.setValue(40)
            widget.marker_id.setText("impact_glow")
            widget.sample()
            widget.resize(round(1024 * args.zoom), round(680 * args.zoom))
            widget.setWindowTitle("R36 Studio Animation Timeline")
            widget.show()
            QTest.qWait(350)
            image = widget.grab().toImage()
            widget.hide()
            widget.close()
        else:
            from PySide6.QtQml import QQmlApplicationEngine
            from PySide6.QtQuick import QQuickItem, QQuickWindow
            from drawtemp.player.action_app import create_bridge
            from drawtemp.player.action_controller import ActionPlayerController, demo_scene
            from drawtemp.assets.r36_runtime import R36PresentationAssets
            from drawtemp.render.qt_viewport import make_controller
            from drawtemp.render.iso_scene import scene_from_action
            project = session.snapshot().to_dict()["project"]
            controller = ActionPlayerController(
                demo_scene(), animation_project=project,
                animation_bindings={"hero": "r36_demo"})
            for tick in range(1, 5):
                controller.step(attack=tick == 1)
            renderer = make_controller(
                scene_from_action(controller.runtime),
                atlas_url="", projection_mode="top_down",
                assets=R36PresentationAssets.for_project(
                    _project_object(project), project_file))
            renderer.camera.zoom = args.zoom
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            renderer.attach_engine(engine)
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("action", bridge)
            engine.setInitialProperties({"smokeMode": False})
            engine.load(QUrl.fromLocalFile(str(ROOT / "drawtemp/player/ActionPreview.qml")))
            if not engine.rootObjects():
                raise RuntimeError("R36 Player Qt Quick root was not instantiated")
            window = engine.rootObjects()[0]
            window.setWidth(1024)
            window.setHeight(680)
            window.show()
            QTest.qWait(350)
            item = window.property("contentItem")
            if not isinstance(item, QQuickItem):
                raise RuntimeError("Action Player Qt Quick contentItem missing")
            quick_window = item.window()
            if not isinstance(quick_window, QQuickWindow):
                raise RuntimeError("Action Player did not expose QQuickWindow")
            image = quick_window.grabWindow()
            window.hide()
            window.close()
            engine.deleteLater()
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise RuntimeError("No real Qt screenshot captured")
    seen = set()
    for yy in range(16):
        for xx in range(20):
            pixel = image.pixelColor(
                xx * (image.width() - 1) // 19,
                yy * (image.height() - 1) // 15)
            seen.add((pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()))
    if len(seen) < 7:
        raise RuntimeError("R36 capture appears blank; cannot bless a fake golden")
    args.png.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(args.png), "PNG"):
        raise RuntimeError("Failed writing real Qt R36 PNG")
    write_json(args.meta, {
        "target": args.target, "dpi": args.dpi, "zoom": args.zoom,
        "width": image.width(), "height": image.height(),
        "capture_status": "captured", "sha256": digest(args.png),
        "qt_screen_dpr": screen.devicePixelRatio(),
        "backend": os.environ["QT_QUICK_BACKEND"],
    })
    return 0


def _project_object(data):
    from sporebound.game_project import GameProject
    # AuthoringSession already validated both canonical documents.
    return GameProject(**data)


def capture_suite(args):
    from importlib.metadata import version
    qt = version("PySide6")
    os_name = platform.system().lower()
    profile = profile_id(os_name, qt)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": 1, "kind": KIND, "profile": profile, "os": os_name,
        "qt": qt, "backend": "software", "revision": os.environ.get("GITHUB_SHA", "local"),
        "capture_complete": False, "release_certified": False, "cases": {},
    }
    for target, dpi, zoom in EXPECTED:
        key = case_id(target, dpi, zoom)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software", QT_SCALE_FACTOR=str(dpi))
        png = output / "actual" / (key + ".png")
        meta = output / "metadata" / (key + ".json")
        command = [
            sys.executable, str(Path(__file__).resolve()), "_frame",
            "--target", target, "--dpi", str(dpi), "--zoom", str(zoom),
            "--png", str(png), "--meta", str(meta),
        ]
        run = subprocess.run(command, cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=90)
        if run.returncode:
            report["cases"][key] = {
                "target": target, "dpi": dpi, "zoom": zoom,
                "capture_status": "failed",
                "error": (run.stderr + run.stdout)[-1500:],
            }
        else:
            report["cases"][key] = json.loads(meta.read_text(encoding="utf-8"))
    report["capture_complete"] = (
        len(report["cases"]) == len(EXPECTED) and
        all(row.get("capture_status") == "captured"
            for row in report["cases"].values()))
    # R14.5 approval/comparison machinery accepts only exact 12-case reports.
    write_json(output / "r14-visual.json", report)
    evaluate_capture(output, args.goldens, report)
    write_json(output / "r14-visual.json", report)
    write_json(output / "r36-visual.json", report)
    html_report(output, report)
    if not report["capture_complete"]:
        return 1
    if args.require_approved and report["comparison"] != "pass":
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("matrix", help="Print expected R36 Studio/Player capture matrix")
    capture = commands.add_parser("capture", help="Capture real Qt candidates, never approve")
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    capture.add_argument("--require-approved", action="store_true")
    approve = commands.add_parser("approve", help="Explicit human-only candidate approval")
    approve.add_argument("--capture", type=Path, required=True)
    approve.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    approve.add_argument("--reviewer", type=str, required=True)
    frame = commands.add_parser("_frame")
    frame.add_argument("--target", choices=("studio", "player"), required=True)
    frame.add_argument("--dpi", type=int, choices=(1, 2), required=True)
    frame.add_argument("--zoom", type=float, choices=(.75, 1., 1.5), required=True)
    frame.add_argument("--png", type=Path, required=True)
    frame.add_argument("--meta", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "matrix":
        print(json.dumps({"schema": 1, "kind": KIND,
                          "cases": [case_id(*row) for row in EXPECTED]},
                         sort_keys=True))
        return 0
    if args.command == "_frame":
        return render_frame(args)
    if args.command == "capture":
        return capture_suite(args)
    source = args.capture / "r36-visual.json"
    details = json.loads(source.read_text(encoding="utf-8"))
    if details.get("kind") != KIND or details.get("capture_complete") is not True:
        raise ValueError("Only complete R36 captures can be approved")
    report = json.loads((args.capture / "r14-visual.json").read_text(encoding="utf-8"))
    if details != report:
        raise ValueError("R36 and shared R14 candidate manifest differ")
    print(approve_candidates(args.capture, args.goldens, reviewer=args.reviewer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
