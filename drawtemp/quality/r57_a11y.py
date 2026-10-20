"""R57.C repeatable WCAG-style foreground/background contrast preflight.

These known Qt/QML palette pairs are a narrow automated evidence set,
not an accessibility certification or a substitute for screen-reader QA.
"""
from __future__ import annotations


class ContrastError(ValueError):
    pass


def relative_luminance(rgb):
    if (type(rgb) is not str or len(rgb) != 7 or rgb[0] != "#" or
            any(c not in "0123456789abcdefABCDEF" for c in rgb[1:])):
        raise ContrastError("Expected opaque #RRGGBB")
    components = (int(rgb[k:k + 2], 16) / 255 for k in (1, 3, 5))
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in components]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground, background):
    values = sorted((relative_luminance(foreground),
                     relative_luminance(background)), reverse=True)
    return (values[0] + 0.05) / (values[1] + 0.05)


# Sampled from fixed screen elements, not arbitrary or semi-transparent
# dynamic cinematic backgrounds. Actual rendered text still needs native QA.
PLAYER_TEXT_PAIRS = {
    "window_high_contrast": ("#ffffff", "#131c25", 4.5),
    "window_muted": ("#b2b8b8", "#131c25", 4.5),
    "cinematic_caption": ("#f5ead5", "#121d2c", 4.5),
    "cinematic_speaker": ("#f5ca91", "#121d2c", 4.5),
    "narrative_body": ("#efe4d2", "#263a40", 4.5),
    "narrative_heading": ("#e7c78b", "#263a40", 3.0),
}


def audit_contrast(pairs=PLAYER_TEXT_PAIRS):
    """Return full evidence, including failures, never just a boolean."""
    report = []
    for label, (fg, bg, minimum) in sorted(pairs.items()):
        ratio = contrast_ratio(fg, bg)
        report.append({
            "id": label, "foreground": fg, "background": bg,
            "ratio": round(ratio, 3), "minimum": minimum,
            "pass": ratio >= minimum,
        })
    return report
