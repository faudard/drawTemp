"""R23.C three-OS external-runner assessment; never equate portable archives to installers."""
from __future__ import annotations

import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PLATFORMS = ("Linux", "Windows", "macOS")
REQUIRED_CHECKS = ("player_title", "player_exploration",
                   "studio_launch", "tamper_rejection", "uninstall")
GATES = tuple("R23." + str(index) for index in range(1, 13))


def aggregate_release(clean_reports, *, revision, r23a=None, r23b=None):
    """Crosscheck evidence, requiring complete OS matrix and matching SHA.

    r23a/r23b are optional summaries from separate workflows. Not supplying
    them leaves gates blocked rather than silently assuming those jobs passed.
    """
    if not isinstance(revision, str) or not _SHA40.fullmatch(revision):
        raise ValueError("R23.C requires exact 40-character commit SHA")
    observed = {}
    for report in clean_reports:
        if (not isinstance(report, dict) or set(report) != {
                "schema", "kind", "revision", "platform", "archive_sha256",
                "runner", "checks", "native_installer", "signing"} or
                type(report["schema"]) is not int or report["schema"] != 1 or
                report["kind"] != "drawtemp-r23c-clean-runner" or
                report["revision"] != revision):
            raise ValueError("Untrusted or mismatched clean-runner report")
        os_name = report["platform"]
        if os_name not in PLATFORMS or os_name in observed:
            raise ValueError("Duplicate or unknown R23.C platform")
        if (not isinstance(report["archive_sha256"], str) or
                not _SHA64.fullmatch(report["archive_sha256"]) or
                report["runner"] != "github-hosted-ephemeral-offscreen" or
                report["native_installer"] != "not-asserted" or
                report["signing"] != "not-asserted"):
            raise ValueError("R23.C external evidence contains unsupported claim")
        checks = report["checks"]
        if (not isinstance(checks, dict) or set(checks) != set(REQUIRED_CHECKS) or
                any(checks[key] != "passed" for key in REQUIRED_CHECKS)):
            raise ValueError("Missing actual clean runner pass")
        observed[os_name] = {
            "archive_sha256": report["archive_sha256"],
            "checks": dict(checks), "runner": report["runner"],
        }
    if set(observed) != set(PLATFORMS):
        raise ValueError("Incomplete R23.C OS matrix: " +
                         ", ".join(sorted(set(PLATFORMS) - set(observed))))
    upstream = {}
    if r23a is not None:
        if (not isinstance(r23a, dict) or
                r23a.get("kind") != "drawtemp-r23-release-ledger" or
                r23a.get("revision") != revision or
                r23a.get("decision") != "NO-GO" or
                r23a.get("certified") is not False or
                set(r23a.get("native_matrix", {})) != set(PLATFORMS)):
            raise ValueError("R23.A ledger does not match release commit/platforms")
        upstream["R23.A"] = "partial-evidence"
    if r23b is not None:
        if (not isinstance(r23b, dict) or
                r23b.get("kind") != "drawtemp-r23b-assessment" or
                r23b.get("revision") != revision or
                r23b.get("decision") != "NO-GO" or
                r23b.get("release_certified") is not False or
                set(r23b.get("matrix", {})) != set(PLATFORMS)):
            raise ValueError("R23.B ledger does not match release commit/platforms")
        upstream["R23.B"] = "partial-evidence"
    checks = {
        gate: {"status": "blocked", "detail": "Independent release proof still required"}
        for gate in GATES
    }
    checks["R23.1"] = {
        "status": "partial",
        "detail": "Portable preview archive installed and removed on fresh CI runners; native OS installer/signature absent",
    }
    checks["R23.2"] = {
        "status": "partial",
        "detail": "Relocated Player smoke and tamper rejection in hosted offscreen CI; external clean physical PC still required",
    }
    checks["R23.11"] = {
        "status": "partial",
        "detail": "Archive SHA-256 and same-revision three-OS checks; no cryptographic publisher signing or reproducibility attestation",
    }
    if r23b is not None:
        checks["R23.6"] = {
            "status": "partial",
            "detail": "R23.B headless soak present; production multi-hour Creator/Player endurance not certified",
        }
        checks["R23.7"] = {
            "status": "partial",
            "detail": "R23.B settings probes; accessibility requires human native-screen audit",
        }
    if r23a is not None:
        checks["R23.4"] = {
            "status": "partial",
            "detail": "R23.A manifest hardening plus R23.C bounded archive extraction; malicious import corpus remains open",
        }
    return {
        "schema": 1, "kind": "drawtemp-r23c-release-assessment",
        "revision": revision, "platform_evidence": observed,
        "upstream": upstream, "checks": checks,
        "decision": "NO-GO", "certified": False,
        "blockers": [
            "Signed/notarized native installers and provenance",
            "User-run clean hardware installation and full offline game flow",
            "Approved redistributable art and attribution",
            "Physical GPU performance and multi-hour endurance",
            "Real keyboard/screen-reader audit, creator/player playtests and retests",
            "Signed human release Go/No-go",
        ],
    }
