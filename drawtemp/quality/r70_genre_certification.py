"""R70.A: deterministic multi-genre regression helpers and fail-closed 11.0 ledger.

All evidence is self-reported until an independent R70.C release review.
This module neither certifies a game nor issues tags; it does not change any
Content/GameProject, GameSession, replay, export or rendering contract.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Callable

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("windows", "linux", "macos")
NEW_GENRES = ("management", "life_sim", "survival_action")
LEGACY_GENRES = ("srpg", "action_adventure")
SEEDS = (0, 1, 42, 65535)
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 500
_FIELDS = frozenset({"kind", "schema", "revision", "requirement", "scope",
                     "platform", "genre", "seed", "outcome", "artifact", "sha256"})


def required_evidence() -> tuple[tuple[str, str, str, str, int], ...]:
    """List every mandatory report slot; R67–R69 are optional studies."""
    slots = [(f"R{n}", "upstream_gate", "agnostic", "agnostic", -1)
             for n in (50, 60, 61, 62, 63, 64, 65, 66)]
    for genre in LEGACY_GENRES:
        for scope in ("schema_migration", "replay", "save_restore"):
            slots.append(("R70.A", scope, "agnostic", genre, -1))
    for genre in NEW_GENRES:
        for scope in ("schema_migration", "no_code_authoring", "save_restore",
                      "export", "simulation_budget", "asset_licenses"):
            slots.append(("R70.B", scope, "agnostic", genre, -1))
        for seed in SEEDS:
            slots.append(("R70.A", "seeded_replay", "agnostic", genre, seed))
    for platform in PLATFORMS:
        for scope in ("ci", "onscreen", "physical_gpu", "clean_machine"):
            slots.append(("R70.C", scope, platform, "agnostic", -1))
    for scope in ("security_review", "qa_review", "human_release_approval"):
        slots.append(("R70.C", scope, "agnostic", "agnostic", -1))
    return tuple(slots)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key: " + key)
        result[key] = value
    return result


def _read_small_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked file")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("File exceeds 8 MiB")
    with path.open("rb") as stream:
        result = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(result) > MAX_ARTIFACT_BYTES:
        raise ValueError("File exceeds 8 MiB")
    return result


def _validate_record(record: object, revision: str, root: Path,
                     expected: set[tuple[str, str, str, str, int]]) -> dict:
    if type(record) is not dict or set(record) != _FIELDS:
        raise ValueError("Unknown or missing evidence fields")
    if record["kind"] != "drawtemp-r70-evidence" or type(record["schema"]) is not int or record["schema"] != 1:
        raise ValueError("Invalid R70 evidence schema")
    if record["revision"] != revision:
        raise ValueError("Evidence from a different commit")
    slot = (record["requirement"], record["scope"], record["platform"],
            record["genre"], record["seed"])
    if any(type(v) is not str for v in slot[:4]) or type(slot[4]) is not int or slot not in expected:
        raise ValueError("Unsupported evidence slot")
    if record["outcome"] not in ("passed", "failed"):
        raise ValueError("Invalid evidence outcome")
    name = record["artifact"]
    if type(name) is not str or len(name) > 240 or "\\" in name:
        raise ValueError("Invalid artifact path")
    rel = PurePosixPath(name)
    if (rel.is_absolute() or len(rel.parts) < 2 or rel.parts[0] != "artifacts"
            or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError("Artifact must be below artifacts/ without traversal")
    digest = record["sha256"]
    if type(digest) is not str or not _SHA64.fullmatch(digest):
        raise ValueError("Invalid checksum")
    artifact = root.joinpath(*rel.parts)
    if any(path.is_symlink() for path in (root, *(root.joinpath(*rel.parts[:i])
                                                 for i in range(1, len(rel.parts) + 1)))):
        raise ValueError("Linked evidence path")
    if not artifact.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escaped evidence root")
    if sha256(_read_small_file(artifact)).hexdigest() != digest:
        raise ValueError("Artifact checksum mismatch")
    return {"requirement": slot[0], "scope": slot[1], "platform": slot[2],
            "genre": slot[3], "seed": slot[4], "outcome": record["outcome"],
            "artifact": name, "sha256": digest}


def build_ledger(revision: str, evidence_dir: Path) -> dict:
    """Inventory attached, checksum-verified claims; never approve a release."""
    if type(revision) is not str or not _SHA40.fullmatch(revision):
        raise ValueError("Use an exact lowercase Git SHA-40")
    root = Path(evidence_dir)
    matrix = required_evidence()
    found: dict[tuple[str, str, str, str, int], dict] = {}
    invalid = []
    directory = root / "records"
    if root.is_symlink() or directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        invalid.append({"record": "records", "reason": "Unsafe records directory"})
    elif directory.is_dir():
        paths = sorted(directory.iterdir())
        if len(paths) > MAX_RECORDS:
            invalid.append({"record": "records", "reason": "Too many evidence records"})
        else:
            for path in paths:
                try:
                    if path.suffix != ".json":
                        raise ValueError("Expected a .json evidence record")
                    record = json.loads(_read_small_file(path).decode("utf-8"),
                                        object_pairs_hook=_unique_keys)
                    item = _validate_record(record, revision, root, set(matrix))
                    slot = (item["requirement"], item["scope"], item["platform"],
                            item["genre"], item["seed"])
                    if slot in found:
                        raise ValueError("Duplicate evidence slot")
                    found[slot] = item
                except (ValueError, OSError, TypeError, UnicodeError) as exc:
                    invalid.append({"record": path.name, "reason": str(exc)})
    missing = [{"requirement": req, "scope": scope, "platform": platform,
                "genre": genre, "seed": seed}
               for req, scope, platform, genre, seed in matrix
               if (req, scope, platform, genre, seed) not in found]
    failures = [item for item in found.values() if item["outcome"] == "failed"]
    blockers = ["Independent R70.C review of provenance, native exports, real GPU and licenses required",
                "Machine-collected evidence does not authorize release tags"]
    if missing:
        blockers.append(f"{len(missing)} required evidence slots missing")
    if invalid:
        blockers.append(f"{len(invalid)} invalid evidence records")
    if failures:
        blockers.append(f"{len(failures)} failing evidence records")
    return {
        "kind": "drawtemp-r70a-evidence-ledger", "schema": 1, "candidate": "11.0",
        "revision": revision, "decision": "NO-GO", "release_certified": False,
        "tag_allowed": False, "independently_verified": False,
        "expected_slots": len(matrix), "reported_slots": len(found),
        "evidence": [found[slot] for slot in matrix if slot in found],
        "missing": missing, "invalid": invalid, "blockers": blockers,
    }


def audit_seeded_replay(execute: Callable[[int], dict], *, seeds=SEEDS,
                        max_agents: int, max_world_cells: int) -> dict:
    """Compare two actual caller-supplied deterministic runs per seed.

    execute(seed) must return tick_digests, restored_digest, peak_agents and
    world_cells. Its provenance remains external; never treat this as GPU or
    release evidence. The same runner should replay the canonical session.
    """
    if (type(max_agents) is not int or max_agents < 1 or
            type(max_world_cells) is not int or max_world_cells < 1):
        raise ValueError("Positive simulation budgets are required")
    if not isinstance(seeds, (tuple, list)) or not 1 <= len(seeds) <= 16 or any(
            type(s) is not int or s < 0 or s > 0xFFFFFFFF for s in seeds
    ) or len(set(seeds)) != len(seeds):
        raise ValueError("Seeds must be unique uint32 values (1..16)")

    def validate(sample):
        if type(sample) is not dict or set(sample) != {"tick_digests", "restored_digest",
                                                       "peak_agents", "world_cells"}:
            raise ValueError("Invalid replay trace shape")
        ticks = sample["tick_digests"]
        if (type(ticks) is not list or not 1 <= len(ticks) <= 20000 or
                any(type(d) is not str or not _SHA64.fullmatch(d) for d in ticks) or
                type(sample["restored_digest"]) is not str or
                not _SHA64.fullmatch(sample["restored_digest"])):
            raise ValueError("Invalid deterministic trace digests")
        if ticks[-1] != sample["restored_digest"]:
            raise ValueError("Disk-restored final state differs from replay")
        if (type(sample["peak_agents"]) is not int or sample["peak_agents"] < 0 or
                sample["peak_agents"] > max_agents or
                type(sample["world_cells"]) is not int or sample["world_cells"] < 0 or
                sample["world_cells"] > max_world_cells):
            raise ValueError("Simulation exceeds agent or world budget")
        return sample

    rows = []
    for seed in seeds:
        first = deepcopy(validate(execute(seed)))
        second = deepcopy(validate(execute(seed)))
        if first != second:
            raise ValueError(f"Non-deterministic replay for seed {seed}")
        transcript = json.dumps(first, sort_keys=True, separators=(",", ":")).encode("utf-8")
        rows.append({"seed": seed, "ticks": len(first["tick_digests"]),
                     "trace_sha256": sha256(transcript).hexdigest(),
                     "peak_agents": first["peak_agents"],
                     "world_cells": first["world_cells"]})
    return {"kind": "drawtemp-r70a-replay-audit", "schema": 1,
            "status": "headless-supporting-evidence", "cases": rows,
            "budgets": {"max_agents": max_agents, "max_world_cells": max_world_cells},
            "release_certified": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true",
                        help="Exit nonzero unless independently certified (currently always NO-GO)")
    args = parser.parse_args(argv)
    try:
        report = build_ledger(args.revision, args.evidence_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                          sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("R70.A audit rejected: " + str(exc), file=sys.stderr)
        return 2
    print(f"R70.A {report['decision']}: {report['reported_slots']}/{report['expected_slots']} "
          f"slots, {len(report['invalid'])} invalid")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
