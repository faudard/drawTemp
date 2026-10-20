"""R57 automated language-coverage gate (NOT a human accessibility certification).

Checks the authored sidecar against an actual saved project. Completeness,
drift, UTF-8 and pseudo bidi/placeholder behavior are machine-verifiable;
translation quality, screen readers, layout and gamepad remain manual gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.localization.r57 import (
    Catalog, LANGUAGES, LocalizationError, _forms, _parameters,
    seeded_for_project,
)


def audit_project(project, catalog):
    """Return deterministic machine-readable evidence, without mutating inputs."""
    current, drift = seeded_for_project(project, catalog)
    source = current.data["source_language"]
    target = next(lang for lang in sorted(LANGUAGES) if lang != source)
    keys = sorted(current.data["entries"])
    issues = [
        {"key": key, "kind": kind}
        for key, kind in current.audit(target)
        if key in keys
    ]
    pseudo_failures = []
    for key in keys:
        entry = current.data["entries"][key]
        forms = _forms(entry["source"])
        for count in (1, 2) if "one" in forms else (None,):
            template = (forms["one"] if count == 1 else forms.get("other", ""))
            args = {
                parameter: "Test" for parameter in _parameters(template)
                if parameter != "count"
            }
            try:
                shown = current.render(
                    key, "qps-plocm", count=count, **args)
                if not (shown.startswith("\u2067[!! ") and
                        shown.endswith(" !!]\u2069")):
                    raise LocalizationError("RTL pseudo direction isolates absent")
            except (LocalizationError, KeyError, ValueError) as exc:
                pseudo_failures.append({
                    "key": key, "count": count, "error": str(exc)})
    expected = len(keys)
    covered = expected - sum(1 for issue in issues if issue["kind"] == "missing")
    return {
        "format": "drawtemp.r57.localization-evidence",
        "version": 1,
        "source_language": source,
        "target_language": target,
        "keys_total": expected,
        "keys_translated": covered,
        "source_drift": sorted(drift),
        "issues": issues,
        "rtl_pseudo_failures": pseudo_failures,
        # Never label this report a VS-57 certificate. Human review is required.
        "automated_pass": bool(
            expected and not drift and not issues and not pseudo_failures),
        "manual_gates": [
            "human-reviewed FR/EN narrative act",
            "visual clipping/RTL screenshot and GPU checks",
            "NVDA/Orca/VoiceOver keyboard and focus audit",
            "controller-only walkthrough on physical gamepad",
            "photosensitivity and device test",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="R57 translation/pseudo-RTL automation (not certification)")
    parser.add_argument("project", type=Path,
                        help="Authored GameProject .game.json manifest")
    parser.add_argument("catalog", type=Path,
                        help="Versioned .l10n.json localization sidecar")
    parser.add_argument("--json-out", type=Path,
                        help="Write evidence file; never change game/catalog")
    args = parser.parse_args(argv)
    try:
        # JSON evidence must never be allowed to overwrite either source,
        # including aliases using ".." or an existing symlink.
        if (args.json_out is not None and
                args.json_out.resolve() in {
                    args.project.resolve(), args.catalog.resolve()}):
            raise ValueError("Evidence output path aliases game or catalog")
        project = json.loads(args.project.read_text(encoding="utf-8"))
        catalog = Catalog.load(args.catalog)
        report = audit_project(project, catalog)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print("R57 preflight failed: " + str(exc), file=sys.stderr)
        return 2
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(output)
    if args.json_out is not None:
        # Evidence-only export; errors must yield nonzero and not claim success.
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(output + "\n", encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print("R57 evidence write failed: " + str(exc), file=sys.stderr)
            return 2
    return 0 if report["automated_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
