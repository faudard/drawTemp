#!/usr/bin/env python3
"""R5.B headless, non-mutating Campaign Flow QA report."""
import argparse
import json
from pathlib import Path

from sporebound.campaign_flow import (audit_campaign, inspect_campaign,
                                     check_campaign_save)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.storage import write_json
from sporebound.tactical_rpg3 import authored_rules_for_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--campaign", action="append",
                        help="Only selected campaign ids (default: all)")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-states", type=int, default=384)
    parser.add_argument("--save-campaign", help="Campaign ID expected for save verification")
    parser.add_argument("--check-slot", type=Path, action="append", default=[],
                        help="Read-only check of a legacy Campaign v1 slot")
    parser.add_argument("--check-session", type=Path, action="append", default=[],
                        help="Read-only check of a unified session checkpoint")
    parser.add_argument("--require-ending-witnesses", action="store_true",
                        help="Fail when a declared ending has no symbolic witness")
    args = parser.parse_args()
    data = json.loads(args.content.read_text(encoding="utf-8"))
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project = GameProject.load(args.project, content)
    selected = args.campaign or [row["id"] for row in project.campaigns]
    reports = []
    save_checks = []
    if args.check_slot or args.check_session:
        if not args.save_campaign:
            parser.error("--save-campaign is required when checking save files")
        if args.save_campaign not in selected:
            parser.error("--save-campaign must be among the selected campaigns")
    for kind, paths in (("slot", args.check_slot), ("session", args.check_session)):
        for path in paths:
            try:
                save_checks.append(check_campaign_save(
                    path, content, project, args.save_campaign,
                    kind=kind, rules=rules))
            except (RuleError, OSError, UnicodeError, ValueError,
                    TypeError, KeyError, AttributeError) as exc:
                save_checks.append({"path": str(path), "kind": kind,
                                    "campaign": args.save_campaign,
                                    "compatible": False, "error": str(exc)})
    for cid in selected:
        report = audit_campaign(content, project, cid, max_states=args.max_states)
        # Generate a genuine session with the authored rules and roundtrip the
        # campaign-only checkpoint. Do not invent tactical victories in a QA gate.
        session = GameSession.new(content, project, cid, rules=rules)
        rebuilt = GameSession.from_recording(session.recording(), content, project, rules=rules)
        assert rebuilt.recording() == session.recording()
        report["initial_inspector"] = inspect_campaign(session.progress, project.campaign_flow)
        report["initial_session_replay"] = "PASS"
        reports.append(report)
    payload = {"format": "campaign-flow-r5b-qa", "version": 1,
               "reports": reports, "save_checks": save_checks}
    write_json(args.report, payload)
    errors = [f'{row["campaign"]}: {error}' for row in reports
              for error in row["errors"]]
    errors.extend(f'{row["kind"]}: {row["path"]}: {row["error"]}'
                  for row in save_checks if not row["compatible"])
    if args.require_ending_witnesses:
        errors.extend(f'{row["campaign"]}: ending {ending} not witnessed'
                      for row in reports
                      for ending in row["unreachable_endings_in_preview"])
    print(json.dumps({"report": str(args.report), "campaigns": selected,
                      "errors": errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
