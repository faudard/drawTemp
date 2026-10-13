#!/usr/bin/env python3
"""Compare two reproducible 3.7.32 profiling JSON reports (no default budgets).

Only measurements from compatible environments and identical parameters are
compared. No p95/p99 performance verdict is claimed from a CI smoke sample.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

KEYS = ("p50_ms", "p95_ms", "p99_ms")
CHECK_PARAMETERS = ("phase", "sizes", "cells", "frames", "samples",
                    "resources", "events", "short_saves", "long_saves",
                    "assets", "quick")
CHECK_ENVIRONMENT = ("platform", "python", "architecture", "logical_cpus",
                     "tk_patchlevel")


def measurements(report):
    """Flatten existing benchmark schemas without discarding operation identity."""
    if report.get("schema") != "drawtemp-performance-scale-v1":
        raise ValueError("Unsupported profiling JSON schema")
    rows = {}

    def add(key, row):
        if key in rows:
            raise ValueError("Duplicate measurement: " + key)
        if not all(isinstance(row.get(field), (int, float)) for field in KEYS):
            raise ValueError("Missing percentile in " + key)
        rows[key] = {
            field: float(row[field]) for field in KEYS
        }
        if isinstance(row.get("rss_bytes"), (int, float)):
            rows[key]["rss_bytes"] = int(row["rss_bytes"])
        elif isinstance(row.get("process_rss_bytes"), (int, float)):
            rows[key]["rss_bytes"] = int(row["process_rss_bytes"])
        if isinstance(row.get("canvas_items"), int):
            rows[key]["canvas_items"] = row["canvas_items"]

    for row in report.get("headless", []):
        add("headless/" + row["operation"], row)

    for scene in report.get("gui", {}).get("editor", []):
        scene_key = "editor/map=%s/cell=%s/assets=%s" % (
            scene["map"], scene["cell_size"], scene["assets"])
        for mode, data in scene["modes"].items():
            for operation, metrics in data["operations"].items():
                add(scene_key + "/" + mode + "/" + operation, metrics)
    for scene in report.get("gui", {}).get("player", []):
        scene_key = "player/mission=%s/actors=%s/cell=%s/pan=%s" % (
            scene["mission"], scene["actors"], scene["cell_size"], scene["pan"])
        add(scene_key, scene)
    if not rows:
        raise ValueError("No comparable measurements found")
    return rows


def check_compatible(baseline, candidate, *, allow_host_mismatch=False):
    if baseline.get("schema") != candidate.get("schema"):
        raise ValueError("Incompatible report schemas")
    for key in CHECK_PARAMETERS:
        a = baseline.get("parameters", {}).get(key)
        b = candidate.get("parameters", {}).get(key)
        if a != b:
            raise ValueError("Benchmark parameters differ: %s (%r != %r)" %
                             (key, a, b))
    mismatches = []
    for key in CHECK_ENVIRONMENT:
        a = baseline.get("environment", {}).get(key)
        b = candidate.get("environment", {}).get(key)
        if a != b:
            mismatches.append("%s: %r vs %r" % (key, a, b))
    if mismatches and not allow_host_mismatch:
        raise ValueError(
            "Environment mismatch; use the same machine/Python/Tk. "
            "Override for inspection only: " + "; ".join(mismatches))
    return mismatches


def compare(baseline, candidate, *, allow_host_mismatch=False,
            block_p95_pct=None, block_p99_pct=None, block_min_ms=0.0):
    mismatch = check_compatible(
        baseline, candidate, allow_host_mismatch=allow_host_mismatch)
    if mismatch and (block_p95_pct is not None or block_p99_pct is not None):
        raise ValueError("Blocking regression gates require matching environments")
    before = measurements(baseline)
    after = measurements(candidate)
    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    if missing or added:
        raise ValueError("Scenario mismatch: missing=%s extra=%s" %
                         (missing[:5], added[:5]))
    records = []
    blocked = []
    for key in sorted(before):
        values = {}
        for percentile in KEYS:
            start = before[key][percentile]
            end = after[key][percentile]
            delta = round(end - start, 3)
            values[percentile] = {
                "baseline": start,
                "candidate": end,
                "delta_ms": delta,
                "delta_pct": round(100.0 * (end / start - 1), 2)
                             if start > 0 else None,
            }
        memory = {}
        for counter in ("rss_bytes", "canvas_items"):
            if counter in before[key] and counter in after[key]:
                memory[counter] = {
                    "baseline": before[key][counter],
                    "candidate": after[key][counter],
                    "delta": after[key][counter] - before[key][counter],
                }
        records.append({"case": key, "latency": values, "counters": memory})
        for field, limit in (("p95_ms", block_p95_pct),
                             ("p99_ms", block_p99_pct)):
            delta = values[field]
            if (limit is not None and delta["delta_pct"] is not None
                    and delta["delta_pct"] > limit
                    and delta["delta_ms"] >= block_min_ms):
                blocked.append({"case": key, "metric": field,
                                "limit_pct": limit,
                                "actual_pct": delta["delta_pct"],
                                "delta_ms": delta["delta_ms"]})
    return {
        "schema": "drawtemp-performance-comparison-v1",
        "baseline_sha": baseline.get("source_sha"),
        "candidate_sha": candidate.get("source_sha"),
        "environment_mismatches": mismatch,
        "compatible": not mismatch,
        "sample_warning": (
            "p99 tails are exploratory with fewer than 100 repetitions."
            if baseline.get("parameters", {}).get("samples", 0) < 100
            or baseline.get("parameters", {}).get("frames", 0) < 100 else None
        ),
        "thresholds": {"p95_pct": block_p95_pct, "p99_pct": block_p99_pct,
                       "min_absolute_ms": block_min_ms},
        "blocked": blocked,
        "comparisons": records,
    }


def markdown(result, limit=25):
    rows = sorted(
        result["comparisons"],
        key=lambda x: x["latency"]["p95_ms"]["delta_ms"],
        reverse=True)
    text = [
        "# Performance & Scale — avant/après",
        "",
        "Baseline: %s → Candidate: %s" %
        (result.get("baseline_sha") or "unknown",
         result.get("candidate_sha") or "unknown"),
        "",
        "Environnements compatibles: **%s**" %
        ("oui" if result["compatible"] else "non (inspection uniquement)"),
        "",
        "| Scénario | p50 Δ ms | p95 Δ ms | p95 Δ %% | p99 Δ ms |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for entry in rows[:limit]:
        lat = entry["latency"]
        text.append("| %s | %+0.3f | %+0.3f | %s | %+0.3f |" % (
            entry["case"], lat["p50_ms"]["delta_ms"],
            lat["p95_ms"]["delta_ms"],
            ("%+.2f%%" % lat["p95_ms"]["delta_pct"]
             if lat["p95_ms"]["delta_pct"] is not None else "n/a"),
            lat["p99_ms"]["delta_ms"]))
    if result["sample_warning"]:
        text.extend(["", "**Avertissement :** " + result["sample_warning"]])
    text.extend(["", "Cas au-delà des seuils optionnels : **%d**" %
                 len(result["blocked"]), ""])
    return "\n".join(text)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--allow-host-mismatch", action="store_true",
                   help="Explore only; report is explicitly marked incompatible")
    p.add_argument("--block-p95-pct", type=float,
                   help="Optional blocking policy AFTER reference-machine baseline")
    p.add_argument("--block-p99-pct", type=float,
                   help="Optional blocking policy AFTER reference-machine baseline")
    p.add_argument("--block-min-ms", type=float, default=0.0)
    p.add_argument("--output", type=Path)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args(argv)
    if any(x is not None and x < 0 for x in
           (args.block_p95_pct, args.block_p99_pct)) or args.block_min_ms < 0:
        p.error("Regression thresholds must be non-negative")
    try:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        new = json.loads(args.candidate.read_text(encoding="utf-8"))
        result = compare(
            base, new, allow_host_mismatch=args.allow_host_mismatch,
            block_p95_pct=args.block_p95_pct,
            block_p99_pct=args.block_p99_pct, block_min_ms=args.block_min_ms)
    except (ValueError, KeyError, OSError) as exc:
        p.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(result), encoding="utf-8")
    else:
        print(markdown(result))
    return 2 if result["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
