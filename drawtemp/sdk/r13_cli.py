"""Headless DrawTemp 5.0 R13 report and regression gate.

Example:
  python -m drawtemp.sdk.r13_cli --content sporebound/content/jeanne.json \\
    --mission <authored-id> --runs 4 --limit 200 --report r13.json
  python -m drawtemp.sdk.r13_cli --content ... --mission ... \\
    --baseline r13.json --report r13-after.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.model import Content, RuleError

from .r13_combat_lab import (
    compare_encounters, evaluate_variant, human_review,
    inspect_encounter, simulate_encounter,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--runs", type=int, default=4)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--trace", action="store_true",
                        help="Include one replay-verified diagnostic timeline")
    parser.add_argument("--variant", type=Path,
                        help="Optional Balance Matrix case edits as JSON")
    parser.add_argument("--human-playtest", type=Path,
                        help="Optional local opt-in human playtest JSON")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    # A report can never replace authored content or the reference used to
    # certify it. This also covers distinct relative spellings of the path.
    if args.report is not None:
        inputs = (args.content, args.baseline, args.variant, args.human_playtest)
        if any(args.report.resolve() == path.resolve()
               for path in inputs if path is not None):
            parser.error("R13 output must not overwrite an input or baseline")
    if not (1 <= args.runs <= 32 and
            0 <= args.seed_start <= 2**32 - args.runs):
        parser.error("Seeds must form a unique unsigned 32-bit range of 1..32")
    if not (1 <= args.limit <= 5000):
        parser.error("Command cap must be between 1 and 5000")
    seeds = tuple(range(args.seed_start, args.seed_start + args.runs))
    try:
        content = Content.load(args.content)
        inspected = inspect_encounter(content, args.mission,
                                      seed=seeds[0])
        current = simulate_encounter(
            content, args.mission, seeds=seeds,
            max_commands=args.limit,
            trace_seed_id=seeds[0] if args.trace else None)
        result = {
            "kind": "r13_evidence", "schema": 1, "mission": args.mission,
            "inspection": inspected, "simulation": current,
            "regression": None, "variant": None, "human": None,
        }
        if args.variant:
            edits = json.loads(args.variant.read_text(encoding="utf-8"))
            result["variant"] = evaluate_variant(
                content, args.mission, edits, seeds=seeds,
                max_commands=args.limit)
        if args.human_playtest:
            result["human"] = human_review(json.loads(
                args.human_playtest.read_text(encoding="utf-8")))
        if args.baseline:
            old = json.loads(args.baseline.read_text(encoding="utf-8"))
            if old.get("kind") == "r13_evidence":
                old = old["simulation"]["battle_lab"]
            elif old.get("kind") == "r13_simulation":
                old = old["battle_lab"]
            result["regression"] = compare_encounters(
                old, current["battle_lab"])
        # Reports are evidence. Explicitly selected export only; never edit
        # Content, GameProject or save slots.
        if args.report:
            args.report.write_text(json.dumps(
                result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8")
        print(json.dumps({
            "mission": args.mission, "seeds": list(seeds),
            "victory_rate": current["battle_lab"]["victory_rate"],
            "replays_verified": all(s["replay_verified"]
                                    for s in current["battle_lab"]["samples"]),
            "regression": result["regression"],
            "report": str(args.report) if args.report else None,
        }, ensure_ascii=False, sort_keys=True))
        return 2 if (result["regression"] is not None
                     and not result["regression"]["passed"]) else 0
    except (OSError, ValueError, TypeError, KeyError, RuleError) as exc:
        parser.exit(1, "R13: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
