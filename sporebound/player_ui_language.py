"""Atomic UI language preference for the legacy Tk game, separate from saves."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile

from drawtemp.localization.ui import DEFAULT_LANGUAGE, LANGUAGES


class PlayerLanguageError(ValueError):
    """Invalid or unsafe Player language preference."""


def language_path(profile):
    profile = Path(profile)
    return profile.with_name(profile.name + ".ui-language.json")


def load_ui_language(profile):
    """Return (locale, diagnostic); never overwrite a malformed profile."""
    path = language_path(profile)
    if not path.exists() and not path.is_symlink():
        return DEFAULT_LANGUAGE, None
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            raise PlayerLanguageError("Unsafe or oversized locale preferences")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (type(data) is not dict or set(data) != {"version", "language"}
                or type(data["version"]) is not int or data["version"] != 1
                or type(data["language"]) is not str or data["language"] not in LANGUAGES):
            raise PlayerLanguageError("Unsupported locale preference")
        return data["language"], None
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return DEFAULT_LANGUAGE, str(exc)


def save_ui_language(profile, language):
    if type(language) is not str or language not in LANGUAGES:
        raise PlayerLanguageError("Unsupported language: " + str(language))
    path = language_path(profile)
    if path.is_symlink():
        raise PlayerLanguageError("Symlinked preference path refused")
    if path.exists() and load_ui_language(profile)[1] is not None:
        raise PlayerLanguageError("Cannot overwrite invalid locale preferences")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".player-language-", suffix=".tmp",
                                         dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"version": 1, "language": language}, output,
                      ensure_ascii=False, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return path
