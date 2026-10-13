"""Publish a complete audited v3 watercolor ZIP into the repo, safely.

No network, Pillow, Git, or modifications to game/save JSON. This prepares
real binary assets for a subsequent git commit; it does not push for the user.

  python scripts/publish_watercolor_pack.py --bundle /path/to/v3.zip
  python scripts/publish_watercolor_pack.py --bundle /path/to/v3.zip --dry-run
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_watercolor_release import (
    PREFIX, verify_archive, verify_directory,
)


def publish(bundle, root=ROOT / "assets" / "watercolor", *, dry_run=False):
    """Preflight all 88 PNGs before changing the target directory.

    Extract only verified, explicitly indexed paths to a temporary sibling,
    then rename the entire sprite directory. An existing complete pack is
    idempotent; incomplete or different art is never overwritten silently.
    """
    bundle, root = Path(bundle), Path(root)
    if not bundle.is_file() or not root.is_dir():
        raise ValueError("Bundle and existing watercolor metadata root are required")

    metadata = {}
    for name in ("index.json", "registry.json", "provenance.json"):
        path = root / name
        if not path.is_file():
            raise ValueError(f"Missing tracked watercolor metadata: {name}")
        metadata[name] = json.loads(path.read_text(encoding="utf-8"))

    provenance = metadata["provenance.json"]
    expected_zip_sha = provenance.get("archive_sha256")
    if not isinstance(expected_zip_sha, str) or sha256(bundle.read_bytes()).hexdigest() != expected_zip_sha:
        raise ValueError("Bundle SHA-256 differs from approved v3 provenance")

    with ZipFile(bundle) as source:
        # Guard compressed archive sizes before reading/decompressing members.
        infos = source.infolist()
        if len({item.filename for item in infos}) != len(infos):
            raise ValueError("Duplicate ZIP member")
        sprite_infos = [item for item in infos if
                        item.filename.startswith(PREFIX + "sprites/") and
                        item.filename.lower().endswith(".png")]
        if len(sprite_infos) != 88 or any(
                item.file_size < 33 or item.file_size > 15_000_000
                for item in sprite_infos) or sum(
                    item.file_size for item in sprite_infos) > 300_000_000:
            raise ValueError("ZIP must contain exactly 88 bounded PNG sprites")

        for name in ("index.json", "registry.json"):
            if json.loads(source.read(PREFIX + name)) != metadata[name]:
                raise ValueError(f"ZIP metadata differs from repository {name}")
        approved = metadata["index.json"]["sprites"]
        if {PREFIX + item["path"] for item in approved} != {
                item.filename for item in sprite_infos}:
            raise ValueError("Archive has unindexed or missing sprites")

        # Validates every PNG chunk CRC, dimensions, registry and animations.
        report = verify_archive(bundle)
        if report["sprites"] != 88 or report["animations"] != 15:
            raise ValueError("Incomplete validated watercolor archive")

        hashes = provenance.get("sprite_hashes", {})
        if len(hashes) != 88 or set(hashes) != {
                sprite["path"] for sprite in approved}:
            raise ValueError("Incomplete approved sprite provenance")
        for sprite in approved:
            rel = sprite["path"]
            if sha256(source.read(PREFIX + rel)).hexdigest() != hashes[rel]:
                raise ValueError(f"Sprite SHA-256 differs from approved art: {rel}")

        dest = root / "sprites"
        if dest.exists():
            # Reject partial packs, symlinks, edited PNGs, or extra sprites.
            if dest.is_symlink() or not dest.is_dir():
                raise ValueError("Unexpected sprites path")
            existing = verify_directory(root)
            return {"status": "already_published", **existing}
        if dry_run:
            return {"status": "ready_to_publish", "sprites": 88,
                    "provenance_sha256_verified": 88}

        # The extraction staging directory is on the destination filesystem.
        with TemporaryDirectory(prefix=".watercolor-stage-", dir=root) as folder:
            staged = Path(folder)
            for name in ("index.json", "registry.json", "provenance.json"):
                shutil.copy2(root / name, staged / name)
            for sprite in approved:
                rel = sprite["path"]
                path = staged / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.open(PREFIX + rel) as stream, path.open("wb") as out:
                    shutil.copyfileobj(stream, out)
            checked = verify_directory(staged)
            if checked.get("provenance_sha256_verified") != 88:
                raise ValueError("Staged art failed provenance verification")
            if dest.exists():
                raise ValueError("Sprite destination changed during publication")
            os.replace(staged / "sprites", dest)
        return {"status": "published", **verify_directory(root)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT / "assets" / "watercolor")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(publish(args.bundle, args.root, dry_run=args.dry_run),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
