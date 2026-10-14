"""Default save profile path with an explicit, non-destructive legacy fallback."""

from pathlib import Path


def default_profile_path(project_path):
    """Choose DrawTemp's save location; keep existing Sporebound saves accessible.

    Session and campaign slots are stored next to the profile using suffix
    directories, so checking the profile JSON alone would miss real saves.
    A newer DrawTemp profile always takes priority if both locations exist.
    The helper never moves, deletes or writes data.
    """
    project_name = Path(project_path).name
    current = Path.home() / ".drawtemp" / project_name
    legacy = Path.home() / ".sporebound" / project_name

    def has_saves(profile):
        return any(path.exists() for path in (
            profile,
            profile.with_name(profile.stem + "_saves"),
            profile.with_name(profile.stem + "_session_saves"),
        ))

    if has_saves(legacy) and not has_saves(current):
        return legacy
    return current
