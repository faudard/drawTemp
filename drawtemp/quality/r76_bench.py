"""R76.C — reproducible native-bundle footprint and Python project-load bench.

This *does not* measure native Player launch, real GPU memory or frame latency.
All measurements are observations; no synthetic sample or certification implied.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
from time import perf_counter_ns
import tracemalloc

from drawtemp.export.r15 import project_path, verify_bundle
from drawtemp.quality.r14 import percentile, validate_gpu_profile

SCHEMA = 1
MIN_SAMPLES = 5
MAX_SAMPLES = 500
MAX_REPORT_BYTES = 4 * 1024 * 1024
REVISION = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
TIMEOUT_S = 30


class BenchmarkError(ValueError):
    pass


def _json(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _safe_report(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise BenchmarkError("Missing, symlinked or oversized benchmark report")
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise BenchmarkError("Duplicate report JSON key")
            d[k] = v
        return d
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def _hash_file(path):
    digest = sha256()
    with Path(path).open("rb") as fd:
        while True:
            part = fd.read(1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def _series(samples):
    if not isinstance(samples, list) or len(samples) < MIN_SAMPLES or any(
            type(x) not in (int, float) or not math.isfinite(x) or x < 0
            for x in samples):
        raise BenchmarkError("Need finite nonnegative observed samples")
    return {
        "count": len(samples),
        "min": round(min(samples), 5),
        "p50": round(percentile(samples, 50), 5),
        "p95": round(percentile(samples, 95), 5),
        "p99": round(percentile(samples, 99), 5),
        "max": round(max(samples), 5),
        "mean": round(statistics.mean(samples), 5),
        "stddev": round(statistics.pstdev(samples), 5),
        "variance": round(statistics.pvariance(samples), 5),
        "tail_exploratory": len(samples) < 100,
    }


def _environment():
    return {
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "runner": os.environ.get("RUNNER_OS", "local"),
        "python_executable": str(Path(sys.executable).resolve()),
    }


def _bundle_inventory(bundle):
    root = Path(bundle)
    if root.is_symlink():
        raise BenchmarkError("Symlinked bundle root forbidden")
    root = root.resolve(strict=True)
    # R15 checks every listed file and rejects surprises or symlinks.
    manifest = verify_bundle(root, require_release=False)
    content = root / manifest["content"]
    if content.is_symlink() or project_path(content).is_symlink():
        raise BenchmarkError("Symlinked content/project forbidden")
    total = (root / "manifest.json").stat().st_size
    groups = {"Player": 0, "game": 0, "other": 0}
    file_count = 1
    for row in manifest["files"]:
        size = row["size"]
        total += size
        file_count += 1
        key = row["path"].split("/", 1)[0]
        groups[key if key in groups else "other"] += size
    return {
        "manifest_sha256": _hash_file(root / "manifest.json"),
        "content_sha256": _hash_file(content),
        "project_sha256": _hash_file(project_path(content)),
        "file_count": file_count,
        "bundle_bytes": total,
        "player_bytes": groups["Player"],
        "game_bytes": groups["game"],
        "other_bytes": groups["other"] + (root / "manifest.json").stat().st_size,
        "content_relative": manifest["content"],
        "release_candidate": manifest["release_candidate"] is True,
    }


def _child_probe(content_path):
    """Run in a fresh Python process; process RSS not available on all OSes."""
    from sporebound.assets import AssetRegistry
    from sporebound.studio_transaction import validate_pair

    tracemalloc.start()
    try:
        with Path(content_path).open(encoding="utf-8") as stream:
            content = json.load(stream)
        with project_path(content_path).open(encoding="utf-8") as stream:
            project = json.load(stream)
        content, project = validate_pair(content, project)
        registry = AssetRegistry(project.get("assets") or None)
        asset_count = len(registry.to_dict()["entries"])
        mission_count = len(content["missions"])
        peak_python = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    rss = None
    if sys.platform != "win32":
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss *= (1 if sys.platform == "darwin" else 1024)
        except (ImportError, OSError):
            pass
    return {"python_peak_bytes": peak_python, "process_peak_rss_bytes": rss,
            "assets": asset_count, "missions": mission_count}


def _measure_once(bundle, content_relative, *, timeout=TIMEOUT_S):
    """Fixed command: no shell and no externally provided executable or args."""
    content = Path(bundle).resolve(strict=True) / content_relative
    if content.is_symlink() or project_path(content).is_symlink():
        raise BenchmarkError("Symlinked project file")
    command = [sys.executable, "-m", "drawtemp.quality.r76_bench", "_probe",
               "--content", str(content)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    started = perf_counter_ns()
    try:
        process = subprocess.run(command, env=env, capture_output=True,
                                 text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise BenchmarkError("Project-load child exceeded timeout") from exc
    elapsed_ms = (perf_counter_ns() - started) / 1_000_000
    if process.returncode != 0:
        raise BenchmarkError("Project-load child failed (no sample accepted): " +
                             process.stderr[-500:])
    try:
        result = json.loads(process.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise BenchmarkError("Invalid child measurement") from exc
    if (not isinstance(result, dict) or
            type(result.get("python_peak_bytes")) is not int or
            result["python_peak_bytes"] < 0 or
            type(result.get("missions")) is not int or
            type(result.get("assets")) is not int or
            (result.get("process_peak_rss_bytes") is not None and (
                type(result["process_peak_rss_bytes"]) is not int or
                result["process_peak_rss_bytes"] <= 0))):
        raise BenchmarkError("Invalid observed memory or corpus sample")
    return elapsed_ms, result


def _revision(value):
    if value is None:
        value = os.environ.get("GITHUB_SHA", "")
    if not isinstance(value, str) or not REVISION.fullmatch(value):
        raise BenchmarkError("An exact 40-hex commit --revision is required")
    return value


def collect(bundle, *, revision=None, samples=30, warmups=3, corpus="r76-default"):
    """Independent subprocess samples; verified disk bytes; read-only bundle."""
    if type(samples) is not int or not MIN_SAMPLES <= samples <= MAX_SAMPLES:
        raise BenchmarkError("Sample count must be 5..500")
    if type(warmups) is not int or not 0 <= warmups <= 20:
        raise BenchmarkError("Warmups must be 0..20")
    if not isinstance(corpus, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", corpus):
        raise BenchmarkError("Corpus must be a stable identifier (1..64 characters)")
    commit = _revision(revision)
    inventory = _bundle_inventory(bundle)
    seen = []
    for _ in range(warmups + samples):
        elapsed, details = _measure_once(bundle, inventory["content_relative"])
        seen.append((elapsed, details))
    observed = seen[warmups:]
    if len({(e["assets"], e["missions"]) for _, e in seen}) != 1:
        raise BenchmarkError("Different mission/asset corpus across subprocess runs")
    if inventory != _bundle_inventory(bundle):
        raise BenchmarkError("Bundle changed during measurement")
    rss = [details["process_peak_rss_bytes"] for _, details in observed]
    peak_rss = _series(rss) if all(v is not None for v in rss) else None
    report = {
        "schema": SCHEMA,
        "kind": "drawtemp-r76c-observed-bench",
        "revision": commit,
        "environment": _environment(),
        "corpus": corpus,
        "workload": {
            "probe": "python_fresh_process_validate_pair",
            "samples": samples, "warmups": warmups,
            "observed_assets": observed[0][1]["assets"],
            "observed_missions": observed[0][1]["missions"],
            "native_player_startup_ms": None,
        },
        "bundle": inventory,
        "measurements": {
            "project_load_process_ms": _series([t for t, _ in observed]),
            "python_traced_peak_bytes": _series(
                [details["python_peak_bytes"] for _, details in observed]),
            "process_peak_rss_bytes": peak_rss,
        },
        "gate": {
            "status": "informational",
            "physical_gpu_observed": False,
            "gpu_memory_bytes": None,
            "frame_p95_ms": None, "frame_p99_ms": None,
            "native_player_verified": False,
            "release_certified": False,
            "note": "Python project-load process, not native Player startup or GPU; p99 exploratory below 100 samples",
        },
    }
    return validate_report(report)


def validate_report(report):
    if not isinstance(report, dict) or set(report) != {
            "schema", "kind", "revision", "environment", "corpus",
            "workload", "bundle", "measurements", "gate"} or (
            report["schema"] != SCHEMA or
            report["kind"] != "drawtemp-r76c-observed-bench"):
        raise BenchmarkError("Unexpected R76.C report schema")
    _revision(report["revision"])
    if not isinstance(report["environment"], dict) or not all(
            isinstance(report["environment"].get(k), str) for k in (
                "os", "architecture", "python", "cpu", "runner",
                "python_executable")):
        raise BenchmarkError("Incomplete host metadata")
    work = report["workload"]
    if (not isinstance(work, dict) or
            work.get("probe") != "python_fresh_process_validate_pair" or
            type(work.get("samples")) is not int or
            not MIN_SAMPLES <= work["samples"] <= MAX_SAMPLES or
            type(work.get("warmups")) is not int or
            not 0 <= work["warmups"] <= 20 or
            work.get("native_player_startup_ms") is not None or
            type(work.get("observed_assets")) is not int or
            type(work.get("observed_missions")) is not int or
            work["observed_assets"] < 0 or work["observed_missions"] < 0):
        raise BenchmarkError("Malformed measured workload")
    bundle = report["bundle"]
    if not isinstance(bundle, dict) or set(bundle) != {
            "manifest_sha256", "content_sha256", "project_sha256",
            "file_count", "bundle_bytes", "player_bytes", "game_bytes",
            "other_bytes", "content_relative", "release_candidate"}:
        raise BenchmarkError("Malformed physical bundle inventory")
    for key in ("manifest_sha256", "content_sha256", "project_sha256"):
        if not isinstance(bundle[key], str) or not HASH.fullmatch(bundle[key]):
            raise BenchmarkError("Invalid inventory hash")
    for key in ("file_count", "bundle_bytes", "player_bytes", "game_bytes", "other_bytes"):
        if type(bundle[key]) is not int or bundle[key] < 0:
            raise BenchmarkError("Invalid bundle bytes/count")
    if (bundle["file_count"] < 3 or
            bundle["bundle_bytes"] != bundle["player_bytes"] +
            bundle["game_bytes"] + bundle["other_bytes"] or
            type(bundle["release_candidate"]) is not bool or
            not isinstance(bundle["content_relative"], str) or
            not bundle["content_relative"].startswith("game/")):
        raise BenchmarkError("Inconsistent bundle inventory")
    m = report["measurements"]
    if not isinstance(m, dict) or set(m) != {
            "project_load_process_ms", "python_traced_peak_bytes",
            "process_peak_rss_bytes"}:
        raise BenchmarkError("Missing measured series")
    for key in ("project_load_process_ms", "python_traced_peak_bytes", "process_peak_rss_bytes"):
        item = m[key]
        if item is None and key == "process_peak_rss_bytes":
            continue
        if not isinstance(item, dict) or item.get("count") != work["samples"]:
            raise BenchmarkError("Missing/short measurement samples")
        for field in ("min", "p50", "p95", "p99", "max", "mean", "stddev", "variance"):
            if type(item.get(field)) not in (int, float) or not math.isfinite(item[field]) or item[field] < 0:
                raise BenchmarkError("Invalid percentile/variance")
        if (not item["min"] <= item["p50"] <= item["p95"] <= item["p99"] <= item["max"]
                or item.get("tail_exploratory") is not (work["samples"] < 100)):
            raise BenchmarkError("Inconsistent percentile observations")
    if report["gate"] != {
        "status": "informational", "physical_gpu_observed": False,
        "gpu_memory_bytes": None, "frame_p95_ms": None, "frame_p99_ms": None,
        "native_player_verified": False, "release_certified": False,
        "note": "Python project-load process, not native Player startup or GPU; p99 exploratory below 100 samples",
    }:
        raise BenchmarkError("R76.C cannot manufacture release/GPU evidence")
    if not isinstance(report["corpus"], str) or not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", report["corpus"]):
        raise BenchmarkError("Unrecognized corpus")
    return report


def compare(baseline, candidate, *, max_p95_growth_pct=15.0):
    """Informational delta only; never auto-authorize an optimized release."""
    validate_report(baseline)
    validate_report(candidate)
    if (baseline["revision"] != candidate["revision"] or
            baseline["environment"] != candidate["environment"] or
            baseline["corpus"] != candidate["corpus"] or
            baseline["workload"] != candidate["workload"] or
            baseline["bundle"]["content_sha256"] != candidate["bundle"]["content_sha256"]):
        raise BenchmarkError("Incomparable revision/host/corpus/Content/workload")
    if type(max_p95_growth_pct) not in (float, int) or not math.isfinite(max_p95_growth_pct) or (
            not 0 <= max_p95_growth_pct <= 10000):
        raise BenchmarkError("Invalid latency growth budget")
    before = baseline["measurements"]["project_load_process_ms"]["p95"]
    after = candidate["measurements"]["project_load_process_ms"]["p95"]
    growth = 100 * (after - before) / before if before else (
        0 if after == 0 else float("inf"))
    delta = candidate["bundle"]["bundle_bytes"] - baseline["bundle"]["bundle_bytes"]
    return {
        "schema": SCHEMA,
        "kind": "drawtemp-r76c-informational-comparison",
        "p95_delta_ms": round(after - before, 5),
        "p95_growth_pct": round(growth, 5) if math.isfinite(growth) else None,
        "bundle_delta_bytes": delta,
        "bundle_reduction_observed": delta < 0,
        "latency_regressed": growth > max_p95_growth_pct,
        "status": "informational_only",
        "release_certified": False,
    }


def inspect_external_gpu(path):
    """Schema-check externally supplied GPU runs, not device attestation."""
    profile = _safe_report(path)
    measured = validate_gpu_profile(profile)
    return {
        "schema": SCHEMA,
        "external_report_sha256": _hash_file(path),
        "evidence_scope": "external_self_reported_not_independently_attested",
        "device": measured["device"],
        "scenes": measured["scenes"],
        "gpu_memory_bytes": None,
        "r76_release_certified": False,
    }


def _write_new(path, data):
    dest = Path(path)
    if dest.is_symlink() or dest.exists():
        raise BenchmarkError("Refusing existing or symlinked output")
    if not dest.parent.is_dir():
        raise BenchmarkError("Report parent must exist (create it separately)")
    with dest.open("xb") as output:
        output.write(_json(data))


def main(argv=None):
    parser = argparse.ArgumentParser(description="R76.C measured CPU/bundle benchmark (NO-GO)")
    sub = parser.add_subparsers(dest="action", required=True)
    internal = sub.add_parser("_probe", help=argparse.SUPPRESS)
    internal.add_argument("--content", required=True, type=Path)
    collect_cmd = sub.add_parser("collect")
    collect_cmd.add_argument("--bundle", required=True, type=Path)
    collect_cmd.add_argument("--revision")
    collect_cmd.add_argument("--corpus", default="r76-default")
    collect_cmd.add_argument("--samples", type=int, default=30)
    collect_cmd.add_argument("--warmups", type=int, default=3)
    collect_cmd.add_argument("--output", type=Path)
    compare_cmd = sub.add_parser("compare")
    compare_cmd.add_argument("--baseline", type=Path, required=True)
    compare_cmd.add_argument("--candidate", type=Path, required=True)
    compare_cmd.add_argument("--max-p95-growth-pct", type=float, default=15.0)
    gpu_cmd = sub.add_parser("inspect-gpu")
    gpu_cmd.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "_probe":
            print(json.dumps(_child_probe(args.content)))
            return 0
        if args.action == "collect":
            result = collect(args.bundle, revision=args.revision,
                             samples=args.samples, warmups=args.warmups,
                             corpus=args.corpus)
            if args.output is not None:
                _write_new(args.output, result)
        elif args.action == "compare":
            result = compare(_safe_report(args.baseline), _safe_report(args.candidate),
                             max_p95_growth_pct=args.max_p95_growth_pct)
        else:
            result = inspect_external_gpu(args.report)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("R76.C NO-GO: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
