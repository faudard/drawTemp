"""R23.A: per-platform native bundle evidence and fail-closed release ledger.

This tool records verifiable hashes from actual checked-out bundles. It does NOT
certify an installer, hardware GPU, accessibility, playtests, signing or legal
rights. R23 remains NO-GO until independently reviewed release evidence exists.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from drawtemp.export.r15 import verify_bundle

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("Linux", "Windows", "macOS")
GATES = tuple(f"R23.{number}" for number in range(1, 13))


def _revision(value: str) -> str:
    if not isinstance(value, str) or not SHA40.fullmatch(value):
        raise ValueError("R23 evidence requires an exact 40-character Git commit SHA")
    return value


def native_evidence(bundle: Path, *, revision: str, platform: str) -> dict:
    """Hash a verified R15 manifest. A CI build is NOT a clean-machine proof."""
    _revision(revision)
    if platform not in PLATFORMS:
        raise ValueError("Unknown R23 target platform")
    root = Path(bundle).resolve(strict=True)
    manifest = verify_bundle(root)
    warnings = manifest.get("license_warnings")
    if not isinstance(warnings, list) or any(not isinstance(x, str) for x in warnings):
        raise ValueError("R15 manifest lacks a valid license-warning ledger")
    return {
        "schema": 1, "kind": "drawtemp-r23-native-evidence",
        "revision": revision, "platform": platform,
        "manifest_sha256": sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "indexed_files": len(manifest["files"]),
        "content": manifest["content"],
        "license_warnings": warnings,
        "integrity": "passed",
        "smoke": "not-asserted",
        "clean_machine": "not-asserted",
        "signing": "not-asserted",
    }


def aggregate(reports: list[dict], *, revision: str) -> dict:
    """Reject mismatched/missing/duplicated OS proofs and never infer release GO."""
    _revision(revision)
    by_platform = {}
    for report in reports:
        if not isinstance(report, dict) or report.get("schema") != 1 or (
                report.get("kind") != "drawtemp-r23-native-evidence"):
            raise ValueError("Invalid R23 native evidence")
        if report.get("revision") != revision:
            raise ValueError("R23 native evidence belongs to a different commit")
        platform = report.get("platform")
        if platform not in PLATFORMS or platform in by_platform:
            raise ValueError("Duplicate or unknown R23 target platform")
        if report.get("integrity") != "passed" or not SHA64.fullmatch(
                str(report.get("manifest_sha256", ""))):
            raise ValueError("Invalid R23 bundle integrity evidence")
        if type(report.get("indexed_files")) is not int or report["indexed_files"] < 3:
            raise ValueError("Invalid R23 bundle file count")
        if not isinstance(report.get("license_warnings"), list) or any(
                not isinstance(v, str) for v in report["license_warnings"]):
            raise ValueError("Invalid R23 license warning ledger")
        # The capture command deliberately cannot assert these external gates.
        for field in ("smoke", "clean_machine", "signing"):
            if report.get(field) != "not-asserted":
                raise ValueError("Unverified R23 external claim: " + field)
        by_platform[platform] = {
            "manifest_sha256": report["manifest_sha256"],
            "indexed_files": report["indexed_files"],
            "license_warnings": report["license_warnings"],
        }
    if set(by_platform) != set(PLATFORMS):
        raise ValueError("Incomplete R23 OS matrix: " +
                         ", ".join(sorted(set(PLATFORMS) - set(by_platform))))
    checks = {
        gate: {"status": "blocked", "detail": "No independent release proof"}
        for gate in GATES
    }
    checks["R23.2"] = {
        "status": "partial",
        "detail": "R15 manifests verified on three OS; portable installation and offline launch still require external evidence",
    }
    checks["R23.11"] = {
        "status": "partial",
        "detail": "Build artifacts checked on the same commit; signed installers, reproducibility and provenance not certified",
    }
    if any(row["license_warnings"] for row in by_platform.values()):
        checks["R23.10"] = {
            "status": "blocked",
            "detail": "At least one native bundle contains unverified redistribution rights",
        }
    return {
        "schema": 1, "kind": "drawtemp-r23-release-ledger",
        "revision": revision, "native_matrix": by_platform,
        "checks": checks, "decision": "NO-GO", "certified": False,
        "explanation": "R23 full release gate requires independent machine, GPU, rights, user and manual sign-off evidence",
    }


def write_report(path: Path, report: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="action", required=True)
    capture = operations.add_parser("native", help="Generate per-OS native-bundle integrity proof")
    capture.add_argument("--bundle", type=Path, required=True)
    capture.add_argument("--platform", choices=PLATFORMS, required=True)
    capture.add_argument("--revision", required=True)
    capture.add_argument("--report", type=Path, required=True)
    summary = operations.add_parser("aggregate", help="Validate three OS proofs and issue NO-GO ledger")
    summary.add_argument("--directory", type=Path, required=True)
    summary.add_argument("--revision", required=True)
    summary.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "native":
            result = native_evidence(args.bundle, revision=args.revision,
                                     platform=args.platform)
        else:
            # Files are named by platform, so one filename cannot mask an
            # accidental duplicate in the aggregate.
            inputs = sorted(args.directory.rglob("r23-native.json"))
            if len(inputs) != len(PLATFORMS):
                raise ValueError("Expected exactly three r23-native.json reports")
            result = aggregate(
                [json.loads(path.read_text(encoding="utf-8")) for path in inputs],
                revision=args.revision)
        write_report(args.report, result)
        print(json.dumps({"result": result.get("decision", "integrity-verified"),
                          "revision": result["revision"]}))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("R23 evidence blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
