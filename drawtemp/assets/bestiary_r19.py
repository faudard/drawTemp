"""R19.B3: honest 4-view bestiary intake, quality gate and canonical R7 export.

NO single-angle watercolor is declared directional. A candidate requires
independently supplied PNGs for every named orientation/action. The input is
an editable art folder; rights and human art approval are NEVER inferred.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile

from .characters import ACTIONS, DIRECTIONS, CharacterError, export_pack, frame, validate

# Eight production targets; the actions reflect their actual roles, but never
# introduce skills, hit points, CT rules or a new bestiary save schema.
ROLE_ACTIONS = {
    "wolf": ("idle", "walk", "attack", "hit", "death"),
    "bandit": ("idle", "walk", "attack", "block", "hit", "death"),
    "archer": ("idle", "walk", "attack", "hit", "death"),
    "spearman": ("idle", "walk", "attack", "block", "hit", "death"),
    "knight": ("idle", "walk", "attack", "block", "hit", "death"),
    "healer": ("idle", "walk", "magic", "hit", "death"),
    "officer": ("idle", "walk", "attack", "magic", "hit", "death"),
    "boss": ("idle", "walk", "attack", "magic", "block", "hit", "death"),
}
ROLE_LABELS = {
    "wolf": "Loup", "bandit": "Bandit", "archer": "Archer",
    "spearman": "Lancier", "knight": "Chevalier", "healer": "Soigneur",
    "officer": "Officier", "boss": "Boss",
}
SIZE = {name: (128 if name == "boss" else 64) for name in ROLE_ACTIONS}
LOOP_ACTIONS = frozenset(("idle", "walk", "run"))


def role_recipe(role):
    """A portable R7 v1 recipe with explicit, editable file-per-frame sources.

    All directions must be supplied. These references are requirements,
    not automatically generated artwork or implied licences.
    """
    if role not in ROLE_ACTIONS:
        raise CharacterError("Unsupported R19 bestiary role")
    side = SIZE[role]
    clips = {
        action: {
            "loop": action in LOOP_ACTIONS,
            "directions": {
                direction: [
                    frame(f"{role}/{direction}/{action}_{i}.png",
                          duration_ms=170 if action != "death" else 230)
                    for i in range(2)]
                for direction in DIRECTIONS
            },
        }
        for action in ROLE_ACTIONS[role]
    }
    return validate({
        "version": 1, "id": role, "name": ROLE_LABELS[role],
        "size": [side, side], "pivot": [side // 2, side - 1],
        "variants": {"default": {
            "name": "Base", "clips": clips, "layers": [], "expressions": {},
        }},
    })


def _decoded_frame(root, relative, side):
    """Load PNG with strict regular-file path and pixel bounds; no alias."""
    from PIL import Image

    if not isinstance(relative, str) or "\\" in relative:
        raise ValueError("Non-portable path")
    parts = Path(relative).parts
    if not parts or any(part in ("..", ".") for part in parts) or Path(relative).is_absolute():
        raise ValueError("Invalid source path")
    file = root.joinpath(*parts)
    if not file.is_file() or file.is_symlink():
        raise ValueError("missing, non-regular or symlinked PNG")
    current = file.parent
    while current != root:
        if current.is_symlink():
            raise ValueError("symlinked source parent")
        current = current.parent
    if not file.resolve().is_relative_to(root):
        raise ValueError("Asset outside source root")
    if file.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("PNG exceeds 32 MiB")
    try:
        with Image.open(file) as image:
            if image.format != "PNG" or image.size != (side, side):
                raise ValueError(f"Expected {side}x{side} PNG")
            rgba = image.convert("RGBA")
            rgba.load()
    except (OSError, SyntaxError) as exc:
        raise ValueError("Invalid PNG data") from exc
    if rgba.getchannel("A").getbbox() is None:
        raise ValueError("Blank sprite is not authored art")
    return rgba


def audit_role(root, role):
    """Report concrete blockers, including same/mirrored pixel sequences.

    Unlike R19.A's Jeanne-specific all-nine-action gate, a bestiary actor is
    checked for the *required actions of its role*. This is a structural pixel
    gate only; it makes no subjective claim that a hand-authored pose is good.
    """
    from PIL import ImageOps

    root = Path(root).resolve(strict=True)
    recipe = role_recipe(role)
    side = SIZE[role]
    issues, seen_pixels = [], {}
    total = 0

    def problem(code, action, direction, detail=""):
        issues.append({"code": code, "action": action,
                       "direction": direction, "detail": detail})

    for action in ROLE_ACTIONS[role]:
        seen_pixels[action] = {}
        for direction in DIRECTIONS:
            hashes, mirrors = [], []
            for entry in recipe["variants"]["default"]["clips"][action]["directions"][direction]:
                total += 1
                try:
                    image = _decoded_frame(root, entry["path"], side)
                except (OSError, ValueError) as exc:
                    problem("missing_or_invalid_frame", action, direction,
                            f"{entry['path']}: {exc}")
                    break
                hashes.append(sha256(image.tobytes()).hexdigest())
                mirrors.append(sha256(ImageOps.mirror(image).tobytes()).hexdigest())
            if len(hashes) != 2:
                continue
            if len(set(hashes)) != 2:
                problem("static_animation", action, direction,
                        "two independently changing poses required")
            seen_pixels[action][direction] = (tuple(hashes), tuple(mirrors))

    # Strong fail-closed test: identical or exact horizontal mirrors are never
    # renamed north/south or east/west. Independently painted work can still be
    # manually reviewed after passing this pixel gate.
    for action, views in seen_pixels.items():
        directions = list(views)
        for i, left in enumerate(directions):
            for right in directions[i + 1:]:
                lhash, lmirror = views[left]
                rhash, _ = views[right]
                if lhash == rhash:
                    problem("recycled_direction", action, right,
                            f"same PNG pixels as {left}")
                elif lmirror == rhash:
                    problem("mirrored_direction", action, right,
                            f"exact horizontal mirror of {left}")
    for direction in DIRECTIONS:
        actions = [(action, seen_pixels[action][direction][0])
                   for action in ROLE_ACTIONS[role]
                   if direction in seen_pixels[action]]
        for i, (left, lseq) in enumerate(actions):
            for right, rseq in actions[i + 1:]:
                if lseq == rseq:
                    problem("recycled_action", right, direction,
                            f"same PNG sequence as {left}")

    return {
        "schema_version": 1, "role": role, "status": "candidate_ready" if not issues else "blocked",
        "expected_frames": len(ROLE_ACTIONS[role]) * len(DIRECTIONS) * 2,
        "examined_frames": total, "issues": issues,
        "human_art_approval": "not_assessed",
        "redistribution_rights": "not_assessed",
        "studio_player_parity": "not_assessed",
    }


def audit_roster(root):
    """Complete roster visibility, including missing roles, never false green."""
    root = Path(root).resolve(strict=True)
    result = {}
    for role in ROLE_ACTIONS:
        result[role] = audit_role(root, role)
    return {"status": "candidate_ready" if all(
        r["status"] == "candidate_ready" for r in result.values()
    ) else "blocked", "roles": result,
            "redistribution_rights": "not_assessed"}


def export_role(root, output, role):
    """Opt-in standalone R7 runtime artifact; no in-place authored art rewrite."""
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise CharacterError("Output already exists: never overwrite reviewed artwork")
    if output == root or root.is_relative_to(output) or output.is_relative_to(root):
        raise CharacterError("Source and destination directories must be separate")
    report = audit_role(root, role)
    if report["status"] != "candidate_ready":
        raise CharacterError("Art cannot be exported: " + json.dumps(report["issues"][:8]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".r19-bestiary-", dir=output.parent) as temp:
        stage = Path(temp) / role
        stage.mkdir()
        recipe = role_recipe(role)
        export_pack(recipe, root, stage, strict=True)
        (stage / "bestiary-provenance.json").write_text(
            json.dumps({
                "version": 1, "role": role,
                "candidate_art": True, "human_art_approval": "pending",
                "redistribution_approved": False,
                "source_sha256": {
                    entry["path"]: sha256((root / entry["path"]).read_bytes()).hexdigest()
                    for action in ROLE_ACTIONS[role] for direction in DIRECTIONS
                    for entry in recipe["variants"]["default"]["clips"][action]["directions"][direction]
                },
            }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="R19.B3 directional bestiary gate")
    parser.add_argument("--source", required=True, type=Path,
                        help="Artist-authored folders role/direction/action_index.png")
    parser.add_argument("--role", choices=tuple(ROLE_ACTIONS))
    parser.add_argument("--output", type=Path,
                        help="Export one candidate role; must not yet exist")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if bool(args.output) and not args.role:
        parser.error("--output requires --role")
    try:
        result = (export_role(args.source, args.output, args.role)
                  if args.output else audit_role(args.source, args.role)
                  if args.role else audit_roster(args.source))
    except (OSError, ValueError) as exc:
        result = {"status": "blocked", "issues": [{"code": "audit_error", "detail": str(exc)}]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "candidate_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
