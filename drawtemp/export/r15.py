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


def _check_asset_rights(root, report, strict):
    """Verify human-supplied, file-bound rights attestations; never grant rights.

    Preview exports retain warnings. A strict export requires an approved
    attestation, SHA-256 and on-disk evidence for *every physical asset*.
    The program checks consistency, not the legal truth of an attestation.
    """
    index = root / "asset-licenses.json"
    issues = report["errors"] if strict else report["warnings"]
    if not index.exists() and not index.is_symlink():
        issues.append("No asset-licenses.json: redistribution rights unverified")
        return
    try:
        rights = _json(safe_asset_path(root, "asset-licenses.json"))
    except (ValueError, OSError, TypeError) as exc:
        report["errors"].append("Invalid asset-licenses.json: " + str(exc))
        return
    if not isinstance(rights, dict):
        report["errors"].append("Asset rights index must be a JSON object")
        return
    if set(rights) != {"schema", "assets"} or rights.get("schema") != 1 or not isinstance(rights.get("assets"), dict):
        issues.append("Structured asset-licenses.json schema 1 (schema + assets) required")
        return
    attestations = rights["assets"]
    folded = set()
    for path in attestations:
        if not isinstance(path, str) or path.casefold() in folded:
            report["errors"].append("Duplicate or invalid asset rights path: " + str(path))
            continue
        folded.add(path.casefold())
        if path not in report["assets"]:
            issues.append("Rights entry references unregistered asset: " + path)
    evidence = set()
    evidence_spelling = {}
    asset_folded = {path.casefold() for path in report["assets"]}
    required = {"status", "rights_holder", "license_id", "evidence_path",
                "sha256", "allow_modification", "allow_redistribution"}
    for relative in report["assets"]:
        entry = attestations.get(relative)
        if not isinstance(entry, dict) or set(entry) != required:
            issues.append("Missing or malformed rights attestation: " + relative)
            continue
        if (entry["status"] != "approved" or
                entry["allow_modification"] is not True or
                entry["allow_redistribution"] is not True):
            issues.append("Pending/insufficient modification or redistribution rights: " + relative)
            continue
        if any(not isinstance(entry[key], str) or not entry[key].strip()
               for key in ("rights_holder", "license_id", "evidence_path", "sha256")):
            issues.append("Incomplete asset rights provenance: " + relative)
            continue
        digest = entry["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            issues.append("Invalid asset rights SHA-256: " + relative)
            continue
        try:
            if _hash(safe_asset_path(root, relative)) != digest:
                issues.append("Rights attestation does not match asset SHA-256: " + relative)
                continue
            proof = entry["evidence_path"]
            if not proof.startswith("licenses/"):
                raise ValueError("Evidence must be a project-local licenses/ file")
            evidence_file = safe_asset_path(root, proof)
            if not evidence_file.is_file() or evidence_file.stat().st_size == 0:
                raise ValueError("Evidence file missing or empty")
            if proof.casefold() in asset_folded:
                raise ValueError("Evidence path collides with an asset")
            previous = evidence_spelling.get(proof.casefold())
            if previous is not None and previous != proof:
                raise ValueError("Non-portable evidence case collision: " + previous)
            evidence_spelling[proof.casefold()] = proof
        except (OSError, ValueError) as exc:
            issues.append("Unverifiable rights evidence for " + relative + ": " + str(exc))
            continue
        evidence.add(proof)
    if strict and not report["errors"]:
        report["rights_attestations_checked"] = True
    report["rights_evidence"] = sorted(evidence)


def preflight(content_path, *, require_licenses=False):
    """Validate both authored documents and every registered on-disk asset.

    Never mutates project files. The report is suitable for Studio UI/CLI.
    """
    source = Path(content_path).resolve()
    game = project_path(source)
    result = {"schema": 1, "kind": "drawtemp5-preexport",
              "content": str(source), "project": str(game),
              "errors": [], "warnings": [], "assets": [], "missions": [],
              "passed": False, "rights_evidence": [],
              "rights_attestations_checked": False}
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
            _check_asset_rights(source.parent, result, require_licenses)
        elif require_licenses:
            # Empty projects have no third-party material to license.
            result["rights_attestations_checked"] = True
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
                require_licenses=False, r14_report=None, release=False):
    """Stage fully hashed Player + game directory, then atomically publish.

    No false claim that a bundled Python interpreter or an offscreen smoke
    equals the R14 / clean-machine release certification.
    """
    if release and (not require_licenses or r14_report is None):
        raise ExportError("Release export requires strict asset rights and R14 evidence")
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
    if output.exists() or output.is_symlink():
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
        for relative in report["rights_evidence"]:
            target = game / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_asset_path(source.parent, relative), target)
        # Recheck the COPIED bytes before publishing: a source file altered
        # between preflight and copy must not bypass the rights SHA binding.
        staged = preflight(game / source.name, require_licenses=require_licenses)
        if (not staged["passed"] or staged["assets"] != report["assets"] or
                staged["rights_evidence"] != report["rights_evidence"]):
            raise ExportError("Staged content or asset rights changed during export: " +
                              "; ".join(staged["errors"]))
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
            "rights_attestations_checked": report["rights_attestations_checked"],
            "rights_evidence": ["game/" + name for name in report["rights_evidence"]],
            "release_candidate": bool(release),
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        verify_bundle(stage)
        os.replace(stage, output)
    return output


