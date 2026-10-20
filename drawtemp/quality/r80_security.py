"""R80.A3: Python SDK compatibility baseline and sandboxed adversarial smoke.

The baseline records the exact public names/features exposed by the 2026-10-15
R16 commit. This is Python-level compatibility evidence, NOT a native ABI
audit, security sign-off or release authorization.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from drawtemp.export.safe_inputs import UnsafeSnapshotError, read_regular_snapshot

R16_COMMIT = "7829988c587b7761e2ec07944b343fef59a06943"
R16_SDK_BLOB = "aca6076af2e34e1351829d32d8534bb7c7c7a454"
R16_NAMES = frozenset({
    "SDK_API_VERSION", "SDK_API_STATUS", "SDK_FEATURES", "capabilities",
    "Simulation", "SimulationError", "StateSnapshot", "GameEvent",
    "Transition", "AuthoringSession", "AuthoringError", "AuthoringSnapshot",
    "AuthoringPlan", "AuthoringTransition", "MigrationError",
    "MigrationPreview", "preview_documents", "preview_pair", "commit_pair",
    "ReplayCommand", "ReplayCheckpoint", "ReplayReport", "ReplayError",
    "verify_recording", "verify_sequence", "PlayerSlotStore",
    "SlotError", "SlotInspection",
})
R16_FEATURES = frozenset({
    "simulation.v1", "authoring.v1",
    "migration.v0-envelope-to-v1", "replay.v1", "player-slots.v1",
})


class A3SecurityError(ValueError):
    """Fail-closed security or SDK surface regression."""


def _require(condition, message):
    if not condition:
        raise A3SecurityError(message)


def check_python_sdk():
    """Probe old public imports and negotiation without changing API version."""
    import drawtemp.sdk as sdk
    from drawtemp.sdk.compatibility import SDKCompatibilityError, negotiate_sdk

    current = sdk.capabilities()
    _require(tuple(sdk.SDK_API_VERSION) == (1, 0),
             "R16 API major/minor unexpectedly changed; explicit review required")
    _require(current.get("api_version") == [1, 0], "SDK capability version drift")
    _require(current.get("status") == "provisional",
             "Stable SDK commitment cannot be silently claimed")
    _require(all(current.get(k) == 1 for k in
                 ("content_schema", "project_schema", "game_session_schema")),
             "Historical schema changed")
    _require(R16_FEATURES.issubset(set(current.get("features", []))),
             "Historical features disappeared")
    missing = R16_NAMES - set(sdk.__all__)
    _require(not missing, "R16 public names removed: " + ", ".join(sorted(missing)))
    # Every old public import must remain resolvable (not just named in __all__).
    for name in sorted(R16_NAMES - {
            "SDK_API_VERSION", "SDK_API_STATUS", "SDK_FEATURES", "capabilities"}):
        try:
            value = getattr(sdk, name)
        except (AttributeError, ImportError, RuntimeError) as exc:
            raise A3SecurityError("Historic SDK import fails: " + name) from exc
        _require(callable(value), "Historic SDK symbol is not callable: " + name)
    negotiated = negotiate_sdk((1, 0), required_features=tuple(sorted(R16_FEATURES)))
    _require(set(negotiated["features"]) == R16_FEATURES,
             "Historic feature negotiation failed")
    for version, features in (((2, 0), ()), ((1, 0), ("arbitrary-execution.v1",))):
        try:
            negotiate_sdk(version, required_features=features)
        except SDKCompatibilityError:
            pass
        else:
            raise A3SecurityError("Incompatible SDK request was accepted")
    return {
        "r16_commit": R16_COMMIT, "r16_sdk_git_blob": R16_SDK_BLOB,
        "api_version": [1, 0], "status": current["status"],
        "resolved_r16_symbols": len(R16_NAMES), "preserved_r16_features": sorted(R16_FEATURES),
        "python_surface_compatible": True, "native_abi_verified": False,
    }


def check_inert_import_security():
    """Real R30/R47 validators challenged with invalid inert input only."""
    from drawtemp.export.creator_packs import PackError, _safe_path
    from drawtemp.sdk.modding import ModError, validate_mod_manifest

    refused = []
    for name in ("../escape.png", "/absolute.png", "x\\evil.png",
                 "bad.ps1", "textures/../../escape.png", "C:/windows.png"):
        try:
            _safe_path(name)
        except PackError:
            refused.append(name)
        else:
            raise A3SecurityError("Unsafe pack resource path accepted: " + name)

    document = {
        "schema": 1, "id": "example-mod", "version": "1.0.0",
        "namespace": "org.example.safe",
        "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                     "features": ["modding-declarative.v1"]},
        "permissions": [], "dependencies": [], "resources": [], "extension": None,
        "rights": {"license": "MIT", "origin": "a3 original test",
                   "evidence": "unverified test declaration", "redistributable": False},
    }
    for key, value in (("entrypoint", "steal.py"), ("permissions", ["python.exec"])):
        forged = dict(document)
        forged[key] = value
        try:
            validate_mod_manifest(forged)
        except ModError:
            pass
        else:
            raise A3SecurityError("Executable or elevated mod declaration was accepted")

    with TemporaryDirectory(prefix="drawtemp-r80a3-") as temp:
        root = Path(temp)
        source = root / "data.bin"
        original = b"R80.A3 original inert resource"
        source.write_bytes(original)
        _require(read_regular_snapshot(source, limit=1024) == original,
                 "Regular bounded snapshot diverged")
        try:
            read_regular_snapshot(source, limit=4)
        except UnsafeSnapshotError:
            pass
        else:
            raise A3SecurityError("Oversized snapshot accepted")
        link = root / "alias.bin"
        try:
            link.symlink_to(source)
        except (OSError, NotImplementedError):
            symlink_tested = False
        else:
            symlink_tested = True
            try:
                read_regular_snapshot(link, limit=1024)
            except UnsafeSnapshotError:
                pass
            else:
                raise A3SecurityError("Symlinked input accepted")
        _require(source.read_bytes() == original,
                 "Read-only security checks modified source")
    return {
        "pack_traversal_cases_rejected": len(refused),
        "executable_mod_cases_rejected": 2,
        "bounded_snapshot_checks": 2,
        "symlink_check_executed": symlink_tested,
        "source_modified": False,
        "rights_verified": False, "plugin_code_executed": False,
    }


def run_a3_audit():
    sdk = check_python_sdk()
    security = check_inert_import_security()
    return {
        "kind": "drawtemp-r80a3-sdk-security-evidence", "schema": 1,
        "sdk": sdk, "security": security,
        "result": "passed",
        "decision": "NO-GO", "release_certified": False, "tag_allowed": False,
        "limitations": [
            "Python SDK import compatibility is not native ABI compatibility",
            "Security smoke uses inert local samples, not an exhaustive vulnerability audit",
            "Windows reparse and parent-directory race protections require OS-level controls",
            "External copyright/rightsholder evidence and clean-machine sign-off absent",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_a3_audit()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (A3SecurityError, OSError, ValueError, TypeError) as exc:
        print("R80.A3 audit blocked: " + str(exc), file=sys.stderr)
        return 2
    print("R80.A3 headless smoke passed; release remains NO-GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
