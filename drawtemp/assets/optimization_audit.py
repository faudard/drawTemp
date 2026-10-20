"""R76.A: read-only, deterministic inventory of canonical project assets.

This module does not transcode, remove or overwrite artwork and cannot certify
visual quality, runtime memory consumption, GPU use, or redistribution rights.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import sys

from sporebound.assets import AssetRegistry

AUDIT_SCHEMA = 1
COMPRESSION_POLICY = {
    "version": 1,
    "images": "preserve_png_bytes; lossless_candidates_only",
    "audio": "preserve_wav_ogg_bytes",
    "shaders": "not_in_canonical_asset_registry",
    "application": "manual_review_only",
}
MAX_SCAN_BYTES = 256 * 1024 * 1024
MAX_PNG_DIMENSION = 8192
CHUNK_BYTES = 1024 * 1024


def _check_physical_file(registry: AssetRegistry, root: Path, relative: str, asset_id: str) -> Path:
    """Refuse symlinks (even intra-root) and ask the canonical resolver to validate."""
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError("symbolic_link")
    path = registry.resolve(asset_id, root)
    if not path.is_relative_to(root):
        raise ValueError("path_escape")
    return path


def _file_fingerprint(path: Path) -> tuple[str, int, bytes]:
    """Streaming bounded hash; detect a file being changed during the scan."""
    before = path.stat()
    if before.st_size > MAX_SCAN_BYTES:
        raise ValueError("file_exceeds_256_mib_audit_limit")
    if not path.is_file():
        raise ValueError("not_regular_file")
    digest = sha256()
    first = b""
    size = 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "rb") as source:
            fd = -1
            opened = os.fstat(source.fileno())
            if (opened.st_ino, opened.st_dev) != (before.st_ino, before.st_dev):
                raise ValueError("file_changed_during_audit")
            while True:
                data = source.read(CHUNK_BYTES)
                if not data:
                    break
                if size + len(data) > MAX_SCAN_BYTES:
                    raise ValueError("file_exceeds_256_mib_audit_limit")
                if not first:
                    first = data[:32]
                size += len(data)
                digest.update(data)
            after = os.fstat(source.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    latest = path.stat()
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if signature(before) != signature(opened) or signature(opened) != signature(after) or signature(after) != signature(latest) or size != before.st_size:
        raise ValueError("file_changed_during_audit")
    return digest.hexdigest(), size, first


def _png_rgba_estimate(header: bytes) -> int:
    """Upper-bound RGBA staging estimate; NOT measured GPU or process memory."""
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n") or header[12:16] != b"IHDR":
        raise ValueError("invalid_png_header")
    width, height = struct.unpack(">II", header[16:24])
    if not 1 <= width <= MAX_PNG_DIMENSION or not 1 <= height <= MAX_PNG_DIMENSION:
        raise ValueError("unsupported_png_dimensions")
    return width * height * 4


def _file_signature(kind: str, relative: str, header: bytes) -> tuple[str, int | None]:
    extension = Path(relative).suffix.lower()
    if extension == ".png" and kind in ("sprite", "portrait"):
        return "png", _png_rgba_estimate(header)
    if extension == ".wav" and kind == "sound" and header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "wav", None
    if extension == ".ogg" and kind == "sound" and header.startswith(b"OggS"):
        return "ogg", None
    raise ValueError("invalid_asset_signature")


def audit_registry(registry: AssetRegistry, root: Path) -> dict:
    """Audit the sole canonical AssetRegistry; no project, atlas or save mutation.

    A missing or unreadable asset makes the report blocked, but remains listed.
    Findings are stable for identical bytes on any host and do not contain
    machine-dependent absolute paths or timestamps.
    """
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("asset root must be a directory")
    manifest = registry.to_dict()
    entries = sorted(manifest["entries"], key=lambda entry: entry["id"])
    physical = defaultdict(list)
    references = []
    kind_counts = {kind: 0 for kind in ("sprite", "portrait", "sound", "animation")}
    for entry in entries:
        kind_counts[entry["kind"]] += 1
        if entry["kind"] == "animation":
            for index, frame in enumerate(entry["frames"]):
                references.append({
                    "source": entry["id"], "target": frame["sprite"],
                    "relation": "animation_frame", "frame": index,
                })
        else:
            physical[entry["path"]].append(entry)
    for kind, slots in sorted(manifest["bindings"].items()):
        for slot, asset_id in sorted(slots.items()):
            references.append({
                "source": kind + ":" + slot, "target": asset_id,
                "relation": "presentation_binding",
            })
    references.sort(key=lambda d: (d["relation"], d["source"], d.get("frame", -1), d["target"]))

    issues = []
    files = []
    casefolded = {}
    digest_groups = defaultdict(list)
    for relative, owners in sorted(physical.items()):
        folded = relative.casefold()
        if folded in casefolded and casefolded[folded] != relative:
            issues.append({"path": relative, "code": "case_collision",
                           "detail": "conflicts with " + casefolded[folded]})
            continue
        casefolded[folded] = relative
        kinds = sorted({entry["kind"] for entry in owners})
        record = {"path": relative, "asset_ids": sorted(entry["id"] for entry in owners),
                  "kinds": kinds, "bytes": None, "sha256": None,
                  "media_type": None, "rgba_staging_bytes_estimate": None}
        try:
            path = _check_physical_file(registry, root, relative, owners[0]["id"])
            digest, nbytes, header = _file_fingerprint(path)
            # A file used by multiple registry kinds must satisfy each signature.
            media_types = set()
            estimates = []
            for kind in kinds:
                media_type, estimate = _file_signature(kind, relative, header)
                media_types.add(media_type)
                if estimate is not None:
                    estimates.append(estimate)
            if len(media_types) != 1:
                raise ValueError("incompatible_references")
            record.update(bytes=nbytes, sha256=digest, media_type=media_types.pop(),
                          rgba_staging_bytes_estimate=max(estimates) if estimates else None)
            digest_groups[(digest, nbytes)].append(relative)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            issues.append({"path": relative, "code": "asset_audit_failed", "detail": str(exc)})
        files.append(record)

    # Conservative, *potential* deduplication only. No claimed bundle savings:
    # different paths can have independent provenance or reference semantics.
    duplicates = [paths for paths in digest_groups.values() if len(paths) > 1]
    duplicates.sort(key=lambda paths: paths[0])
    verified_files = [row for row in files if row["bytes"] is not None]
    summary = {
        "registered_assets": len(entries),
        "physical_paths": len(physical),
        "hashed_files": len(verified_files),
        "encoded_bytes_hashed": sum(row["bytes"] for row in verified_files),
        "rgba_staging_bytes_estimate": sum(
            row["rgba_staging_bytes_estimate"] or 0 for row in verified_files
        ),
        "kind_counts": kind_counts,
        "duplicate_content_groups": len(duplicates),
    }
    return {
        "schema": AUDIT_SCHEMA,
        "kind": "drawtemp-r76a-asset-audit",
        "integrity": "blocked" if issues else "inspected",
        "rights": "not_assessed",
        "release_certified": False,
        "quality": {"decoded_pixel_comparison": "not_assessed",
                    "audio_quality": "not_assessed", "gpu_memory": "not_measured"},
        "compression_policy": dict(COMPRESSION_POLICY),
        "summary": summary,
        "dependency_edges": references,
        "files": files,
        "duplicate_candidates": duplicates,
        "issues": sorted(issues, key=lambda row: (row["path"], row["code"])),
    }


def audit_content(content_path: Path) -> dict:
    """Include the existing R15 strict rights/preflight result, not a new policy."""
    from drawtemp.export.r15 import preflight, project_path

    content_path = Path(content_path).resolve(strict=True)
    pre = preflight(content_path, require_licenses=True)
    project = json.loads(project_path(content_path).read_text(encoding="utf-8"))
    registry = AssetRegistry(project.get("assets") or None)
    report = audit_registry(registry, content_path.parent)
    report["rights"] = (
        "r15_strict_preflight_passed"
        if pre["passed"] and pre["rights_attestations_checked"]
        else "blocked"
    )
    report["r15_preflight"] = {
        "passed": pre["passed"],
        "rights_attestations_checked": pre["rights_attestations_checked"],
        "errors": sorted(pre["errors"]),
        "warnings": sorted(pre["warnings"]),
    }
    if not pre["passed"] or not pre["rights_attestations_checked"]:
        report["integrity"] = "blocked"
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="R76.A read-only asset/build cost audit")
    parser.add_argument("--content", required=True, type=Path,
                        help="Path to canonical Content JSON next to its .game.json project")
    parser.add_argument("--report", type=Path, help="Optional JSON destination (not under the game project)")
    args = parser.parse_args(argv)
    try:
        report = audit_content(args.content)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"schema": AUDIT_SCHEMA, "kind": "drawtemp-r76a-asset-audit",
                  "integrity": "blocked", "rights": "blocked",
                  "release_certified": False,
                  "issues": [{"code": "invalid_project", "detail": str(exc)}]}
    payload = json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.report is not None:
        destination = args.report.resolve()
        project_root = args.content.resolve().parent
        if destination == project_root or project_root in destination.parents:
            parser.error("--report must be outside the audited project (read-only contract)")
        if destination.exists() and destination.is_symlink():
            parser.error("symlinked report targets are unsupported")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["integrity"] == "inspected" else 1


if __name__ == "__main__":
    sys.exit(main())
