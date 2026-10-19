"""R24.3: canonical, declarative project extension data (no code execution).

Extensions are part of GameProject v1, not a sidecar database. Unknown
namespaces remain inert data. Schema upgrades require an explicit editor
transaction, rather than an automatic migration during load.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import re

from .model import RuleError

_NAMESPACE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){1,5}\Z")
_MAX_EXTENSION_BYTES = 65536
_MAX_TOTAL_BYTES = 262144


class ProjectExtensionError(RuleError):
    """Rejected extension envelope, with a stable machine-readable reason."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise ProjectExtensionError(code, message)


def _json_value(value, depth=0):
    """Validate true JSON values, not Python objects coerced to JSON strings."""
    if depth > 24:
        _fail("invalid_payload", "Extension JSON nesting exceeds 24 levels")
    if value is None or type(value) in (str, bool):
        if type(value) is str and len(value) > 65536:
            _fail("invalid_payload", "Extension string is too long")
        return
    if type(value) is int:
        if not -(2 ** 53 - 1) <= value <= 2 ** 53 - 1:
            _fail("invalid_payload", "Extension integer is outside portable JSON range")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail("invalid_payload", "Non-finite extension number")
        return
    if type(value) is list:
        if len(value) > 4096:
            _fail("invalid_payload", "Extension array is too long")
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > 4096:
            _fail("invalid_payload", "Extension object is too large")
        for key, item in value.items():
            if type(key) is not str or not 1 <= len(key) <= 128:
                _fail("invalid_payload", "Extension keys must be strings of 1..128 characters")
            _json_value(item, depth + 1)
        return
    _fail("invalid_payload", "Extension contains a non-JSON value")


def validate_project_extensions(extensions, *, content, campaigns):
    """Return a detached copy of safe, namespaced GameProject extension data.

    Each value is {"schema_version": 1, "data": {}, "references": [...]},
    with references optional and limited to existing mission/campaign IDs.
    Future versions fail closed; authored changes go through AuthoringSession.
    Does not import plugins or execute hooks.
    """
    if type(extensions) is not dict or len(extensions) > 32:
        _fail("invalid_extensions", "Expected at most 32 extension namespaces")
    mission_ids = set(content.missions)
    campaign_ids = {campaign["id"] for campaign in campaigns}
    total_size = 0
    for namespace, spec in extensions.items():
        if type(namespace) is not str or len(namespace) > 120 or not _NAMESPACE.fullmatch(namespace):
            _fail("invalid_namespace", "Expected a lowercase reverse-domain namespace")
        if type(spec) is not dict or not {"schema_version", "data"} <= set(spec) or (
                set(spec) - {"schema_version", "data", "references"}):
            _fail("invalid_envelope", namespace + ": unsupported envelope keys")
        if type(spec["schema_version"]) is not int or spec["schema_version"] != 1:
            _fail("unsupported_schema", namespace + ": explicit migration required")
        if type(spec["data"]) is not dict:
            _fail("invalid_payload", namespace + ": data must be a JSON object")
        _json_value(spec["data"])
        references = spec.get("references", [])
        if type(references) is not list or len(references) > 1024:
            _fail("invalid_references", namespace + ": invalid reference list")
        seen = set()
        for item in references:
            if type(item) is not dict or set(item) != {"kind", "id"}:
                _fail("invalid_reference", namespace + ": reference needs kind and id")
            kind, identifier = item["kind"], item["id"]
            if type(kind) is not str or type(identifier) is not str or not identifier:
                _fail("invalid_reference", namespace + ": malformed reference")
            if kind == "mission":
                exists = identifier in mission_ids
            elif kind == "campaign":
                exists = identifier in campaign_ids
            else:
                _fail("invalid_reference", namespace + ": unsupported reference kind")
            if not exists or (kind, identifier) in seen:
                _fail("invalid_reference", namespace + ": missing or repeated " + kind + " reference")
            seen.add((kind, identifier))
        try:
            size = len(json.dumps(spec, ensure_ascii=True, sort_keys=True,
                                  allow_nan=False, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ProjectExtensionError("invalid_payload", namespace + ": invalid JSON") from exc
        if size > _MAX_EXTENSION_BYTES:
            _fail("size_limit", namespace + ": maximum extension size exceeded")
        total_size += size
        if total_size > _MAX_TOTAL_BYTES:
            _fail("size_limit", "Maximum combined extension size exceeded")
    return deepcopy(extensions)
