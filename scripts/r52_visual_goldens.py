"""R52.B3: capture real Qt Quick Studio/Player viewports in 36 fixed cases.

  python scripts/r52_visual_goldens.py capture --output r52-visual-report
  python scripts/r52_visual_goldens.py capture --output r52-visual-report --require-approved
  python scripts/r52_visual_goldens.py approve --capture r52-visual-report --reviewer "QA name"

The first command produces candidates/parity evidence only. No auto-approval.
Offscreen Qt software captures cannot certify physical GPU behavior.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from drawtemp.quality.r52_goldens import (
    DPRS, EXPECTED, MAX_CHANGED_FRACTION, MODES, PHASES,
    approve_candidates, case_id, evaluate_capture, fingerprint,
    fixture_scene, profile_id, reference_projection, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "tests_standalone" / "goldens" / "r52"


def _check_visible_frame(image, expected_dpr, logical_width, logical_height):
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise RuntimeError("Qt produced null/empty framebuffer; no golden")
    if (abs(image.width() - logical_width * expected_dpr) > 2 or
            abs(image.height() - logical_height * expected_dpr) > 2):
        raise RuntimeError("Qt actual physical capture dimensions do not match DPI")
    colors = set()
    opaque = 0
    for sy in range(24):
        for sx in range(36):
            pixel = image.pixelColor(sx * (image.width() - 1) // 35,
                                     sy * (image.height() - 1) // 23)
            colors.add((pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()))
            opaque += pixel.alpha() >= 240
    if len(colors) < 3 or opaque < 500:
        raise RuntimeError("Qt captured blank, monochrome or transparent frame")


def capture_child(args):
    """Each case uses a new process; Qt_SCALE_FACTOR is fixed before import."""
    if (os.environ.get("QT_SCALE_FACTOR") != str(args.dpi) or
            os.environ.get("QT_QPA_PLATFORM") != "offscreen" or
            os.environ.get("QT_QUICK_BACKEND") != "software"):
        raise RuntimeError("Capture requires isolated offscreen software Qt process")

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQuickWidgets import QQuickWidget

    from drawtemp.render.qt_viewport import create_view, make_controller

    app = QApplication.instance() or QApplication(["r52-qt-golden"])
    screen = app.primaryScreen()
    if screen is None or abs(screen.devicePixelRatio() - args.dpi) > .1:
        raise RuntimeError("Qt screen does not honor requested scale factor")

    source = fixture_scene()
    size = (640, 480)
    profile = {
        "projection": args.mode,
        "layers": [{
            "id": "backdrop", "x": 2, "y": 2, "width": 260, "height": 140,
            "parallax": 0.3, "color": "#3d697a", "opacity": 0.45,
        }],
    }
    if args.target == "player":
        view, renderer = create_view(source, projection_mode=args.mode,
                                     depth_profile=profile)
    else:
        renderer = make_controller(source, projection_mode=args.mode,
                                   depth_profile=profile)
        view = QQuickWidget()
        renderer.attach_engine(view.engine())
        view.rootContext().setContextProperty("renderer", renderer)
        view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        name = "IsoViewport.qml" if args.mode == "isometric" else "TopDownViewport.qml"
        view.setSource(QUrl.fromLocalFile(str((ROOT / "drawtemp/render" / name).resolve())))
        if view.status() == QQuickWidget.Error:
            raise RuntimeError("Qt Studio viewport failed to load: %s" % view.errors())
    if view.rootObject() is None:
        raise RuntimeError("Qt root QML item is missing")
    if args.mode == "isometric":
        # The R3 viewport's default legend is a Player UI decoration; parity
        # here covers the shared *scene*, not app-specific chrome.
        view.rootObject().setProperty("showLegend", False)
    view.resize(*size)
    view.show()
    QTest.qWait(200)
    renderer.resizeViewport(*size)
    renderer.camera.zoom = 1.0
    renderer.camera.center(*renderer.projection.project(2.5, 2.5))
    renderer.refresh()
    renderer.setLightingProfile({"phase": 0 if args.phase == "day" else 1})
    QTest.qWait(120)
    if view.rootObject() is None:
        raise RuntimeError("QML root vanished during frame capture")
    expected = reference_projection(args.mode)
    anchors = {row["id"]: (row["sx"], row["sy"])
               for row in renderer.items if row["id"] in expected}
    if anchors != expected:
        raise RuntimeError("Scene projection diverges from R52.B3 approved anchors")
    image = (view.grabWindow() if args.target == "player"
             else view.grabFramebuffer())
    _check_visible_frame(image, args.dpi, *size)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(args.png), "PNG"):
        raise RuntimeError("Unable to save real R52 Qt capture")
    write_json(args.meta, {
        "capture_status": "captured", "target": args.target,
        "mode": args.mode, "dpi": args.dpi, "phase": args.phase,
        "width": image.width(), "height": image.height(),
        "qt_screen_dpr": screen.devicePixelRatio(),
        "qt_image_dpr": image.devicePixelRatio(),
        "sha256": fingerprint(args.png),
        "root": "IsoViewport.qml" if args.mode == "isometric" else "TopDownViewport.qml",
        "backend": "software", "platform": "offscreen",
    })
    view.close()
    view.deleteLater()
    return 0


def capture_matrix(args):
    from importlib.metadata import version
    qt = version("PySide6")
    os_name = platform.system().lower()
    profile = profile_id(os_name, qt)
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": 1, "profile": profile, "os": os_name,
        "qt": qt, "backend": "software",
        "revision": os.environ.get("GITHUB_SHA", "local"),
        "capture_complete": False, "release_certified": False,
        "hardware_gpu_certified": False, "cases": {}, "errors": {},
    }
    for target, mode, dpi, phase in EXPECTED:
        key = case_id(target, mode, dpi, phase)
        png = destination / "actual" / (key + ".png")
        meta = destination / "metadata" / (key + ".json")
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software", QT_SCALE_FACTOR=str(dpi))
        cmd = [sys.executable, str(Path(__file__).resolve()), "_child",
               "--target", target, "--mode", mode, "--dpi", str(dpi),
               "--phase", phase, "--png", str(png), "--meta", str(meta)]
        try:
            result = subprocess.run(cmd, cwd=ROOT, env=env,
                                    text=True, capture_output=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError((result.stderr + result.stdout)[-3000:])
            report["cases"][key] = json.loads(meta.read_text("utf-8"))
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            report["errors"][key] = str(exc)
    report["capture_complete"] = not report["errors"] and len(report["cases"]) == len(EXPECTED)
    if report["capture_complete"]:
        evaluate_capture(destination, GOLDENS, report)
    else:
        report.update(parity_pass=False, goldens_reviewed=False,
                      comparison="blocked", golden_pass=False)
    write_json(destination / "r52-visual.json", report)
    print(json.dumps({
        "capture_complete": report["capture_complete"],
        "cases": len(report["cases"]), "expected": len(EXPECTED),
        "parity_pass": report.get("parity_pass", False),
        "comparison": report["comparison"],
        "goldens_reviewed": report["goldens_reviewed"],
        "hardware_gpu_certified": False,
        "errors": report["errors"],
    }, indent=2))
    if not report["capture_complete"] or not report.get("parity_pass"):
        return 1
    if args.require_approved and report["comparison"] != "pass":
        return 2
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--output", type=Path, default=Path("r52-visual-report"))
    capture.add_argument("--require-approved", action="store_true")
    approve = commands.add_parser("approve")
    approve.add_argument("--capture", type=Path, required=True)
    approve.add_argument("--reviewer", required=True)
    child = commands.add_parser("_child")
    child.add_argument("--target", choices=("studio", "player"), required=True)
    child.add_argument("--mode", choices=MODES, required=True)
    child.add_argument("--dpi", type=float, choices=DPRS, required=True)
    child.add_argument("--phase", choices=PHASES, required=True)
    child.add_argument("--png", type=Path, required=True)
    child.add_argument("--meta", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "capture":
        return capture_matrix(args)
    if args.command == "approve":
        print(approve_candidates(args.capture, GOLDENS, reviewer=args.reviewer))
        return 0
    return capture_child(args)


if __name__ == "__main__":
    raise SystemExit(main())
