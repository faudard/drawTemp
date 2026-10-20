"""R52.B3 visual evidence contracts for the SINGLE shared Qt Quick pipeline.

Captures are candidates until separately reviewed and committed. Never treat a
new capture, absent reviewer, null framebuffer or backend mismatch as a golden.
R52 software pixel parity does not imply any physical GPU certification.
"""
from hashlib import sha256
import json
from pathlib import Path
import shutil

from drawtemp.quality.visual import compare_png

SCHEMA = 1
TARGETS = ("studio", "player")
MODES = ("isometric", "top_down", "side")
DPRS = (1, 1.5, 2)
PHASES = ("day", "night")
EXPECTED = tuple((target, mode, dpi, phase)
                 for mode in MODES for dpi in DPRS for phase in PHASES
                 for target in TARGETS)
MAX_CHANNEL_DELTA = 12
MAX_CHANGED_FRACTION = 0.02


def case_id(target, mode, dpi, phase):
    if (target, mode, dpi, phase) not in EXPECTED:
        raise ValueError("Unknown R52.B3 visual configuration")
    return "%s-%s-dpi%s-%s" % (target, mode, str(dpi).replace(".", "p"), phase)


def profile_id(os_name, qt_version, backend="software"):
    os_name = str(os_name).lower()
    if os_name not in ("linux", "windows", "darwin"):
        raise ValueError("Unsupported golden OS")
    if not str(qt_version).startswith("6.8.3") or backend != "software":
        raise ValueError("R52.B3 requires pinned Qt 6.8.3 software profile")
    return "%s-qt%s-%s" % (os_name, qt_version, backend)


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def fixture_scene():
    """Fixed authored-free test content; same records in Studio and Player."""
    return {
        "mission": "r52b3-golden",
        "width": 6, "height": 6,
        "tiles": [{"x": x, "y": y, "height": 2 if (x, y) == (4, 3) else 0,
                   "surface": "stone" if (x, y) == (2, 2) else "grass"}
                  for y in range(6) for x in range(6)],
        "actors": [], "objects": [], "structures": [], "interior_floors": [],
    }


def expected_world_anchors():
    """Pre-reviewed world-space anchors independent of Qt/DPI/camera scale."""
    return {
        "isometric": {"tile:1:1": (0, 48), "tile:2:2": (0, 96),
                      "tile:4:3": (48, 144)},
        "top_down": {"tile:1:1": (64, 64), "tile:2:2": (128, 128),
                     "tile:4:3": (256, 192)},
        "side": {"tile:1:1": (64, 24), "tile:2:2": (128, 48),
                 "tile:4:3": (256, 48)},
    }


def reference_projection(mode):
    """Headless deterministic anchors used before any Qt screenshot attempt."""
    from drawtemp.render.iso_scene import (IsoProjection, TopDownProjection,
                                           SideProjection, Camera, render_items)
    projections = {"isometric": IsoProjection, "top_down": TopDownProjection,
                   "side": SideProjection}
    if mode not in projections:
        raise ValueError("Unknown reference projection")
    scene = fixture_scene()
    camera = Camera(width=640, height=480)
    projection = projections[mode]()
    camera.center(*projection.project(2.5, 2.5))
    rows = {row["id"]: row for row in render_items(scene, camera, projection)}
    return {key: (rows[key]["sx"], rows[key]["sy"])
            for key in expected_world_anchors()[mode]}


def _checked_png(root, filename, expected_hash):
    if (not isinstance(filename, str) or not filename.endswith(".png") or
            filename.startswith(".") or "/" in filename or "\\" in filename):
        raise ValueError("Unsafe visual filename")
    if (not isinstance(expected_hash, str) or len(expected_hash) != 64 or
            any(x not in "0123456789abcdef" for x in expected_hash)):
        raise ValueError("Invalid visual SHA-256")
    path = Path(root) / filename
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("R52 visual frame missing: %s" % path)
    if fingerprint(path) != expected_hash:
        raise ValueError("R52 visual frame has changed: %s" % path)
    return path


def _validate_capture(report, root):
    if (report.get("schema") != SCHEMA or report.get("capture_complete") is not True or
            report.get("profile") != profile_id(report.get("os"), report.get("qt")) or
            not isinstance(report.get("cases"), dict) or
            set(report["cases"]) != {case_id(*item) for item in EXPECTED}):
        raise ValueError("Incomplete/unqualified R52.B3 candidate matrix")
    for target, mode, dpi, phase in EXPECTED:
        key = case_id(target, mode, dpi, phase)
        row = report["cases"][key]
        if (row.get("target") != target or row.get("mode") != mode or
                row.get("dpi") != dpi or row.get("phase") != phase or
                row.get("capture_status") != "captured" or
                type(row.get("width")) is not int or row["width"] <= 0 or
                type(row.get("height")) is not int or row["height"] <= 0):
            raise ValueError("Invalid candidate metadata: " + key)
        _checked_png(Path(root) / "actual", key + ".png", row.get("sha256"))


