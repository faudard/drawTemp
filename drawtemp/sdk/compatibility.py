"""R24.1: explicit semver-major SDK capability negotiation.

SDK API versions are separate from Content/GameProject/save envelope versions.
No import of Qt, renderer, or plugin code is needed for inspection.
"""
from __future__ import annotations

from . import SDK_API_VERSION, SDK_FEATURES


class SDKCompatibilityError(ValueError):
    """A requested API or feature cannot be supported safely."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def negotiate_sdk(api_version, *, required_features=()):
    """Validate minimum client API and features; return a detached selection.

    Both major and minor are strict non-negative integers. The major must
    match exactly, and a client requesting a newer minor cannot run against
    this implementation. Extra SDK features are never implicitly requested.
    """
    if (type(api_version) not in (tuple, list) or len(api_version) != 2 or
            any(type(v) is not int or v < 0 for v in api_version)):
        raise SDKCompatibilityError("invalid_version", "Expected [major, minor] integers")
    major, minor = api_version
    if major != SDK_API_VERSION[0]:
        raise SDKCompatibilityError("incompatible_major", "Unsupported SDK API major version")
    if minor > SDK_API_VERSION[1]:
        raise SDKCompatibilityError("unsupported_minor", "Client requires a newer SDK API")
    if type(required_features) not in (list, tuple, frozenset, set):
        raise SDKCompatibilityError("invalid_features", "Features must be a collection of strings")
    features = tuple(required_features)
    if (any(type(feature) is not str or not feature for feature in features) or
            len(features) != len(set(features))):
        raise SDKCompatibilityError("invalid_features", "Invalid or duplicate SDK features")
    missing = sorted(set(features) - SDK_FEATURES)
    if missing:
        raise SDKCompatibilityError("missing_feature", "Unavailable SDK features: " + ", ".join(missing))
    return {
        "api_version": list(SDK_API_VERSION),
        "requested_version": [major, minor],
        "features": sorted(features),
    }
