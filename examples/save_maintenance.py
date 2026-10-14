"""R8.18: command-line inspection and explicit retention for long save slots.

Examples:
  python -m examples.save_maintenance --save slot_1.long.json --inspect
  python -m examples.save_maintenance --save slot_1.long.json --archive
  python -m examples.save_maintenance --save slot_1.long.json --retention-plan --keep 3
  python -m examples.save_maintenance --save slot_1.long.json --apply-retention --keep 3 --token HASH

Commands with side effects require explicit flags. Nothing runs on startup.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.save_maintenance import LongSessionMaintenance
from sporebound.storage import write_json
from sporebound.tactical_rpg3 import authored_rules_for_document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", required=True, type=Path)
    parser.add_argument("--content", type=Path, default=Path(DEFAULT_CONTENT))
    parser.add_argument("--project", type=Path)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--inspect", action="store_true")
    command.add_argument("--archive", action="store_true")
    command.add_argument("--retention-plan", action="store_true")
    command.add_argument("--apply-retention", action="store_true")
    command.add_argument("--temp-plan", action="store_true")
    command.add_argument("--quarantine-temp", action="store_true")
    parser.add_argument("--keep", type=int, default=3)
    parser.add_argument("--min-age-seconds", type=int, default=3600)
    parser.add_argument("--token", help="Explicit acknowledgement of a dry-run plan")
    parser.add_argument("--checkpoint-every", type=int, default=32)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    document = json.loads(args.content.read_text(encoding="utf-8"))
    rules = authored_rules_for_document(document)
    content = Content.from_dict(document, rules=rules)
    project_path = args.project or args.content.with_suffix(".game.json")
    project = (GameProject.load(project_path, content) if project_path.is_file()
               else GameProject.default(content))
    manager = LongSessionMaintenance(
        args.save, content, project, rules=rules,
        checkpoint_every=args.checkpoint_every)

    if args.inspect:
        result = manager.inspect()
    elif args.archive:
        result = manager.archive_verified()
    elif args.retention_plan:
        result = manager.retention_plan(keep=args.keep)
    elif args.apply_retention:
        result = manager.prune_archives(
            keep=args.keep, expected_token=args.token)
    elif args.temp_plan:
        result = manager.temp_plan(min_age_seconds=args.min_age_seconds)
    else:
        result = manager.quarantine_temps(
            min_age_seconds=args.min_age_seconds, expected_token=args.token)

    if args.output is not None:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
