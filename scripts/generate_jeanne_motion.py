"""Jeanne watercolor cel in-betweens; authoring-only, never game simulation.

Dependencies (authoring, not Player): Pillow, NumPy and OpenCV headless.
python scripts/generate_jeanne_motion.py --root assets/watercolor

Reuses the 88 original V3 PNGs byte-for-byte. Warps only one neighboring
approved pose for each transitional cel to avoid double-exposed faces/swords.
Generated cels are NOT independently hand-painted animation drawings.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

FRAME_SIZE = (384, 341)
SOURCE_STAGES = (
    "walk_a", "idle", "walk_b", "ready", "windup",
    "slash", "followthrough", "guard",
)
TRANSITIONS = {
    "walk": (("walk_a", "idle", 1), ("idle", "walk_b", 1),
             ("walk_b", "idle", 1), ("idle", "walk_a", 1)),
    "attack": (("ready", "windup", 2), ("windup", "slash", 2),
               ("slash", "followthrough", 2), ("followthrough", "guard", 1)),
}
DURATIONS = {"walk": 75, "attack": 36}


def source_frame(root, name):
    from PIL import Image
    path = root / "sprites" / "jeanne" / (name + ".png")
    if not path.is_file():
        raise FileNotFoundError(f"Approved original missing: {path}")
    with Image.open(path) as image:
        if image.size != FRAME_SIZE:
            raise ValueError(f"{path}: requires original size {FRAME_SIZE}")
        return image.convert("RGBA")


def morph(image_a, image_b, fraction):
    """Bidirectional optical-flow deformation with clean, unblended cels."""
    import cv2
    import numpy as np
    from PIL import Image

    if not 0 < fraction < 1:
        raise ValueError("Expected an intermediate frame")
    a = np.asarray(image_a, dtype=np.uint8)
    b = np.asarray(image_b, dtype=np.uint8)

    def grayscale(rgba):
        alpha = rgba[..., 3:4].astype(np.float32) / 255.0
        rgb = rgba[..., :3].astype(np.float32)
        opaque = rgb * alpha + 115.0 * (1.0 - alpha)
        return cv2.cvtColor(opaque.astype(np.uint8), cv2.COLOR_RGB2GRAY)

    grayscale_a, grayscale_b = grayscale(a), grayscale(b)
    forward = cv2.calcOpticalFlowFarneback(
        grayscale_a, grayscale_b, None, .5, 4, 24, 4, 7, 1.5, 0)
    reverse = cv2.calcOpticalFlowFarneback(
        grayscale_b, grayscale_a, None, .5, 4, 24, 4, 7, 1.5, 0)
    height, width = grayscale_a.shape
    xx, yy = np.meshgrid(np.arange(width, dtype=np.float32),
                         np.arange(height, dtype=np.float32))
    # A cross-fade between two different illustrations creates a semi-
    # transparent ghost (two faces, two swords). Keep one warped cel only.
    source, flow, strength = (
        (a, forward, fraction) if fraction <= .5
        else (b, reverse, 1.0 - fraction))
    rgba = source.astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]
    premultiplied = np.concatenate((rgba[..., :3] * alpha, alpha), axis=2)
    warped = cv2.remap(
        premultiplied, xx - flow[..., 0] * strength,
        yy - flow[..., 1] * strength, cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    out_alpha = warped[..., 3:4]
    rgb = np.divide(warped[..., :3], np.maximum(out_alpha, 1e-5))
    result = np.concatenate((np.clip(rgb, 0, 1),
                             np.clip(out_alpha, 0, 1)), axis=2)
    return Image.fromarray(
        np.uint8(np.clip(result * 255.0 + .5, 0, 255)), "RGBA")


def build(root):
    """Rebuild 12 derived PNGs + entries atomically after input validation.

    Baseline provenance remains immutable and covers only the 88 original
    drawings. A separate derived_hashes map verifies the extra PNGs.
    """
    from sporebound.assets import AssetRegistry

    root = Path(root)
    index_path, registry_path, provenance_path = (
        root / "index.json", root / "registry.json", root / "provenance.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    originals = provenance["sprite_hashes"]
    if len(originals) != 88:
        raise ValueError("Expected 88 original V3 provenance hashes")
    for relative, digest in originals.items():
        original = root / relative
        if not original.is_file() or sha256(original.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Approved original missing or modified: {relative}")

    # Safe to rerun: keep original IDs and unrelated animations unchanged.
    index["sprites"] = [item for item in index["sprites"]
                        if item["path"] in originals]
    if len(index["sprites"]) != 88:
        raise ValueError("Baseline index must contain all original art")
    registry["entries"] = [
        item for item in registry["entries"]
        if not item["id"].startswith("jeanne_motion_")
        and item["id"] not in ("anim_jeanne_walk", "anim_jeanne_attack")]
    images = {name: source_frame(root, name) for name in SOURCE_STAGES}
    generated = {}
    for action, steps in TRANSITIONS.items():
        frames = []
        for segment, (start, end, count) in enumerate(steps):
            frames.append({"sprite": f"jeanne_{start}",
                           "duration_ms": DURATIONS[action]})
            for subframe in range(1, count + 1):
                frame_id = f"jeanne_motion_{action}_{segment:02d}_{subframe:02d}"
                relative = f"sprites/jeanne_motion/{action}_{segment:02d}_{subframe:02d}.png"
                cel = morph(images[start], images[end], subframe / (count + 1))
                encoded = BytesIO()
                cel.save(encoded, format="PNG", compress_level=9)
                generated[relative] = encoded.getvalue()
                index["sprites"].append({
                    "id": frame_id, "kind": "sprite", "path": relative,
                    "sheet": "jeanne", "cell": [segment, subframe],
                    "frame_size": list(FRAME_SIZE), "pivot": [192, 306],
                })
                registry["entries"].append({
                    "id": frame_id, "kind": "sprite", "path": relative})
                frames.append({
                    "sprite": frame_id, "duration_ms": DURATIONS[action]})
        if action == "attack":
            frames.append({"sprite": "jeanne_guard",
                           "duration_ms": DURATIONS[action]})
        expected = 8 if action == "walk" else 12
        if len(frames) != expected:
            raise AssertionError(f"{action}: expected {expected} cels")
        registry["entries"].append({
            "id": f"anim_jeanne_{action}", "kind": "animation",
            "loop": action == "walk", "frames": frames})

    provenance["derived_hashes"] = {
        path: sha256(png).hexdigest() for path, png in sorted(generated.items())}
    AssetRegistry(registry)
    # Superseded generated cels must not poison the strict PNG release gate.
    # Only this owned, derived directory is pruned; originals are untouched.
    derived_dir = root / "sprites" / "jeanne_motion"
    if derived_dir.is_dir():
        for stale in derived_dir.glob("*.png"):
            if stale.relative_to(root).as_posix() not in generated:
                stale.unlink()
    for relative, png in generated.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(png)
    for path, obj in ((index_path, index), (registry_path, registry),
                      (provenance_path, provenance)):
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return {"new_pngs": len(generated), "walk_frames": 8, "attack_frames": 12}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("assets/watercolor"))
    args = parser.parse_args(argv)
    print(json.dumps(build(args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
