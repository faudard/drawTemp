"""R68.A evidence inventory for alternative Player platforms.

Research-only: never upgrades a mobile/Web platform to a supported release.
No Qt import, cross-compilation, packaging or hardware certification is performed.
"""
from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re

SCHEMA = 1
KIND = "drawtemp-r68-probe-evidence"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_PROOF_BYTES = 4 * 1024 * 1024

REQUIREMENTS = {
    "android": (
        "build", "install", "launch", "touch", "suspend_resume",
        "save_replay", "gpu_budget", "accessibility", "license_review",
    ),
    "ios": (
        "build", "signing_distribution", "install", "launch", "touch",
        "suspend_resume", "save_replay", "gpu_budget", "accessibility",
        "license_review",
    ),
    "web": (
        "python_runtime", "browser_launch", "touch_keyboard",
        "visibility_resume", "storage", "webgl_perf", "accessibility",
        "license_review",
    ),
}
ENVIRONMENTS = {"android": "physical-device", "ios": "physical-device",
                "web": "real-browser-on-physical-hardware"}
SOURCES = (
    "pyproject.toml",
    "drawtemp/player/qt_app.py",
    "drawtemp/player/action_app.py",
    "drawtemp/export/publication_matrix.py",
)


class EvidenceError(ValueError):
    """Evidence is malformed, inconsistent or not independently hash-verifiable."""


def _unique_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise EvidenceError("Duplicate JSON key: " + key)
        data[key] = value
    return data


def _hex(value, pattern):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _proof(root, relative, expected_hash):
    if (not isinstance(relative, str) or not relative or
            "\\" in relative or relative.startswith("/") or
            any(x in ("", ".", "..") for x in relative.split("/")) or
            ":" in relative or not _hex(expected_hash, SHA64)):
        raise EvidenceError("Unsafe or invalid evidence artifact")
    base = Path(root).resolve(strict=True)
    candidate = base
    for segment in relative.split("/"):
        candidate = candidate / segment
        if candidate.is_symlink():
            raise EvidenceError("Evidence artifact uses a symlink")
    if not candidate.resolve().is_relative_to(base) or not candidate.is_file():
        raise EvidenceError("Evidence artifact missing or outside dossier")
    if candidate.stat().st_size > MAX_PROOF_BYTES:
        raise EvidenceError("Evidence artifact exceeds size limit")
    if sha256(candidate.read_bytes()).hexdigest() != expected_hash:
        raise EvidenceError("Evidence artifact SHA-256 mismatch")
    return relative


def load_evidence(path, revision):
    """Check declared evidence integrity, not the truth of test attestations."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_PROOF_BYTES:
            raise EvidenceError("Evidence manifest exceeds size limit")
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("Unreadable evidence manifest") from exc
    if (type(data) is not dict or
            set(data) != {"schema", "kind", "revision", "target", "environment", "checks"} or
            type(data["schema"]) is not int or data["schema"] != SCHEMA or
            data["kind"] != KIND or data["revision"] != revision or
            data["target"] not in REQUIREMENTS or
            data["environment"] != ENVIRONMENTS[data["target"]] or
            type(data["checks"]) is not dict):
        raise EvidenceError("Malformed or inconsistent R68 manifest")
    target = data["target"]
    if set(data["checks"]) - set(REQUIREMENTS[target]):
        raise EvidenceError("Unknown platform checks")
    verified = []
    artifacts = set()
    for check, item in data["checks"].items():
        if (type(item) is not dict or set(item) != {"status", "artifact", "sha256"} or
                item["status"] != "passed"):
            raise EvidenceError("Non-passing or malformed evidence check")
        artifact = _proof(path.parent, item["artifact"], item["sha256"])
        if artifact in artifacts:
            raise EvidenceError("Reused evidence artifact for independent checks")
        artifacts.add(artifact)
        verified.append(check)
    return target, tuple(sorted(verified))


def _qt_imports(text):
    """Detect direct Qt imports anywhere in source, including inside functions."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise EvidenceError("Invalid Python source during R68 audit") from exc
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names if a.name.startswith("PySide6"))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("PySide6"):
            modules.add(node.module)
    return sorted(modules)


def source_inventory(root):
    """Exact source-file fingerprints; an inventory, not a platform build."""
    root = Path(root)
    inventory = {}
    missing = []
    for relative in SOURCES:
        file = root / relative
        if not file.is_file():
            missing.append(relative)
            continue
        raw = file.read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise EvidenceError("Oversized audited source: " + relative)
        inventory[relative] = {"sha256": sha256(raw).hexdigest()}
        if relative.startswith("drawtemp/player/"):
            inventory[relative]["qt_imports"] = _qt_imports(raw.decode("utf-8"))
    if "pyproject.toml" in inventory:
        raw = (root / "pyproject.toml").read_text(encoding="utf-8")
        inventory["pyproject.toml"]["pyside6_683_python312_only"] = (
            "PySide6==6.8.3; python_version == '3.12'" in raw
        )
    return inventory, missing


def build_report(root, *, revision=None, evidence=()):
    """Fail closed: even complete checked artifacts require external human review."""
    if revision is not None and not _hex(revision, SHA40):
        raise EvidenceError("A revision must be a full lowercase Git SHA")
    if evidence and revision is None:
        raise EvidenceError("Evidence requires a pinned revision")
    inventory, missing_source = source_inventory(root)
    attestations = {}
    for path in evidence:
        target, verified = load_evidence(path, revision)
        if target in attestations:
            raise EvidenceError("Duplicate platform evidence dossier")
        attestations[target] = verified
    platforms = {}
    for target, required in REQUIREMENTS.items():
        verified = set(attestations.get(target, ()))
        missing = sorted(set(required) - verified)
        complete = not missing and not missing_source and revision is not None
        platforms[target] = {
            "environment_required": ENVIRONMENTS[target],
            "verified_artifact_checks": sorted(verified),
            "missing_checks": missing,
            "evidence_complete_for_manual_review": complete,
            "decision": "MANUAL_REVIEW_REQUIRED" if complete else "NO-GO",
            "player_supported": False,
            "release_certified": False,
        }
    return {
        "schema": SCHEMA,
        "kind": "drawtemp-r68-source-feasibility",
        "revision": revision,
        "scope": "research-only; source hashes and local artifact integrity, not device results",
        "source_inventory": inventory,
        "missing_sources": missing_source,
        "platforms": platforms,
        "pc_reference_unchanged": True,
        "release_certified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--revision", help="Full Git commit SHA for evidence comparison")
    parser.add_argument("--evidence", type=Path, action="append", default=[],
                        help="External evidence manifest (repeat per platform)")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root, revision=args.revision,
                              evidence=args.evidence)
    except (EvidenceError, OSError, UnicodeError) as exc:
        parser.exit(2, "R68 audit refused: " + str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
