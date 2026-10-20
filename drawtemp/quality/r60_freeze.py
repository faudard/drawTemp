"""R60.A — read-only contract freeze and historical migration preflight.

The current Content/GameProject/GameSession formats remain v1. Product release
numbers (5.x -> 10.x) are NOT document schema versions. This module neither
migrates unknown schemas nor authorizes a 10.0 release.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys

_FROZEN_SDK = {
    "api_version": [1, 0],
    "status": "provisional",
    "content_schema": 1,
    "project_schema": 1,
    "game_session_schema": 1,
}
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_BYTES = 16 * 1024 * 1024
_MAX_PAIRS = 128
_REFERENCE = "docs/drawtemp5/reference-baseline.json"


class FreezeError(ValueError):
    """A version, fixture, path, or migration contract was rejected."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise FreezeError("duplicate_json_key", "Duplicate JSON key: " + key)
        obj[key] = value
    return obj


def _read(root: Path, name: str) -> tuple[bytes, dict]:
    """Read only bounded, regular, non-linked files within the checkout."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise FreezeError("unsafe_path", "A repository-relative POSIX path is required")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or any(p in ("", ".", "..") for p in name.split("/"))
            or relative.as_posix() != name):
        raise FreezeError("unsafe_path", "Path must be canonical and repository-relative")
    location = root / name
    if not location.resolve().is_relative_to(root.resolve()):
        raise FreezeError("unsafe_path", "Fixture is outside the checkout")
    if any(p.is_symlink() for p in (location, *location.parents) if p != root.parent):
        raise FreezeError("unsafe_path", "Linked fixture path is forbidden")
    if not location.is_file() or location.stat().st_size > _MAX_BYTES:
        raise FreezeError("invalid_file", "Missing or oversized fixture: " + name)
    try:
        raw = location.read_bytes()
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except FreezeError:
        raise
    except (UnicodeError, ValueError, OSError) as exc:
        raise FreezeError("invalid_json", "Unreadable fixture: " + name) from exc
    if not isinstance(parsed, dict):
        raise FreezeError("invalid_json", "Expected JSON object: " + name)
    return raw, parsed


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _validate_manifest(root: Path, manifest: str) -> list[dict]:
    _, data = _read(root, manifest)
    if (set(data) != {"schema", "pairs"} or type(data["schema"]) is not int
            or data["schema"] != 1 or not isinstance(data["pairs"], list)
            or len(data["pairs"]) > _MAX_PAIRS):
        raise FreezeError("invalid_manifest", "Expected R60 fixture manifest schema 1")
    seen = set()
    results = []
    for row in data["pairs"]:
        keys = {"id", "content", "project", "content_sha256", "project_sha256"}
        if not isinstance(row, dict) or set(row) != keys:
            raise FreezeError("invalid_pair", "Unknown or missing fixture fields")
        name = row["id"]
        if (not isinstance(name, str) or re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name) is None
                or name in seen):
            raise FreezeError("invalid_pair", "Invalid or duplicate fixture ID")
        seen.add(name)
        content_path = row["content"]
        project_path = row["project"]
        if (not isinstance(content_path, str) or not content_path.endswith(".json")
                or content_path.endswith(".game.json")
                or not isinstance(project_path, str)
                or project_path != content_path[:-5] + ".game.json"):
            raise FreezeError("invalid_pair", "Expected exact Content/GameProject pair")
        expected = (row["content_sha256"], row["project_sha256"])
        if any(not isinstance(x, str) or _DIGEST.fullmatch(x) is None for x in expected):
            raise FreezeError("invalid_digest", "Expected pinned SHA-256 for both documents")
        content_bytes, content = _read(root, content_path)
        project_bytes, project = _read(root, project_path)
        actual = (_hash(content_bytes), _hash(project_bytes))
        if actual != expected:
            raise FreezeError("digest_mismatch", "Historical fixture changed: " + name)
        # Canonical, opt-in v0 envelope handling. No speculative 5.x -> 10.x
        # schema conversion, no disk writes, no imported plugin execution.
        from drawtemp.sdk.content_migration import preview_documents
        try:
            cv, pv, changes, normalized_content, normalized_project = preview_documents(
                content, project)
        except (ValueError, TypeError, KeyError) as exc:
            raise FreezeError("unsupported_schema", "Invalid historical pair: " + name) from exc
        results.append({
            "id": name, "source_versions": [cv, pv],
            "canonical_versions": [
                normalized_content["version"], normalized_project["version"]],
            "proposed_changes": list(changes),
            "strategy": "read_only_v0_envelope_preview" if changes else "canonical_v1_identity",
            "sha256": list(actual), "sources_unchanged": True,
        })
    return results


def build_report(root: Path, revision: str, *, manifest: str | None = None,
                 parity_runner=None) -> dict:
    """Create untrusted *supporting* evidence; never grant release approval.

    Optional parity_runner is injectable for tests. Production uses the real
    R0 save/reload/Jeanne CT parity gate and compares the frozen entire trace.
    """
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        raise FreezeError("invalid_revision", "Full lowercase commit SHA required")
    root = Path(root)
    if not root.is_dir():
        raise FreezeError("invalid_root", "Checkout directory does not exist")

    from drawtemp.sdk import capabilities
    observed = capabilities()
    contract_errors = [
        f"{key}: expected {expected!r}, got {observed.get(key)!r}"
        for key, expected in _FROZEN_SDK.items()
        if observed.get(key) != expected
    ]
    # R60 must not silently change or stabilize the SDK major.
    frozen_ok = not contract_errors
    errors = []
    parity = {"status": "blocked", "trace_steps": 0}
    try:
        _, baseline = _read(root, _REFERENCE)
        if parity_runner is None:
            from drawtemp.sdk.migration import run_gate
            parity_runner = run_gate
        current = parity_runner()
        if current != baseline:
            raise FreezeError("reference_drift", "Jeanne R0 CT/save/replay golden differs")
        parity = {"status": "passed", "trace_steps": len(current["trace"]),
                  "reference_sha256": _hash(json.dumps(
                      baseline, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8"))}
    except (FreezeError, AssertionError, ValueError, OSError, KeyError) as exc:
        errors.append("r0_parity: " + str(exc))

    fixtures = []
    if manifest is not None:
        try:
            fixtures = _validate_manifest(root, manifest)
        except (FreezeError, OSError) as exc:
            errors.append("historical_corpus: " + str(exc))

    blockers = [
        "No independent 10.0 master CI / three-OS native Player certification",
        "No independent GPU, third-party UX, licensing or clean-machine evidence",
        "No R60.B hybrid showcase / R60.C signed release dossier verified",
        "Historical 5.x-to-10.x migration coverage remains incomplete",
    ]
    if manifest is None or not fixtures:
        blockers.append("No verified historical fixture pairs for additional migrations")
    if contract_errors:
        blockers.append("Frozen SDK or document contract drift")
    if errors:
        blockers.append("Headless compatibility or migration preflight failed")

    return {
        "kind": "drawtemp-r60a-freeze-report", "schema": 1,
        "candidate": "10.0", "revision": revision,
        "sdk_snapshot": {key: observed.get(key) for key in _FROZEN_SDK},
        "sdk_contract_frozen": frozen_ok, "contract_errors": contract_errors,
        "r0_reference": parity, "historical_pairs": fixtures,
        "preflight_errors": errors,
        "regressions_passed": frozen_ok and not errors,
        "release_decision": "NO-GO", "release_certified": False,
        "tag_allowed": False, "evidence_only": True, "blockers": blockers,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--revision", required=True)
    parser.add_argument("--fixture-manifest", help="Optional hash-pinned Content/GameProject pairs")
    parser.add_argument("--output", type=Path, help="Output report path; stdout by default")
    parser.add_argument("--enforce-regressions", action="store_true",
                        help="Fail CI on contract/parity errors, never authorize release")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root, args.revision, manifest=args.fixture_manifest)
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            if args.output.is_symlink():
                raise FreezeError("unsafe_output", "Output path must not be a symlink")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
    except (OSError, FreezeError) as exc:
        print("R60.A blocked: " + str(exc), file=sys.stderr)
        return 2
    return 1 if args.enforce_regressions and not report["regressions_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
