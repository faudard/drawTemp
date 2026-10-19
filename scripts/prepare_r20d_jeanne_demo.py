"""R20.D — prepare a self-contained Jeanne Act I content pair for the Player.

Developer mode stages a valid, paired project and the exact referenced assets.
Native mode invokes the EXISTING R15 exporter and fails closed unless real
native runtime, R14 evidence and asset redistribution-license index exist.
This tool never fabricates native binaries, licenses or certification.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import os
import shutil
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import ExportError, export_game, preflight
from sporebound.game_project import GameProject
from sporebound.model import Content

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.r20c.game.json"
CONTENT_NAME = "jeanne-act1.json"
PROJECT_NAME = "jeanne-act1.game.json"


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def stage_pair(destination, *, license_manifest=None, require_licenses=False):
    """Create a validated, independent, portable pair in an EMPTY directory.

    The caller is responsible for an outer temporary directory: failure never
    corrupts existing user content or a previous published bundle.
    """
    output = Path(destination)
    if not output.is_dir() or any(output.iterdir()):
        raise ExportError("Demo staging directory must exist and be empty")
    content = Content.load(SOURCE)
    project = GameProject.load(PROJECT, content)
    registry = project.asset_registry()
    shutil.copy2(SOURCE, output / CONTENT_NAME)
    shutil.copy2(PROJECT, output / PROJECT_NAME)
    entries = registry.to_dict()["entries"]
    paths = sorted({row["path"] for row in entries if row["kind"] != "animation"})
    for path in paths:
        original = registry.resolve(
            next(row["id"] for row in entries if row.get("path") == path), SOURCE.parent)
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    if license_manifest is not None:
        license_file = Path(license_manifest).resolve(strict=True)
        if not license_file.is_file():
            raise ExportError("License index must be a file")
        shutil.copy2(license_file, output / "asset-licenses.json")
    elif (SOURCE.parent / "asset-licenses.json").is_file():
        shutil.copy2(SOURCE.parent / "asset-licenses.json",
                     output / "asset-licenses.json")
    report = preflight(output / CONTENT_NAME,
                       require_licenses=require_licenses)
    if not report["passed"]:
        raise ExportError("Jeanne demo preflight failed: " +
                          "; ".join(report["errors"]))
    loaded_content = Content.load(output / CONTENT_NAME)
    loaded_project = GameProject.load(output / PROJECT_NAME, loaded_content)
    if loaded_content.to_dict() != content.to_dict() or (
            loaded_project.to_dict() != project.to_dict()):
        raise ExportError("Staged content differs from canonical pair")
    return {"schema": 1, "kind": "r20d-jeanne-staged-pair",
            "content": CONTENT_NAME, "project": PROJECT_NAME,
            "content_sha256": _sha(output / CONTENT_NAME),
            "project_sha256": _sha(output / PROJECT_NAME),
            "assets": [{"path": path, "sha256": _sha(output / path)}
                       for path in paths],
            "preflight_passed": True,
            "license_warnings": report["warnings"],
            "native_runtime_included": False,
            "release_certified": False}


def prepare(output, *, native_runtime=None, r14_report=None,
            license_manifest=None):
    """Create a dev content pair OR an R15 integrity-checked native candidate."""
    output = Path(output).absolute()
    if output.exists():
        raise ExportError("Destination exists: refusing overwrite")
    if native_runtime is None and r14_report is not None:
        raise ExportError("--r14-report requires --native-runtime")
    if native_runtime is not None and r14_report is None:
        raise ExportError("Native candidate requires a complete R14 evidence report")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".r20d-jeanne-", dir=output.parent) as tmp:
        stage = Path(tmp) / "staged"
        stage.mkdir()
        report = stage_pair(stage, license_manifest=license_manifest,
                            require_licenses=native_runtime is not None)
        if native_runtime is not None:
            # Native release candidates are always licensed and backed by a
            # complete verified R14 report (the exporter verifies both).
            bundle = export_game(stage / CONTENT_NAME, native_runtime, output,
                                 require_licenses=True, r14_report=r14_report)
            from drawtemp.export.r15 import verify_bundle
            manifest = verify_bundle(bundle)
            return {"kind": "r20d-native-candidate", "bundle": str(bundle),
                    "native_integrity_verified": True,
                    "r14_evidence": manifest["certification"],
                    "license_warnings": manifest["license_warnings"],
                    "release_certified": False,
                    "external_playtest": "not evidenced"}
        report_path = stage / "r20d-preflight.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                          sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return {"kind": "r20d-developer-pair",
                "directory": str(output),
                "preflight": report,
                "release_certified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory to publish")
    parser.add_argument("--native-runtime", type=Path,
                        help="Previously built real R15 native Player runtime")
    parser.add_argument("--r14-report", type=Path,
                        help="Complete validated R14 quality evidence (required native)")
    parser.add_argument("--license-manifest", type=Path,
                        help="Reviewed source asset-licenses.json, no autogenerated claims")
    args = parser.parse_args(argv)
    try:
        report = prepare(args.output, native_runtime=args.native_runtime,
                         r14_report=args.r14_report,
                         license_manifest=args.license_manifest)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"passed": False, "error": str(exc),
                          "release_certified": False}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
