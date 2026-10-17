"""R17.1 offline evidence for stacked PRs whose GitHub 'merged' badge is ambiguous.

Run inside a full local clone (or an Actions checkout with fetch-depth: 0):
    python scripts/audit_r17_merge_ledger.py --ref master
    python scripts/audit_r17_merge_ledger.py --ref master --format json
    python scripts/audit_r17_merge_ledger.py --ref master --strict

This inspects commit ancestry AND the resulting master tree; it cannot certify
Qt UI, visual QA, or behavioral correctness merely from file/symbol presence.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PRSpec:
    number: int
    milestone: str
    merge_commit: str
    probes: tuple[tuple[str, str], ...]


# Merge SHA is deliberately the GitHub merge commit, not the PR head.
# These snapshots are evidence inputs, not a live reflection of GitHub status.
PR_SPECS = (
    PRSpec(248, "R7.B", "6648cc3a284d4f4ac966bc0e102001078a5cc438", (
        ("drawtemp/assets/character_runtime.py", "class CharacterPack"),
        ("drawtemp/render/qt_viewport.py", "def make_controller"),
    )),
    PRSpec(264, "R7.C", "9fa8851f4863f56e6a2aa422f3935880f78288eb", (
        ("drawtemp/assets/jeanne_art.py", "def build_jeanne_art"),
        ("drawtemp/assets/character_outfits.py", "def outfit_from_progress"),
    )),
    PRSpec(263, "R9.C", "475700c5feaa94562e045c92bca540932b379aee", (
        ("drawtemp/render/event_overlay.py", ""),
        ("drawtemp/studio/event_command_catalog.py", ""),
        ("drawtemp/studio/event_graph_qt.py", ""),
        ("tests_standalone/test_drawtemp5_r9c.py", ""),
    )),
    PRSpec(273, "R9.D", "ac90249ae9844659be98cde014ebf59c75c1c24d", (
        ("sporebound/event_pages.py", ""),
        ("tests_standalone/test_drawtemp5_r9d.py", ""),
    )),
    PRSpec(253, "R16", "7829988c587b7761e2ec07944b343fef59a06943", (
        ("drawtemp/sdk/legacy_migration.py", ""),
    )),
    PRSpec(255, "R15", "d8f7e840e123332bdad38af67d6e25e4ab152bc6", (
        ("drawtemp/export/r15.py", ""),
    )),
    PRSpec(275, "R14.5", "8dd6b324192fe59fcd2f20d30e1289a4080cf239", (
        ("drawtemp/quality/r14_goldens.py", ""),
    )),
    PRSpec(254, "R14", "9dc808ed23ec248683c922e230f01fe9a27369bb", (
        ("drawtemp/quality/r14_matrix.py", ""),
    )),
)


class AuditError(RuntimeError):
    pass


def git(repo: Path, *args: str, allowed=(0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True,
        check=False,
    )
    if result.returncode not in allowed:
        raise AuditError(
            f"git {(' '.join(args))}: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def audit(repo: Path, ref: str, specs=PR_SPECS) -> dict:
    """Check a full git history; never mistake a shallow clone for a lost PR."""
    head = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()
    tree = set(git(repo, "ls-tree", "-r", "--name-only", head).stdout.splitlines())
    rows = []
    for spec in specs:
        available = git(repo, "cat-file", "-e",
                        f"{spec.merge_commit}^{{commit}}", allowed=(0, 1, 128))
        ancestry = "unknown"
        if available.returncode == 0:
            status = git(repo, "merge-base", "--is-ancestor",
                         spec.merge_commit, head, allowed=(0, 1))
            ancestry = "yes" if status.returncode == 0 else "no"
        missing_paths = sorted(path for path, _ in spec.probes if path not in tree)
        missing_symbols = []
        for path, symbol in spec.probes:
            if symbol and path in tree:
                body = git(repo, "show", f"{head}:{path}").stdout
                if symbol not in body:
                    missing_symbols.append(f"{path} :: {symbol}")
        if ancestry == "yes" and not missing_paths and not missing_symbols:
            integration = "ancestor-and-probes"
        elif ancestry == "unknown":
            integration = "history-unavailable"
        elif ancestry == "no":
            integration = "not-an-ancestor"
        else:
            integration = "ancestor-with-missing-probes"
        rows.append({
            "pr": spec.number, "milestone": spec.milestone,
            "merge_commit": spec.merge_commit, "ancestor_of_ref": ancestry,
            "integration": integration, "missing_paths": missing_paths,
            "missing_symbols": missing_symbols,
        })
    return {"ref": ref, "head": head, "rows": rows,
            "certification": "not-assessed"}


def markdown(result: dict) -> str:
    lines = [
        "# R17.1 — Audit de fusions empilées",
        "",
        f"Référence : `{result['ref']}` @ `{result['head']}`.",
        "",
        "| PR | Lot | Ancêtre de la référence | Preuves statiques |",
        "| --- | --- | --- | --- |",
    ]
    for row in result["rows"]:
        problems = row["missing_paths"] + row["missing_symbols"]
        proof = row["integration"]
        if problems:
            proof += "; absents : " + ", ".join(f"`{p}`" for p in problems)
        lines.append(
            f"| #{row['pr']} | {row['milestone']} | "
            f"{row['ancestor_of_ref']} | {proof} |"
        )
    lines.extend([
        "",
        "Un badge GitHub « merged » ne garantit pas l'intégration dans master.",
        "Les sondes vérifient présence de fichiers/symboles, pas le comportement.",
        "L'absence d'historique complet vaut « history-unavailable », jamais « intégré ».",
        "Ce rapport **ne certifie pas** le gameplay, l'UX, le GPU ou une release.",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", default="master")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--strict", action="store_true",
                        help="Fail if any required merge is not evidenced")
    args = parser.parse_args(argv)
    try:
        report = audit(args.repo, args.ref)
    except (AuditError, OSError) as exc:
        parser.exit(2, f"R17 audit unavailable: {exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False)
          if args.format == "json" else markdown(report), end="")
    return int(args.strict and any(
        row["integration"] != "ancestor-and-probes" for row in report["rows"]
    ))


if __name__ == "__main__":
    raise SystemExit(main())
