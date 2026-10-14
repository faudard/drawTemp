#!/usr/bin/env python3
"""R5.B headless, non-mutating Campaign Flow QA report."""
import argparse
import json
from pathlib import Path

from sporebound.campaign_flow import audit_campaign, inspect_campaign
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content
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
    parser.add_argument("--require-ending-witnesses", action="store_true",
                        help="Fail when a declared ending has no symbolic witness")
    args = parser.parse_args()
    data = json.loads(args.content.read_text(encoding="utf-8"))
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project = GameProject.load(args.project, content)
    selected = args.campaign or [row["id"] for row in project.campaigns]
    reports = []
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
               "reports": reports}
    write_json(args.report, payload)
    errors = [f'{row["campaign"]}: {error}' for row in reports
              for error in row["errors"]]
    if args.require_ending_witnesses:
        errors.extend(f'{row["campaign"]}: ending {ending} not witnessed'
                      for row in reports
                      for ending in row["unreachable_endings_in_preview"])
    print(json.dumps({"report": str(args.report), "campaigns": selected,
                      "errors": errors}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
