"""INT-03: fail-closed proof that Jeanne PNGs are shipped and usable.

The art generator and a CI run are not release evidence on their own.
This gate checks checked-out bytes, original/derived hashes, asset IDs,
animation frames, runtime resolving and an explicit rights attestation.
No Pillow, OpenCV, GUI or regeneration is used in the release gate.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from drawtemp.assets.resolver import AssetResolver
from scripts.generate_jeanne_motion import TRANSITIONS
from scripts.verify_watercolor_release import verify_directory
from sporebound.assets import AssetRegistry
from sporebound.watercolor_catalog import WatercolorCatalog

SHA256 = re.compile(r"[a-f0-9]{64}\\Z")
UNVERIFIED = {"", "unknown", "unverified", "pending", "todo", "none"}


def expected_derived_paths() -> set[str]:
    return {
        f"sprites/jeanne_motion/{action}_{segment:02d}_{frame:02d}.png"
        for action, steps in TRANSITIONS.items()
        for segment, (_, _, count) in enumerate(steps)
        for frame in range(1, count + 1)
    }


def verify_rights(rights: dict, provenance: dict) -> dict:
    """Require a reviewable license grant; never infer one from a PNG hash."""
    if not isinstance(rights, dict) or rights.get("schema_version") != 1:
        raise ValueError("INT-03: rights manifest missing or unsupported")
    if rights.get("source_archive_sha256") != provenance.get("archive_sha256"):
        raise ValueError("INT-03: rights provenance/source archive mismatch")
    if rights.get("status") != "approved":
        raise ValueError("INT-03: asset rights have not been approved")
    for key in ("rights_holder", "license_id", "evidence"):
        val = rights.get(key)
        if not isinstance(val, str) or val.strip().lower() in UNVERIFIED:
            raise ValueError(f"INT-03: rights {key} is missing or unverified")
    if rights.get("allow_modification") is not True:
        raise ValueError("INT-03: derived images lack modification permission")
    if rights.get("allow_redistribution") is not True:
        raise ValueError("INT-03: redistribution permission is not recorded")
    return {"status": "approved", "license_id": rights["license_id"],
            "rights_holder": rights["rights_holder"],
            "evidence": rights["evidence"]}


def certify(root: Path, *, require_rights: bool = True) -> dict:
    """Certify the *published tree* (not a generator's temporary output)."""
    root = Path(root).resolve(strict=True)
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    derived = provenance.get("derived_hashes")
    if not isinstance(derived, dict) or set(derived) != expected_derived_paths():
        raise ValueError("INT-03: exactly 11 named Jeanne derived PNGs are required")
    if len(derived) != 11 or any(not isinstance(v, str) or not SHA256.fullmatch(v)
                                 for v in derived.values()):
        raise ValueError("INT-03: invalid derived provenance digests")
    for relative in derived:
        target = root / relative
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
            raise ValueError(f"INT-03: derived PNG not published safely: {relative}")
        if sha256(target.read_bytes()).hexdigest() != derived[relative]:
            raise ValueError(f"INT-03: derived PNG hash mismatch: {relative}")

    # Strict verification covers all 99 real images, PNG CRC/size,
    # original provenance, index paths and canonical animation references.
    artwork = verify_directory(root)
    if (artwork["sprites"], artwork["animations"],
            artwork["provenance_sha256_verified"]) != (99, 15, 99):
        raise ValueError("INT-03: incomplete 99-image provenance / registry")

    registry = AssetRegistry(json.loads((root / "registry.json").read_text(encoding="utf-8")))
    catalog = WatercolorCatalog(root)
    resolver = AssetResolver(registry, root)
    from scripts.install_watercolor_pack import MOTION
    for action, count, loop in (("walk", 8, True), ("attack", 12, False)):
        aid = f"anim_jeanne_{action}"
        animation = registry.require_reference(aid, "animation")
        if len(animation["frames"]) != count or animation["loop"] is not loop:
            raise ValueError(f"INT-03: broken {aid} frames or loop")
        if MOTION["jeanne"][("move" if action == "walk" else "attack")] != aid:
            raise ValueError(f"INT-03: Player Jeanne binding does not target {aid}")
        if catalog.lookup(aid).frame_count != count:
            raise ValueError(f"INT-03: catalog frame mismatch for {aid}")
        elapsed = 0
        for frame in animation["frames"]:
            sprite_id = frame["sprite"]
            if catalog.status(sprite_id, verify=True)[0] != "ready":
                raise ValueError(f"INT-03: runtime sprite unavailable: {sprite_id}")
            resolved = resolver.resolve(aid, elapsed_ms=elapsed)
            if resolved.asset_id != sprite_id or not resolved.filename.is_file():
                raise ValueError(f"INT-03: renderer cannot resolve {sprite_id}")
            elapsed += frame["duration_ms"]
        if action == "attack" and resolver.resolve(aid, elapsed_ms=elapsed + 100).asset_id != "jeanne_guard":
            raise ValueError("INT-03: attack must hold its terminal guard pose")

    rights = {"status": "not_checked"}
    if require_rights:
        rights_file = root / "rights.json"
        if not rights_file.is_file() or rights_file.is_symlink():
            raise ValueError("INT-03: rights.json missing from published asset tree")
        rights = verify_rights(
            json.loads(rights_file.read_text(encoding="utf-8")), provenance)
    return {
        "status": "passed" if require_rights else "technical_only",
        "source_sha256": provenance["archive_sha256"],
        "derived_pngs": len(derived),
        "published_pngs": artwork["sprites"],
        "checked_animations": {"anim_jeanne_walk": 8, "anim_jeanne_attack": 12},
        "rights": rights,
        "commit": os.getenv("GITHUB_SHA", "local"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("assets/watercolor"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--technical-only", action="store_true",
                        help="Publisher preflight only; NEVER a release certification")
    args = parser.parse_args(argv)
    try:
        result = certify(args.root, require_rights=not args.technical_only)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        result = {"status": "blocked", "error": str(exc),
                  "commit": os.getenv("GITHUB_SHA", "local")}
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if args.report:
        args.report.write_text(payload, encoding="utf-8")
    return 0 if result["status"] in ("passed", "technical_only") else 1


if __name__ == "__main__":
    raise SystemExit(main())
