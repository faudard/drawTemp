"""R57 optional localization contract; never changes headless gameplay state."""
from .ui import DEFAULT_LANGUAGE, LANGUAGES as UI_LANGUAGES, normalize_language, ui_text
from .r57 import (
    Catalog, LocalizationError, file_revision, localize_view, rebase_project_sources, seeded_for_project, sidecar_path,
)

__all__ = (
    "Catalog", "LocalizationError", "file_revision", "localize_view", "rebase_project_sources", "seeded_for_project",
    "sidecar_path", "DEFAULT_LANGUAGE", "UI_LANGUAGES", "normalize_language", "ui_text",
)
