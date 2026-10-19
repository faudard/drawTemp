"""R30.F — reproducible HEADLESS CPU authoring and asset-budget profiles.

No fabricated FPS, Qt frame time, GPU device, or release certification.
Benchmarks operate on the canonical R1 AuthoringSession and R2 projections;
measured wall time and Python traced-memory peak are kept separately.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter_ns
import tracemalloc

from drawtemp.quality.r14 import percentile, safe_asset_path
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.workspace_model import resources
from drawtemp.studio.r30_scene_gallery import load_catalog
from drawtemp.export.r15 import project_path

SCHEMA = "drawtemp-r30f-scale-v1"
OPS = ("authoring_open", "snapshot", "resource_projection", "gallery_load", "asset_inventory",
       "synthetic_resource_projection", "synthetic_asset_registry")
MAX_ASSETS = 10000
MAX_SAMPLES = 250
_MAX_REPORT = 1024 * 1024


class ScaleError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _file_digest(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ScaleError("unsafe_project", "Require ordinary, non-symlink documents")
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_reference(content_path):
    if content_path is None:
        content, project = reference_project()
        return content, project, None, None
    path = Path(content_path).absolute()
    project_file = project_path(path)
    hashes = (_file_digest(path), _file_digest(project_file))
    session = AuthoringSession.open(path)
    if (_file_digest(path), _file_digest(project_file)) != hashes:
        raise ScaleError("source_changed", "Project changed while reading")
    snapshot = session.snapshot().to_dict()
    return snapshot["content"], snapshot["project"], path, hashes


def _asset_inventory(project, content_path):
    """Budget only: no decoding, licensing inference or image rendering."""
    from sporebound.assets import AssetRegistry
    from drawtemp.core import RuleError
    try:
        registry = AssetRegistry(project.get("assets") or None).to_dict()
    except (RuleError, ValueError, TypeError) as exc:
        raise ScaleError("invalid_assets", str(exc)) from exc
    entries = registry["entries"]
    if len(entries) > MAX_ASSETS:
        raise ScaleError("too_many_assets", "Asset inventory budget exceeded")
    indexed = []
    total_bytes = 0
    for entry in entries:
        if entry["kind"] == "animation":
            # Animation references other registered assets, not a disk file.
            continue
        if content_path is None:
            # Reference fixture is memory-only; no asset is claimed present.
            indexed.append({"kind": entry["kind"], "size_bytes": None})
            continue
        try:
            target = safe_asset_path(content_path.parent, entry["path"])
            size = target.stat().st_size
        except (OSError, ValueError) as exc:
            raise ScaleError("unsafe_asset", str(exc)) from exc
        total_bytes += size
        indexed.append({"kind": entry["kind"], "size_bytes": size})
    return {
        "registry_entries": len(entries),
        "disk_files_checked": sum(row["size_bytes"] is not None for row in indexed),
        "bytes": total_bytes,
        "bytes_verified": content_path is not None,
        "sampled": False,
    }


def _stats(ms):
    if not ms or any(type(x) not in (int, float) or not 0 <= x < float("inf")
                     for x in ms):
        raise ScaleError("invalid_samples", "Finite nonnegative wall times required")
    return {
        "samples": len(ms),
        "p50_ms": round(percentile(ms, 50), 5),
        "p95_ms": round(percentile(ms, 95), 5),
        "p99_ms": round(percentile(ms, 99), 5),
        "max_ms": round(max(ms), 5),
        "tail_exploratory": len(ms) < 100,
    }


def _timed(operation, warmups, samples):
    for _ in range(warmups):
        operation()
    measurements = []
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        for _ in range(samples):
            begin = perf_counter_ns()
            operation()
            measurements.append((perf_counter_ns() - begin) / 1_000_000)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {**_stats(measurements), "python_traced_peak_bytes": peak}


def collect_profile(*, content_path=None, samples=30, warmups=3,
                    synthetic_resources=1000):
    """Measure real, canonical operations. Read-only for files and session."""
    if type(samples) is not int or not 3 <= samples <= MAX_SAMPLES:
        raise ScaleError("invalid_samples", "Choose 3..250 independent samples")
    if type(warmups) is not int or not 0 <= warmups <= 20:
        raise ScaleError("invalid_warmups", "Choose 0..20 warmup runs")
    if type(synthetic_resources) is not int or not 10 <= synthetic_resources <= 10000:
        raise ScaleError("invalid_synthetic_size", "Choose 10..10000 synthetic resources")
    content, project, source, source_hashes = _read_reference(content_path)
    # Explicitly synthetic R2 projections: NOT a validated game or playable scene.
    synthetic_document = {"content": {"missions": []},
                          "project": {"title": "R30.F synthetic workload",
                                      "story": {"scenes": [
                                          {"id": f"scale_{n:05d}", "title": "Scale"}
                                          for n in range(synthetic_resources)]}}}
    synthetic_assets = {"assets": {"version": 1, "entries": [
        {"id": f"scale_{n:05d}", "kind": "sprite",
         "path": f"assets/scale_{n:05d}.png"}
        for n in range(synthetic_resources)], "bindings": {}}}
    opened = AuthoringSession.new(content, project)
    source_copy = opened.snapshot().to_dict()
    def open_session():
        return AuthoringSession.new(content, project)
    def take_snapshot():
        return opened.snapshot().to_dict()
    def project_resources():
        return resources(opened.snapshot())
    def read_gallery():
        return load_catalog()
    def assets():
        return _asset_inventory(project, source)
    actions = {
        "authoring_open": open_session, "snapshot": take_snapshot,
        "resource_projection": project_resources, "gallery_load": read_gallery,
        "asset_inventory": assets,
        "synthetic_resource_projection": lambda: resources(synthetic_document),
        "synthetic_asset_registry": lambda: _asset_inventory(synthetic_assets, None),
    }
    rows = []
    for name in OPS:
        rows.append({"operation": name,
                     "workload_kind": ("synthetic" if name.startswith("synthetic_")
                                       else "canonical"),
                     **_timed(actions[name], warmups, samples)})
    if opened.snapshot().to_dict() != source_copy:
        raise ScaleError("mutated_session", "Benchmark changed the authoring session")
    if source is not None and (
        _file_digest(source), _file_digest(project_path(source))
    ) != source_hashes:
        raise ScaleError("source_changed", "Benchmark input changed during measurement")
    asset_budget = assets()
    project_digest = sha256(json.dumps(
        {"content": content.to_dict() if hasattr(content, "to_dict") else content,
         "project": project.to_dict() if hasattr(project, "to_dict") else project},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": SCHEMA,
        "environment": {
            "os": platform.system(), "architecture": platform.machine(),
            "python": platform.python_version(), "cpu": platform.processor() or "unknown",
            "runner": os.environ.get("RUNNER_OS", "local"),
            "hostname": platform.node(),
        },
        "workload": {
            "project_sha256": project_digest, "samples": samples,
            "warmups": warmups, "operations": list(OPS),
            "synthetic_resources": synthetic_resources,
            "disk_project": source is not None,
        },
        "asset_budget": asset_budget,
        "metrics": rows,
        "gate": {
            "status": "informational",
            "gpu_certified": False,
            "player_certified": False,
            "reason": "CPU/asset profiling only; no real GPU frame measurements",
        },
    }


def validate_report(report):
    if not isinstance(report, dict) or set(report) != {
        "schema", "environment", "workload", "asset_budget", "metrics", "gate"
    } or report["schema"] != SCHEMA:
        raise ScaleError("invalid_report", "Unexpected R30.F report schema")
    env, workload, budget, gate = (
        report["environment"], report["workload"], report["asset_budget"], report["gate"]
    )
    if (not isinstance(env, dict) or not isinstance(workload, dict) or
            not isinstance(budget, dict) or not isinstance(gate, dict)):
        raise ScaleError("invalid_report", "Malformed environment, workload or gate")
    for key in ("os", "architecture", "python", "cpu", "runner", "hostname"):
        if not isinstance(env.get(key), str):
            raise ScaleError("invalid_report", "Missing host field " + key)
    if (not isinstance(workload.get("project_sha256"), str) or
            len(workload["project_sha256"]) != 64 or
            not all(c in "0123456789abcdef" for c in workload["project_sha256"]) or
            type(workload.get("samples")) is not int or
            not 3 <= workload["samples"] <= MAX_SAMPLES or
            type(workload.get("warmups")) is not int or
            not 0 <= workload["warmups"] <= 20 or
            type(workload.get("synthetic_resources")) is not int or
            not 10 <= workload["synthetic_resources"] <= 10000 or
            workload.get("operations") != list(OPS) or
            type(workload.get("disk_project")) is not bool):
        raise ScaleError("invalid_report", "Invalid workload parameters")
    if (type(budget.get("registry_entries")) is not int or
            not 0 <= budget["registry_entries"] <= MAX_ASSETS or
            type(budget.get("disk_files_checked")) is not int or
            not 0 <= budget["disk_files_checked"] <= budget["registry_entries"] or
            type(budget.get("bytes")) is not int or budget["bytes"] < 0 or
            type(budget.get("bytes_verified")) is not bool or
            budget.get("sampled") is not False):
        raise ScaleError("invalid_report", "Bad asset budget")
    if gate != {
        "status": "informational", "gpu_certified": False,
        "player_certified": False,
        "reason": "CPU/asset profiling only; no real GPU frame measurements",
    }:
        raise ScaleError("invalid_report", "Certification cannot be inferred from a CPU profile")
    rows = report["metrics"]
    if not isinstance(rows, list) or [r.get("operation") if isinstance(r, dict)
                                      else None for r in rows] != list(OPS):
        raise ScaleError("invalid_report", "Incomplete operation coverage")
    for row in rows:
        if (set(row) != {
            "operation", "workload_kind", "samples", "p50_ms", "p95_ms", "p99_ms", "max_ms",
            "tail_exploratory", "python_traced_peak_bytes"
        } or row["samples"] != workload["samples"] or
                row["workload_kind"] != ("synthetic" if row["operation"].startswith("synthetic_") else "canonical") or
                row["tail_exploratory"] is not (row["samples"] < 100) or
                type(row["python_traced_peak_bytes"]) is not int or
                row["python_traced_peak_bytes"] < 0 or
                any(type(row[key]) not in (float, int) or
                    not 0 <= row[key] < float("inf")
                    for key in ("p50_ms", "p95_ms", "p99_ms", "max_ms")) or
                not row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"] <= row["max_ms"]):
            raise ScaleError("invalid_report", "Invalid percentile or memory evidence")
    return report


def compare_profiles(baseline, candidate, *, max_p95_growth_pct=25.0,
                     min_delta_ms=1.0, allow_host_mismatch=False):
    """A fully opt-in regression gate; fail closed on incomparable workloads."""
    validate_report(baseline)
    validate_report(candidate)
    b, c = baseline["workload"], candidate["workload"]
    if b != c:
        raise ScaleError("incomparable", "Different profile scenarios/workloads")
    same = baseline["environment"] == candidate["environment"]
    if not same and not allow_host_mismatch:
        raise ScaleError("incomparable", "Different environments; cannot gate fairly")
    if not isinstance(max_p95_growth_pct, (int, float)) or not 0 <= max_p95_growth_pct <= 10000:
        raise ScaleError("invalid_threshold", "Expected nonnegative growth percent")
    if not isinstance(min_delta_ms, (int, float)) or not 0 <= min_delta_ms < float("inf"):
        raise ScaleError("invalid_threshold", "Expected nonnegative absolute delta")
    differences = []
    for before, after in zip(baseline["metrics"], candidate["metrics"]):
        change = after["p95_ms"] - before["p95_ms"]
        ratio = change / before["p95_ms"] * 100 if before["p95_ms"] else (
            float("inf") if change > 0 else 0.0)
        exceeded = change > min_delta_ms and ratio > max_p95_growth_pct
        differences.append({
            "operation": before["operation"],
            "base_p95_ms": before["p95_ms"],
            "candidate_p95_ms": after["p95_ms"],
            "growth_pct": round(ratio, 3) if ratio < float("inf") else None,
            "delta_ms": round(change, 5),
            "regressed": exceeded,
        })
    return {
        "schema": SCHEMA + "-comparison",
        "comparable_hosts": same, "blocked": any(row["regressed"] for row in differences),
        "thresholds": {
            "max_p95_growth_pct": max_p95_growth_pct,
            "min_delta_ms": min_delta_ms,
        },
        "changes": differences,
        "gate": "opt-in comparison only; not GPU certification",
    }


def _load_report(path):
    if Path(path).stat().st_size > _MAX_REPORT:
        raise ScaleError("oversized_report", "Report exceeds 1 MiB")
    return validate_report(json.loads(Path(path).read_text(encoding="utf-8")))


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp R30.F CPU and asset profiling")
    parser.add_argument("--content", type=Path, help="Paired Content/GameProject; default reference Jeanne")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--synthetic-resources", type=int, default=1000,
                        help="Synthetic R2 projection and asset registry size: 10..10000")
    parser.add_argument("--output", type=Path, help="Create a NEW JSON report (never overwrite)")
    parser.add_argument("--baseline", type=Path, help="Compare with an existing JSON report")
    parser.add_argument("--max-p95-growth-pct", type=float, default=25.0)
    parser.add_argument("--min-delta-ms", type=float, default=1.0)
    parser.add_argument("--allow-host-mismatch", action="store_true")
    args = parser.parse_args(argv)
    if args.baseline is not None and args.output is None:
        parser.error("--baseline requires --output for the current report")
    try:
        report = validate_report(collect_profile(
            content_path=args.content, samples=args.samples,
            warmups=args.warmups, synthetic_resources=args.synthetic_resources))
        compare = None
        if args.baseline is not None:
            compare = compare_profiles(
                _load_report(args.baseline), report,
                max_p95_growth_pct=args.max_p95_growth_pct,
                min_delta_ms=args.min_delta_ms,
                allow_host_mismatch=args.allow_host_mismatch)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
        print(json.dumps({"report": report, "comparison": compare},
                         sort_keys=True, ensure_ascii=False, indent=2))
        return 2 if compare is not None and compare["blocked"] else 0
    except (ScaleError, OSError, ValueError) as exc:
        print("R30.F: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
