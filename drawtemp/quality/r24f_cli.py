"""CLI for R24.F CPU renderer profiling and cancellable native Battle Lab."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import sys

from drawtemp.core import Content
from drawtemp.quality.r24f_scale import (
    ScaleProfileError, compare_cpu_scale, profile_cpu_renderer,
)
from drawtemp.sdk.r24f_mass_lab import (
    MassiveSimulationJob, compare_massive_runs,
)
from sporebound.model import RuleError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("renderer", "battle", "both"), default="both")
    parser.add_argument("--content", type=Path, help="Canonical Content v1 JSON (defaults to bundled Asterion)")
    parser.add_argument("--mission", default="signal_depot")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--command-limit", type=int, default=16)
    parser.add_argument("--cancel-after", type=int, help="Cancel after N verified seeds")
    parser.add_argument("--sizes", nargs="+", type=int, default=[32, 64, 128])
    parser.add_argument("--zooms", nargs="+", type=int, default=[24, 54, 96])
    parser.add_argument("--actors", type=int, default=20)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--baseline", type=Path, help="Compare against a previous same-workload report")
    parser.add_argument("--report", type=Path, help="Create-only output JSON")
    args = parser.parse_args(argv)
    try:
        if not (1 <= args.seeds <= 128 and 0 <= args.seed_start < 2**32
                and args.seeds <= 2**32 - args.seed_start
                and 1 <= args.command_limit <= 1500
                and args.seeds * args.command_limit <= 50000):
            parser.error("Invalid bounded seed/command budget")
        if args.cancel_after is not None and not 0 <= args.cancel_after <= args.seeds:
            parser.error("Cancel-after must be between 0 and seeds")
        content_path = args.content or Path(str(files("drawtemp").joinpath(
            "creator_examples/asterion.json")))
        if args.report:
            for source in (content_path, args.baseline):
                if source is not None and args.report.resolve() == source.resolve():
                    parser.error("Report cannot overwrite the Content JSON or baseline")
            if args.report.exists() or args.report.is_symlink():
                parser.error("Report destination already exists")
        result = {
            "schema": 1, "kind": "r24f-software-scale-and-simulation",
            "renderer_cpu": None, "massive_battle_lab": None,
            "comparison": None,
            "gpu_certified": False, "release_certified": False,
        }
        if args.mode in ("renderer", "both"):
            result["renderer_cpu"] = profile_cpu_renderer(
                sizes=tuple(args.sizes), zooms=tuple(args.zooms),
                actors=args.actors, samples=args.samples)
        if args.mode in ("battle", "both"):
            content = Content.load(content_path)
            job = MassiveSimulationJob(
                content, args.mission,
                seeds=tuple(range(args.seed_start, args.seed_start + args.seeds)),
                max_commands=args.command_limit)
            while not job.finished:
                if args.cancel_after is not None and job.remaining == args.seeds - args.cancel_after:
                    job.cancel()
                    break
                job.step()
            result["massive_battle_lab"] = job.report()
        if args.baseline:
            previous = json.loads(args.baseline.read_text(encoding="utf-8"))
            if previous.get("kind") != result["kind"] or previous.get("schema") != 1:
                raise RuleError("Incompatible R24.F baseline report")
            comparisons = {}
            if result["renderer_cpu"] is not None:
                if previous.get("renderer_cpu") is None:
                    raise RuleError("Baseline lacks renderer CPU measurements")
                comparisons["renderer_cpu"] = compare_cpu_scale(
                    previous["renderer_cpu"], result["renderer_cpu"])
            if result["massive_battle_lab"] is not None:
                if previous.get("massive_battle_lab") is None:
                    raise RuleError("Baseline lacks Battle Lab measurements")
                comparisons["massive_battle_lab"] = compare_massive_runs(
                    previous["massive_battle_lab"], result["massive_battle_lab"])
            result["comparison"] = {
                "passed": all(item["passed"] for item in comparisons.values()),
                "components": comparisons,
            }
        if args.report:
            with args.report.open("x", encoding="utf-8") as target:
                json.dump(result, target, ensure_ascii=False, sort_keys=True, indent=2)
                target.write("\n")
        print(json.dumps({
            "mode": args.mode, "report": str(args.report) if args.report else None,
            "renderer_cases": len(result["renderer_cpu"]["cases"])
                              if result["renderer_cpu"] else 0,
            "seeds_completed": (result["massive_battle_lab"]["completed"]
                                if result["massive_battle_lab"] else 0),
            "status": (result["massive_battle_lab"]["status"]
                       if result["massive_battle_lab"] else "renderer-only"),
            "gpu_certified": False,
            "comparison_passed": (result["comparison"]["passed"]
                                  if result["comparison"] else None),
        }, sort_keys=True))
        if result["massive_battle_lab"] and result["massive_battle_lab"]["status"] == "cancelled":
            return 3
        return 2 if result["comparison"] and not result["comparison"]["passed"] else 0
    except (OSError, ValueError, TypeError, KeyError, RuleError, ScaleProfileError) as exc:
        print("R24.F: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
