#!/usr/bin/env python3
"""Collect comparable 3.7.5 render measurements in isolated processes.

Each sample invokes the single-backend benchmark in a fresh Python process:
libraries and native GUI heaps must never leak across comparison runs.
No backend is silently skipped when an explicit run was requested.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path(__file__).resolve().with_name("benchmark_renderers_375.py")
VALID_BACKENDS = ("tk", "pygame", "qt")


def plan(backends=("tk", "pygame", "qt"), actors=(20, 80, 200),
         scales=(1, 2), repeats=3):
    if not backends or not actors or not scales or not 1 <= repeats <= 10:
        raise ValueError("Expected backends, actors, scales and 1..10 repeats")
    if any(b not in VALID_BACKENDS for b in backends):
        raise ValueError("Unknown renderer backend")
    if any(a not in (20, 80, 200) for a in actors):
        raise ValueError("Use 20, 80, 200 actors")
    if any(s not in (1, 2) for s in scales):
        raise ValueError("Use 1x or 2x")
    return [{"backend": backend, "actors": count, "scale": scale, "repeat": n + 1}
            for backend in backends for count in actors for scale in scales
            for n in range(repeats)]


def summarize(samples):
    """Median of each repeated p50/p95. Keep original runs for audit."""
    keys = sorted({(r["backend"], r["actors"], r["scale"]) for r in samples})
    result = []
    for backend, actors, scale in keys:
        rows = [r for r in samples if (r["backend"], r["actors"], r["scale"])
                == (backend, actors, scale)]
        result.append({
            "backend": backend, "actors": actors, "scale": scale,
            "runs": len(rows),
            "median_p50_ms": round(statistics.median(r["p50_ms"] for r in rows), 3),
            "median_p95_ms": round(statistics.median(r["p95_ms"] for r in rows), 3),
            "max_p95_ms": round(max(r["p95_ms"] for r in rows), 3),
            "within_33ms_heuristic": max(r["p95_ms"] for r in rows) < 33.3,
        })
    return result


def collect(sequence, *, frames, timeout):
    samples = []
    for spec in sequence:
        cmd = [sys.executable, str(BENCH), "--backend", spec["backend"],
               "--actors", str(spec["actors"]), "--scale", str(spec["scale"]),
               "--frames", str(frames)]
        run = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        if run.returncode:
            raise RuntimeError(
                f'{spec["backend"]} {spec["actors"]} actors, {spec["scale"]}x, '
                f'repeat {spec["repeat"]}: renderer failed with exit '
                f'{run.returncode}: {run.stderr[-1200:]}')
        try:
            # GUI libraries can print startup banners. The benchmark itself
            # always emits exactly one machine-readable JSON record last.
            lines = [line for line in run.stdout.splitlines() if line.strip()]
            record = json.loads(lines[-1])
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Renderer emitted invalid JSON: " + str(spec)) from exc
        for key in ("backend", "actors", "scale"):
            if record.get(key) != spec[key]:
                raise RuntimeError("Renderer returned mismatched case: " + str(spec))
        if (record.get("dry_run") or record.get("frames") != frames
                or any(type(record.get(k)) not in (int, float)
                       or record[k] < 0 for k in ("p50_ms", "p95_ms"))):
            raise RuntimeError("Renderer returned missing or invalid timing: " + str(spec))
        samples.append({**record, "repeat": spec["repeat"]})
    return samples


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backends", nargs="+", choices=VALID_BACKENDS,
                        default=list(VALID_BACKENDS))
    parser.add_argument("--actors", nargs="+", type=int, choices=(20, 80, 200),
                        default=[20, 80, 200])
    parser.add_argument("--scales", nargs="+", type=int, choices=(1, 2),
                        default=[1, 2])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.frames < 20 or args.timeout < 1:
        parser.error("At least 20 frames and a positive process timeout are required")
    try:
        sequence = plan(args.backends, args.actors, args.scales, args.repeats)
    except ValueError as exc:
        parser.error(str(exc))

    report = {
        "format": "drawtemp-renderer-375-comparison-v1",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "frames_per_case": args.frames,
        "cases": sequence,
        "metric_scope": "single-process full-frame wall time incl event pump",
        "memory_scope": "Python tracemalloc only; excludes native allocations",
    }
    if args.dry_run:
        report["dry_run"] = True
        report["samples"] = []
        report["summary"] = []
    else:
        # Missing display/runtime must produce a nonzero exit, not fake zeros.
        try:
            samples = collect(sequence, frames=args.frames, timeout=args.timeout)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            parser.exit(2, f"Renderer benchmark failed: {exc}\n")
        report["samples"] = samples
        report["summary"] = summarize(samples)
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if not args.output.parent.is_dir():
            parser.error("Output directory does not exist")
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
