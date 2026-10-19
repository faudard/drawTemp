"""R18 Studio navigation and recent-project policy, independent of Qt.

The current project remains the sole R1 AuthoringSession owner. Navigation
aliases never create additional document or rendering models.
"""
from __future__ import annotations

import os
from pathlib import Path

WORKSPACES = (
    "project", "profiles", "gameplay", "maps", "construction", "actors", "database", "events",
    "campaigns", "cinematics", "analysis", "publication",
)
LABELS = {
    "project": "Projet", "profiles": "Profils de jeu", "gameplay": "Gameplay", "maps": "Carte", "construction": "Construction",
    "actors": "Personnages", "database": "Base RPG", "events": "Événements",
    "campaigns": "Campagne", "cinematics": "Cinématiques",
    "analysis": "Analyse", "publication": "Publication",
}
EN = {
    "project": "Project", "profiles": "Game profiles", "gameplay": "Gameplay", "maps": "Map", "construction": "Construction",
    "actors": "Characters", "database": "RPG Database", "events": "Events",
    "campaigns": "Campaign", "cinematics": "Cinematics",
    "analysis": "Analysis", "publication": "Publish",
}
RECENT_LIMIT = 8


def workspace_host(identifier: str) -> str:
    """Construction is a mode of the *same* R5/R6 map workspace."""
    if identifier not in WORKSPACES:
        raise ValueError("Unknown workspace: " + str(identifier))
    return "maps" if identifier == "construction" else identifier


def recent_projects(stored, *, selected=None, limit=RECENT_LIMIT):
    """Newest-first canonical file paths without duplicates.

    Return missing paths too: the UI can offer an explicit recovery action
    rather than silently forgetting an unavailable external drive.
    """
    if isinstance(stored, (str, Path)):
        stored = [stored]
    candidates = ([selected] if selected else []) + list(stored or [])
    results = []
    seen = set()
    for candidate in candidates:
        if not candidate or not str(candidate).strip():
            continue
        try:
            absolute = str(Path(candidate).expanduser().resolve(strict=False))
        except (OSError, RuntimeError, ValueError, TypeError):
            continue
        key = os.path.normcase(absolute)
        if key in seen:
            continue
        seen.add(key)
        results.append(absolute)
        if len(results) == limit:
            break
    return results
