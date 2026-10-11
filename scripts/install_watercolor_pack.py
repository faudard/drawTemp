"""Install the 88-sprite watercolor ZIP into an isolated Jeanne Player project.

Example:
    python scripts/install_watercolor_pack.py --bundle drawTemp_assets_Jeanne_88_sprites_v2.zip \
      --content sporebound/content/jeanne.json \
      --project sporebound/content/jeanne.game.json \
      --output /tmp/jeanne-art-demo
    python -m sporebound player --content /tmp/jeanne-art-demo/jeanne.json \
      --project /tmp/jeanne-art-demo/jeanne.game.json

Source files and original game projects are never modified.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
from tempfile import TemporaryDirectory
import zipfile

# Support the documented "python scripts/install_watercolor_pack.py" command
# without requiring an editable pip install of sporebound.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREFIX = "assets/watercolor/"
ACTORS = {
    "jeanne": "jeanne_idle",
    "renaud_mentor": "townfolk_royal_knight",
    "pillard_1": "soldiers_bandit", "pillard_2": "soldiers_bandit",
    "raider_secours_1": "soldiers_bandit",
    "raider_secours_2": "soldiers_bandit",
    "margot": "townfolk_militia_axewoman",
    "messager": "townfolk_messenger",
    "garde_messager": "soldiers_spearman",
    "refugie": "townfolk_scout",
    "guetteur_route": "soldiers_ranger",
    "etienne": "heroes_knight_captain",
    "agnes": "heroes_healer",
    "eclaireur_rouge": "soldiers_ranger",
    "brigand_route": "soldiers_bandit",
    "lancier_pont": "spearman_idle",
    "arbaletrier_pont": "soldiers_crossbowman",
    "bandit_hospice": "soldiers_bandit",
    "arbaletrier_hospice": "soldiers_crossbowman",
    "clerc_armes": "townfolk_royal_knight",
    "bailli_soldat": "soldiers_spearman",
    "otage_anne": "townfolk_messenger",
    "geolier": "soldiers_heavy_guard",
    "garde_otages": "soldiers_spearman",
    "capitaine_porte": "heroes_red_knight",
    "garde_porte": "soldiers_spearman",
    "archer_rempart": "soldiers_ranger",
}
MOTION = {
    "jeanne": {"move": "anim_jeanne_walk", "attack": "anim_jeanne_attack",
               "hit": "anim_jeanne_hit", "defeat": "anim_jeanne_ko"},
    "lancier_pont": {"move": "anim_spearman_walk",
                     "attack": "anim_spearman_attack",
                     "defeat": "anim_spearman_ko"},
}


def _read_json(archive, path):
    try:
        return json.loads(archive.read(path).decode("utf-8"))
    except KeyError as exc:
        raise ValueError(f"Missing ZIP manifest: {path}") from exc


def validate_bundle(archive):
    """Verify the entire reusable asset registry and every extracted PNG.

    No archive member is extracted until preflight has checked path safety,
    unique paths/IDs, dimensions and plausible decompressed byte sizes.
    Files outside the allowlist are ignored, never extracted.
    """
    import struct
    from sporebound.assets import AssetRegistry

    index = _read_json(archive, PREFIX + "index.json")
    registry = _read_json(archive, PREFIX + "registry.json")
    if not isinstance(index, dict) or not isinstance(registry, dict):
        raise ValueError("Watercolor manifests must be objects")
    if index.get("schema_version") != 1:
        raise ValueError("Unsupported watercolor index schema")
    # Enforce all typed references, including unknown animation frame IDs.
    AssetRegistry(registry)
    sprites = index.get("sprites")
    entries = registry.get("entries")
    if not isinstance(sprites, list) or len(sprites) != 88:
        raise ValueError("Expected 88 indexed sprites")
    if len(entries) != 103 or sum(e["kind"] == "animation" for e in entries) != 15:
        raise ValueError("Expected 88 sprites and 15 animations")
    sprite_entries = {e["id"]: e for e in entries if e["kind"] == "sprite"}
    if len(sprite_entries) != 88:
        raise ValueError("Incomplete sprite registry")

    # A ZIP may contain duplicate names; ZipFile.getinfo() would silently
    # return just the last entry. Reject ambiguity for all expected assets.
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("Duplicate ZIP member")
    members, seen_paths, seen_ids = [], set(), set()
    total = 0
    for item in sprites:
        if not isinstance(item, dict):
            raise ValueError("Invalid indexed sprite")
        path, asset_id = item.get("path"), item.get("id")
        if not isinstance(path, str) or not isinstance(asset_id, str):
            raise ValueError("Invalid sprite path or ID")
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or
                len(relative.parts) != 3 or relative.parts[0] != "sprites" or
                relative.suffix != ".png" or str(relative) != path):
            raise ValueError(f"Invalid sprite path: {path}")
        if path.casefold() in seen_paths or asset_id.casefold() in seen_ids:
            raise ValueError("Duplicate indexed sprite path or ID")
        seen_paths.add(path.casefold())
        seen_ids.add(asset_id.casefold())
        spec = sprite_entries.get(asset_id)
        if spec is None or spec["path"] != path:
            raise ValueError("Sprite index/registry mismatch")
        name = PREFIX + path
        try:
            info = archive.getinfo(name)
        except KeyError as exc:
            raise ValueError(f"Missing sprite: {name}") from exc
        if info.flag_bits & 1:
            raise ValueError(f"Encrypted ZIP member: {name}")
        if not 33 <= info.file_size <= 15_000_000:
            raise ValueError(f"Invalid PNG byte size: {name}")
        total += info.file_size
        if total > 300_000_000:
            raise ValueError("Watercolor pack exceeds 300MB expanded size")
        # Verify PNG signature and IHDR dimensions without Pillow.
        with archive.open(info) as stream:
            header = stream.read(24)
        if (header[:8] != b"\x89PNG\r\n\x1a\n" or
                header[12:16] != b"IHDR" or header[8:12] != b"\x00\x00\x00\x0d"):
            raise ValueError(f"Invalid PNG header: {name}")
        width, height = struct.unpack(">II", header[16:24])
        if not (1 <= width <= 4096 and 1 <= height <= 4096):
            raise ValueError(f"Invalid sprite dimensions: {name}")
        frame_size = item.get("frame_size")
        if frame_size is not None and frame_size != [width, height]:
            raise ValueError(f"Sprite dimensions mismatch: {name}")
        members.append(name)
    if seen_ids != {id_.casefold() for id_ in sprite_entries}:
        raise ValueError("Index does not cover registered sprites")
    return entries, members


def install(bundle, content, project, output):
    """Write a relocatable demo containing source content, assets, and bindings."""
    bundle, content, project, output = map(Path, (bundle, content, project, output))
    if output.exists():
        raise FileExistsError(f"Destination already exists: {output}")
    content_obj = json.loads(content.read_text(encoding="utf-8"))
    game = json.loads(project.read_text(encoding="utf-8"))
    actors = {unit["id"] for mission in content_obj["missions"]
              for unit in mission.get("units", [])}
    if not {"jeanne", "lancier_pont"}.issubset(actors):
        raise ValueError("This demo expects the Jeanne campaign")
    assets = deepcopy(game.get("assets") or
                      {"version": 1, "entries": [], "bindings": {}})
    if assets.get("version") != 1:
        raise ValueError("Unsupported asset registry")
    with zipfile.ZipFile(bundle) as archive:
        entries, members = validate_bundle(archive)
        used = {e["id"].casefold() for e in assets["entries"]}
        if used & {e["id"].casefold() for e in entries}:
            raise ValueError("Conflicting asset IDs in game project")
        for entry in entries:
            entry = deepcopy(entry)
            if entry["kind"] == "sprite":
                entry["path"] = PREFIX + entry["path"]
            assets["entries"].append(entry)
        # Preserve the canonical project's existing atlases/portraits.
        # They remain referenced by the unchanged presentation metadata.
        from sporebound.assets import AssetRegistry
        source_registry = AssetRegistry(game.get("assets") or None)
        source_files = {}
        for original in source_registry.to_dict()["entries"]:
            if original["kind"] != "animation":
                source_files[original["path"]] = source_registry.resolve(
                    original["id"], project.parent)
        imported_paths = {PREFIX + e["path"] for e in entries
                          if e["kind"] == "sprite"}
        if set(source_files).intersection(imported_paths):
            raise ValueError("Artwork ZIP conflicts with an existing asset path")

        bindings = assets.setdefault("bindings", {})
        statics = bindings.setdefault("sprite", {})
        motions = bindings.setdefault("animation", {})
        for actor, sprite in ACTORS.items():
            if actor in actors:
                # A standalone watercolor demo must show the requested new art.
                # The original campaign file remains untouched.
                if actor == "jeanne":
                    statics[actor] = sprite
                else:
                    statics.setdefault(actor, sprite)
        for actor, actions in MOTION.items():
            if actor not in actors:
                continue
            for action, aid in actions.items():
                motions[f"{actor}_{action}"] = aid
            if actor == "jeanne":
                # Existing directional bindings outrank the generic slot in
                # visual_motion.animation_sprite_id; override only in this
                # isolated preview. The source PNG is single-view, so all
                # direction aliases intentionally share the same frame.
                for direction in ("north", "south", "east", "west"):
                    motions.pop(f"jeanne_idle_{direction}", None)
                    for action, aid in actions.items():
                        motions[f"jeanne_{action}_{direction}"] = aid
        registry = AssetRegistry(assets)
        game["assets"] = assets
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".watercolor-", dir=output.parent) as tmp:
            stage = Path(tmp) / "game"
            stage.mkdir()
            # Copy every previously-referenced local asset into the demo so
            # its original portraits and direction atlases still validate.
            for relative, source in source_files.items():
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            for member in members + [PREFIX + "index.json", PREFIX + "registry.json"]:
                dest = stage / member
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, dest.open("wb") as target:
                    shutil.copyfileobj(source, target)
            shutil.copyfile(content, stage / "jeanne.json")
            (stage / "jeanne.game.json").write_text(
                json.dumps(game, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            errors = registry.diagnostics(stage)
            if errors:
                raise ValueError(f"Invalid installed assets: {errors[:3]}")
            stage.rename(output)
    return output / "jeanne.game.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(install(args.bundle, args.content, args.project, args.output))


if __name__ == "__main__":
    main()
