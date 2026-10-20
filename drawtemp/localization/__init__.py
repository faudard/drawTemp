"""R57 optional localization contract; never changes headless gameplay state."""
from .r57 import (
    Catalog, LocalizationError, file_revision, localize_view, seeded_for_project, sidecar_path,
)

__all__ = (
    "Catalog", "LocalizationError", "file_revision", "localize_view", "seeded_for_project",
    "sidecar_path",
)
