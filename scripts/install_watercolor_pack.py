"""Opt-in install of the Jeanne watercolor ZIP in a relocatable Player demo.

The source project and source content are never mutated.  No optional
image-processing dependencies or GUI are required for installation.

python scripts/install_watercolor_pack.py \
  --bundle drawTemp_assets_Jeanne_88_sprites.zip \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.game.json \
  --output /tmp/jeanne-watercolor-demo
python -m sporebound player --content /tmp/jeanne-watercolor-demo/jeanne.json \
  --project /tmp/jeanne-watercolor-demo/jeanne.game.json
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
    "raider_secours_1": "soldiers_bandit", "raider_secours_2": "soldiers_bandit",
    "margot": "townfolk_militia_axewoman", "messager": "townfolk_messenger",
    "garde_messager": "soldiers_spearman", "refugie": "townfolk_scout",
    "guetteur_route": "soldiers_ranger", "etienne": "heroes_knight_captain",
    "agnes": "heroes_healer", "eclaireur_rouge": "soldiers_ranger",
    "brigand_route": "soldiers_bandit", "lancier_pont": "spearman_idle",
    "arbaletrier_pont": "soldiers_crossbowman",
    "bandit_hospice": "soldiers_bandit",
    "arbaletrier_hospice": "soldiers_crossbowman",
    "clerc_armes": "townfolk_royal_knight", "bailli_soldat": "soldiers_spearman",
    "otage_anne": "townfolk_messenger", "geolier": "soldiers_heavy_guard",
    "garde_otages": "soldiers_spearman", "capitaine_porte": "heroes_red_knight",
    "garde_porte": "soldiers_spearman", "archer_rempart": "soldiers_ranger",
}
MOTION = {
    "jeanne": {"move": "anim_jeanne_walk", "attack": "anim_jeanne_attack",
               "hit": "anim_jeanne_hit", "defeat": "anim_jeanne_ko"},
    "lancier_pont": {"move": "anim_spearman_walk", "attack": "anim_spearman_attack",
                     "defeat": "anim_spearman_ko"},
}


def _json_from_zip(archive, name):
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except KeyError as exc:
        raise ValueError(f"Missing ZIP manifest: {name}") from exc


def _validated_bundle(archive):
    index = _json_from_zip(archive, PREFIX + "index.json")
    manifest = _json_from_zip(archive, PREFIX + "registry.json")
    if index.get("schema_version") != 1 or manifest.get("version") != 1:
        raise ValueError("Unexpected watercolor manifest version")
    sprites = index.get("sprites")
    if not isinstance(sprites, list) or len(sprites) != 88:
        raise ValueError("Expected exactly 88 sprites")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != 103:
        raise ValueError("Expected 88 sprites and 15 animations")
    ids = [e.get("id") for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate asset ID in pack")
    members = []
    for item in sprites:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Invalid sprite descriptor")
        relative = PurePosixPath(item["path"])
        if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 3
                or relative.parts[0] != "sprites" or relative.suffix.lower() != ".png"
                or str(relative) != item["path"]):
            raise ValueError(f"Unsafe sprite path: {item['path']}")
        name = PREFIX + item["path"]
        info = archive.getinfo(name)  # Raise if an expected PNG is absent.
        if info.file_size <= 24 or info.file_size > 15_000_000:
            raise ValueError(f"Unexpected PNG size: {name}")
        with archive.open(info) as image:
            if image.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"Not PNG: {name}")
        members.append(name)
    from_manifest = {e["id"]: e for e in entries if e["kind"] == "sprite"}
    if len(from_manifest) != 88:
        raise ValueError("Pack sprite count mismatch")
    if {i["id"] for i in sprites} != set(from_manifest):
        raise ValueError("Pack sprite IDs mismatch")
    for item in sprites:
        if item["path"] != from_manifest[item["id"]]["path"]:
            raise ValueError("Pack sprite paths mismatch")
    if not isinstance(manifest.get("bindings"), dict):
        raise ValueError("Invalid asset binding groups")
    return entries, members


def install(bundle, content, project, output):
    """Create a standalone game copy with all sprites and active Player bindings."""
    bundle, content, project, output = map(Path, (bundle, content, project, output))
    # Preflight all arguments before writing anything.
    if output.exists():
        raise FileExistsError(f"Destination already exists: {output}")
    game = json.loads(project.read_text(encoding="utf-8"))
    data = json.loads(content.read_text(encoding="utf-8"))
    actor_ids = {actor["id"] for mission in data["missions"]
                 for actor in mission.get("units", [])}
    if not {"jeanne", "lancier_pont"}.issubset(actor_ids):
        raise ValueError("This example expects the Jeanne campaign")
    existing = game.get("assets") or {"version": 1, "entries": [], "bindings": {}}
    if existing.get("version") != 1:
        raise ValueError("Unsupported existing asset manifest")
    with zipfile.ZipFile(bundle) as archive:
        entries, members = _validated_bundle(archive)
        reserved = {entry["id"].casefold() for entry in existing["entries"]}
        if reserved & {entry["id"].casefold() for entry in entries}:
            raise ValueError("Conflicting asset IDs in existing project")
        merged = deepcopy(existing)
        for entry in entries:
            entry = deepcopy(entry)
            if entry["kind"] == "sprite":
                entry["path"] = PREFIX + entry["path"]
            merged["entries"].append(entry)
        # Bind static sprites and motion to exact actor IDs used in Jeanne.
        bindings = merged.setdefault("bindings", {})
        static = bindings.setdefault("sprite", {})
        animation = bindings.setdefault("animation", {})
        for actor, aid in ACTORS.items():
            if actor in actor_ids:
                static.setdefault(actor, aid)
        for actor, moves in MOTION.items():
            if actor in actor_ids:
                for action, aid in moves.items():
                    animation.setdefault(f"{actor}_{action}", aid)
        game["assets"] = merged
        # Validate the schema before writing a project on disk.
        from sporebound.assets import AssetRegistry
        registry = AssetRegistry(merged)
        # Stage all files, then rename.  An interrupted import leaves no half-project.
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".jeanne-art-", dir=output.parent) as folder:
            stage = Path(folder) / "project"
            stage.mkdir()
            for name in members:
                dest = stage / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, dest.open("wb") as target:
                    shutil.copyfileobj(source, target)
            # Retain provenance and a reusable standalone manifest alongside art.
            for manifest_name in ('index.json', 'registry.json'):
                with archive.open(PREFIX + manifest_name) as source, (stage / PREFIX / manifest_name).open('wb') as target:
                    shutil.copyfileobj(source, target)
            shutil.copy2(content, stage / "jeanne.json")
            (stage / "jeanne.game.json").write_text(
                json.dumps(game, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            failures = registry.diagnostics(stage)
            if failures:
                raise ValueError(f"Invalid installed assets: {failures[:3]}")
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
