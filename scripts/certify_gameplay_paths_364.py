#!/usr/bin/env python3
"""3.6.4: fail-closed, reproducible GameSession narrative route CI gate."""
import argparse
import json
from pathlib import Path
import sys

# CLI can be invoked by filename from any working directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sporebound.game_project import GameProject
from sporebound.gameplay_certification_364 import (
    certify_gameplay_paths, enforce_certification, format_certification)
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


def run(argv=None):
    parser = argparse.ArgumentParser(
        description='Replay-verified GameSession path coverage gate')
    parser.add_argument('--content', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--baseline', type=Path,
                        help='Previously approved semantic_baseline JSON')
    parser.add_argument('--report', type=Path,
                        help='Write full report even if gate fails')
    parser.add_argument('--write-baseline', type=Path,
                        help='Write a baseline only when the gate passes')
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.content.read_text(encoding='utf-8'))
        content = Content.from_dict(
            raw, rules=authored_rules_for_document(raw))
        project = GameProject.load(args.project, content)
        suite = json.loads(args.suite.read_text(encoding='utf-8'))
        baseline = (json.loads(args.baseline.read_text(encoding='utf-8'))
                    if args.baseline else None)
        report = certify_gameplay_paths(raw, project, suite, baseline=baseline)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(
                report, indent=2, ensure_ascii=False, sort_keys=True)+'\n',
                encoding='utf-8')
        print('\n'.join(format_certification(report)))
        enforce_certification(report)
        if args.write_baseline:
            args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
            args.write_baseline.write_text(json.dumps(
                report['semantic_baseline'], indent=2,
                ensure_ascii=False, sort_keys=True)+'\n', encoding='utf-8')
        return 0
    except (RuleError, ValueError, KeyError, OSError, TypeError) as exc:
        print('GAMESESSION PATH GATE FAILED: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(run())