def load_approved(golden_root, profile):
    manifest = Path(golden_root) / profile / "manifest.json"
    if not manifest.is_file():
        return None
    data = json.loads(manifest.read_text("utf-8"))
    if (data.get("schema") != SCHEMA or data.get("profile") != profile or
            data.get("reviewed") is not True or
            not isinstance(data.get("reviewer"), str) or
            not data["reviewer"].strip() or
            not isinstance(data.get("cases"), dict) or
            set(data["cases"]) != {case_id(*item) for item in EXPECTED}):
        raise ValueError("R52.B3 golden manifest not reviewed/complete")
    for target, mode, dpi, phase in EXPECTED:
        key = case_id(target, mode, dpi, phase)
        row = data["cases"][key]
        if (row.get("target") != target or row.get("mode") != mode or
                row.get("dpi") != dpi or row.get("phase") != phase or
                row.get("filename") != key + ".png"):
            raise ValueError("Golden metadata mismatch: " + key)
        _checked_png(manifest.parent, row["filename"], row.get("sha256"))
    return data


def evaluate_capture(root, golden_root, report):
    """Parity and optional approved-baseline comparison are separate gates."""
    _validate_capture(report, root)
    approved = load_approved(golden_root, report["profile"])
    comparisons = {}
    root = Path(root)
    parity_pass = True
    baselines_pass = approved is not None
    for mode in MODES:
        for dpi in DPRS:
            for phase in PHASES:
                pair = [case_id(target, mode, dpi, phase) for target in TARGETS]
                names = [root / "actual" / (case + ".png") for case in pair]
                metrics = compare_png(names[0], names[1],
                                      max_channel_delta=MAX_CHANNEL_DELTA,
                                      max_changed_fraction=MAX_CHANGED_FRACTION,
                                      diff_path=root / "diff" / (pair[0] + "-vs-player.png"))
                comparisons["/".join(pair)] = metrics
                parity_pass &= metrics["passed"]
    if approved is not None:
        for target, mode, dpi, phase in EXPECTED:
            key = case_id(target, mode, dpi, phase)
            before = Path(golden_root) / report["profile"] / (key + ".png")
            actual = root / "actual" / (key + ".png")
            metrics = compare_png(actual, before,
                                  max_channel_delta=MAX_CHANNEL_DELTA,
                                  max_changed_fraction=MAX_CHANGED_FRACTION,
                                  diff_path=root / "diff" / (key + "-vs-golden.png"))
            report["cases"][key]["golden_comparison"] = metrics
            baselines_pass &= metrics["passed"]
    report.update(
        parity_pass=bool(parity_pass), goldens_reviewed=approved is not None,
        golden_pass=bool(baselines_pass),
        comparison="pass" if parity_pass and baselines_pass else
                   "fail" if not parity_pass or (approved is not None and not baselines_pass)
                   else "blocked",
        parity=comparisons,
        hardware_gpu_certified=False,
        release_certified=False,
    )
    return report


def approve_candidates(capture_root, golden_root, *, reviewer):
    """Explicit review step only: CI never promotes its own screenshots."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Named human reviewer required")
    capture_root = Path(capture_root)
    report = json.loads((capture_root / "r52-visual.json").read_text("utf-8"))
    _validate_capture(report, capture_root)
    if report.get("parity_pass") is not True:
        raise ValueError("Cannot approve a failed/unverified Studio/Player parity")
    profile = report["profile"]
    folder = Path(golden_root) / profile
    if (folder / "manifest.json").exists():
        raise ValueError("Already reviewed; use a separate code-reviewed update")
    folder.mkdir(parents=True, exist_ok=True)
    rows = {}
    for target, mode, dpi, phase in EXPECTED:
        key = case_id(target, mode, dpi, phase)
        original = _checked_png(capture_root / "actual", key + ".png",
                                report["cases"][key]["sha256"])
        shutil.copyfile(original, folder / (key + ".png"))
        rows[key] = {"target": target, "mode": mode, "dpi": dpi, "phase": phase,
                     "filename": key + ".png",
                     "sha256": fingerprint(folder / (key + ".png"))}
    write_json(folder / "manifest.json", {
        "schema": SCHEMA, "profile": profile, "reviewed": True,
        "reviewer": reviewer.strip(), "cases": rows,
        "source_revision": report.get("revision", "unknown"),
    })
    return folder / "manifest.json"
