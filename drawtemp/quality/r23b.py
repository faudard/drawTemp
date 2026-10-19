"""R23.B factual endurance/accessibility/playtest evidence, never automatic release approval.

Keep headless CI measurements separate from real GUI/GPU/human certification.
The historic checkpoint, journal, and combat formats remain unchanged.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
from tempfile import TemporaryDirectory

from examples.persistence_soak import run_soak
from sporebound.game_session import digest
from sporebound.player_preferences import (
    default_preferences, load_preferences, save_preferences, validate_preferences,
)
from sporebound.playtest_telemetry import analyze_playtests, validate_report

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PLATFORMS = frozenset({"Linux", "Windows", "macOS"})
_METRICS = ("p50", "p95", "p99", "max")


def _revision(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("R23.B requires the exact 40-character Git revision")
    return value


def verify_soak(soak):
    """Reject malformed, truncated, fake-success or internally divergent soak data."""
    if (not isinstance(soak, dict) or soak.get("version") != 1 or
            soak.get("gate") != "R8.13" or soak.get("verified") is not True):
        raise ValueError("R23.B requires verified R8.13 endurance results")
    iterations = soak.get("iterations")
    commands = soak.get("commands_per_iteration")
    if (type(iterations) is not int or not 1 <= iterations <= 100 or
            type(commands) is not int or not 1 <= commands <= 500):
        raise ValueError("Invalid endurance iteration or command count")
    cases = soak.get("cases")
    if not isinstance(cases, list) or len(cases) != iterations:
        raise ValueError("Incomplete endurance cases")
    seeds = set()
    for case in cases:
        if not isinstance(case, dict) or case.get("commands") != commands:
            raise ValueError("Invalid endurance case")
        seed = case.get("seed")
        if type(seed) is not int or seed in seeds:
            raise ValueError("Duplicate or invalid endurance seed")
        seeds.add(seed)
        for field in ("final_digest", "campaign_digest"):
            value = case.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("Missing verified endurance digest: " + field)
        if type(case.get("checkpoint_sequence")) is not int or case["checkpoint_sequence"] < 1:
            raise ValueError("Missing endurance checkpoint sequence")
        if type(case.get("max_checkpoint_bytes")) is not int or case["max_checkpoint_bytes"] < 1:
            raise ValueError("Missing checkpoint size measurement")
    if digest(cases) != soak.get("report_digest"):
        raise ValueError("Endurance case report checksum mismatch")
    metrics = soak.get("operation_seconds")
    if not isinstance(metrics, dict):
        raise ValueError("Missing measured operation timings")
    values = [metrics.get(key) for key in _METRICS]
    if any(type(x) not in (int, float) or not 0 <= x < float("inf") for x in values):
        raise ValueError("Invalid endurance timing")
    if values != sorted(values):
        raise ValueError("Endurance timing percentiles are inconsistent")
    peak = soak.get("python_peak_tracemalloc_bytes")
    elapsed = soak.get("elapsed_seconds")
    if (type(peak) is not int or peak < 0 or
            type(elapsed) not in (int, float) or not 0 < elapsed < float("inf")):
        raise ValueError("Missing memory/timing observations")
    return soak


def accessibility_settings_probe():
    """Exercise real atomic Player settings persistence, not a GUI/a11y audit."""
    with TemporaryDirectory(prefix="drawtemp-r23b-a11y-") as folder:
        path = Path(folder) / "profile"
        prefs = default_preferences()
        prefs["text_scale"] = 150
        prefs["high_contrast"] = True
        prefs["keybindings"]["execute"] = "<F1>"
        expected = validate_preferences(prefs)
        saved = save_preferences(path, expected)
        loaded, warning = load_preferences(path)
        if warning is not None or loaded != expected or not saved.is_file():
            raise ValueError("Player accessibility preferences did not round-trip")
        bad = dict(expected, text_scale=999)
        original = saved.read_bytes()
        try:
            save_preferences(path, bad)
        except ValueError:
            pass
        else:
            raise ValueError("Invalid accessibility preference accepted")
        if saved.read_bytes() != original:
            raise ValueError("Invalid preference mutated saved settings")
        return {"persisted": True, "scale_percent": 150,
                "high_contrast": True, "remapped_execute": "<F1>",
                "gui_keyboard_traversal": "not-asserted",
                "screen_reader": "not-asserted",
                "contrast_ratio": "not-asserted"}


def capture_ci_evidence(*, revision, platform, iterations=1, commands=8):
    """Run *actual* deterministic replay soak and preferences against this checkout."""
    _revision(revision)
    if platform not in _PLATFORMS:
        raise ValueError("Unknown R23.B OS")
    soak = verify_soak(run_soak(iterations=iterations, commands=commands))
    return {
        "schema": 1, "kind": "drawtemp-r23b-ci",
        "revision": revision, "platform": platform, "python": platform_version(),
        "mode": "headless-ci-smoke", "endurance": soak,
        "accessibility_settings": accessibility_settings_probe(),
        "hardware_gpu": "not-asserted", "human_playtest": "not-asserted",
        "hours_long_soak": "not-asserted"}


def platform_version():
    return platform.python_version()


def summarize_human_reports(reports):
    """Read only explicit opt-in JSONs. No telemetry implies no human evidence."""
    summaries = []
    for item in reports:
        if type(item) is not dict:
            raise ValueError("Invalid opt-in human playtest document")
        validate_report(item)
        if item.get("privacy") != "local_export_only_no_personal_identifiers":
            raise ValueError("Unrecognized human playtest privacy contract")
        summaries.append(analyze_playtests(item))
    return {
        "reports": len(summaries),
        "observed_sessions": sum(x["sessions"] for x in summaries),
        "complete_observations": sum(x["complete_observations"] for x in summaries),
        "human_signoff": "not-asserted",
        "findings_triaged": "not-asserted",
        "retests": "not-asserted"}


def aggregate_ci(reports, *, revision, human_reports=()):
    """Require the actual three-platform checks; always emit explicit NO-GO."""
    _revision(revision)
    by_platform = {}
    for row in reports:
        if (type(row) is not dict or row.get("schema") != 1 or
                row.get("kind") != "drawtemp-r23b-ci" or
                row.get("revision") != revision):
            raise ValueError("Wrong revision or malformed R23.B report")
        os_name = row.get("platform")
        if os_name not in _PLATFORMS or os_name in by_platform:
            raise ValueError("Duplicate or unknown R23.B platform")
        if row.get("mode") != "headless-ci-smoke" or any(
                row.get(key) != "not-asserted"
                for key in ("hardware_gpu", "human_playtest", "hours_long_soak")):
            raise ValueError("Unverified R23.B certification claim")
        verify_soak(row.get("endurance"))
        prefs = row.get("accessibility_settings")
        if not isinstance(prefs, dict) or prefs != {
                "persisted": True, "scale_percent": 150,
                "high_contrast": True, "remapped_execute": "<F1>",
                "gui_keyboard_traversal": "not-asserted",
                "screen_reader": "not-asserted",
                "contrast_ratio": "not-asserted"}:
            raise ValueError("Missing or forged accessibility settings probe")
        by_platform[os_name] = {
            "iterations": row["endurance"]["iterations"],
            "commands": row["endurance"]["commands_per_iteration"],
            "operation_seconds": row["endurance"]["operation_seconds"],
            "peak_tracemalloc_bytes": row["endurance"]["python_peak_tracemalloc_bytes"],
            "case_digest": row["endurance"]["report_digest"],
        }
    if set(by_platform) != _PLATFORMS:
        raise ValueError("Incomplete R23.B platform matrix: " +
                         ", ".join(sorted(_PLATFORMS - set(by_platform))))
    human = summarize_human_reports(human_reports)
    return {
        "schema": 1, "kind": "drawtemp-r23b-assessment",
        "revision": revision, "matrix": by_platform,
        "playtests": human,
        "checks": {
            "R23.6": {"status": "partial",
                      "detail": "Short headless persistence/replay soak, not multi-hour Studio/Player endurance"},
            "R23.7": {"status": "partial",
                      "detail": "Preferences roundtrip only; real keyboard traversal, assistive technology and contrast audit open"},
            "R23.8": {"status": "blocked" if not human["reports"] else "partial",
                      "detail": "No independently reviewed tester tasks, issue triage and retest signoff"},
        },
        "decision": "NO-GO",
        "release_certified": False,
    }


def write_json(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2)
                    + "\n", encoding="utf-8")
