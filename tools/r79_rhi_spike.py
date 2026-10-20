"""R79.B experimental Qt Quick RHI spike, strictly isolated from the PC Player.

Run on a real desktop session: python tools/r79_rhi_spike.py --backend opengl
    --revision <40-hex-Git-SHA> --output-dir ./r79b-probe
Requires Python 3.12 and PySide6 6.8.3 (the repo's optional qt6 dependency).
A successful probe is NOT a hardware certification or release GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCHEMA = 1
BACKENDS = {
    "linux": ("auto", "opengl", "vulkan", "software"),
    "windows": ("auto", "opengl", "vulkan", "d3d11", "d3d12", "software"),
    "macos": ("auto", "opengl", "metal", "software"),
}
PROJECTIONS = ("isometric", "top_down")
HEADLESS = {"offscreen", "minimal", "vnc"}


def host_os():
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    raise ValueError("unsupported operating system")


def validate(backend, projection, revision, os_name):
    if os_name not in BACKENDS or backend not in BACKENDS[os_name]:
        raise ValueError("requested graphics API is not a research candidate on this OS")
    if projection not in PROJECTIONS:
        raise ValueError("unknown projection")
    if not isinstance(revision, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", revision):
        raise ValueError("full 40-hex source Git revision required")


def normalize_observation(data, backend, projection):
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != SCHEMA:
        raise ValueError("invalid child schema")
    if data.get("requested_backend") != backend or data.get("projection") != projection:
        raise ValueError("child backend/projection mismatch")
    if data.get("observed_backend") not in (
            "opengl", "vulkan", "d3d11", "d3d12", "metal", "software", "null", "unknown"):
        raise ValueError("unrecognized graphics API")
    for field in ("qml_ready", "scenegraph_initialized", "first_frame_observed",
                  "picking_centres_passed", "capture_saved"):
        if type(data.get(field)) is not bool:
            raise ValueError("invalid child flag: " + field)
    if type(data.get("picking_samples")) is not int or not 0 <= data["picking_samples"] <= 3:
        raise ValueError("invalid picking sample count")
    for field in ("qt_version", "qpa_platform", "error"):
        if not isinstance(data.get(field), str) or len(data[field]) > 2048:
            raise ValueError("invalid child text: " + field)
    sha = data.get("capture_sha256")
    if (sha is not None and (not isinstance(sha, str) or
                            not re.fullmatch(r"[0-9a-f]{64}", sha))):
        raise ValueError("invalid capture digest")
    if data["capture_saved"] != (sha is not None):
        raise ValueError("capture flag/hash inconsistent")
    return {field: data[field] for field in (
        "requested_backend", "observed_backend", "projection", "qt_version",
        "qpa_platform", "qml_ready", "scenegraph_initialized",
        "first_frame_observed", "picking_centres_passed", "picking_samples",
        "capture_saved", "capture_sha256", "error")}


def run_spike(*, backend, projection, revision, output_dir, timeout_ms=5000,
              allow_headless=False, os_name=None, runner=None):
    os_name = host_os() if os_name is None else os_name
    validate(backend, projection, revision, os_name)
    if type(timeout_ms) is not int or not 1000 <= timeout_ms <= 20000:
        raise ValueError("timeout-ms must be 1000..20000")
    if output_dir.is_symlink() or output_dir.exists():
        raise ValueError("output-dir must be a new directory; no overwrite")
    report = {
        "schema": SCHEMA, "kind": "drawtemp-r79b-experimental-rhi-spike",
        "candidate": "qtquick-rhi-adaptive", "revision": revision.lower(),
        "platform": os_name, "requested_backend": backend, "projection": projection,
        "status": "inconclusive", "decision": "NO-GO", "release_certified": False,
        "eligible_for_r79c": False, "physical_gpu_verified": False,
        "changes_player_defaults": False, "observations": None, "findings": [],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    qpa = os.environ.get("QT_QPA_PLATFORM", "").lower()
    if qpa in HEADLESS and not allow_headless:
        report["findings"].append("headless QPA refused without --allow-headless")
    else:
        args = [sys.executable, str(Path(__file__).resolve()), "--child",
                "--backend", backend, "--projection", projection,
                "--timeout-ms", str(timeout_ms),
                "--capture-path", str(output_dir / "viewport.png")]
        env = os.environ.copy()
        env.pop("QSG_RHI_BACKEND", None)
        env.pop("QT_QUICK_BACKEND", None)
        try:
            call = subprocess.run if runner is None else runner
            proc = call(args, capture_output=True, text=True,
                        timeout=timeout_ms / 1000 + 6, env=env, check=False)
            if proc.stderr:
                report["child_stderr_excerpt"] = proc.stderr[-2048:]
            if proc.returncode != 0:
                report["findings"].append("Qt child exited with code " + str(proc.returncode))
            elif len(proc.stdout) > 65536:
                report["findings"].append("child output exceeds size limit")
            else:
                try:
                    observation = normalize_observation(
                        json.loads(proc.stdout), backend, projection)
                    if observation["capture_saved"]:
                        image = output_dir / "viewport.png"
                        if (image.is_symlink() or not image.is_file()
                                or image.stat().st_size > 12 * 1024 * 1024
                                or hashlib.sha256(image.read_bytes()).hexdigest()
                                   != observation["capture_sha256"]):
                            raise ValueError("missing/altered/oversized screenshot")
                    report["observations"] = observation
                    if observation["error"]:
                        report["findings"].append(observation["error"])
                    if not observation["qml_ready"]:
                        report["findings"].append("QML shared view not ready")
                    if not observation["scenegraph_initialized"]:
                        report["findings"].append("scenegraph never initialized")
                    if not observation["first_frame_observed"]:
                        report["findings"].append("no frame swapped")
                    if (not observation["picking_centres_passed"]
                            or observation["picking_samples"] != 3):
                        report["findings"].append("shared R3 picking failure")
                    if not observation["capture_saved"]:
                        report["findings"].append("no screenshot")
                    actual = observation["observed_backend"]
                    if actual in ("unknown", "null"):
                        report["findings"].append("backend unverified")
                    elif backend != "auto" and actual != backend:
                        report["findings"].append("silent backend fallback: " + actual)
                    if not report["findings"]:
                        report["status"] = "observed"  # never release-certified
                except (ValueError, OSError, TypeError) as exc:
                    report["findings"].append("invalid child evidence: " + str(exc))
        except subprocess.TimeoutExpired:
            report["findings"].append("Qt child timed out")
        except OSError as exc:
            report["findings"].append("Qt child launch failed: " + type(exc).__name__)
    (output_dir / "spike-result.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return report


def qt_child(backend, projection, timeout_ms, capture_path):
    """Qt imports/renderer selection confined to one subprocess only."""
    obs = {
        "schema": SCHEMA, "requested_backend": backend, "observed_backend": "unknown",
        "projection": projection, "qt_version": "", "qpa_platform": "",
        "qml_ready": False, "scenegraph_initialized": False,
        "first_frame_observed": False, "picking_centres_passed": False,
        "picking_samples": 0, "capture_saved": False, "capture_sha256": None,
        "error": "",
    }
    try:
        from PySide6.QtCore import QTimer, qVersion
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
        from drawtemp.sdk.reference import MISSION, reference_project
        from drawtemp.render.iso_scene import scene_from_mission
        from drawtemp.render.qt_viewport import create_view
        apis = QSGRendererInterface.GraphicsApi
        requested = {
            "auto": apis.Unknown, "opengl": apis.OpenGL, "vulkan": apis.Vulkan,
            "metal": apis.Metal, "d3d11": apis.Direct3D11,
            "d3d12": apis.Direct3D12, "software": apis.Software,
        }
        QQuickWindow.setGraphicsApi(requested[backend])  # FIRST Qt Quick window not constructed yet
        app = QGuiApplication([sys.argv[0]])
        obs["qt_version"] = qVersion()
        obs["qpa_platform"] = app.platformName()
        content, _ = reference_project()
        scene = scene_from_mission(content.missions[MISSION])
        view, controller = create_view(scene, projection_mode=projection)
        view.resize(960, 640)
        view.setTitle("DrawTemp R79.B — isolated probe, not Player")

        def frame_ready():
            obs["first_frame_observed"] = True
            QTimer.singleShot(50, app.quit)

        view.frameSwapped.connect(frame_ready)
        QTimer.singleShot(timeout_ms, app.quit)
        view.show()
        app.exec()
        obs["qml_ready"] = bool(view.rootObject()) and view.status() == view.Ready
        obs["scenegraph_initialized"] = bool(view.isSceneGraphInitialized())
        actual = view.rendererInterface().graphicsApi()
        obs["observed_backend"] = {
            apis.OpenGL: "opengl", apis.Vulkan: "vulkan",
            apis.Metal: "metal", apis.Direct3D11: "d3d11",
            apis.Direct3D12: "d3d12", apis.Software: "software",
            apis.Null: "null",
        }.get(actual, "unknown")
        if obs["qml_ready"] and len(scene["tiles"]) > 0:
            cells = (scene["tiles"][0], scene["tiles"][len(scene["tiles"]) // 2],
                     scene["tiles"][-1])
            count = 0
            for tile in cells:
                sx, sy = controller.camera.screen(*controller.projection.project(
                    tile["x"], tile["y"], tile.get("height", 0)))
                count += controller.cellAt(float(sx), float(sy)) == {
                    "x": tile["x"], "y": tile["y"]}
            obs["picking_samples"] = int(count)
            obs["picking_centres_passed"] = count == 3
        if obs["first_frame_observed"] and obs["scenegraph_initialized"]:
            capture = view.grabWindow()
            if not capture.isNull() and capture.save(str(capture_path), "PNG"):
                obs["capture_saved"] = True
                obs["capture_sha256"] = hashlib.sha256(
                    capture_path.read_bytes()).hexdigest()
        if not obs["qml_ready"]:
            obs["error"] = "; ".join(str(err) for err in view.errors())[:2048]
    except Exception as exc:
        obs["error"] = (type(exc).__name__ + ": " + str(exc))[:2048]
    print(json.dumps(obs, sort_keys=True, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True,
                        choices=("auto", "opengl", "vulkan", "d3d11",
                                 "d3d12", "metal", "software"))
    parser.add_argument("--projection", default="isometric", choices=PROJECTIONS)
    parser.add_argument("--revision")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--allow-headless", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--capture-path", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        validate(args.backend, args.projection, args.revision or "0" * 40, host_os())
        if args.child:
            if args.capture_path is None:
                parser.error("--capture-path required by internal child")
            return qt_child(args.backend, args.projection,
                            args.timeout_ms, args.capture_path)
        if not args.revision or args.output_dir is None:
            parser.error("--revision and --output-dir are required")
        report = run_spike(backend=args.backend, projection=args.projection,
                           revision=args.revision, output_dir=args.output_dir,
                           timeout_ms=args.timeout_ms, allow_headless=args.allow_headless)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"status": report["status"], "decision": report["decision"],
                      "report": str(args.output_dir / "spike-result.json")}))
    return 0 if report["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
