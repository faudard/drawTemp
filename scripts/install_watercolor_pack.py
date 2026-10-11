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
from tempfile import TemporaryDirectory
import zipfile

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
    """Validate all expected assets and reject unsafe paths before extraction."""
    index = _read_json(archive, PREFIX + "index.json")
    registry = _read_json(archive, PREFIX + "registry.json")
    if index.get("schema_version") != 1 or registry.get("version") != 1:
        raise ValueError("Unsupported watercolor pack schema")
    sprites = index.get("sprites", [])
    entries = registry.get("entries", [])
    if len(sprites) != 88 or len(entries) != 103:
        raise ValueError("Expected 88 sprites and 15 animations")
    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate sprite/animation asset IDs")
    sprite_entries = {entry["id"]: entry for entry in entries
                      if entry["kind"] == "sprite"}
    if len(sprite_entries) != 88:
        raise ValueError("Incomplete sprite registry")
    members = []
    for item in sprites:
        path = item["path"]
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or
                len(relative.parts) != 3 or relative.parts[0] != "sprites" or
                relative.suffix != ".png" or str(relative) != path):
            raise ValueError(f"Invalid sprite path: {path}")
        if item["id"] not in sprite_entries or sprite_entries[item["id"]]["path"] != path:
            raise ValueError("Sprite index/registry mismatch")
        name = PREFIX + path
        try:
            info = archive.getinfo(name)
        except KeyError as exc:
            raise ValueError(f"Missing sprite: {name}") from exc
        if not 24 <= info.file_size <= 15_000_000:
            raise ValueError(f"Invalid PNG size: {name}")
        with archive.open(info) as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"Invalid PNG signature: {name}")
        members.append(name)
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
        bindings = assets.setdefault("bindings", {})
        statics = bindings.setdefault("sprite", {})
        motions = bindings.setdefault("animation", {})
        for actor, sprite in ACTORS.items():
            if actor in actors:
                statics.setdefault(actor, sprite)
        for actor, actions in MOTION.items():
            if actor in actors:
                for action, aid in actions.items():
                    motions.setdefault(f"{actor}_{action}", aid)
        from sporebound.assets import AssetRegistry
        registry = AssetRegistry(assets)
        game["assets"] = assets
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".watercolor-", dir=output.parent) as tmp:
            stage = Path(tmp) / "game"
            stage.mkdir()
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
