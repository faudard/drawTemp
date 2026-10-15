"""DrawTemp 5.0 R14 evidence runner. No claim of GPU/release certification from CI.

Example:
  python scripts/certify_drawtemp5_r14.py --report build/r14-report.json --qt --soak --faults
  python scripts/certify_drawtemp5_r14.py --aggregate build/r14-matrix --report build/r14-aggregate.json
  python scripts/certify_drawtemp5_r14.py --aggregate build/r14-matrix --report build/release.json --require-complete
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from drawtemp.quality.r14 import (
    ALL_CHECKS, evidence_report, validate_gpu_profile, verify_report, write_report,
)

ROOT = Path(__file__).resolve().parents[1]


def run_probe(key, command, destination, *, timeout=420):
    """Record actual process exit code; a skipped probe is never marked passed."""
    path = destination / (key + ".log")
    try:
        process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=timeout, check=False)
        path.write_text(process.stdout[-120000:], encoding="utf-8", errors="replace")
        return {"status": "pass" if process.returncode == 0 else "fail",
                "command": command, "exit_code": process.returncode,
                "log": path.name}
    except subprocess.TimeoutExpired as exc:
        path.write_text("Timed out after " + str(timeout) + " seconds\n", encoding="utf-8")
        return {"status": "fail", "command": command, "exit_code": None,
                "detail": str(exc), "log": path.name}


def produce(args):
    destination = args.report.parent
    destination.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    probes = {
        "r14_contracts": run_probe(
            "r14-contracts", [py, "-m", "unittest",
                              "tests_standalone.test_drawtemp5_r14", "-v"], destination),
        "core": run_probe(
            "core", [py, "-m", "unittest",
                     "tests_standalone.test_drawtemp5_r0",
                     "tests_standalone.test_drawtemp5_r1",
                     "tests_standalone.test_drawtemp5_r1_authoring", "-v"], destination),
    }
    if args.qt:
        probes["qt"] = run_probe(
            "qt", [py, "-m", "unittest",
                   "tests_standalone.test_drawtemp5_r14_qt", "-v"], destination)
    if args.gui:
        probes["gui"] = run_probe(
            "gui", [py, "-m", "unittest",
                    "tests_standalone.test_drawtemp5_r14_gui", "-v"],
            destination, timeout=360)
    if args.visual:
        probes["visual"] = run_probe(
            "visual", [py, "-m", "unittest",
                       "tests_standalone.test_drawtemp5_r14_visual", "-v"],
            destination)
    if args.soak:
        probes["soak"] = run_probe(
            "soak", [py, "-m", "examples.reliability_gate", "--seeds", "1", "7",
                     "--output", str((destination / "r14-reliability.json").resolve())],
            destination)
    if args.faults:
        probes["faults"] = run_probe(
            "faults", [py, "-m", "unittest",
                       "tests_standalone.test_persistence_fault_r817", "-v"],
            destination, timeout=600)
    checks = {}
    mapping = {"r14_contracts": "R14.10", "core": "R14.2", "qt": "R14.3",
               "soak": "R14.8", "faults": "R14.9", "gui": "R14.4",
               "visual": "R14.5"}
    for probe, check in mapping.items():
        if probe in probes:
            succeeded = probes[probe]["status"] == "pass"
            checks[check] = {
                "status": "partial" if succeeded else "fail",
                "detail": ("Bounded regression probe passed; full R14 scope remains open"
                           if succeeded else "Regression probe failed: see attached log"),
                "probe": probe,
            }
    # Hardware samples are evidence supplied by a separate real GPU runner.
    gpu_summary = None
    if args.gpu_profile:
        try:
            gpu_summary = validate_gpu_profile(
                json.loads(args.gpu_profile.read_text(encoding="utf-8")))
            checks["R14.6"] = {"status": "partial", "detail": "External GPU frame-time matrix validated; CPU, VRAM and leaks still pending"}
            checks["R14.7"] = {"status": "partial", "detail": "All required map/zoom and 80-actor samples present; thresholds pending"}
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            checks["R14.6"] = {"status": "fail", "detail": "Invalid GPU evidence: " + str(exc)}
    checks["R14.1"] = {"status": "blocked", "detail": "Single runner only; aggregate Windows/Linux/macOS artifacts"}
    if not args.gui:
        checks["R14.4"] = {"status": "blocked", "detail": "GUI input journey not run"}
    else:
        checks["R14.4"]["detail"] = (
            "Qt mouse/toolbar/QML journey passed; onscreen environments still pending"
            if probes["gui"]["status"] == "pass" else "GUI journey failed: inspect gui.log")
    if not args.visual:
        checks["R14.5"] = {"status": "blocked", "detail": "Golden comparison not run"}
    else:
        checks["R14.5"]["detail"] = (
            "Pixel comparison tested; Studio captures need approved multi-DPI goldens"
            if probes["visual"]["status"] == "pass" else "Visual comparator failed: inspect visual.log")
    checks["R14.11"] = {"status": "blocked", "detail": "Accessibility review/assistive technology evidence pending"}
    checks["R14.12"] = {"status": "blocked", "detail": "Release gate needs all P0 evidence and GPU hardware"}
    report = evidence_report(checks, revision=os.environ.get("GITHUB_SHA", "local"))
    report["probes"] = probes
    if gpu_summary:
        report["gpu"] = gpu_summary
    write_report(args.report, report)
    return 1 if any(value["status"] == "fail" for value in probes.values()) or any(
        item["status"] == "fail" for item in report["checks"].values()) else 0


def aggregate(args):
    files = sorted(args.aggregate.glob("**/r14-report.json"))
    reports = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        verify_report(data)
        reports.append(data)
    by_os = {r["environment"]["runner"]: r for r in reports}
    required = {"Linux", "Windows", "macOS"}
    missing = sorted(required - set(by_os))
    checks = {}
    required_probes = {"r14_contracts", "core", "qt", "gui", "visual", "soak", "faults"}
    matrix_success = not missing and all(
        r["environment"]["python"].startswith("3.12.") and
        all(r.get("probes", {}).get(probe, {}).get("status") == "pass"
            for probe in required_probes)
        for r in (by_os[name] for name in required))
    checks["R14.1"] = {
        "status": "pass" if matrix_success else "fail",
        "detail": "Python 3.12, PySide6 6.8.3; three-host matrix"
                  if matrix_success else "Missing/failed CI runner: " + ", ".join(missing)}
    for key in ALL_CHECKS:
        if key == "R14.1":
            continue
        statuses = [r["checks"][key]["status"] for r in reports]
        checks[key] = {
            "status": ("fail" if "fail" in statuses else
                       "partial" if "partial" in statuses else "blocked"),
            "detail": "Aggregated from " + str(len(reports)) + " per-platform reports",
        }
    # Do not infer release certification from availability of matrix artifacts.
    checks["R14.12"] = {"status": "blocked", "detail": "Hardware, E2E, visual and release reviews outstanding"}
    report = evidence_report(checks, revision=os.environ.get("GITHUB_SHA", "local"))
    report["matrix"] = {"required": sorted(required), "found": sorted(by_os), "sources": len(files)}
    write_report(args.report, report)
    return 1 if not matrix_success or any(r["checks"][key]["status"] == "fail"
                                          for r in reports for key in ALL_CHECKS) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--qt", action="store_true", help="Qt 6 installed, exercise real QQuickWidget lifecycle")
    parser.add_argument("--gui", action="store_true", help="Exercise Qt Studio/Player real mouse journeys")
    parser.add_argument("--visual", action="store_true", help="Validate Qt pixel-golden comparator")
    parser.add_argument("--soak", action="store_true", help="Exercise checkpointed campaigns")
    parser.add_argument("--faults", action="store_true", help="Run interruption/recovery suite")
    parser.add_argument("--gpu-profile", type=Path, help="External hardware evidence, never generated by software CI")
    parser.add_argument("--aggregate", type=Path, help="Directory containing R14 runner artifact folders")
    parser.add_argument("--require-complete", action="store_true", help="Fail unless every R14 P0 gate is proven")
    args = parser.parse_args(argv)
    if args.aggregate and (args.qt or args.gui or args.visual or args.soak or args.faults or args.gpu_profile):
        parser.error("--aggregate cannot run probes")
    result = aggregate(args) if args.aggregate else produce(args)
    if args.require_complete:
        try:
            verify_report(json.loads(args.report.read_text(encoding="utf-8")),
                          require_complete=True)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print("R14 report: " + str(args.report) + " (not a release certificate unless p0_certified=true)")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
