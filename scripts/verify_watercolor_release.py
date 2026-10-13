"""Validate 88 PNGs, the index, and animation registry; no optional deps.

Usage:
 python scripts/verify_watercolor_release.py --bundle art_v3.zip
 python scripts/verify_watercolor_release.py --root assets/watercolor
 python scripts/verify_watercolor_release.py --root assets/watercolor --allow-missing

Allow-missing only skips an entirely absent art pack. Partial packs fail.
"""
from __future__ import annotations

import argparse
from binascii import crc32
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import struct
from zipfile import ZipFile

PREFIX = "assets/watercolor/"
MAGIC = b"\x89PNG\r\n\x1a\n"


def png_dimensions(data, path):
    """Verify PNG chunks and terminal marker, not just its eight-byte signature."""
    if not data.startswith(MAGIC):
        raise ValueError(f"Invalid PNG signature: {path}")
    pos, dimensions, seen_idat, seen_end = 8, None, False, False
    while pos < len(data):
        if len(data) - pos < 12:
            raise ValueError(f"Truncated PNG chunk: {path}")
        length = struct.unpack_from(">I", data, pos)[0]
        end = pos + 12 + length
        if end > len(data):
            raise ValueError(f"Truncated PNG chunk: {path}")
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        checksum = struct.unpack_from(">I", data, end - 4)[0]
        if crc32(tag + payload) & 0xffffffff != checksum:
            raise ValueError(f"PNG CRC mismatch: {path}")
        if dimensions is None:
            if tag != b"IHDR" or length != 13 or payload[8:] != b"\x08\x06\x00\x00\x00":
                raise ValueError(f"Invalid 8-bit RGBA PNG: {path}")
            dimensions = struct.unpack_from(">II", payload)
        elif tag == b"IHDR":
            raise ValueError(f"Duplicate PNG IHDR: {path}")
        elif tag == b"IDAT":
            seen_idat = True
        elif tag == b"IEND":
            if length or not seen_idat or end != len(data):
                raise ValueError(f"Invalid PNG end: {path}")
            seen_end = True
            break
        pos = end
    if dimensions is None or not seen_idat or not seen_end:
        raise ValueError(f"Incomplete PNG: {path}")
    return dimensions


def validate(index, registry, read_file, available):
    from sporebound.assets import AssetRegistry

    AssetRegistry(registry)  # Validate unique IDs and animation references.
    if not isinstance(index, dict) or index.get("schema_version") != 1:
        raise ValueError("Wrong watercolor index schema")
    sprites = index.get("sprites")
    if not isinstance(sprites, list) or len(sprites) != 88:
        raise ValueError("Expected 88 indexed sprites")
    counts = Counter(entry["kind"] for entry in registry["entries"])
    if counts != {"sprite": 88, "animation": 15}:
        raise ValueError("Expected 88 sprites and 15 animations")
    registered = {entry["id"]: entry for entry in registry["entries"]
                  if entry["kind"] == "sprite"}
    ids, paths, groups = set(), set(), Counter()
    total_bytes = 0
    for sprite in sprites:
        aid, rel = sprite.get("id"), sprite.get("path")
        if not isinstance(aid, str) or not isinstance(rel, str):
            raise ValueError("Invalid sprite ID or path")
        parts = PurePosixPath(rel).parts
        if (len(parts) != 3 or parts[0] != "sprites" or
                str(PurePosixPath(rel)) != rel or ".." in parts or
                "\\" in rel or not rel.endswith(".png")):
            raise ValueError(f"Nonportable sprite path: {rel}")
        if aid.casefold() in ids or rel.casefold() in paths:
            raise ValueError("Duplicate indexed ID or path")
        ids.add(aid.casefold())
        paths.add(rel.casefold())
        if aid not in registered or registered[aid]["path"] != rel:
            raise ValueError(f"Index/registry mismatch for {aid}")
        full = PREFIX + rel
        if full not in available:
            raise ValueError(f"Missing sprite: {full}")
        data = read_file(full)
        width, height = png_dimensions(data, full)
        expected_hash = sprite.get("sha256")
        if expected_hash is not None and (not isinstance(expected_hash, str)
                or sha256(data).hexdigest() != expected_hash.lower()):
            raise ValueError(f"PNG SHA-256 mismatch: {full}")
        if not (1 <= width <= 4096 and 1 <= height <= 4096):
            raise ValueError(f"Invalid PNG size: {full}")
        if sprite.get("frame_size") != [width, height]:
            raise ValueError(f"PNG/index dimensions mismatch: {aid}")
        groups[parts[1]] += 1
        total_bytes += len(data)
    if set(registered) != {sprite["id"] for sprite in sprites}:
        raise ValueError("Manifest contains unindexed sprite references")
    return {"schema_version": 1, "sprites": 88, "animations": 15,
            "groups": dict(sorted(groups.items())), "png_bytes": total_bytes}


def verify_archive(bundle):
    with ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate ZIP member")
        index = json.loads(archive.read(PREFIX + "index.json"))
        registry = json.loads(archive.read(PREFIX + "registry.json"))
        return validate(index, registry, archive.read, set(names))


def verify_directory(root, *, allow_missing=False):
    root = Path(root)
    images = list((root / "sprites").rglob("*.png"))
    if not images:
        if allow_missing:
            return {"status": "not_published", "sprites": 0,
                    "note": "Publish the 88 PNGs before merging PR #71."}
        raise ValueError("88-PNG gate blocked: no files have been committed")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    paths = {PREFIX + p.relative_to(root).as_posix() for p in images}
    def read_file(name):
        rel = name.removeprefix(PREFIX)
        if (not name.startswith(PREFIX) or
                len(PurePosixPath(rel).parts) != 3 or
                ".." in PurePosixPath(rel).parts):
            raise ValueError("Invalid source path")
        return (root / rel).read_bytes()
    report = validate(index, registry, read_file, paths)
    if len(images) != 88:
        raise ValueError("Extra or missing PNG files")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--bundle", type=Path)
    sources.add_argument("--root", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = (verify_archive(args.bundle) if args.bundle else
              verify_directory(args.root, allow_missing=args.allow_missing))
    report = json.dumps(result, indent=2, ensure_ascii=False)
    print(report)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
