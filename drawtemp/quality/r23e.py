"""R23.E exact-file redistribution inventory and conservative release dossier.

An asset-licenses.json string is a *declaration*, NOT permission from the
rights holder. Neither human approvals nor trust in signatures can be inferred
from CI, hashes, vendor names, or test fixtures.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

from drawtemp.export.r15 import preflight, verify_bundle
from drawtemp.quality.r23c_release import GATES
from drawtemp.quality.r23d_release import PLATFORMS

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_DOC_BYTES = 8 * 1024 * 1024


class EvidenceError(ValueError):
    pass


def _sha(path):
    h = sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _revision(value):
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise EvidenceError("Exact 40-hex release revision required")
    return value


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_DOC_BYTES:
        raise EvidenceError("Missing, symlinked or unbounded evidence JSON")
    def distinct(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise EvidenceError("Duplicate JSON key: " + key)
            obj[key] = value
        return obj
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=distinct)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("Malformed evidence JSON") from exc


def asset_inventory(bundle, *, revision, platform):
    """Use the actual checked R15 asset manifest and associated content.

    Paths are rooted at the exported game directory, not the repo checkout.
    Return factual checksums/declarations, NEVER 'legal clearance'.
    """
    _revision(revision)
    if platform not in PLATFORMS:
        raise EvidenceError("Unknown distribution platform")
    root = Path(bundle).resolve(strict=True)
    manifest = verify_bundle(root)
    content = root / manifest["content"]
    report = preflight(content, require_licenses=False)
    if not report["passed"]:
        raise EvidenceError("Bundled Content/GameProject preflight fails: " +
                            "; ".join(report["errors"]))
    declared_path = content.parent / "asset-licenses.json"
    declared = _json(declared_path) if declared_path.exists() else None
    if declared is not None and type(declared) is not dict:
        raise EvidenceError("Invalid asset-licenses.json structure")
    # R17.E uses a structured attestation contract. Legacy flat-string
    # indexes are not legal authorization and are recorded as claims only.
    if declared is not None and set(declared) == {"schema", "assets"}:
        if type(declared["schema"]) is not int or declared["schema"] != 1 or (
                type(declared["assets"]) is not dict):
            raise EvidenceError("Invalid R17.E structured rights index")
        rights = declared["assets"]
        if any(type(path) is not str or type(entry) is not dict
               for path, entry in rights.items()):
            raise EvidenceError("Invalid structured asset rights entry")
        claims = {key: entry.get("license_id") for key, entry in rights.items()}
    else:
        claims = declared or {}
        if any(type(path) is not str or type(value) is not str
               for path, value in claims.items()):
            raise EvidenceError("Invalid legacy asset license declarations")
    checked_files = {row["path"]: row["sha256"] for row in manifest["files"]}
    rows = []
    for relative in sorted(set(report["assets"])):
        indexed = "game/" + relative
        if indexed not in checked_files:
            raise EvidenceError("Asset missing from verified R15 file index: " + relative)
        raw_license = claims.get(relative)
        if raw_license is not None and type(raw_license) is not str:
            raise EvidenceError("Invalid rights license declaration: " + relative)
        license_info = raw_license.strip() if raw_license is not None else ""
        rows.append({
            "path": indexed,
            "sha256": checked_files[indexed],
            "license_declaration": license_info or None,
            "declaration_present": bool(license_info),
            "rights_holder_approved": "not-asserted",
            "attribution_approved": "not-asserted",
        })
    if declared is not None:
        surplus = set(claims) - set(report["assets"])
        if surplus:
            raise EvidenceError("Undeclared/non-exported asset license entries: " +
                                ", ".join(sorted(surplus)[:5]))
    warnings = manifest.get("license_warnings")
    if not isinstance(warnings, list) or any(type(x) is not str for x in warnings):
        raise EvidenceError("Invalid R15 license-warning manifest")
    return {
        "schema": 1, "kind": "drawtemp-r23e-asset-inventory",
        "revision": revision, "platform": platform,
        "manifest_sha256": _sha(root / "manifest.json"),
        "assets": rows,
        "license_warnings": warnings,
        "packaged_notices": declared_path.is_file(),
        "evidence_kind": "machine-inventory-not-legal-approval",
        "legal_status": "blocked-pending-human-rights-review",
    }


def verify_asset_inventory(inventory, *, revision, platform):
    """Conservative input check for inventories consumed outside a build job."""
    _revision(revision)
    if (type(inventory) is not dict or
            set(inventory) != {"schema", "kind", "revision", "platform",
                               "manifest_sha256", "assets", "license_warnings",
                               "packaged_notices", "evidence_kind", "legal_status"} or
            inventory["schema"] != 1 or
            inventory["kind"] != "drawtemp-r23e-asset-inventory" or
            inventory["revision"] != revision or inventory["platform"] != platform or
            inventory["evidence_kind"] != "machine-inventory-not-legal-approval" or
            inventory["legal_status"] != "blocked-pending-human-rights-review"):
        raise EvidenceError("Invalid, mismatched or overclaimed asset inventory")
    digest = inventory["manifest_sha256"]
    if not isinstance(digest, str) or not _SHA64.fullmatch(digest):
        raise EvidenceError("Invalid R15 hash in asset inventory")
    if (type(inventory["assets"]) is not list or
            type(inventory["license_warnings"]) is not list or
            any(type(x) is not str for x in inventory["license_warnings"]) or
            type(inventory["packaged_notices"]) is not bool):
        raise EvidenceError("Invalid asset or license warning rows")
    seen = set()
    for item in inventory["assets"]:
        if type(item) is not dict or set(item) != {
                "path", "sha256", "license_declaration", "declaration_present",
                "rights_holder_approved", "attribution_approved"}:
            raise EvidenceError("Malformed license review record")
        path = item["path"]
        if (type(path) is not str or not path.startswith("game/") or
                path in seen or ".." in path.split("/") or "\\" in path or
                type(item["sha256"]) is not str or
                not _SHA64.fullmatch(item["sha256"])):
            raise EvidenceError("Unsafe/duplicated asset review path")
        seen.add(path)
        v = item["license_declaration"]
        if (v is not None and (type(v) is not str or not v.strip())) or (
                item["declaration_present"] is not bool(v)):
            raise EvidenceError("Contradictory rights declaration")
        if (item["rights_holder_approved"] != "not-asserted" or
                item["attribution_approved"] != "not-asserted"):
            raise EvidenceError("Automated asset inventory cannot assert legal approval")
    return inventory


def validate_external_evidence(evidence, *, revision):
    """External signoff descriptions cannot change certification status via input.

    The artifact's SHA, platform and evidence category are checked. Its
    existence is recorded as a *submission*, not an accepted certification.
    """
    _revision(revision)
    allowed = {"offline_native_qa", "license_counsel_review", "accessibility_review",
               "human_playtest_retests", "hardware_performance", "long_session"}
    if type(evidence) is not list or len(evidence) > 100:
        raise EvidenceError("Malformed external evidence list")
    unique = set()
    submissions = []
    for row in evidence:
        if type(row) is not dict or set(row) != {
                "kind", "revision", "platform", "sha256", "reference", "status"}:
            raise EvidenceError("Malformed external evidence submission")
        if (row["kind"] not in allowed or row["revision"] != revision or
                row["platform"] not in PLATFORMS or
                type(row["sha256"]) is not str or
                not _SHA64.fullmatch(row["sha256"]) or
                type(row["reference"]) is not str or not 1 <= len(row["reference"]) <= 256 or
                "\n" in row["reference"] or "\r" in row["reference"] or
                row["status"] != "submitted-unreviewed"):
            raise EvidenceError("Unreviewed external evidence cannot claim a pass")
        key = (row["kind"], row["platform"], row["sha256"])
        if key in unique:
            raise EvidenceError("Duplicate external evidence")
        unique.add(key)
        submissions.append({**row})
    return submissions


def release_dossier(*, revision, r23d, inventories, external=()):
    """Form an immutable-input NO-GO packet, not a self-service GO button."""
    _revision(revision)
    if (type(r23d) is not dict or
            r23d.get("kind") != "drawtemp-r23d-assessment" or
            r23d.get("revision") != revision or
            r23d.get("decision") != "NO-GO" or
            r23d.get("release_certified") is not False or
            set(r23d.get("installer_matrix", {})) != set(PLATFORMS)):
        raise EvidenceError("R23.D native installer matrix is absent or stale")
    indexed = {}
    for row in inventories:
        if type(row) is not dict:
            raise EvidenceError("Malformed rights inventory")
        platform = row.get("platform")
        if platform not in PLATFORMS or platform in indexed:
            raise EvidenceError("Duplicate or unknown rights inventory platform")
        indexed[platform] = verify_asset_inventory(
            row, revision=revision, platform=platform)
    if set(indexed) != set(PLATFORMS):
        raise EvidenceError("Missing same-revision three-OS asset inventories")
    declarations = {
        plat: {"asset_count": len(doc["assets"]),
               "missing_declarations": sum(
                   not item["declaration_present"] for item in doc["assets"]),
               "warnings": doc["license_warnings"],
               "manifest_sha256": doc["manifest_sha256"],
               "rights_review": "required",
               "notice_review": "required"}
        for plat, doc in sorted(indexed.items())
    }
    received = validate_external_evidence(external, revision=revision)
    checks = {gate: {"status": "blocked", "evidence": "independent signoff required"}
              for gate in GATES}
    for gate in ("R23.1", "R23.2", "R23.11"):
        checks[gate] = {
            "status": "partial", "evidence": "R23.D isolated native installer test only"}
    checks["R23.10"] = {
        "status": "blocked",
        "evidence": "Checksummed asset declarations, not independent rights/attribution approval"}
    checks["R23.12"] = {
        "status": "blocked",
        "evidence": "All twelve gates require reviewed and signed Go/No-go board decision"}
    return {
        "schema": 1, "kind": "drawtemp-r23e-release-dossier",
        "revision": revision, "r23d": "linked-same-sha",
        "rights_matrix": declarations, "external_submissions": received,
        "checks": checks, "decision": "NO-GO", "certified": False,
        "blockers": [
            "Real authorized publisher signatures and Apple notarization",
            "Verified package provenance and independently pinned trust",
            "Approved artwork/font/music/dependency redistribution rights",
            "Offline real-hardware Studio and Player installer journeys",
            "Measured performance/endurance and accessible UI walkthroughs",
            "Human creator/player playtests, fixes and retests",
            "Independent and explicit release committee signoff",
        ],
    }
