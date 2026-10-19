"""R50.A: read-only, fail-closed inventory of release 9.0 evidence.

This module does NOT certify a release. A record is a self-reported test result,
not a trusted CI run, a physical GPU measurement or an independent approval.
R50.C must independently verify provenance and authorize any future release.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("windows", "linux", "macos")
FAMILIES = (
    "srpg", "action_adventure", "classic_rpg",
    "metroidvania", "roguelite", "narrative_hybrid",
)
REQUIREMENTS = ("R40",) + tuple(f"R{i}" for i in range(41, 50)) + (
    tuple(f"R50.{i}" for i in range(1, 11))
)
_FIELDS = frozenset({
    "kind", "schema", "revision", "requirement", "scope",
    "platform", "family", "outcome", "artifact", "sha256",
})
_MAX_BYTES = 8 * 1024 * 1024


def _slot(requirement: str, scope: str, platform: str = "agnostic",
          family: str = "agnostic") -> tuple[str, str, str, str]:
    return requirement, scope, platform, family


def required_evidence() -> tuple[tuple[str, str, str, str], ...]:
    """Explicit matrix; being listed is NOT equivalent to being certified."""
    slots = [_slot(f"R{number}", "upstream_gate") for number in range(40, 50)]
    slots.append(_slot("R50.2", "migration"))
    for family in FAMILIES:
        slots.append(_slot("R50.3", "replay", family=family))
    for family in FAMILIES[:5]:
        slots.append(_slot("R50.4", "template", family=family))
    for family in FAMILIES:
        slots.append(_slot("R50.5", "authoring", family=family))
    for platform in PLATFORMS:
        slots.extend((
            _slot("R50.6", "onscreen", platform),
            _slot("R50.7", "clean_machine", platform),
            _slot("R50.8", "physical_gpu", platform),
        ))
    slots.extend((
        _slot("R50.9", "security"),
        _slot("R50.9", "asset_rights"),
        _slot("R50.10", "human_approval"),
    ))
    return tuple(slots)


def _object_without_duplicate_keys(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("Duplicate JSON object key: " + key)
        record[key] = value
    return record


def _read_limited(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or linked evidence file")
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("Evidence file exceeds 8 MiB")
    return path.read_bytes()


def _validate_record(record: object, revision: str, root: Path,
                     expected: set[tuple[str, str, str, str]]) -> dict:
    if type(record) is not dict or set(record) != _FIELDS:
        raise ValueError("Unknown or missing evidence schema fields")
    if (record["kind"] != "drawtemp-r50-evidence" or
            type(record["schema"]) is not int or record["schema"] != 1):
        raise ValueError("Unknown evidence kind/schema")
    if record["revision"] != revision:
        raise ValueError("Evidence from a different commit")
    slot = _slot(record["requirement"], record["scope"],
                 record["platform"], record["family"])
    if slot not in expected:
        raise ValueError("Unsupported requirement, scope, platform or family")
    if record["outcome"] not in ("passed", "failed"):
        raise ValueError("Evidence must report an explicit outcome")
    name = record["artifact"]
    if not isinstance(name, str) or len(name) > 240 or "\\" in name:
        raise ValueError("Invalid artifact path")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or len(relative.parts) < 2 or
            relative.parts[0] != "artifacts" or
            any(part in (".", "..") for part in name.split("/"))):
        raise ValueError("Artifact must be a safe path below artifacts/")
    digest = record["sha256"]
    if not isinstance(digest, str) or not _SHA64.fullmatch(digest):
        raise ValueError("Invalid artifact digest")
    artifact = root / name
    if not artifact.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escaped evidence directory")
    if sha256(_read_limited(artifact)).hexdigest() != digest:
        raise ValueError("Artifact checksum mismatch")
    return {
        "requirement": slot[0], "scope": slot[1],
        "platform": slot[2], "family": slot[3],
        "outcome": record["outcome"],
        "artifact": name, "sha256": digest,
    }


def build_ledger(revision: str, evidence_dir: Path) -> dict:
    """Return an evidence ledger that cannot authorize or tag a release.

    Malformed, duplicate, stale or tampered rows are explicitly rejected,
    never silently dropped. Missing independent tests remain visible.
    """
    if not isinstance(revision, str) or not _SHA40.fullmatch(revision):
        raise ValueError("Expected the exact 40-character Git commit SHA")
    root = Path(evidence_dir)
    matrix = required_evidence()
    expected = set(matrix)
    collected: dict[tuple[str, str, str, str], dict] = {}
    invalid = []
    records = root / "records"
    if records.exists() and (not records.is_dir() or records.is_symlink()):
        invalid.append({"record": "records", "reason": "Unsafe evidence directory"})
    elif records.is_dir():
        for path in sorted(records.iterdir()):
            if path.suffix != ".json" or not path.is_file() or path.is_symlink():
                invalid.append({"record": path.name, "reason": "Unsupported or linked record"})
                continue
            try:
                raw = _read_limited(path)
                record = json.loads(raw.decode("utf-8"),
                                    object_pairs_hook=_object_without_duplicate_keys)
                item = _validate_record(record, revision, root, expected)
                key = _slot(item["requirement"], item["scope"],
                            item["platform"], item["family"])
                if key in collected:
                    raise ValueError("Duplicate evidence for a matrix slot")
                collected[key] = item
            except (ValueError, OSError, TypeError, UnicodeError) as exc:
                invalid.append({"record": path.name, "reason": str(exc)})
    missing = [
        {"requirement": req, "scope": scope, "platform": platform,
         "family": family}
        for req, scope, platform, family in matrix
        if (req, scope, platform, family) not in collected
    ]
    failures = [item for item in collected.values()
                if item["outcome"] == "failed"]
    rows = {}
    for req in REQUIREMENTS:
        if req == "R50.1":
            rows[req] = {"status": "generated-unapproved", "reported": 0,
                         "required": 0}
            continue
        keys = [key for key in matrix if key[0] == req]
        found = [collected[key] for key in keys if key in collected]
        rows[req] = {
            "status": ("missing" if len(found) != len(keys)
                       else "reported-failure" if any(
                           item["outcome"] == "failed" for item in found)
                       else "reported-unverified"),
            "reported": len(found), "required": len(keys),
        }
    blockers = [
        "R50.A evidence records are not independent certification or release approval",
        "R50.C human/CI/hardware/rights authorization has not been performed",
    ]
    if missing:
        blockers.append(f"{len(missing)} required evidence slots missing")
    if invalid:
        blockers.append(f"{len(invalid)} invalid or tampered evidence records")
    if failures:
        blockers.append(f"{len(failures)} explicitly failed checks")
    return {
        "kind": "drawtemp-r50a-release-ledger",
        "schema": 1,
        "candidate": "9.0",
        "revision": revision,
        "matrix_version": 1,
        "requirements": rows,
        "expected_slots": len(matrix),
        "reported_slots": len(collected),
        "evidence": [collected[key] for key in matrix if key in collected],
        "missing": missing,
        "invalid": invalid,
        "decision": "NO-GO",
        "release_certified": False,
        "tag_allowed": False,
        "blockers": blockers,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true",
                        help="Fail CI whenever the release is not authorized")
    args = parser.parse_args(argv)
    try:
        report = build_ledger(args.revision, args.evidence_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("R50.A ledger blocked: " + str(exc), file=sys.stderr)
        return 2
    print(f"R50.A {report['decision']} — "
          f"{report['reported_slots']}/{report['expected_slots']} evidence slots; "
          f"{len(report['invalid'])} invalid; {len(report['missing'])} missing")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
