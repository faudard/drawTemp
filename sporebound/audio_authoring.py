"""Validated sound authoring for GameProject assets; independent of Tk and pygame.

Sound paths are project-relative. Importing only copies WAV/OGG files into the
project and never changes tactical content, battle saves, or replay rules.
"""
from copy import deepcopy
from pathlib import Path
import shutil

from .assets import AssetRegistry, _identifier
from .game_project import GameProject
from .model import RuleError, require


def _edit(project, content, operation):
    data = deepcopy(project.to_dict() if isinstance(project, GameProject) else project)
    if not data.get("assets"):
        data["assets"] = AssetRegistry().to_dict()
    operation(data["assets"])
    return GameProject.from_dict(data, content)


def _signature_ok(path):
    with path.open("rb") as handle:
        header = handle.read(12)
    extension = path.suffix.lower()
    return ((extension == ".ogg" and header.startswith(b"OggS")) or
            (extension == ".wav" and header.startswith(b"RIFF") and
             header[8:12] == b"WAVE"))


def import_sound(project, content, source, asset_root, asset_id):
    """Import without overwriting existing files or mutating project on failure."""
    require(bool(_identifier(asset_id)), "Identifiant audio invalide")
    source = Path(source)
    require(source.is_file(), "Fichier sonore introuvable")
    require(source.suffix.lower() in (".ogg", ".wav"), "Format requis : WAV ou OGG")
    require(_signature_ok(source), "Signature de fichier WAV/OGG invalide")
    root = Path(asset_root).resolve()
    relative = f"assets/audio/{asset_id}{source.suffix.lower()}"
    target = root / relative
    require(target.parent.resolve().is_relative_to(root),
            "Le dossier audio sort du répertoire du projet")
    require(not target.exists() and not target.is_symlink(),
            "Un fichier audio de ce nom existe déjà")
    def update(assets):
        require(not any(entry["id"].casefold() == asset_id.casefold()
                        for entry in assets["entries"]),
                "Identifiant audio déjà utilisé")
        assets["entries"].append({"id": asset_id, "kind": "sound", "path": relative})
    updated = _edit(project, content, update)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents silent replacement of a user's sound.
    created = False
    try:
        with target.open("xb") as dest:
            created = True
            with source.open("rb") as inp:
                shutil.copyfileobj(inp, dest)
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return updated


def bind_sound(project, content, slot, asset_id=""):
    """Set or clear a presentation-only cue; no gameplay event changes."""
    require(bool(_identifier(slot)), "Nom de déclencheur audio invalide")
    def update(assets):
        bindings = assets["bindings"].setdefault("sound", {})
        if asset_id:
            bindings[slot] = asset_id
        else:
            bindings.pop(slot, None)
            if not bindings:
                assets["bindings"].pop("sound", None)
    return _edit(project, content, update)


def remove_sound(project, content, asset_id):
    """Remove a registry entry (never delete the actual file from disk)."""
    def update(assets):
        entry = next((e for e in assets["entries"] if e["id"] == asset_id), None)
        require(entry is not None and entry["kind"] == "sound",
                "Son introuvable dans la bibliothèque")
        require(asset_id not in assets["bindings"].get("sound", {}).values(),
                "Délier ce son de ses déclencheurs avant suppression")
        assets["entries"].remove(entry)
    return _edit(project, content, update)


def suggested_slots(content, project):
    """Discover mission and scene targets; custom event kinds remain editable."""
    scene_ids = [scene["id"] for scene in project.story.get("scenes", [])]
    music = ["title", "campaign", "battle"]
    music.extend(f"mission_{mid}" for mid in sorted(content.missions))
    music.extend(f"music_scene_{sid}" for sid in scene_ids)
    effects = ["attack", "move", "hit", "defeated", "interact"]
    effects.extend(f"scene_enter_{sid}" for sid in scene_ids)
    for slot in project.asset_registry().to_dict()["bindings"].get("sound", {}):
        if slot not in music and slot not in effects:
            effects.append(slot)
    return music, effects
