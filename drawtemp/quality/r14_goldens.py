"""R14.5 reviewed Qt screenshot baselines; capture evidence is never self-approved.

A golden is valid only if a manually reviewed, committed manifest matches the
backend/Qt version/OS, all twelve scene-DPI-zoom configurations and SHA-256.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil

from .visual import compare_png

TARGETS = ("studio", "player")
DPRS = (1, 2)
ZOOMS = (0.75, 1.0, 1.5)
EXPECTED = tuple((target, dpi, zoom) for target in TARGETS
                 for dpi in DPRS for zoom in ZOOMS)
SCHEMA = 1
MAX_CHANNEL_DELTA = 12
MAX_CHANGED_FRACTION = 0.001


def case_id(target, dpi, zoom):
    if (target, dpi, zoom) not in EXPECTED:
        raise ValueError("Unknown R14.5 capture case")
    return f"{target}-dpi{dpi}-zoom{round(zoom * 100):03d}"


def profile_id(os_name, qt_version, backend="software"):
    """Avoid comparing incompatible rasterization/font/backend environments."""
    os_name = str(os_name).lower()
    if os_name not in ("linux", "windows", "darwin"):
        raise ValueError("Unqualified OS: " + os_name)
    if backend != "software" or not str(qt_version).startswith("6.8.3"):
        raise ValueError("R14.5 reference profile requires pinned Qt 6.8.3 software")
    return f"{os_name}-qt{qt_version}-{backend}"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")


def _checked_png(root, filename, hash_hex):
    """Never read arbitrary absolute/path-traversal targets from a manifest."""
    if not isinstance(filename, str) or "/" in filename or "\\" in filename or \
            filename.startswith(".") or not filename.endswith(".png"):
        raise ValueError("Unsafe golden filename")
    if not isinstance(hash_hex, str) or len(hash_hex) != 64 or \
            any(c not in "0123456789abcdef" for c in hash_hex):
        raise ValueError("Invalid golden SHA-256")
    path = Path(root) / filename
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"Approved golden missing: {path}")
    if digest(path) != hash_hex:
        raise ValueError(f"Approved golden SHA-256 changed: {path}")
    return path


def load_approved(root, profile):
    """Return None for absent approval; reject malformed/incomplete approvals."""
    folder = Path(root) / profile
    path = folder / "manifest.json"
    if not path.is_file():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != SCHEMA or
            manifest.get("profile") != profile or
            manifest.get("reviewed") is not True or
            not isinstance(manifest.get("reviewer"), str) or
            not manifest["reviewer"].strip() or
            not isinstance(manifest.get("cases"), dict)):
        raise ValueError("Invalid or unreviewed R14.5 golden manifest")
    expected_keys = {case_id(*case) for case in EXPECTED}
    if set(manifest["cases"]) != expected_keys:
        raise ValueError("Incomplete or unexpected approved R14.5 matrix")
    for target, dpi, zoom in EXPECTED:
        name = case_id(target, dpi, zoom)
        item = manifest["cases"][name]
        if (not isinstance(item, dict) or item.get("target") != target or
                item.get("dpi") != dpi or item.get("zoom") != zoom or
                type(item.get("width")) is not int or item["width"] <= 0 or
                type(item.get("height")) is not int or item["height"] <= 0):
            raise ValueError("Golden metadata mismatch: " + name)
        _checked_png(folder, item.get("filename"), item.get("sha256"))
    return manifest


def approve_candidates(capture_dir, golden_root, *, reviewer):
    """Explicit, separate human action. Never called from CI capture/comparison."""
    if not reviewer or not reviewer.strip():
        raise ValueError("A named human reviewer is required")
    source = Path(capture_dir)
    report = json.loads((source / "r14-visual.json").read_text("utf-8"))
    profile = report.get("profile")
    if not isinstance(profile, str) or not profile or report.get("capture_complete") is not True:
        raise ValueError("Cannot approve an incomplete candidate capture")
    profile_expected = profile_id(report.get("os"), report.get("qt"))
    if profile != profile_expected:
        raise ValueError("Candidate profile has conflicting OS/Qt metadata")
    entries = report.get("cases", {})
    if set(entries) != {case_id(*case) for case in EXPECTED}:
        raise ValueError("Cannot approve an incomplete R14.5 capture matrix")
    target = Path(golden_root) / profile
    if (target / "manifest.json").exists():
        raise ValueError("Already reviewed. Remove/replace in a separate code-reviewed PR.")
    target.mkdir(parents=True, exist_ok=True)
    approved = {}
    for scene, dpi, zoom in EXPECTED:
        key = case_id(scene, dpi, zoom)
        row = entries[key]
        if row.get("capture_status") != "captured":
            raise ValueError("Missing real capture: " + key)
        image = _checked_png(source / "actual", key + ".png", row.get("sha256"))
        filename = key + ".png"
        if (source / "actual" / filename) != image:
            raise ValueError("Capture name mismatch")
        shutil.copyfile(image, target / filename)
        approved[key] = {
            "target": scene, "dpi": dpi, "zoom": zoom,
            "width": row["width"], "height": row["height"],
            "filename": filename, "sha256": digest(target / filename),
        }
    manifest = {
        "schema": SCHEMA, "profile": profile, "reviewed": True,
        "reviewer": reviewer.strip(),
        "approved_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": report.get("revision", "unknown"), "cases": approved,
        "tolerance": {"max_channel_delta": MAX_CHANNEL_DELTA,
                      "max_changed_fraction": MAX_CHANGED_FRACTION},
    }
    write_json(target / "manifest.json", manifest)
    return target / "manifest.json"


def evaluate_capture(capture_root, golden_root, report):
    """Compare every real candidate to a separately approved immutable baseline."""
    profile = report["profile"]
    approved = load_approved(golden_root, profile)
    output = Path(capture_root)
    for scene, dpi, zoom in EXPECTED:
        name = case_id(scene, dpi, zoom)
        row = report["cases"].get(name)
        if not row or row.get("capture_status") != "captured":
            continue
        if approved is None:
            row.update(comparison="blocked", reason="No independently reviewed baseline for this profile")
            continue
        item = approved["cases"][name]
        if row["width"] != item["width"] or row["height"] != item["height"]:
            row.update(comparison="fail", reason="Captured image dimensions differ")
            continue
        baseline = _checked_png(Path(golden_root) / profile,
                                item["filename"], item["sha256"])
        # Save a copy beside the report so HTML artifacts remain portable.
        copy = output / "baseline" / (name + ".png")
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(baseline, copy)
        result = compare_png(output / "actual" / (name + ".png"), baseline,
                             max_channel_delta=MAX_CHANNEL_DELTA,
                             max_changed_fraction=MAX_CHANGED_FRACTION,
                             diff_path=output / "diff" / (name + ".png"))
        row.update(comparison="pass" if result["passed"] else "fail", metrics=result)
    statuses = [v.get("comparison") for v in report["cases"].values()]
    report["comparison"] = ("fail" if "fail" in statuses else
                            "pass" if len(statuses) == len(EXPECTED) and
                            all(s == "pass" for s in statuses) else "blocked")
    report["goldens_reviewed"] = approved is not None
    # Software/offscreen comparison never constitutes visual hardware certification.
    report["release_certified"] = False
    return report


def html_report(folder, report):
    """Human review with side-by-side actual/reference/heatmap links."""
    root = Path(folder)
    rows = []
    for name, item in sorted(report.get("cases", {}).items()):
        def visual(subdir):
            path = root / subdir / (name + ".png")
            return (f'<a href="{subdir}/{escape(name)}.png"><img width="300" '
                    f'src="{subdir}/{escape(name)}.png" alt="{escape(subdir)}"></a>'
                    if path.is_file() else "<em>Absent</em>")
        metrics = item.get("metrics", {})
        rows.append("<tr><th>" + escape(name) + "</th><td>" +
                    escape(str(item.get("comparison", item.get("capture_status", "blocked")))) +
                    "</td><td>" + visual("actual") + "</td><td>" +
                    visual("baseline") + "</td><td>" + visual("diff") +
                    "</td><td><pre>" + escape(json.dumps(metrics, indent=2)) +
                    "</pre></td></tr>")
    document = ("<!doctype html><html lang='fr'><meta charset='utf-8'>"
                "<title>DrawTemp R14.5 — Visual Goldens</title>"
                "<style>body{font-family:sans-serif;background:#f6f7f9;color:#17212b}"
                "table{border-collapse:collapse}td,th{border:1px solid #abb2ba;"
                "padding:8px;vertical-align:top}img{max-width:300px}pre{white-space:pre-wrap}"
                "</style><h1>R14.5 — Visual Goldens</h1><p>Profil: " +
                escape(str(report.get("profile"))) + " | comparaison: " +
                escape(str(report.get("comparison", "blocked"))) +
                " | certification matérielle: NON</p>"
                "<p>Seuil: 12/255 par canal, 0,1 % de pixels modifiés.</p>"
                "<table><tr><th>Cas</th><th>État</th><th>Capture</th>"
                "<th>Référence approuvée</th><th>Différence</th><th>Mesures</th>"
                "</tr>" + "".join(rows) + "</table></html>")
    (root / "index.html").write_text(document, encoding="utf-8")
