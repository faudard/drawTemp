"""R23.F release candidate rehearsal: authored export, relocated Player and NO-GO.

A Python acceptance journey is *not* a native installer, hardware, legal,
signature, accessibility or external-user acceptance certification.
"""
from __future__ import annotations

from hashlib import sha256
import re

from drawtemp.quality.r23c_release import GATES, PLATFORMS

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
JOURNEY_CHECKS = (
    "studio_authoring",
    "content_gameproject_roundtrip",
    "export_integrity",
    "export_relocated",
    "player_story_to_battle",
    "save_and_reopen",
    "replay_state_equal",
    "tamper_rejected",
)


class CandidateError(ValueError):
    pass


def _revision(value):
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise CandidateError("Exact 40-character RC source revision required")
    return value


def verify_journey(record, *, revision, platform):
    """Inspect an actual test report; never treat runtime stub as a native executable."""
    _revision(revision)
    if (type(record) is not dict or set(record) != {
            "schema", "kind", "revision", "platform", "journey",
            "manifest_sha256", "checks", "runtime", "native_gui_qa",
            "signed", "elapsed_seconds"} or
            type(record["schema"]) is not int or record["schema"] != 1 or
            record["kind"] != "drawtemp-r23f-authoring-player" or
            record["revision"] != revision or
            record["platform"] != platform or platform not in PLATFORMS or
            record["journey"] != "real-api-headless-acceptance" or
            record["runtime"] != "synthetic-native-stub" or
            record["native_gui_qa"] != "not-asserted" or
            record["signed"] is not False):
        raise CandidateError("Untrusted, incomplete or overclaimed R23.F journey")
    if (not isinstance(record["manifest_sha256"], str) or
            not _SHA64.fullmatch(record["manifest_sha256"])):
        raise CandidateError("Missing export manifest checksum")
    checks = record["checks"]
    if type(checks) is not dict or set(checks) != set(JOURNEY_CHECKS) or any(
            checks.get(x) != "passed" for x in JOURNEY_CHECKS):
        raise CandidateError("R23.F project creation/export/resume journey is incomplete")
    seconds = record["elapsed_seconds"]
    if type(seconds) not in (int, float) or not 0 < seconds < float("inf"):
        raise CandidateError("Missing measured journey duration")
    return record


def candidate_assessment(*, revision, journeys, r23e, r23b=None):
    """Same Git SHA for complete journeys and licensing/install dossier.

    R23.B is intentionally optional: a missing independent CI workflow's
    evidence cannot be silently treated as green.
    """
    _revision(revision)
    if (type(r23e) is not dict or
            r23e.get("kind") != "drawtemp-r23e-release-dossier" or
            r23e.get("revision") != revision or
            r23e.get("decision") != "NO-GO" or
            r23e.get("certified") is not False or
            set(r23e.get("rights_matrix", {})) != set(PLATFORMS) or
            r23e.get("r23d") != "linked-same-sha"):
        raise CandidateError("R23.E distribution/licensing evidence is missing or stale")
    rows = {}
    for row in journeys:
        if type(row) is not dict:
            raise CandidateError("Malformed R23.F journey row")
        os_name = row.get("platform")
        if os_name not in PLATFORMS or os_name in rows:
            raise CandidateError("Duplicate or unknown R23.F OS journey")
        rows[os_name] = verify_journey(row, revision=revision, platform=os_name)
    if set(rows) != set(PLATFORMS):
        raise CandidateError("Missing R23.F Studio-to-Player OS journey")
    linked_b = "not-provided"
    if r23b is not None:
        if (type(r23b) is not dict or
                r23b.get("kind") != "drawtemp-r23b-assessment" or
                r23b.get("revision") != revision or
                r23b.get("decision") != "NO-GO" or
                r23b.get("release_certified") is not False or
                set(r23b.get("matrix", {})) != set(PLATFORMS)):
            raise CandidateError("R23.B endurance evidence belongs to a different build")
        linked_b = "linked-same-sha"
    gates = {gate: {"status": "blocked", "reason": "Independent approval required"}
             for gate in GATES}
    for gate in ("R23.1", "R23.2", "R23.3", "R23.9", "R23.11"):
        gates[gate] = {
            "status": "partial",
            "reason": "Source-based headless acceptance and upstream preview packaging only"}
    if linked_b == "linked-same-sha":
        gates["R23.6"] = {"status": "partial", "reason": "Headless R23.B endurance only"}
        gates["R23.7"] = {"status": "partial", "reason": "R23.B settings only"}
    gates["R23.10"] = {
        "status": "blocked",
        "reason": "Formal human rights/attribution review absent"}
    gates["R23.12"] = {
        "status": "blocked",
        "reason": "The publishing decision must be independently signed"}
    return {
        "schema": 1, "kind": "drawtemp-r23f-rc-assessment",
        "revision": revision, "candidate": "5.5.0-rc0",
        "journeys": {
            os_name: {"manifest_sha256": rows[os_name]["manifest_sha256"],
                      "elapsed_seconds": rows[os_name]["elapsed_seconds"],
                      "runtime": rows[os_name]["runtime"]}
            for os_name in PLATFORMS
        },
        "upstream": {"R23.E": "linked-same-sha", "R23.B": linked_b},
        "gates": gates,
        "decision": "NO-GO",
        "release_certified": False,
        "candidate_ready_for_publication": False,
        "tag_allowed": False,
        "blockers": [
            "Source-based Player rehearsal uses a stub, not a certified native installer",
            "Signed/notarized installers and trusted publisher identity missing",
            "Asset/dependency rights and external legal attribution signoff missing",
            "Physical offline multi-OS Creator+Player user journeys missing",
            "Real GPU benchmarks, multi-hour soak, accessibility and human retests missing",
            "R23.B independent evidence may not be present on this exact revision",
            "Formal human twelve-gate publication signoff missing",
        ],
    }
