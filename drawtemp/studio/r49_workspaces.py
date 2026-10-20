"""R49.B1: safe per-workspace focus preferences for the Qt Creator Studio.

The preference is a *region*, never a QWidget address, a resource ID, a
document path or a selection. This avoids stale pointers when R1 replaces the
canonical AuthoringSession and Qt destroys lazy-loaded editor pages.
"""
from __future__ import annotations

from collections.abc import Mapping

from drawtemp.studio.r18_navigation import WORKSPACES

FOCUS_REGIONS = frozenset({
    "workspace", "search", "resources", "inspector", "diagnostics",
})
FALLBACK_REGIONS = (
    "workspace", "search", "resources", "inspector", "diagnostics",
)


def focus_settings_key(workspace: str) -> str:
    if workspace not in WORKSPACES:
        raise ValueError("Unknown workspace: " + str(workspace))
    return "ux/r49/focus/" + workspace


class WorkspaceFocusMemory:
    """Validated ephemeral state, optionally seeded from QSettings.

    No disk IO here. Qt callers persist only validated region values.
    Unsupported values from old/corrupt settings are ignored, not interpreted
    as QWidget paths/object names.
    """

    def __init__(self, stored: Mapping[str, object] | None = None):
        self._regions: dict[str, str] = {}
        if stored is None:
            return
        if not isinstance(stored, Mapping):
            raise TypeError("Focus preferences must be a mapping")
        for workspace in WORKSPACES:
            value = stored.get(workspace)
            if isinstance(value, str) and value in FOCUS_REGIONS:
                self._regions[workspace] = value

    def remember(self, workspace: str, region: str) -> bool:
        focus_settings_key(workspace)
        if not isinstance(region, str) or region not in FOCUS_REGIONS:
            raise ValueError("Unknown focus region: " + str(region))
        changed = self._regions.get(workspace) != region
        self._regions[workspace] = region
        return changed

    def preferred(self, workspace: str) -> str | None:
        focus_settings_key(workspace)
        return self._regions.get(workspace)

    def resolve(self, workspace: str, available) -> str | None:
        """Choose a usable region without creating/opening a missing widget.

        Callers supply only regions whose Qt widgets actually exist, are
        enabled and visible. Empty sets never force focus to an invisible dock.
        """
        focus_settings_key(workspace)
        if isinstance(available, (str, bytes)):
            raise TypeError("available must contain region IDs")
        candidates = frozenset(available)
        if not candidates.issubset(FOCUS_REGIONS):
            raise ValueError("Unknown available focus region")
        preferred = self._regions.get(workspace)
        if preferred in candidates:
            return preferred
        return next((item for item in FALLBACK_REGIONS if item in candidates), None)

    def snapshot(self) -> dict[str, str]:
        return self._regions.copy()
