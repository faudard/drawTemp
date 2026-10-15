"""R14 evidence contracts and asset validation; pure Python, safe for headless CI.

Reports explicitly distinguish a passed check from an unverified release gate.
GPU evidence cannot be inferred from Qt's offscreen/software backend.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys

P0_CHECKS = tuple(f"R14.{i}" for i in range(1, 11)) + ("R14.12",)
ALL_CHECKS = tuple(f"R14.{i}" for i in range(1, 13))
SCENE_SIZES = (32, 64, 128)
ZOOMS = (24, 54, 96)
MIN_GPU_SAMPLES = 120
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def percentile(values, percentage):
    """Linear interpolation over an ordered empirical series (not an FPS estimate)."""
    if not values or not 0 <= percentage <= 100:
        raise ValueError("Need observations and a percentile from 0 to 100")
    numbers = sorted(float(value) for value in values)
    if any(not (0 <= value < float("inf")) for value in numbers):
        raise ValueError("All observations must be finite and nonnegative")
    index = (len(numbers) - 1) * percentage / 100
    lower = int(index)
    fraction = index - lower
    return numbers[lower] * (1 - fraction) + numbers[min(lower + 1, len(numbers) - 1)] * fraction


def frame_metrics(samples_ms):
    return {"samples": len(samples_ms),
            "p50_ms": round(percentile(samples_ms, 50), 4),
            "p95_ms": round(percentile(samples_ms, 95), 4),
            "p99_ms": round(percentile(samples_ms, 99), 4)}


def validate_gpu_profile(profile):
    """Validate *externally measured* real-GPU evidence, without manufacturing it.

    The recorder must supply actual per-frame wall times and identify the adapter,
    driver, Qt backend and resolution. Offscreen/software profiles are refused.
    """
    if not isinstance(profile, dict) or profile.get("schema") != 1:
        raise ValueError("Expected GPU profile schema 1")
    device = profile.get("device")
    if not isinstance(device, dict):
        raise ValueError("Missing GPU device metadata")
    for key in ("os", "gpu", "driver", "qt", "backend"):
        if not isinstance(device.get(key), str) or not device[key].strip():
            raise ValueError("Missing GPU device field: " + key)
    if device.get("software") is not False or device["backend"].lower() in ("software", "offscreen", "null"):
        raise ValueError("Real hardware GPU evidence required, not software/offscreen")
    resolution = device.get("resolution")
    if not isinstance(resolution, list) or len(resolution) != 2 or any(
            type(value) is not int or value < 1 for value in resolution):
        raise ValueError("Provide positive pixel resolution [width, height]")
    scenes = profile.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("Missing GPU scenes")
    covered = set()
    result = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("Invalid scene entry")
        size, zoom = scene.get("map_size"), scene.get("zoom_px")
        if type(size) is not int or type(zoom) is not int:
            raise ValueError("Scene must specify integer map_size and zoom_px")
        if (size, zoom) in covered:
            raise ValueError("Repeated scene dimensions")
        covered.add((size, zoom))
        samples = scene.get("frame_times_ms")
        if not isinstance(samples, list) or len(samples) < MIN_GPU_SAMPLES:
            raise ValueError("At least 120 measured frames required per scene")
        if any(type(value) not in (int, float) for value in samples):
            raise ValueError("Frame times must be numeric")
        metrics = frame_metrics(samples)
        actors = scene.get("actors")
        if type(actors) is not int or actors < 0:
            raise ValueError("Missing actor count")
        result.append({"map_size": size, "zoom_px": zoom,
                       "actors": actors, **metrics})
    missing = sorted({(size, zoom) for size in SCENE_SIZES for zoom in ZOOMS} - covered)
    if missing:
        raise ValueError("Missing size/zoom scenes: " + str(missing))
    if not any(scene["actors"] >= 80 for scene in result):
        raise ValueError("Missing 80-actor stress scene")
    return {"device": device, "scenes": result, "matrix_covered": True,
            "budget_policy": "informational; thresholds require a hardware baseline"}


def safe_asset_path(root, relative):
    """Reject traversal, absolute/drive paths and symlinks escaping the asset root."""
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValueError("Invalid asset path")
    if "\\" in relative or relative.startswith("/") or relative.startswith("//"):
        raise ValueError("Asset paths must be relative POSIX paths")
    if re.match(r"^[A-Za-z]:", relative):
        raise ValueError("Drive paths are forbidden")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Asset path traversal or empty component")
    path = PurePosixPath(relative)
    if path.is_absolute():
        raise ValueError("Absolute path forbidden")
    base = Path(root).resolve(strict=True)
    candidate = base.joinpath(*path.parts).resolve(strict=True)
    if candidate != base and base not in candidate.parents:
        raise ValueError("Asset escapes the project root")
    if not candidate.is_file():
        raise ValueError("Asset must be a regular file")
    return candidate


def validate_asset_manifest(root, entries):
    """Validate an external manifest's on-disk asset hashes before import/export."""
    if not isinstance(entries, list):
        raise ValueError("Manifest must contain an asset list")
    seen = set()
    errors = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"asset[{index}]: invalid entry")
            continue
        relative, digest = entry.get("path"), entry.get("sha256")
        if not isinstance(relative, str) or relative in seen:
            errors.append(f"asset[{index}]: duplicate/invalid asset path")
            continue
        seen.add(relative)
        try:
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise ValueError("Invalid SHA-256")
            target = safe_asset_path(root, relative)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("SHA-256 mismatch")
        except (ValueError, OSError) as exc:
            errors.append(f"asset[{index}]: {exc}")
    return errors


def evidence_report(checks, *, revision="unknown"):
    """Build a fail-closed gate: missing proof remains blocked, never success."""
    result = {}
    for key in ALL_CHECKS:
        item = checks.get(key, {"status": "blocked", "detail": "Not yet certified"})
        if not isinstance(item, dict) or item.get("status") not in ("pass", "partial", "fail", "blocked"):
            raise ValueError("Invalid evidence status for " + key)
        if not isinstance(item.get("detail"), str) or not item["detail"]:
            raise ValueError("Evidence detail required for " + key)
        result[key] = item.copy()
    return {"schema": 1, "kind": "drawtemp5-r14-certification",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "revision": revision, "environment": {
                "os": platform.platform(), "python": sys.version.split()[0],
                "qt": "not checked here", "runner": os.environ.get("RUNNER_OS", "local")},
            "checks": result, "p0_certified": all(result[key]["status"] == "pass"
                                                 for key in P0_CHECKS)}


def verify_report(report, *, require_complete=False):
    if not isinstance(report, dict) or report.get("schema") != 1 or (
            report.get("kind") != "drawtemp5-r14-certification"):
        raise ValueError("Invalid certification report")
    checks = report.get("checks", {})
    if not isinstance(checks, dict) or set(checks) != set(ALL_CHECKS):
        raise ValueError("Certification check matrix incomplete")
    expected = all(checks[key].get("status") == "pass" for key in P0_CHECKS)
    if type(report.get("p0_certified")) is not bool or report["p0_certified"] != expected:
        raise ValueError("Forged/mismatched gate status")
    if require_complete and not expected:
        raise ValueError("R14 P0 certification is incomplete")
    return expected


def write_report(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")
