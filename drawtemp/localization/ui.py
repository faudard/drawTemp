"""UI language catalogs stored as JSON resources, shared by Studio and Player.

The interface language is not the authoring source language and never changes
gameplay state, canonical saves, replay digests, or R57 story translations.
Only this loading/validation code lives in Python; translated labels are JSON.
"""
from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import json
import re
from string import Formatter

DEFAULT_LANGUAGE = "en"
_LOCALE_CODE = re.compile(r"[a-z]{2}(?:-[A-Za-z0-9]{2,8})?\Z")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}\Z")
_FIELD = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*\Z")


class UiLocalizationError(ValueError):
    """Invalid manifest or locale JSON; do not silently ship bad catalogs."""


def _no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise UiLocalizationError("Duplicate localization JSON key: " + key)
        value[key] = item
    return value


def _read_resource(filename):
    try:
        raw = files("drawtemp.localization").joinpath("locales", filename).read_text(encoding="utf-8")
        if len(raw) > 1_000_000:
            raise UiLocalizationError("Localization file exceeds 1 MB: " + filename)
        return json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UiLocalizationError("Cannot load localization file: " + filename) from exc


@lru_cache(maxsize=1)
def _manifest():
    doc = _read_resource("manifest.json")
    if (type(doc) is not dict or set(doc) != {"version", "default", "languages"}
            or type(doc["version"]) is not int or doc["version"] != 1
            or doc["default"] != DEFAULT_LANGUAGE
            or type(doc["languages"]) is not list or not doc["languages"]):
        raise UiLocalizationError("Invalid localization manifest")
    seen = set()
    for entry in doc["languages"]:
        if (type(entry) is not dict or set(entry) != {"code", "name"}
                or type(entry["code"]) is not str or not _LOCALE_CODE.fullmatch(entry["code"])
                or type(entry["name"]) is not str or not entry["name"].strip()
                or entry["code"] in seen):
            raise UiLocalizationError("Invalid or duplicate locale in manifest")
        seen.add(entry["code"])
    if DEFAULT_LANGUAGE not in seen:
        raise UiLocalizationError("English default missing from manifest")
    return doc


def language_choices():
    """Installed UI languages as (locale, display name) pairs; driven by manifest."""
    return tuple((item["code"], item["name"]) for item in _manifest()["languages"])


LANGUAGES = tuple(code for code, _ in language_choices())


def normalize_language(language):
    """Never guess from system locale; unsupported UI codes use English."""
    return language if type(language) is str and language in LANGUAGES else DEFAULT_LANGUAGE


def _placeholders(template):
    try:
        fields = set()
        for _literal, field, fmt, conversion in Formatter().parse(template):
            if field is not None:
                if not _FIELD.fullmatch(field) or fmt or conversion:
                    raise UiLocalizationError("Only simple {name} placeholders are allowed")
                fields.add(field)
        return fields
    except ValueError as exc:
        raise UiLocalizationError("Unbalanced braces in UI translation") from exc


@lru_cache(maxsize=32)
def get_catalog(language):
    """Validated immutable-resource UI messages; cached for every render."""
    code = normalize_language(language)
    doc = _read_resource(code + ".json")
    if (type(doc) is not dict or set(doc) != {"version", "locale", "strings"}
            or type(doc["version"]) is not int or doc["version"] != 1
            or doc["locale"] != code or type(doc["strings"]) is not dict
            or len(doc["strings"]) > 3000):
        raise UiLocalizationError("Invalid UI catalogue structure: " + code)
    for key, value in doc["strings"].items():
        if (type(key) is not str or not _KEY.fullmatch(key)
                or type(value) is not str or not value or len(value) > 2000):
            raise UiLocalizationError("Invalid UI translation entry: " + str(key))
        _placeholders(value)
    if code != DEFAULT_LANGUAGE:
        english = get_catalog(DEFAULT_LANGUAGE)
        for key, value in doc["strings"].items():
            if key not in english:
                raise UiLocalizationError("Locale has unknown UI key: " + key)
            if _placeholders(value) != _placeholders(english[key]):
                raise UiLocalizationError("Different placeholders for " + key + " in " + code)
    return doc["strings"]


def audit_catalogs():
    """Return missing keys per language; raise on invalid keys or placeholders."""
    source = get_catalog(DEFAULT_LANGUAGE)
    return {code: sorted(set(source) - set(get_catalog(code)))
            for code in LANGUAGES if code != DEFAULT_LANGUAGE}


def ui_text(key, language=DEFAULT_LANGUAGE, **values):
    """Resolve an interface label, falling back to English for untranslated keys."""
    if not isinstance(key, str):
        raise UiLocalizationError("UI key must be a string")
    source = get_catalog(DEFAULT_LANGUAGE).get(key, key)
    translated = get_catalog(language).get(key, source)
    required = _placeholders(translated)
    if required - values.keys():
        raise UiLocalizationError("Missing UI translation parameters: " + key)
    return translated.format_map({name: values[name] for name in required})
