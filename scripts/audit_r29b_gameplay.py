#!/usr/bin/env python3
"""R29.B static action-adventure puzzle audit and optional *real* R26 replay.

Examples:
 python scripts/audit_r29b_gameplay.py --scene ruins.json --goal 4,2 --report out/r29b.json
 python scripts/audit_r29b_gameplay.py --scene ruins.json --goal 4,2 --commands trace.json --report out/r29b.json

No generated output is a release certificate. Exits: 0 = static reachability
witness; 1 = definite static risk or invalid input; 2 = inconclusive/blocked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawtemp.quality.r29b_gameplay import analyze_action_scene, audit_action_replay


def parse_goal(value):
    try:
        parts = value.split(",")
        if len(parts) != 2 or any(not part.strip().isdigit() for part in parts):
            raise ValueError
        return [int(part) for part in parts]
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError("Expected goal X,Y with nonnegative integers")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--goal", type=parse_goal, action="append", required=True)
    parser.add_argument("--state-budget", type=int, default=50000)
    parser.add_argument("--commands", type=Path, help="Optional R26 tick-input JSON array")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-solved", action="store_true",
                        help="Reject static risks or inconclusive exploration (NOT release gate)")
    args = parser.parse_args(argv)
    try:
        scene = json.loads(args.scene.read_text(encoding="utf-8"))
        static = analyze_action_scene(scene, args.goal, state_budget=args.state_budget)
        replay = ({"status": "not_requested", "runtime_certified": False}
                  if args.commands is None else audit_action_replay(
                      scene, json.loads(args.commands.read_text(encoding="utf-8"))))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print("R29.B invalid scene/replay: " + str(exc), file=sys.stderr)
        return 1
    result = {"schema": 1, "kind": "drawtemp-r29b-gameplay-lab",
              "static_analysis": static, "action_replay": replay,
              "decision": "no-go", "release_ready": False,
              "scope": "static scene reachability and optional bounded R26 replay; NOT gameplay certification"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.report), "status": static["status"],
                      "action_replay": replay["status"], "decision": "no-go"}))
    if static["status"] == "softlock_risk":
        return 1
    if static["status"] == "inconclusive" or replay["status"] == "blocked":
        return 2
    if args.require_solved and any("enemy AI" in limit for limit in static["limitations"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
