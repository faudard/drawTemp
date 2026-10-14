"""R5.15 reproducible real-path evidence for both castle endings.

python -m examples.campaign_certification_r515 --report campaign-cert.json

This fixture is intentionally tiny, so the gate verifies lifecycle without
claiming that any authored Jeanne d'Arc encounter is already certified.
"""
import argparse
from pathlib import Path

from examples.reliability_gate import fixture
from scripts.certify_campaign_paths import run
from sporebound.model import require
from sporebound.storage import write_json


def build_fixture():
    content, project = fixture()
    project.campaign_flow = {
        "gates": {
            "walls": {"completed_mission": "gate"},
            "throne": {"completed_mission": "walls"},
        },
        "outcomes": {
            "gate": {"victory": [
                {"kind": "add_flag", "flag": "supplies_player", "amount": 2},
                {"kind": "wound", "hero": "captain", "wound": "arm_injury"},
            ]},
            "walls": {"victory": [
                {"kind": "heal_wound", "hero": "captain", "wound": "arm_injury"},
            ]},
        },
        "endings": {
            "mercy": {"flag": "ending", "eq": "mercy"},
            "occupation": {"flag": "ending", "eq": "occupation"},
        },
    }
    project.validate(content)
    return content, project


def suite():
    steps = [
        {"kind": "choice", "id": "assault"},
        {"kind": "mission", "id": "gate", "outcome": "victory"},
        {"kind": "mission", "id": "walls", "outcome": "victory"},
        {"kind": "mission", "id": "throne", "outcome": "victory"},
    ]
    return {"version": 1, "cases": [
        {"id": "castle_mercy", "campaign": "main", "seed": 7,
         "steps": steps + [{"kind": "choice", "id": "spare"}],
         "expect": {"completed": ["gate", "walls", "throne"],
                    "endings": ["mercy"]}},
        {"id": "castle_occupation", "campaign": "main", "seed": 7,
         "steps": steps + [{"kind": "choice", "id": "occupy"}],
         "expect": {"completed": ["gate", "walls", "throne"],
                    "endings": ["occupation"]}},
    ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    content, project = build_fixture()
    result = run(content, project, None, suite(), max_commands=800,
                 checkpoint_every=5, require_all_endings=True)
    write_json(args.report, result)
    require(result["verified"], "R5.15 castle route certification failed")
    require(result["coverage"]["complete_for_declared_endings"],
            "R5.15 castle endings lack actual replay witnesses")
    print("R5.15: certified 2 actual castle endings; report", args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
