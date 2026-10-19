"""R30.1 — declarative SDK compatibility negotiation (no plugin execution).

The R1 SDK is provisional; this module does not certify a stable public ABI.
A capability is available only if it is actually advertised by the SDK.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from drawtemp.sdk import SDK_API_STATUS, SDK_API_VERSION, SDK_FEATURES

_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
_FEATURE = re.compile(r"[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+\Z")
CURRENT_API = (*SDK_API_VERSION, 0)

# Entries are explicit and must be reviewed before removal from the R1 surface.
DEPRECATED_FEATURES: dict[str, str] = {}


class CapabilityError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Compatibility:
    compatible: bool
    api_version: str
    status: str
    available: tuple[str, ...]
    missing: tuple[str, ...]
    deprecated: tuple[str, ...]
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "compatible": self.compatible,
            "api_version": self.api_version,
            "status": self.status,
            "available": list(self.available),
            "missing": list(self.missing),
            "deprecated": list(self.deprecated),
            "reason": self.reason,
        }


def parse_semver(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise CapabilityError("invalid_version", "SDK version must be a string")
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise CapabilityError("invalid_version", "Expected exact MAJOR.MINOR.PATCH SemVer")
    return tuple(int(part) for part in match.groups())


def negotiate_sdk(*, min_api: str = "1.0.0", max_api: str = "2.0.0",
                  required_features: Iterable[str] = ()) -> Compatibility:
    """Negotiate a half-open API range and an exact set of advertised features.

    Unknown requirements fail closed, including future movement/combat modes.
    Negotiation is informational and does not grant permission to execute code.
    """
    lower, upper = parse_semver(min_api), parse_semver(max_api)
    if lower >= upper:
        raise CapabilityError("invalid_range", "API upper bound must exceed lower bound")
    if isinstance(required_features, (str, bytes)):
        raise CapabilityError("invalid_features", "Expected a sequence of feature IDs")
    try:
        features = tuple(required_features)
    except TypeError as exc:
        raise CapabilityError("invalid_features", "Expected iterable feature IDs") from exc
    if (len(features) > 128 or len(features) != len(set(map(repr, features))) or
            any(not isinstance(feature, str) or
                _FEATURE.fullmatch(feature) is None for feature in features)):
        raise CapabilityError("invalid_features", "Feature IDs must be unique and qualified")
    missing = tuple(sorted(set(features) - SDK_FEATURES))
    available = tuple(sorted(set(features) & SDK_FEATURES))
    deprecated = tuple(sorted(set(features) & DEPRECATED_FEATURES.keys()))
    current = ".".join(str(piece) for piece in CURRENT_API)
    in_range = lower <= CURRENT_API < upper
    reason = None
    if not in_range:
        reason = "sdk_api_out_of_range"
    elif missing:
        reason = "missing_features"
    return Compatibility(not reason, current, SDK_API_STATUS,
                         available, missing, deprecated, reason)


def require_sdk(**kwargs) -> Compatibility:
    """Raise with stable error codes instead of silently ignoring requirements."""
    result = negotiate_sdk(**kwargs)
    if not result.compatible:
        raise CapabilityError(result.reason or "incompatible", str(result.to_dict()))
    return result
