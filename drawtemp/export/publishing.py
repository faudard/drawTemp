"""R39.A publication planning over the canonical R15 export, without certification.

Build provenance is a producer declaration bound to bundle bytes, not a signature.
Plans never run binaries or modify bundles and can be generated on any host OS.
"""
from hashlib import sha256
from pathlib import Path
import re

from .r15 import ExportError, preflight, verify_bundle
from .native_identity import inspect_native

PC_TARGETS = {
    "windows-x86_64": ("Windows", "x86_64", "DrawTempPlayer.exe"),
    "linux-x86_64": ("Linux", "x86_64", "DrawTempPlayer"),
    "macos-x86_64": ("macOS", "x86_64", "DrawTempPlayer"),
    "macos-arm64": ("macOS", "arm64", "DrawTempPlayer"),
}
GAME_FAMILIES = ("srpg", "action-adventure", "metroidvania", "roguelite")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 512


def publication_plan(bundle, provenance, *, revision, target, family):
    """Verify immutable export bytes and strict rights, then list outstanding gates.

    Family remains declared intent; header identity does not prove launchability.
    A valid plan is deliberately NO-GO; this API cannot certify a release.
    """
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ExportError("Publication requires an exact 40-character Git revision")
    if not isinstance(target, str) or target not in PC_TARGETS:
        raise ExportError("Unsupported PC target; Web/mobile/consoles require separate ADRs")
    if not isinstance(family, str) or family not in GAME_FAMILIES:
        raise ExportError("Unknown game family")
    fields = {"schema", "kind", "revision", "target", "manifest_sha256", "dependencies"}
    if (type(provenance) is not dict or set(provenance) != fields or
            type(provenance["schema"]) is not int or provenance["schema"] != 1 or
            provenance["kind"] != "drawtemp-r39-build-provenance" or
            provenance["revision"] != revision or provenance["target"] != target):
        raise ExportError("Malformed or mismatched build provenance")
    dependencies = provenance["dependencies"]
    if not isinstance(dependencies, list) or not dependencies or len(dependencies) > 10000:
        raise ExportError("A bounded, nonempty dependency inventory is required")
    names = set()
    for dependency in dependencies:
        if (type(dependency) is not dict or set(dependency) != {"name", "version", "license"} or
                not all(_text(value) for value in dependency.values())):
            raise ExportError("Dependency name, version and license are required")
        name = dependency["name"].strip().casefold()
        if name in names:
            raise ExportError("Duplicate dependency identity")
        names.add(name)
    root = Path(bundle).resolve(strict=True)
    manifest = verify_bundle(root)
    digest = sha256((root / "manifest.json").read_bytes()).hexdigest()
    if provenance["manifest_sha256"] != digest:
        raise ExportError("Build provenance does not match bundle manifest bytes")
    platform, architecture, executable = PC_TARGETS[target]
    if manifest["player"] != "Player/" + executable:
        raise ExportError("Player executable identity does not match publication target")
    identity = inspect_native(root / manifest["player"])
    expected_format = {"Linux": "ELF64", "Windows": "PE32+", "macOS": "Mach-O64"}[platform]
    if identity != {"format": expected_format, "architecture": architecture}:
        raise ExportError("Native Player header does not match publication target")
    rights = preflight(root / manifest["content"], require_licenses=True)
    if not rights["passed"]:
        raise ExportError("Publication preflight failed: " + "; ".join(rights["errors"]))
    # Recheck after preflight so changes during content inspection fail closed.
    verify_bundle(root)
    if sha256((root / "manifest.json").read_bytes()).hexdigest() != digest:
        raise ExportError("Bundle manifest changed during publication planning")
    return {
        "schema": 1, "kind": "drawtemp-r39-publication-plan",
        "revision": revision, "target": target, "platform": platform,
        "architecture": architecture, "declared_family": family,
        "manifest_sha256": digest, "player": manifest["player"],
        "native_header": identity,
        "files": len(manifest["files"]),
        "dependencies": sorted((dict(row) for row in dependencies),
                               key=lambda row: row["name"].casefold()),
        "checks": {"bundle_integrity": "passed", "asset_rights": "passed",
                   "provenance_binding": "passed", "native_header_identity": "passed"},
        "provenance_authenticity": "not-verified",
        "release_certified": False, "decision": "NO-GO",
        "blockers": [
            "Native runtime launch/ABI compatibility and dependency inventory independently verified",
            "Same-revision builds and clean-machine install/launch on all PC targets",
            "Four game-family Studio-to-Player journeys",
            "Controller, keyboard remapping, focus, accessibility and scaling on hardware",
            "Save migration, corruption recovery, rollback and suspend/resume",
            "GPU performance budgets measured on named hardware",
            "Dependency redistribution review, signing and release approval",
        ],
    }


def build_provenance(bundle, dependencies, *, revision, target):
    """Generate a byte-bound declaration for a built bundle; never infer a Git SHA.

    Callers provide the exact build revision and dependency inventory. Neither
    is authenticated by this function. The same strict publication checks apply.
    """
    root = Path(bundle).resolve(strict=True)
    verify_bundle(root)
    declaration = {
        "schema": 1, "kind": "drawtemp-r39-build-provenance",
        "revision": revision, "target": target,
        "manifest_sha256": sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "dependencies": dependencies,
    }
    plan = publication_plan(root, declaration, revision=revision, target=target, family="srpg")
    declaration["dependencies"] = plan["dependencies"]
    return declaration
