#!/usr/bin/env python3
"""Certify planned campaign routes using real tactical commands and disk replay.

Example:
python scripts/certify_campaign_paths.py --content game.json --project game.game.json \
    --plans route_cases.json --report certificate.json --require-all-endings

No real save slot is read or written. Missing, failed or unplayed routes are
reported as such; the command returns nonzero and never reports certification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.campaign_path_certification import (certificate_coverage,
                                                     certify_path)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError, require
from sporebound.storage import write_json
from sporebound.tactical_rpg3 import authored_rules_for_document


def run(content, project, rules, suite, *, max_commands=1600,
        checkpoint_every=7, require_all_endings=False):
    require(isinstance(suite, dict) and set(suite) == {"version", "cases"}
            and type(suite["version"]) is int and suite["version"] == 1
            and isinstance(suite["cases"], list)
            and 1 <= len(suite["cases"]) <= 100,
            "Invalid campaign path certification suite")
    require(all(isinstance(case, dict) and isinstance(case.get("id"), str)
                for case in suite["cases"]),
            "All certification plans need stable IDs")
    ids = [case["id"] for case in suite["cases"]]
    require(len(set(ids)) == len(ids),
            "Duplicate certification case ID")
    results = []
    for plan in suite["cases"]:
        try:
            results.append(certify_path(
                content, project, plan, rules=rules,
                checkpoint_every=checkpoint_every,
                max_commands=max_commands))
        except (RuleError, ValueError, TypeError, KeyError, OverflowError,
                AttributeError) as exc:
            results.append({"id": plan["id"], "campaign": plan.get("campaign"),
                            "status": "FAILED", "error": str(exc),
                            "scope": "No certificate emitted; real route failed or was invalid"})
    coverage = certificate_coverage(project, results, required_ids=ids)
    passed = not coverage["required_paths_missing"] and (
        not require_all_endings or coverage["complete_for_declared_endings"])
    return {"format": "campaign-path-certification-suite-r515",
            "version": 1,
            "verified": passed,
            "cases": results,
            "coverage": coverage,
            "policy": {"require_all_endings": require_all_endings,
                       "max_commands": max_commands,
                       "checkpoint_every": checkpoint_every,
                       "evidence": "real GameSession/Battle replay and disk checkpoint parity"}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-commands", type=int, default=1600)
    parser.add_argument("--checkpoint-every", type=int, default=7)
    parser.add_argument("--require-all-endings", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(args.content.read_text(encoding="utf-8"))
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project = GameProject.load(args.project, content)
    suite = json.loads(args.plans.read_text(encoding="utf-8"))
    report = run(content, project, rules, suite,
                 max_commands=args.max_commands,
                 checkpoint_every=args.checkpoint_every,
                 require_all_endings=args.require_all_endings)
    write_json(args.report, report)
    failures = [item for item in report["cases"] if item["status"] != "CERTIFIED"]
    print(json.dumps({
        "verified": report["verified"],
        "report": str(args.report),
        "certified": len(report["cases"]) - len(failures),
        "failed": [{"id": r["id"], "error": r["error"]} for r in failures],
        "uncertified_endings": report["coverage"]["uncertified_endings"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
