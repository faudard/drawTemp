"""R80.A: read-only compatibility and security evidence inventory (NO-GO).

This is *not* a 12.0 certification or a schema migration. Evidence artifacts
are untrusted assertions, even when their bytes match the claimed SHA-256.
The existing SDK/content/session versions are deliberately not renumbered.
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
_MAX_FILE_BYTES = 8 * 1024 * 1024
_MAX_RECORDS = 256
_RECORD_FIELDS = frozenset({"kind", "schema", "revision", "check", "outcome",
                            "artifact", "sha256"})
# Enumerated checks are explicit acceptance obligations, not installed modes.
CHECKS = (
    "sdk_public_api",
    "sdk_abi_change_review",
    "content_v0_to_v1_migration",
    "content_v1_project_v1_roundtrip",
    "unknown_schema_rejection",
    "legacy_jeanne_ct_replay",
    "multi_mode_replay",
    "session_v1_save_restore",
    "session_store_v2_recovery",
    "long_session_fault_recovery",
    "migration_rollback",
    "asset_rights_and_hashes",
    "plugin_fail_closed",
)


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON key: " + name)
        result[name] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number: " + value)


def _read_limited(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing, linked or non-regular file")
    with path.open("rb") as stream:
        data = stream.read(_MAX_FILE_BYTES + 1)
    if len(data) > _MAX_FILE_BYTES:
        raise ValueError("Evidence file exceeds 8 MiB")
    return data


def _safe_artifact(root: Path, name: object) -> Path:
    if type(name) is not str or not name or len(name) > 240 or "\\" in name:
        raise ValueError("Invalid artifact path")
    rel = PurePosixPath(name)
    if (rel.is_absolute() or len(rel.parts) < 2 or rel.parts[0] != "artifacts" or
            any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("Expected safe artifacts/ relative path")
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes evidence directory")
    # Reject symlinked directories too, even when pointing inside the root.
    cursor = path.parent
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("Linked artifact directory")
        cursor = cursor.parent
    return path


def _validate_record(value: object, revision: str, root: Path) -> dict:
    if type(value) is not dict or set(value) != _RECORD_FIELDS:
        raise ValueError("Unknown or missing record fields")
    if value["kind"] != "drawtemp-r80a-compatibility-proof" or type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Unsupported record kind/schema")
    if value["revision"] != revision:
        raise ValueError("Stale or foreign revision")
    if type(value["check"]) is not str or value["check"] not in CHECKS:
        raise ValueError("Unknown compatibility check")
    if type(value["outcome"]) is not str or value["outcome"] not in ("passed", "failed"):
        raise ValueError("Explicit passed/failed outcome required")
    digest = value["sha256"]
    if type(digest) is not str or not _SHA64.fullmatch(digest):
        raise ValueError("Invalid SHA-256 digest")
    artifact = _safe_artifact(root, value["artifact"])
    if sha256(_read_limited(artifact)).hexdigest() != digest:
        raise ValueError("Artifact checksum mismatch")
    return {"check": value["check"], "outcome": value["outcome"],
            "artifact": value["artifact"], "sha256": digest}


def probe_public_sdk() -> dict:
    """Exercise the installed, headless public SDK *without* promoting its ABI.

    This checks the current implementation at audit time, not an archived
    version. Unknown versions/features must continue failing closed.
    """
    from drawtemp.sdk import (SDK_API_STATUS, SDK_API_VERSION, SDKCompatibilityError,
                              capabilities, negotiate_sdk)

    contract = capabilities()
    if (type(contract) is not dict or
            type(contract.get("api_version")) is not list or
            contract["api_version"] != list(SDK_API_VERSION) or
            contract.get("status") != SDK_API_STATUS or
            type(contract.get("features")) is not list or
            not all(type(f) is str for f in contract["features"]) or
            "sdk-negotiation.v1" not in contract["features"]):
        raise ValueError("Public SDK contract is inconsistent")
    selected = negotiate_sdk(SDK_API_VERSION, required_features=("sdk-negotiation.v1",))
    if (selected.get("requested_version") != list(SDK_API_VERSION) or
            selected.get("features") != ["sdk-negotiation.v1"]):
        raise ValueError("SDK self-negotiation failed")
    for version, features in (((SDK_API_VERSION[0] + 1, 0), ()),
                              (SDK_API_VERSION, ("unavailable-r80-feature",))):
        try:
            negotiate_sdk(version, required_features=features)
        except SDKCompatibilityError:
            pass
        else:
            raise ValueError("SDK accepted an incompatible request")
    snapshot = json.dumps(contract, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    return {"api_version": contract["api_version"],
            "api_status": contract["status"],
            "content_schema": contract.get("content_schema"),
            "project_schema": contract.get("project_schema"),
            "game_session_schema": contract.get("game_session_schema"),
            "contract_sha256": sha256(snapshot).hexdigest(),
            "compatible_requests_enforced": True}


def build_audit(revision: str, evidence_dir: Path) -> dict:
    """Inventory bounded untrusted claims and the *current* SDK probe.

    Missing or failed checks, invalid artifacts and absent independent QA are
    permanent blockers. This function cannot authorize a release, even when
    all checks have self-reported success.
    """
    if type(revision) is not str or not _SHA40.fullmatch(revision):
        raise ValueError("Expected exact lowercase 40-character commit SHA")
    root = Path(evidence_dir).absolute()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Unsafe evidence root")
    records_dir = root / "records"
    artifacts_dir = root / "artifacts"
    invalid = []
    records = {}
    if artifacts_dir.is_symlink() or (artifacts_dir.exists() and not artifacts_dir.is_dir()):
        invalid.append({"record": "artifacts", "reason": "Unsafe artifacts directory"})
    if records_dir.is_symlink() or (records_dir.exists() and not records_dir.is_dir()):
        invalid.append({"record": "records", "reason": "Unsafe records directory"})
    elif records_dir.is_dir():
        entries = sorted(records_dir.iterdir())
        if len(entries) > _MAX_RECORDS:
            invalid.append({"record": "records", "reason": "Evidence record count exceeds 256"})
        else:
            for path in entries:
                if path.suffix != ".json" or not path.is_file() or path.is_symlink():
                    invalid.append({"record": path.name, "reason": "Unsupported or linked record"})
                    continue
                try:
                    payload = json.loads(_read_limited(path).decode("utf-8"),
                                         object_pairs_hook=_unique_object,
                                         parse_constant=_reject_constant)
                    item = _validate_record(payload, revision, root)
                    if item["check"] in records:
                        raise ValueError("Duplicate compatibility check")
                    records[item["check"]] = item
                except (ValueError, OSError, UnicodeError, TypeError, RecursionError) as exc:
                    invalid.append({"record": path.name, "reason": str(exc)})
    try:
        sdk = probe_public_sdk()
        sdk_error = None
    except (ValueError, TypeError, ImportError, AttributeError) as exc:
        sdk = None
        sdk_error = str(exc)
    missing = [item for item in CHECKS if item not in records]
    failed = [item for item in CHECKS if item in records and records[item]["outcome"] == "failed"]
    blockers = [
        "R80.A artifacts are self-reported; independent replay/migration/ABI and security verification is required",
        "R80.B six independent authorable/exportable games are not certified by this audit",
        "R80.C independent three-OS, physical GPU, accessibility, licenses and clean-machine evidence is required",
    ]
    if sdk_error:
        blockers.append("SDK inspection failed: " + sdk_error)
    elif sdk["api_status"] != "stable":
        blockers.append("Public SDK is not marked stable: " + str(sdk["api_status"]))
    if missing:
        blockers.append(f"{len(missing)} R80.A compatibility checks missing")
    if failed:
        blockers.append(f"{len(failed)} R80.A compatibility checks failed")
    if invalid:
        blockers.append(f"{len(invalid)} invalid evidence records")
    return {
        "kind": "drawtemp-r80a-compatibility-audit", "schema": 1,
        "candidate": "12.0", "revision": revision,
        "sdk": sdk, "sdk_error": sdk_error,
        "required_checks": list(CHECKS),
        "reported_checks": [records[key] for key in CHECKS if key in records],
        "missing": missing, "failed": failed, "invalid": invalid,
        "decision": "NO-GO", "release_certified": False,
        "tag_allowed": False, "blockers": blockers,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true",
                        help="Return nonzero while release authorization is absent")
    args = parser.parse_args(argv)
    try:
        result = build_audit(args.revision, args.evidence_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("R80.A audit blocked: " + str(exc), file=sys.stderr)
        return 2
    print(f"R80.A {result['decision']} — "
          f"{len(result['reported_checks'])}/{len(CHECKS)} checks reported; "
          f"{len(result['invalid'])} invalid")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
