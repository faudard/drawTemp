"""R57.A: versioned, optional and deterministic localization sidecar.

Presentation is kept out of the canonical GameSession, Content and save/replay
contracts. An absent sidecar changes nothing about historical games.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from string import Formatter
import tempfile

FORMAT = "drawtemp.localization"
VERSION = 1
LANGUAGES = frozenset(("fr", "en"))
PSEUDO_LANGUAGES = frozenset(("qps-ploc", "qps-plocm"))
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
PARAM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ACCENTS = str.maketrans("aeiouAEIOU", "àëïôüÀËÏÔÜ")


class LocalizationError(ValueError):
    """Invalid localization data, concurrency conflict or unsafe edit."""


def sidecar_path(content_path):
    """game.json -> game.l10n.json, sibling to the canonical document pair."""
    path = Path(content_path)
    return path.with_suffix(".l10n.json")


def file_revision(path):
    path = Path(path)
    if path.is_symlink():
        raise LocalizationError("Localization sidecar cannot be a symbolic link")
    if not path.exists():
        return None
    if not path.is_file():
        raise LocalizationError("Localization sidecar must be a regular file")
    return sha256(path.read_bytes()).hexdigest()


def _forms(value, *, allow_empty=False):
    if isinstance(value, str):
        if not value and not allow_empty:
            raise LocalizationError("A source string cannot be empty")
        return {"other": value}
    if (isinstance(value, dict) and set(value) == {"one", "other"} and
            all(isinstance(item, str) and (bool(item) or allow_empty)
                for item in value.values())):
        return value
    raise LocalizationError("Text must be a string or one/other plural forms")


def _parameters(text):
    try:
        fields = set()
        for _literal, name, fmt, conversion in Formatter().parse(text):
            if name is not None:
                if not PARAM.fullmatch(name) or fmt or conversion:
                    raise LocalizationError("Only simple {name} placeholders are allowed")
                fields.add(name)
        return fields
    except ValueError as exc:
        raise LocalizationError("Unbalanced formatting braces") from exc


def _validate_text(source, translated):
    original = _forms(source)
    target = _forms(translated, allow_empty=True)
    if set(original) != set(target):
        raise LocalizationError("Plural categories must match the source")
    for form in original:
        # Empty target means explicit fallback to the source.
        if target[form] and _parameters(original[form]) != _parameters(target[form]):
            raise LocalizationError("Translated placeholders must match source placeholders")
        _parameters(original[form])


def _variant(value, count, locale):
    forms = _forms(value, allow_empty=True)
    if "one" not in forms:
        return forms["other"]
    if count is None or type(count) not in (int, float):
        raise LocalizationError("Plural messages require numeric count")
    singular = (count in (0, 1) if locale == "fr" else count == 1)
    return forms["one" if singular else "other"]


def _pseudolocalize(value, *, mirrored=False):
    # Protect parameters while stretching visible characters; no RNG/locale OS.
    chunks = re.split(r"(\{[A-Za-z_][A-Za-z0-9_]*\})", value)
    output = "".join(
        chunk if chunk.startswith("{") and chunk.endswith("}")
        else chunk.translate(ACCENTS) + ("~" * max(1, len(chunk) // 5) if chunk else "")
        for chunk in chunks
    )
    output = "[!! " + output + " !!]"
    return "\u2067" + output + "\u2069" if mirrored else output


class Catalog:
    def __init__(self, data):
        if not isinstance(data, dict) or set(data) != {
                "format", "version", "source_language", "entries"}:
            raise LocalizationError("Expected strict localization v1 document")
        if data["format"] != FORMAT or type(data["version"]) is not int or data["version"] != VERSION:
            raise LocalizationError("Unsupported localization format/version")
        if data["source_language"] not in LANGUAGES:
            raise LocalizationError("Source language must be fr or en")
        entries = data["entries"]
        if not isinstance(entries, dict) or len(entries) > 20000:
            raise LocalizationError("Invalid/oversized translation catalog")
        for key, entry in entries.items():
            if not isinstance(key, str) or not KEY.fullmatch(key):
                raise LocalizationError("Invalid stable localization key: " + str(key))
            if not isinstance(entry, dict) or set(entry) != {
                    "source", "context", "max_length", "translations"}:
                raise LocalizationError("Invalid entry fields: " + key)
            if not isinstance(entry["context"], str) or len(entry["context"]) > 500:
                raise LocalizationError("Invalid localization context: " + key)
            limit = entry["max_length"]
            if limit is not None and (type(limit) is not int or not 1 <= limit <= 10000):
                raise LocalizationError("Invalid max_length: " + key)
            _validate_text(entry["source"], entry["source"])
            translations = entry["translations"]
            if not isinstance(translations, dict) or not set(translations) <= LANGUAGES:
                raise LocalizationError("Unsupported translation language: " + key)
            for lang, translated in translations.items():
                if lang == data["source_language"]:
                    raise LocalizationError("Do not override source language: " + key)
                _validate_text(entry["source"], translated)
        self.data = deepcopy(data)

    @classmethod
    def empty(cls, source_language="fr"):
        return cls({"format": FORMAT, "version": VERSION,
                    "source_language": source_language, "entries": {}})

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.is_symlink():
            raise LocalizationError("Localization sidecar cannot be a symbolic link")
        if path.stat().st_size > 5_000_000:
            raise LocalizationError("Localization sidecar is too large")
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def render(self, key, language, *, source=None, count=None, **parameters):
        if language not in LANGUAGES | PSEUDO_LANGUAGES:
            raise LocalizationError("Unsupported display language")
        entry = self.data["entries"].get(key)
        if entry is None:
            if source is None:
                raise LocalizationError("Unknown localization key: " + key)
            return source
        actual_source = _variant(entry["source"], count, self.data["source_language"])
        # Old or independently edited content must not display stale translations.
        if source is not None and source != actual_source:
            return source
        if language in PSEUDO_LANGUAGES:
            template = _pseudolocalize(
                actual_source, mirrored=language == "qps-plocm")
        else:
            translated = entry["translations"].get(language)
            template = (_variant(translated, count, language)
                        if translated is not None else "")
            if not template:
                template = actual_source
        allowed = _parameters(template)
        values = dict(parameters)
        if count is not None:
            values.setdefault("count", count)
        if allowed - values.keys():
            raise LocalizationError("Missing formatting parameters: " +
                                    ", ".join(sorted(allowed - values.keys())))
        return template.format_map({k: str(values[k]) for k in allowed})

    def audit(self, language):
        if language not in LANGUAGES:
            raise LocalizationError("Audit requires fr or en")
        issues = []
        for key, entry in sorted(self.data["entries"].items()):
            translated = entry["translations"].get(language)
            if language == self.data["source_language"]:
                translated = entry["source"]
            if translated is None or not all(_forms(translated, allow_empty=True).values()):
                issues.append((key, "missing"))
                continue
            maximum = entry["max_length"]
            if maximum and any(len(text) > maximum for text in
                               _forms(translated).values()):
                issues.append((key, "too_long"))
        return issues

    def with_translation(self, key, language, text):
        if language not in LANGUAGES or language == self.data["source_language"]:
            raise LocalizationError("Choose a target language different from source")
        if key not in self.data["entries"]:
            raise LocalizationError("Unknown localization key")
        data = deepcopy(self.data)
        data["entries"][key]["translations"][language] = text
        return Catalog(data)

    def save(self, path, *, expected_revision=None):
        path = Path(path)
        if file_revision(path) != expected_revision:
            raise LocalizationError("Sidecar changed since opening; reload before saving")
        encoded = (json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) +
                   "\n").encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".drawtemp-l10n-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return file_revision(path)


def seeded_for_project(project, catalog=None):
    """Create missing explicit keys without rewriting translated or stale sources."""
    if not isinstance(project, dict):
        raise LocalizationError("Project snapshot must be a mapping")
    language = project.get("options", {}).get("language", "fr")
    base = catalog or Catalog.empty(language)
    if base.data["source_language"] != language:
        raise LocalizationError("Project/catalog source language mismatch")
    data = deepcopy(base.data)
    sources = {
        "project.title": (project.get("title", ""), "Title screen", 120),
        "project.subtitle": (project.get("subtitle", ""), "Title screen subtitle", 240),
    }
    for campaign in project.get("campaigns", []):
        cid = campaign["id"]
        sources["campaign." + cid + ".name"] = (
            campaign["name"], "Campaign selection", 120)
        if campaign.get("description"):
            sources["campaign." + cid + ".description"] = (
                campaign["description"], "Campaign summary", 500)
    story = project.get("story", {})
    for scene in story.get("scenes", []) if isinstance(story, dict) else []:
        if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
            continue
        sid = scene["id"]
        for field, context, limit in (
                ("title", "Narrative scene title", 120),
                ("speaker", "Narrative speaker", 120),
                ("text", "Narrative dialogue and subtitles", 1500)):
            value = scene.get(field)
            if isinstance(value, str) and value:
                sources["story." + sid + "." + field] = (value, context, limit)
        for choice in scene.get("choices", []):
            if (isinstance(choice, dict) and isinstance(choice.get("id"), str)
                    and isinstance(choice.get("label"), str) and choice["label"]):
                sources["story." + sid + ".choice." + choice["id"] + ".label"] = (
                    choice["label"], "Narrative choice", 160)
    # Sources added above are included in the same deterministic migration.
    drift = []
    for key, (source, context, limit) in sources.items():
        if not isinstance(source, str) or not source or not KEY.fullmatch(key):
            raise LocalizationError("Cannot derive a stable source key: " + key)
        if key in data["entries"]:
            if data["entries"][key]["source"] != source:
                drift.append(key)
        else:
            data["entries"][key] = {
                "source": source, "context": context, "max_length": limit,
                "translations": {},
            }
    return Catalog(data), tuple(drift)


def rebase_project_sources(project, catalog):
    """Explicit migration: changed source keys lose stale translations only.

    Consumers must request confirmation before calling this. Unchanged keys
    preserve all translations and no canonical game state is modified.
    """
    current, drift = seeded_for_project(project, catalog)
    if not drift:
        return current, ()
    fresh, _ = seeded_for_project(project)
    data = deepcopy(current.data)
    for key in drift:
        data["entries"][key] = deepcopy(fresh.data["entries"][key])
    return Catalog(data), drift



def localize_view(view, catalog, language):
    """R57 projection on an already calculated Player view; never mutates state."""
    result = dict(view)
    result["language"] = language
    if catalog is None:
        return result

    def translate(key, source):
        if not isinstance(source, str) or not source:
            return source
        try:
            return catalog.render(key, language, source=source)
        except LocalizationError:
            # Missing runtime placeholders or stale authoring must stay legible.
            return source

    campaign = str(view.get("campaign", ""))
    if campaign.endswith("_journey"):
        result["title"] = translate("campaign." + campaign + ".name",
                                    view.get("title"))
        result["subtitle"] = translate("campaign." + campaign + ".description",
                                       view.get("subtitle"))
    else:
        result["title"] = translate("project.title", view.get("title"))
        result["subtitle"] = translate("project.subtitle", view.get("subtitle"))

    scene = view.get("scene")
    if isinstance(scene, dict) and isinstance(scene.get("id"), str):
        sid = scene["id"]
        result["scene"] = dict(scene)
        for field in ("title", "speaker", "text"):
            if field in scene:
                result["scene"][field] = translate(
                    "story." + sid + "." + field, scene[field])
        choices = view.get("choices")
        if isinstance(choices, list):
            result["choices"] = [
                dict(row, label=translate(
                    "story." + sid + ".choice." + row["id"] + ".label",
                    row.get("label", "")))
                if isinstance(row, dict) and isinstance(row.get("id"), str)
                else row for row in choices
            ]
    return result
