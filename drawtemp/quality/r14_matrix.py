"""Independent R14 CI evidence checks: never infer success from filenames alone."""
from __future__ import annotations

from pathlib import Path
import re

from .r14 import verify_report

REQUIRED_RUNNERS = ("Linux", "macOS", "Windows")
REQUIRED_PROBES = ("r14_contracts", "core", "qt", "soak", "faults")
PINNED_QT = "6.8.3"
_REVISION = re.compile(r"[0-9a-f]{40}\Z")


def inspect_matrix(sources, *, expected_revision=None):
    """Return (accepted_reports_by_os, problems).

    sources is a sequence of (report_path, decoded_report) pairs. Problems
    invalidate R14.1, even if a different artifact from the same OS succeeds.
    """
    reports = {}
    problems = []
    revisions = set()
    if not sources:
        problems.append("No R14 runner reports found")
    for path, report in sources:
        path = Path(path)
        try:
            verify_report(report)
        except (TypeError, KeyError, ValueError, AttributeError) as exc:
            problems.append(f"{path}: invalid report: {exc}")
            continue
        env = report.get("environment", {})
        if not isinstance(env, dict):
            problems.append(f"{path}: environment must be an object")
            continue
        runner = env.get("runner")
        if runner not in REQUIRED_RUNNERS:
            problems.append(f"{path}: unrecognised runner {runner!r}")
            continue
        if runner in reports:
            problems.append(f"{path}: duplicate {runner} artifact")
            continue
        reports[runner] = report
        revision = report.get("revision")
        if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
            problems.append(f"{path}: missing immutable 40-digit git revision")
        else:
            revisions.add(revision)
        if not str(env.get("python", "")).startswith("3.12."):
            problems.append(f"{path}: Python 3.12 required")
        if env.get("qt") != PINNED_QT:
            problems.append(f"{path}: expected PySide6 {PINNED_QT}; got {env.get('qt')!r}")
        probes = report.get("probes", {})
        if not isinstance(probes, dict):
            problems.append(f"{path}: missing probe map")
            continue
        for key in REQUIRED_PROBES:
            probe = probes.get(key)
            if not isinstance(probe, dict):
                problems.append(f"{path}: {key} probe missing")
                continue
            if (probe.get("status") != "pass" or
                    type(probe.get("exit_code")) is not int or probe["exit_code"] != 0 or
                    not isinstance(probe.get("command"), list) or not probe["command"]):
                problems.append(f"{path}: {key} did not exit successfully")
            log = probe.get("log")
            if (not isinstance(log, str) or not log.endswith(".log") or
                    Path(log).name != log or not (path.parent / log).is_file() or
                    (path.parent / log).stat().st_size == 0):
                problems.append(f"{path}: missing/empty/unsafe log for {key}")
    missing = sorted(set(REQUIRED_RUNNERS) - set(reports))
    if missing:
        problems.append("Missing runners: " + ", ".join(missing))
    if len(revisions) != 1:
        problems.append("Reports must all come from the same immutable commit")
    if expected_revision is not None and revisions != {expected_revision}:
        problems.append("Runner reports do not match aggregation commit " + str(expected_revision))
    return reports, problems
