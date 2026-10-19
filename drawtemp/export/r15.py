"""R15: fail-closed Creator preflight and reproducible *content* packaging.

A bundle requires a separately built, native Player runtime. A Python wheel
or a script is never accepted as a standalone Player executable.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import re
from tempfile import TemporaryDirectory

from drawtemp.quality.r14 import safe_asset_path, verify_report
from sporebound.assets import AssetRegistry
from sporebound.studio_transaction import validate_pair


class ExportError(ValueError):
    pass


def project_path(content_path):
    path = Path(content_path)
    if path.name.endswith(".game.json"):
        raise ExportError("Expected Content JSON, not GameProject JSON")
    return path.with_name(path.stem + ".game.json")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def preflight(content_path, *, require_licenses=False):
    """Validate both authored documents and every registered on-disk asset.

    Never mutates project files. The report is suitable for Studio UI/CLI.
    """
    source = Path(content_path).resolve()
    game = project_path(source)
    result = {"schema": 1, "kind": "drawtemp5-preexport",
              "content": str(source), "project": str(game),
              "errors": [], "warnings": [], "assets": [], "missions": [],
              "passed": False}
    try:
        content, project = validate_pair(_json(source), _json(game))
        registry = AssetRegistry(project.get("assets") or None)
        result["missions"] = [m["id"] for m in content["missions"]]
        result["errors"].extend(
            issue["message"] for issue in registry.diagnostics(source.parent))
        from drawtemp.assets.packs import verify_installed_packs
        result["errors"].extend(verify_installed_packs(source.parent, project))
        # Several sprite regions legitimately share one atlas PNG. Export a
        # physical file once, but refuse ambiguous case-folding collisions
        # that would overwrite a different file on Windows/macOS.
        seen = {}
        for entry in registry.to_dict()["entries"]:
            if entry["kind"] == "animation":
                continue
            relative = entry["path"]
            folded = relative.casefold()
            previous = seen.get(folded)
            if previous is not None:
                if previous != relative:
                    result["errors"].append(
                        "Non-portable asset path collision: " + previous +
                        " vs " + relative)
                continue
            seen[folded] = relative
            try:
                safe_asset_path(source.parent, relative)
            except (ValueError, OSError) as exc:
                result["errors"].append(f"{relative}: {exc}")
                continue
            result["assets"].append(relative)
        if result["assets"]:
            license_file = source.parent / "asset-licenses.json"
            if not license_file.is_file():
                message = "No asset-licenses.json: redistribution rights unverified"
                (result["errors"] if require_licenses else
                 result["warnings"]).append(message)
            else:
                try:
                    licenses = _json(safe_asset_path(source.parent, "asset-licenses.json"))
                    if not isinstance(licenses, dict):
                        raise ValueError("License index must be a path-to-license object")
                    for relative in result["assets"]:
                        info = licenses.get(relative)
                        if not isinstance(info, str) or not info.strip():
                            (result["errors"] if require_licenses else
                             result["warnings"]).append(
                                 "Missing redistribution license: " + relative)
                except (ValueError, OSError) as exc:
                    result["errors"].append("Invalid asset-licenses.json: " + str(exc))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        result["errors"].append(str(exc))
    result["passed"] = not result["errors"]
    return result


def _hash(path):
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _native_name():
    return "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"


def _files(root):
    return sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix())


def _assert_safe_tree(root):
    root = Path(root).resolve(strict=True)
    for node in root.rglob("*"):
        if node.is_symlink() and not node.resolve(strict=True).is_relative_to(root):
            raise ExportError("External symlink in Player runtime: " + str(node))
        if not node.is_dir() and not node.is_file():
            raise ExportError("Unsupported runtime entry: " + str(node))


def export_game(content_path, runtime_dir, destination, *,
                require_licenses=False, r14_report=None):
    """Stage fully hashed Player + game directory, then atomically publish.

    No false claim that a bundled Python interpreter or an offscreen smoke
    equals the R14 / clean-machine release certification.
    """
    source = Path(content_path).resolve(strict=True)
    report = preflight(source, require_licenses=require_licenses)
    if not report["passed"]:
        raise ExportError("Pre-export validation failed: " + "; ".join(report["errors"]))
    if r14_report is not None:
        try:
            verify_report(_json(r14_report), require_complete=True)
        except (OSError, ValueError) as exc:
            raise ExportError("R14 release gate is not certified: " + str(exc)) from exc
    runtime = Path(runtime_dir).resolve(strict=True)
    _assert_safe_tree(runtime)
    if not (runtime / _native_name()).is_file():
        raise ExportError("Native Player executable is missing: " + _native_name())
    output = Path(destination).absolute()
    if output.exists():
        raise ExportError("Destination exists; never overwrite an export")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".drawtemp-r15-", dir=output.parent) as folder:
        stage = Path(folder) / "bundle"
        stage.mkdir()
        shutil.copytree(runtime, stage / "Player")
        game = stage / "game"
        game.mkdir()
        shutil.copy2(source, game / source.name)
        project = project_path(source)
        shutil.copy2(project, game / project.name)
        for relative in report["assets"]:
            target = game / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_asset_path(source.parent, relative), target)
        if (source.parent / "asset-licenses.json").is_file():
            shutil.copy2(safe_asset_path(source.parent, "asset-licenses.json"),
                         game / "asset-licenses.json")
        files = [
            {"path": file.relative_to(stage).as_posix(), "size": file.stat().st_size,
             "sha256": _hash(file)}
            for file in _files(stage)
        ]
        manifest = {
            "schema": 1, "kind": "drawtemp5-standalone-game",
            "content": "game/" + source.name,
            "player": "Player/" + _native_name(),
            "files": files,
            "certification": "R14 evidenced" if r14_report else "R14 not certified",
            "license_warnings": report["warnings"],
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        verify_bundle(stage)
        os.replace(stage, output)
    return output


def verify_bundle(path):
    """Reject missing, substituted, unexpected or escaping bundle files."""
    root = Path(path).resolve(strict=True)
    manifest = _json(root / "manifest.json")
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1 or
            manifest.get("kind") != "drawtemp5-standalone-game" or
            not isinstance(manifest.get("files"), list)):
        raise ExportError("Invalid standalone manifest")
    entries = manifest["files"]
    listed = set()
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise ExportError("Malformed manifest file entry")
        relative = row["path"]
        if not isinstance(relative, str) or relative.casefold() in listed:
            raise ExportError("Duplicate/invalid manifest path")
        listed.add(relative.casefold())
        if (type(row["size"]) is not int or row["size"] < 0 or
                not isinstance(row["sha256"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ExportError("Invalid size or SHA-256 in manifest")
        try:
            file = safe_asset_path(root, relative)
        except (OSError, ValueError) as exc:
            raise ExportError(f"Unsafe or missing file {relative}: {exc}") from exc
        if file.stat().st_size != row["size"] or _hash(file) != row["sha256"]:
            raise ExportError("Bundle integrity mismatch: " + relative)
    actual = {file.relative_to(root).as_posix().casefold()
              for file in _files(root) if file != root / "manifest.json"}
    if actual != listed:
        raise ExportError("Unlisted or missing bundle files")
    content = manifest.get("content")
    player = manifest.get("player")
    if (not isinstance(content, str) or not isinstance(player, str) or
            content.casefold() not in listed or player.casefold() not in listed):
        raise ExportError("Bundle lacks an indexed game or native Player")
    return manifest