def _manifest_pairs(pairs):
    """Disallow duplicate JSON keys: different parsers must not see different data."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExportError("Duplicate JSON manifest key: " + key)
        result[key] = value
    return result


def _verified_manifest(root):
    manifest = root / "manifest.json"
    # The manifest must be a real, bounded file inside the bundle, not a
    # symlink or an unbounded attacker-controlled input.
    if manifest.is_symlink() or not manifest.is_file():
        raise ExportError("Standalone manifest must be a regular file")
    size = manifest.stat().st_size
    if size < 1 or size > 8 * 1024 * 1024:
        raise ExportError("Standalone manifest exceeds the 8 MiB safety limit")
    try:
        return json.loads(manifest.read_text(encoding="utf-8"),
                          object_pairs_hook=_manifest_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExportError("Malformed standalone manifest: " + str(exc)) from exc


def _check_published_tree(root):
    """Reject even *internal* links and special files in relocated bundles.

    Symlinks are allowed in the incoming PyInstaller tree if contained, but
    copytree materializes their bytes. Published bundles must be independent
    of symlink resolution and safe to relocate/extract.
    """
    for node in root.rglob("*"):
        if node.is_symlink():
            raise ExportError("Symlink forbidden in published bundle: " + str(node))
        if not node.is_file() and not node.is_dir():
            raise ExportError("Special file forbidden in published bundle: " + str(node))


def verify_bundle(path, *, require_release=False):
    """Reject missing, substituted, unexpected or escaping bundle files."""
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ExportError("Standalone bundle root is not a directory")
    _check_published_tree(root)
    manifest = _verified_manifest(root)
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1 or
            manifest.get("kind") != "drawtemp5-standalone-game" or
            not isinstance(manifest.get("files"), list)):
        raise ExportError("Invalid standalone manifest")
    if require_release and (not manifest.get("release_candidate") or
                            manifest.get("rights_attestations_checked") is not True or
                            manifest.get("license_warnings") or
                            manifest.get("certification") != "R14 evidenced"):
        raise ExportError("Bundle is an unverified preview, not a release candidate")
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
    # Require the GameProject companion; without it the Player can silently
    # fall back to a bundled/default ruleset instead of the authored game.
    if (not content.startswith("game/") or not content.endswith(".json") or
            content.endswith(".game.json") or not player.startswith("Player/") or
            player.rsplit("/", 1)[-1] not in ("DrawTempPlayer", "DrawTempPlayer.exe")):
        raise ExportError("Invalid Content or native Player manifest identity")
    project = content[:-5] + ".game.json"
    if project.casefold() not in listed:
        raise ExportError("Bundle lacks the indexed GameProject companion")
    return manifest
