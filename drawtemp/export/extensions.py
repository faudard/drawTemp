"""R15.8 declarative, non-executable extension manifest contract.

This is a discovery/compatibility surface, NOT an untrusted Python loader.
"""
from pathlib import Path
import json
import re

CAPABILITIES = frozenset({"asset-catalog", "property-panel", "project-template"})
API_VERSION = 1


def validate_extension_manifest(document):
    if not isinstance(document, dict) or set(document) != {
            "api_version", "id", "name", "capabilities"}:
        raise ValueError("Extension needs api_version, id, name, capabilities")
    if type(document["api_version"]) is not int or document["api_version"] != API_VERSION:
        raise ValueError("Unsupported extension API version")
    if not isinstance(document["id"], str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{2,63}", document["id"]):
        raise ValueError("Invalid extension id")
    if not isinstance(document["name"], str) or not 1 <= len(document["name"]) <= 100:
        raise ValueError("Invalid extension name")
    values = document["capabilities"]
    if not isinstance(values, list) or not values or any(
            not isinstance(v, str) or v not in CAPABILITIES for v in values
    ) or len(values) != len(set(values)):
        raise ValueError("Unknown or duplicate declarative extension capability")
    return dict(document)


def inspect_extension(path):
    """Validate descriptor only; never import/execute plugin code."""
    return validate_extension_manifest(
        json.loads(Path(path).read_text(encoding="utf-8")))
