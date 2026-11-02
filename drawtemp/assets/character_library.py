"""Searchable character source library; no UI dependency.

Starter entries and project-owned .character.json documents use one recipe
format. Malformed files are skipped rather than crashing the editor.
"""
from __future__ import annotations

import json
from pathlib import Path
from .characters import validate

LIBRARY_FOLDERS = ("characters", "assets/characters", "assets/character_recipes")
MAX_LIBRARY_FILES = 512
MAX_RECIPE_BYTES = 2_000_000


def discover_character_library(root, starters):
    """Return {stable_key: (label, recipe)} without copying or changing files."""
    root = Path(root).resolve()
    result = {}
    for key, doc in starters.items():
        try:
            recipe = validate(doc)
        except (TypeError, KeyError, ValueError):
            continue
        result["starter:" + key] = (recipe["name"], recipe)
    for folder_name in LIBRARY_FOLDERS:
        folder = root / folder_name
        if not folder.is_dir() or not folder.resolve().is_relative_to(root):
            continue
        for path in sorted(folder.glob("*.character.json"))[:MAX_LIBRARY_FILES]:
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    continue
                if resolved.stat().st_size > MAX_RECIPE_BYTES:
                    continue
                recipe = validate(json.loads(resolved.read_text(encoding="utf-8")))
                key = "file:" + resolved.relative_to(root).as_posix()
                result[key] = (recipe["name"], recipe)
            except (OSError, TypeError, KeyError, ValueError, UnicodeError):
                continue
    return result


def search_characters(library, query):
    """Filter by display name or ID; stable order for large libraries."""
    words = tuple(query.strip().casefold().split())
    return tuple(
        (key, label) for key, (label, recipe) in
        sorted(library.items(), key=lambda row: (row[1][0].casefold(), row[0]))
        if all(term in (key + " " + label + " " + recipe["id"]).casefold()
               for term in words)
    )
