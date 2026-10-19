#!/usr/bin/env python3
"""R29.C: independent action and tactical-router disk replay probes.

Exit 0: evidence collected (still NO-GO); 1: probe failure;
2: required capability unavailable or release not certified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawtemp.quality.r29c_integrated import (
    assemble_evidence, audit_action_disk, audit_route_disk,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--scene", type=Path)
    p.add_argument("--action-commands", type=Path)
    p.add_argument("--route-content", type=Path)
    p.add_argument("--route-project", type=Path)
    p.add_argument("--route-initial", type=Path,
                   help="Authentic canonical GameSession recording")
    p.add_argument("--route-commands", type=Path)
    p.add_argument("--checkpoint-every", type=int, default=2)
    p.add_argument("--revision", default="unknown")
    p.add_argument("--require-action", action="store_true")
    p.add_argument("--require-route", action="store_true")
    p.add_argument("--require-release", action="store_true")
    args = p.parse_args(argv)
    action, routes = None, None
    problem = False
    has_action = args.scene is not None or args.action_commands is not None
    has_route = any(x is not None for x in (
        args.route_content, args.route_project, args.route_initial,
        args.route_commands))
    if has_action:
        try:
            if args.scene is None or args.action_commands is None:
                raise ValueError("Both --scene and --action-commands required")
            action = audit_action_disk(read(args.scene), read(args.action_commands),
                                       checkpoint_every=args.checkpoint_every)
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            action = {"status": "fail", "reason": str(exc),
                      "runtime_verified": False, "release_certified": False}
            problem = True
    if has_route:
        try:
            if any(x is None for x in (args.route_content, args.route_project,
                                       args.route_initial, args.route_commands)):
                raise ValueError("All four --route-* arguments are required")
            from sporebound.model import Content
            from sporebound.game_project import GameProject
            from sporebound.game_session import GameSession
            content = Content.load(args.route_content)
            project = GameProject.load(args.route_project, content)
            session = GameSession.from_recording(read(args.route_initial), content, project)
            routes = audit_route_disk(session, read(args.route_commands),
                                      checkpoint_every=args.checkpoint_every)
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            routes = {"status": "fail", "reason": str(exc),
                      "runtime_verified": False, "release_certified": False}
            problem = True
    report = assemble_evidence(action, routes, revision=args.revision)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                      sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.report), "action": report["action"]["status"],
                      "route": report["tactical_route"]["status"],
                      "hybrid": report["hybrid"]["status"],
                      "decision": report["decision"]}, ensure_ascii=False))
    if problem:
        return 1
    if (args.require_release or
            (args.require_action and report["action"]["status"] != "partial") or
            (args.require_route and report["tactical_route"]["status"] != "partial")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
