"""R19.A: check R7 animations through actual pixels, without touching game state.

A successful scan is not artistic approval, a redistribution license or a GPU
certificate. Character Recipe v1 remains the only authoring source.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import sys

from .characters import ACTIONS, DIRECTIONS, validate

MAX_PNG_BYTES = 32 * 1024 * 1024
LOOP_ACTIONS = frozenset(("idle", "walk", "run"))


def _pixel_digest(root: Path, frame: dict) -> str:
    """Hash decoded RGBA frame pixels rather than path names or source bytes."""
    raw_path = frame["path"]
    path = PurePosixPath(raw_path)
    if (not raw_path or "\\" in raw_path or path.is_absolute()
            or any(p in (".", "..", "") for p in path.parts)):
        raise ValueError("non-portable source path")
    source = root.joinpath(*path.parts)
    if not source.is_file() or source.is_symlink():
        raise ValueError("missing source or symbolic link")
    if not source.resolve().is_relative_to(root):
        raise ValueError("source outside project root")
    if source.stat().st_size > MAX_PNG_BYTES:
        raise ValueError("source exceeds 32 MiB")
    ancestor = source.parent
    while ancestor != root:
        if ancestor.is_symlink():
            raise ValueError("symbolic link in asset path")
        ancestor = ancestor.parent
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow required: pip install '.[art]'") from exc
    try:
        with Image.open(source) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width > 8192 or height > 8192:
                raise ValueError("invalid image dimensions")
            image.load()
            region = frame["region"]
            if region is not None:
                x, y, w, h = region
                if x + w > width or y + h > height:
                    raise ValueError("frame region outside PNG")
                image = image.crop((x, y, x + w, y + h))
            rgba = image.convert("RGBA")
            payload = rgba.width.to_bytes(4, "big") + rgba.height.to_bytes(4, "big")
            return sha256(payload + rgba.tobytes()).hexdigest()
    except (OSError, SyntaxError) as exc:
        raise ValueError("PNG cannot be decoded") from exc


def audit_character(recipe: dict, project_root: Path) -> dict:
    """Verify all 9 R19.3 actions in each outfit and all 4 directions.

    Reports measurable integrity, not art quality. Never updates a recipe,
    the runtime asset registry, a savegame, CT or replay state.
    """
    checked = validate(recipe)
    root = Path(project_root).resolve(strict=True)
    issues = []
    frame_count = 0
    unique_sources = set()

    def issue(code, variant, action="", direction="", detail=""):
        issues.append({"code": code, "variant": variant, "action": action,
                       "direction": direction, "detail": detail})

    for variant, data in sorted(checked["variants"].items()):
        clips = data["clips"]
        sequences = {d: {} for d in DIRECTIONS}
        for action in ACTIONS:
            clip = clips.get(action)
            if clip is None:
                issue("missing_action", variant, action)
                continue
            if clip["loop"] is not (action in LOOP_ACTIONS):
                issue("loop_policy", variant, action, detail="unexpected loop flag")
            for direction in DIRECTIONS:
                frames = clip["directions"].get(direction)
                if not frames:
                    issue("missing_direction", variant, action, direction)
                    continue
                if len(frames) < 2:
                    issue("static_clip", variant, action, direction,
                          "at least two frames needed for an animated action")
                digests = []
                for index, frame in enumerate(frames):
                    frame_count += 1
                    try:
                        digest = _pixel_digest(root, frame)
                    except (OSError, ValueError) as exc:
                        issue("invalid_frame", variant, action, direction,
                              f"frame {index}: {exc}")
                    else:
                        digests.append(digest)
                        unique_sources.add(frame["path"])
                if len(digests) != len(frames):
                    continue
                if len(set(digests)) < 2:
                    issue("duplicate_pixels", variant, action, direction,
                          "clip contains no visual motion")
                sequences[direction][action] = tuple(digests)
        for direction, actions in sequences.items():
            for action, sequence in actions.items():
                others = set().union(*(set(seq) for name, seq in actions.items()
                                        if name != action))
                if set(sequence) <= others:
                    issue("recycled_action", variant, action, direction,
                          "no pose unique to this action")
        for action in ACTIONS:
            directional = [(d, sequences[d][action]) for d in DIRECTIONS
                           if action in sequences[d]]
            for index, (left, sequence) in enumerate(directional):
                for right, other in directional[index + 1:]:
                    if sequence == other:
                        issue("recycled_direction", variant, action, right,
                              f"identical frame sequence to {left}")

    return {
        "schema_version": 1,
        "character_id": checked["id"],
        "status": "passed_structural_pixel" if not issues else "blocked",
        "variants_checked": len(checked["variants"]),
        "frames_checked": frame_count,
        "source_files_checked": len(unique_sources),
        "issues": issues,
        "human_art_approval": "not_assessed",
        "redistribution_rights": "not_assessed",
        "studio_player_parity": "not_assessed",
    }


def audit_watercolor_rights(pack_root: Path, *, require_rights: bool = True) -> dict:
    """Reuse the existing INT-03 gate rather than creating a competing license."""
    from scripts.certify_int03_assets import certify
    try:
        return certify(Path(pack_root), require_rights=require_rights)
    except (OSError, ValueError, KeyError) as exc:
        return {"status": "blocked", "reason": str(exc)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="R19 character animations and rights")
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--watercolor-root", type=Path)
    parser.add_argument("--require-rights", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.require_rights and args.watercolor_root is None:
        parser.error("--require-rights needs --watercolor-root")
    try:
        document = json.loads(args.recipe.read_text(encoding="utf-8"))
        result = audit_character(document, args.project_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"schema_version": 1, "status": "blocked",
                  "issues": [{"code": "invalid_recipe", "detail": str(exc)}]}
    if args.watercolor_root is not None:
        result["production_pack"] = audit_watercolor_rights(
            args.watercolor_root, require_rights=args.require_rights)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    pack = result.get("production_pack", {})
    return 0 if result["status"] == "passed_structural_pixel" and (
        not args.require_rights or pack.get("status") == "passed") else 1


if __name__ == "__main__":
    sys.exit(main())
