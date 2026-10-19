"""R23.D formal assessment for native per-OS installers, signing always unverified."""
from __future__ import annotations

import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("Linux", "Windows", "macOS")
FORMATS = {"Linux": "deb", "Windows": "inno-setup", "macOS": "dmg"}
CHECKS = ("digest", "install", "player_title", "player_exploration",
          "studio_launch", "tamper_rejection", "uninstall")


def native_assessment(reports, *, revision, r23c=None):
    """Only verified CI execution can assert install smoke, never signed release."""
    if not isinstance(revision, str) or not _SHA40.fullmatch(revision):
        raise ValueError("Exact 40-character release revision required")
    matrix = {}
    for report in reports:
        if (type(report) is not dict or
                set(report) != {"schema", "kind", "revision", "platform", "format",
                                "installer_sha256", "signed", "notarized",
                                "runner", "checks"} or
                type(report["schema"]) is not int or report["schema"] != 1 or
                report["kind"] != "drawtemp-r23d-clean-install" or
                report["revision"] != revision):
            raise ValueError("Malformed or mismatched R23.D install report")
        osname = report["platform"]
        if osname not in PLATFORMS or osname in matrix:
            raise ValueError("Unknown or duplicate R23.D platform")
        if (report["format"] != FORMATS[osname] or
                not isinstance(report["installer_sha256"], str) or
                not _SHA64.fullmatch(report["installer_sha256"]) or
                report["signed"] is not False or
                report["notarized"] is not False or
                report["runner"] != "hosted-ephemeral-offscreen"):
            raise ValueError("R23.D cannot claim signed, notarized or real-hardware evidence")
        checks = report["checks"]
        if (type(checks) is not dict or set(checks) != set(CHECKS) or
                any(checks[name] != "passed" for name in CHECKS)):
            raise ValueError("Incomplete native installation/uninstallation smoke")
        matrix[osname] = {
            "format": report["format"], "installer_sha256": report["installer_sha256"],
            "checks": checks,
        }
    if set(matrix) != set(PLATFORMS):
        raise ValueError("Incomplete installer OS matrix: " +
                         ", ".join(sorted(set(PLATFORMS) - set(matrix))))
    upstream = "not-provided"
    if r23c is not None:
        if (type(r23c) is not dict or
                r23c.get("kind") != "drawtemp-r23c-release-assessment" or
                r23c.get("revision") != revision or
                r23c.get("decision") != "NO-GO" or
                r23c.get("certified") is not False or
                set(r23c.get("platform_evidence", {})) != set(PLATFORMS)):
            raise ValueError("R23.C evidence not for the exact build revision")
        upstream = "linked-same-sha"
    return {
        "schema": 1, "kind": "drawtemp-r23d-assessment", "revision": revision,
        "installer_matrix": matrix, "r23c": upstream,
        "gates": {
            "R23.1": {
                "status": "partial",
                "reason": "Native installers smoke-tested in ephemeral CI; no real clean physical machine, signing, or supported OS matrix",
            },
            "R23.2": {
                "status": "partial",
                "reason": "Native Player title/exploration smoke only; user journey and hardware not validated",
            },
            "R23.10": {
                "status": "blocked",
                "reason": "Redistribution license/attribution signoff missing",
            },
            "R23.11": {
                "status": "partial",
                "reason": "Installer archive hashes and CI outcomes; publisher signing, Apple notarization and verified reproducible provenance absent",
            },
            "R23.12": {
                "status": "blocked",
                "reason": "Release board signoff required after all R23 requirements are satisfied",
            },
        },
        "release_certified": False, "decision": "NO-GO",
        "blockers": [
            "Windows Authenticode publisher signature",
            "Apple Developer ID signing and notarization / Gatekeeper",
            "Linux repository signing and distribution provenance",
            "Offline clean-PC installation with full Player+Studio journeys",
            "Asset redistribution and dependency licenses",
            "Hardware endurance, GPU performance, accessibility and external playtests",
            "Release-board Go/No-go signoff",
        ],
    }
