#!/usr/bin/env python3
"""Summarize real Studio opt-in Tk callback traces without leaking game content.

Only aggregate identical operation + size/complexity buckets. These timings
are callback->idle approximations, not physical pointer-to-photon latency.
"""
from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.profile_scale_3732 import percentiles

BUCKET_BY_OPERATION = {
    "map.refresh": "map_cells",
    "workspace.refresh": "resource_nodes",
    "event_graph.draw": "nodes",
    "story_graph.draw": "nodes",
}
FIELDS = ("callback_ms", "callback_to_idle_ms", "queued_idle_ms")


def summarize(lines):
    groups = {}
    for number, text in enumerate(lines, 1):
        if not text.strip():
            continue
        try:
            row = json.loads(text)
        except ValueError as exc:
            raise ValueError("Invalid JSONL row %d: %s" % (number, exc)) from exc
        if row.get("schema") != "drawtemp-ui-trace-v1":
            raise ValueError("Unexpected trace schema at row %d" % number)
        operation = row.get("operation")
        if operation not in BUCKET_BY_OPERATION:
            raise ValueError("Unknown traced operation at row %d" % number)
        bucket = BUCKET_BY_OPERATION[operation]
        complexity = row.get("counts", {}).get(bucket)
        if type(complexity) is not int or complexity < 0:
            raise ValueError("Missing scene complexity (%s), row %d" %
                             (bucket, number))
        for field in FIELDS:
            value = row.get(field)
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not isfinite(value) or value < 0):
                raise ValueError("Invalid %s, row %d" % (field, number))
        key = (operation, bucket, complexity)
        group = groups.setdefault(key, {name: [] for name in FIELDS})
        for field in FIELDS:
            group[field].append(row[field])

    if not groups:
        raise ValueError("No valid UI trace samples")
    results = []
    for (operation, bucket, complexity), values in sorted(groups.items()):
        results.append({
            "operation": operation,
            "complexity_dimension": bucket,
            "complexity_value": complexity,
            "samples": len(values[FIELDS[0]]),
            "sufficient_for_tail_exploration": len(values[FIELDS[0]]) >= 100,
            "timings": {key: percentiles(sample) for key, sample in values.items()},
        })
    return {
        "schema": "drawtemp-ui-trace-summary-v1",
        "scope": "Tk callback to next idle, not physical input-to-photon",
        "sample_warning": "p99 values with fewer than 100 samples are exploratory",
        "groups": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="SPOREBOUND_UI_TRACE .jsonl path")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.trace.open("r", encoding="utf-8") as src:
            report = summarize(src)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
