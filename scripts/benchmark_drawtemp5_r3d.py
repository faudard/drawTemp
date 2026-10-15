"""R3.D scenegraph profiling: backend, batch reduction and presented frames.

CPU prepare time is not GPU time. frameSwapped intervals are frame cadence,
NOT GPU timestamps. Hardware runs need a real window/device, not offscreen CI.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
from statistics import median
from time import perf_counter


def scene_of_size(size):
    return {
        "mission": "r3d-benchmark", "width": size, "height": size,
        "revision": 0,
        "tiles": [{"x": x, "y": y,
                   "height": 0, "surface": ("grass", "dirt", "cobble")[(x//8 + y//8) % 3],
                   "feature": "", "blocked": False, "cover": 0, "hazard": 0,
                   "goal": False}
                  for y in range(size) for x in range(size)],
        "actors": [], "objects": [],
    }


def pctl(samples, n):
    if not samples:
        return None
    sorted_values = sorted(samples)
    return round(sorted_values[min(len(samples)-1,
                                   max(0, math.ceil(n / 100 * len(samples)) - 1))], 3)


def benchmark(size, frames, *, smoke=False):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from drawtemp.render.qt_viewport import create_view
    from drawtemp.render.iso_scene import IsoProjection

    app = QGuiApplication.instance() or QGuiApplication(["drawtemp-r3d"])
    view, controller = create_view(scene_of_size(size))
    view.resize(960, 640)
    view.show()
    profile = str(view.rendererInterface().graphicsApi())
    timings, swaps = [], []
    frame_number = 0
    prev_swap = None
    def on_swap():
        nonlocal prev_swap, frame_number
        t = perf_counter()
        if prev_swap is not None:
            swaps.append((t-prev_swap)*1000)
        prev_swap = t
        if smoke or len(swaps) >= frames:
            app.quit()
        elif frame_number < frames + 8:
            frame_number += 1
            controller.panBy(11 if frame_number % 2 else -13, 6)
            view.update()

    view.frameSwapped.connect(on_swap)
    def probe():
        for i in range(frames if not smoke else 3):
            t0 = perf_counter()
            controller.panBy(2 if i % 2 else -2, 1)
            timings.append((perf_counter()-t0)*1000)
        view.update()
    QTimer.singleShot(0, probe)
    # Software/offscreen render loops may never swap. Always return a clear
    # incomplete result rather than silently report zero-millisecond frames.
    QTimer.singleShot(6000 if not smoke else 1500, app.quit)
    app.exec()
    stats = controller.textureStats
    report = {
        "map": "%dx%d" % (size, size), "backend": profile,
        "qt_platform": QGuiApplication.platformName(),
        "os": platform.platform(), "python": platform.python_version(),
        "batch_enabled": controller.textureBatching,
        "batched_tiles": stats["tiles"], "chunk_images": stats["images"],
        "cpu_cache_bytes": stats["bytes"], "cpu_cache_budget": stats["budget"],
        "cpu_prepare_ms_p50": pctl(timings, 50),
        "cpu_prepare_ms_p95": pctl(timings, 95),
        "cpu_prepare_ms_p99": pctl(timings, 99),
        "present_intervals": len(swaps),
        "present_interval_ms_p50": pctl(swaps, 50),
        "present_interval_ms_p95": pctl(swaps, 95),
        "present_interval_ms_p99": pctl(swaps, 99),
        "measurement_notes": "present interval includes Qt scheduling/vsync; no GPU timestamps",
    }
    report["hardware_gpu_certified"] = False
    report["status"] = ("software_or_smoke_only" if smoke or
                        "Software" in profile or
                        os.environ.get("QT_QPA_PLATFORM") == "offscreen"
                        else "hardware_cadence_only" if len(swaps) >= frames
                        else "insufficient_presented_frames")
    view.close()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-size", type=int, choices=(32, 64, 128), default=64)
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--smoke", action="store_true",
                        help="CI software backend: report only, no hardware claim")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 3 <= args.frames <= 1000:
        parser.error("--frames must be 3..1000")
    result = benchmark(args.map_size, args.frames, smoke=args.smoke)
    body = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0 if result["batched_tiles"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
