"""R79 research-only evidence gate; never certifies or enables a platform.

Run: python tools/r79_platform_gate.py --candidate qtquick-rhi-adaptive \
    --revision <40-hex-sha> --evidence-root ./r79-evidence --output report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA = 1
SAMPLE_MIN = 30
SAMPLE_MAX = 10000
MAX_JSON_BYTES = 256 * 1024
MAX_ARTIFACT_BYTES = 20 * 1024 * 1024
SHA_RE = re.compile(r"[a-fA-F0-9]{40}\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
CANDIDATES = {
    "qtquick-rhi-adaptive": {"windows": {"d3d11", "d3d12", "vulkan", "opengl"},
                             "linux": {"vulkan", "opengl"},
                             "macos": {"metal", "opengl"}},
    "android-touch": {"android": {"vulkan", "opengl"}},
    "web-wasm": {"web": {"webgl", "webgpu"}},
}
CHECKS = ("picking", "studio_player_parity", "save_replay", "input",
          "packaging", "license_review", "rollback")


def _finite_positive(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return float(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
        raise ValueError(f"{label} must be nonempty (max 200 chars)")
    return value.strip()


def _quantile(values: list[float], numerator: int) -> float:
    ordered = sorted(values)
    index = max(0, (len(ordered) * numerator + 99) // 100 - 1)
    return round(ordered[index], 3)


def _verify_artifact(root: Path, item: Any) -> None:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("artifact requires path and sha256")
    name = _text(item["path"], "artifact path")
    if Path(name).name != name or name in {".", ".."} or "\\" in name:
        raise ValueError("artifact path must be a simple filename")
    if not isinstance(item["sha256"], str) or not HASH_RE.fullmatch(item["sha256"]):
        raise ValueError("artifact sha256 must be lower-case hex")
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or symlink artifact: {name}")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError(f"oversized artifact: {name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    if digest.hexdigest() != item["sha256"]:
        raise ValueError(f"artifact sha256 mismatch: {name}")


def _validate_evidence(payload: Any, root: Path, candidate: str, revision: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("evidence must be a JSON object")
    required = {"schema", "candidate", "revision", "platform", "renderer_backend",
                "physical_device", "device_id", "os_version", "qt_version", "driver_version",
                "benchmarks", "checks", "artifacts", "maintenance_hours_per_quarter", "cost_basis"}
    if set(payload) != required or type(payload["schema"]) is not int or payload["schema"] != SCHEMA:
        raise ValueError("unsupported schema or unknown/missing fields")
    if payload["candidate"] != candidate or payload["revision"] != revision:
        raise ValueError("candidate/revision mismatch")
    platform = payload["platform"]
    if platform not in CANDIDATES[candidate]:
        raise ValueError("platform is not in selected candidate matrix")
    if payload["renderer_backend"] not in CANDIDATES[candidate][platform]:
        raise ValueError("renderer backend is not allowed for this platform")
    if payload["physical_device"] is not True:
        raise ValueError("emulated or unverified hardware is not physical evidence")
    for field in ("device_id", "os_version", "qt_version", "driver_version", "cost_basis"):
        _text(payload[field], field)
    _finite_positive(payload["maintenance_hours_per_quarter"], "maintenance_hours_per_quarter")
    bench = payload["benchmarks"]
    if not isinstance(bench, dict) or set(bench) != {"frame_ms", "cold_start_ms", "peak_memory_mib"}:
        raise ValueError("benchmarks must contain frame_ms, cold_start_ms, peak_memory_mib")
    frames = bench["frame_ms"]
    if not isinstance(frames, list) or not SAMPLE_MIN <= len(frames) <= SAMPLE_MAX:
        raise ValueError(f"frame_ms needs {SAMPLE_MIN}..{SAMPLE_MAX} samples")
    durations = [_finite_positive(v, "frame_ms") for v in frames]
    _finite_positive(bench["cold_start_ms"], "cold_start_ms")
    _finite_positive(bench["peak_memory_mib"], "peak_memory_mib")
    checks = payload["checks"]
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        raise ValueError("checks must name each mandatory validation")
    if any(checks[name] is not True for name in CHECKS):
        raise ValueError("one or more mandatory checks failed or were not measured")
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 20:
        raise ValueError("at least one and at most 20 hashed source artifacts required")
    names = [a.get("path") if isinstance(a, dict) else None for a in artifacts]
    if len(names) != len(set(names)):
        raise ValueError("duplicate artifacts")
    for item in artifacts:
        _verify_artifact(root, item)
    return {
        "platform": platform, "device_id": payload["device_id"],
        "renderer_backend": payload["renderer_backend"],
        "frame_ms_p50": _quantile(durations, 50),
        "frame_ms_p95": _quantile(durations, 95),
        "frame_ms_p99": _quantile(durations, 99),
        "cold_start_ms": bench["cold_start_ms"],
        "peak_memory_mib": bench["peak_memory_mib"],
        "maintenance_hours_per_quarter": payload["maintenance_hours_per_quarter"],
        "artifact_count": len(artifacts),
    }


def evaluate(candidate: str, revision: str, evidence_root: Path) -> dict[str, Any]:
    """Only readiness for independent human review can ever be produced."""
    if candidate not in CANDIDATES:
        raise ValueError("unknown candidate")
    if not SHA_RE.fullmatch(revision):
        raise ValueError("revision must be a full 40-hex Git SHA")
    records: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    root = evidence_root.resolve(strict=False)
    if evidence_root.is_symlink():
        findings.append("evidence root is a symlink")
    elif not evidence_root.is_dir():
        findings.append("no evidence directory")
    else:
        manifests = sorted(evidence_root.glob("*.json"))
        if len(manifests) > 100:
            findings.append("too many evidence manifests")
        else:
            for path in manifests:
                try:
                    if path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
                        raise ValueError("symlink or oversized manifest")
                    data = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite number")))
                    record = _validate_evidence(data, root, candidate, revision)
                    record["manifest"] = path.name
                    record["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    platform = record["platform"]
                    if platform in records:
                        raise ValueError(f"duplicate platform: {platform}")
                    records[platform] = record
                except (ValueError, OSError, UnicodeError, TypeError, json.JSONDecodeError) as exc:
                    findings.append(f"{path.name}: {exc}")
    missing = sorted(set(CANDIDATES[candidate]) - set(records))
    if missing:
        findings.append("missing physical evidence: " + ", ".join(missing))
    review_ready = not findings and not missing
    return {
        "schema": SCHEMA,
        "candidate": candidate,
        "revision": revision.lower(),
        "decision": "NO-GO",  # Never automatically authorize a new platform/backend.
        "review_ready": review_ready,
        "release_certified": False,
        "scope": "isolated research only; PC Player unchanged",
        "required_platforms": sorted(CANDIDATES[candidate]),
        "observations": [records[key] for key in sorted(records)],
        "findings": findings,
        "next_action": "independent security, license, UX, GPU and maintenance review; separate signed ADR required" if review_ready
                       else "collect missing evidence and resolve findings; no product activation",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-review-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.candidate, args.revision, args.evidence_root)
    except ValueError as exc:
        parser.error(str(exc))
    body = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
    else:
        print(body, end="")
    return 0 if not args.require_review_ready or report["review_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
