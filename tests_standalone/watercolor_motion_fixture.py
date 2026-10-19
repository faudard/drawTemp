"""Detect whether the optional INT-03 11-cel art publication is attempted.

The default development checkout contains 88 source PNGs and legacy preview
animations; that is not an incomplete 99-image *claim*. As soon as anyone
publishes derived files, hashes or an extended manifest, all 99-image tests
must run and fail on incomplete or mismatched publication.

Production certification is separate and ALWAYS fail-closed:
    python scripts/certify_int03_assets.py --root assets/watercolor
"""
import json

from sporebound.watercolor_catalog import DEFAULT_WATERCOLOR_ROOT


def motion_publication_claimed(root=DEFAULT_WATERCOLOR_ROOT):
    """Do not confuse missing optional release art with a failed gameplay test."""
    root = root.resolve()
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    animations = {
        row["id"]: row for row in registry["entries"]
        if row["kind"] == "animation"
    }
    return (
        "derived_hashes" in provenance
        or len(index["sprites"]) != 88
        or len(animations["anim_jeanne_walk"]["frames"]) != 2
        or len(animations["anim_jeanne_attack"]["frames"]) != 3
        or any((root / "sprites" / "jeanne_motion").glob("*.png"))
    )
