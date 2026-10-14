"""Headless editor view identifiers shared by legacy and Qt-facing SDK.

These are presentation channel names only. No importing controller, renderer
or GUI code is allowed from this module.
"""

RENDERER = "renderer"
MINIMAP = "minimap"
INSPECTOR = "inspector"
WORKSPACE = "workspace"
ALL_VIEWS = (RENDERER, MINIMAP, INSPECTOR, WORKSPACE)

__all__ = ["RENDERER", "MINIMAP", "INSPECTOR", "WORKSPACE", "ALL_VIEWS"]
