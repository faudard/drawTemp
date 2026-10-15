# DrawTemp 5.0 — R14 Quality, Performance & Reliability

## Scope and current acceptance state

This PR establishes an **executable, fail-closed certification baseline**, not an R14 release sign-off.
R14 is transverse across R0–R16. The existing Tk application is kept intact until an equivalent Qt path is exercised and certified.

| Roadmap lot | What this tranche exercises | Still required to close the lot |
| --- | --- | --- |
| R14.1 Cross-Platform CI | Python 3.12 + pinned PySide6 6.8.3 on Windows, Linux and macOS; CI evidence aggregation | Green cross-platform CI and review of runner artefacts |
| R14.2 Core Unit Tests | Existing R0/R1 simulation, authoring, replay and migration suites | Broader Core, AI, rules and schema matrix |
| R14.3 Qt Integration Tests | Real Qt Widgets + project QML composition, resize, focus and keyboard events under offscreen | Studio/Player production models, signals, transactions and focus |
| R14.4 GUI End-to-End | None; an isolated Qt smoke **is not** Player E2E | Onscreen automated journeys: Studio → Player → save → resume, mouse and keyboard |
| R14.5 Visual Goldens | Real Qt Studio/Player 1×/2× captures at zoom 0.75/1/1.5 (12 per OS), reviewed SHA-256 manifests and HTML/JSON/PNG diffs | Approval of each OS baseline plus onscreen visual sign-off; software captures alone remain partial |
| R14.6 GPU Profiling | Reject software/offscreen profiles; validate external real-GPU frame samples and percentile computation | Real GPU measurements for CPU/GPU/VRAM/leaks/loading and repeatable runner |
| R14.7 Large Map Scale | Require 32²/64²/128² × 24/54/96 px, ≥120 frames/scene and ≥80 actors in supplied profile | Author and benchmark representative renderer scenes and calibrate budgets |
| R14.8 Long Session | Existing checkpointed three-mission, two-seed, two-ending integration | Prolonged soak with resume/fault cycles and memory leak detection |
| R14.9 Crash Recovery | Existing persistence fault test suite | Qt/5.0 save manager integration and interruption/fallback UX |
| R14.10 Security & Validation | Non-destructive asset path containment, drive/traversal/symlink and SHA-256 manifest checks | Apply to all real import/export entry points and fuzz third-party inputs |
| R14.11 Accessibility QA | Keyboard driver foundation only | Screen-reader, focus/contrast/text-size audit of real Qt UI |
| R14.12 Release Certification | Structured report with explicit missing/failed checks, source revision and matrix evidence | Full R14 gate, release acceptance and signed-off performance/visual evidence |

Only **complete evidence** may be marked passed. A successful but incomplete probe is recorded as `partial`; absent evidence is `blocked`. A process failure is `fail`. A release can be marked certified only when **every P0 lot** has `pass` and the report is independently reviewed. No CI job should claim a GPU benchmark from Qt's software or offscreen backend.

## Run locally

Install dependencies from the current repository:

```sh
python -m pip install ".[qt6]"
```

On Python 3.12, to generate actual test logs and a machine-readable report:

```sh
python scripts/certify_drawtemp5_r14.py --report out/r14-report.json
# For Qt software-backed functional tests (NOT real GPU certification):
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python scripts/certify_drawtemp5_r14.py --report out/r14-report.json --qt --soak --faults
```

The latter environment syntax is for bash; on Windows set those environment variables before running Python. The script executes the existing Core SDK tests, the new R14 contract tests, optionally the Qt test, the checkpointed gameplay fixture, and the existing crash/fault suite. Each test writes a log, records a process return code, and fails its CI job on a non-zero result. The generated JSON does **not** certify R14. The long-session and fault probes are intentionally bounded and are not full-duration soak tests.

The GitHub Actions workflow `.github/workflows/drawtemp5-r14.yml` runs the same evidence probes on all three OSes, uploads per-run artefacts, and aggregates them. The aggregate refuses to mark the cross-platform check passed if any required probe is missing or unsuccessful.

For release validation:

```sh
python scripts/certify_drawtemp5_r14.py --aggregate r14-artifacts \
  --report r14-aggregate.json --require-complete
```

This **must fail** until all P0 lots have acceptable evidence. Do not waive blocked checks with fabricated `pass` fields.

## Real-GPU profile input contract

The optional `--gpu-profile measured.json` accepts schema 1 data with the required fields below. It validates submitted **external measurements**; it does not run a renderer benchmark or verify the asserted hardware identity. Hardware data and raw samples must be collected from an identified GPU runner, captured as unmodified job artefacts and reviewed.

```json
{
  "schema": 1,
  "device": {
    "os": "Linux",
    "gpu": "ADAPTER_NAME_FROM_DRIVER",
    "driver": "DRIVER_VERSION",
    "qt": "6.8.3",
    "backend": "vulkan",
    "software": false,
    "resolution": [1920, 1080]
  },
  "scenes": [
    {
      "map_size": 32,
      "zoom_px": 24,
      "actors": 80,
      "frame_times_ms": []
    }
  ]
}
```

The example is **illustrative and deliberately invalid** (missing raw frame samples and eight other scene configurations). Each scene requires at least 120 numeric finite nonnegative frame-time observations; the matrix requires all nine map/zoom pairs and at least one scene with 80 actors. The report calculates p50/p95/p99 in milliseconds and identifies the device. Thresholds (including the provisional p95 16.7 ms / 60 FPS) are **informational** until a hardware baseline is recorded and approved. Real GPU VRAM, CPU and driver metrics must be added before closing R14.6.

## Security, reproducibility and evidence policy

The asset validator `drawtemp.quality.r14.validate_asset_manifest(root, entries)` rejects traversals, absolute/drive paths, embedded NULs, path aliases, missing files, paths resolving outside a project root, duplicate paths and mismatched SHA-256 digests. It is a contract for future import/export integration; do not treat its presence as protection for unmodified legacy importers.

Each report captures host OS, Python, runner OS, source revision, per-probe logs and coverage. Do not suppress historical failures or reclassify skipped tests as passed. Any regression should leave an actionable report with its failed command and log. Qt software tests, virtual display tests, visual goldens and real-GPU measurements must be labelled separately. Retain artefacts from representative Windows, macOS and Linux hosts; record GPU, driver, Qt backend and display resolution for measurements.

See [the R14 roadmap](../DRAWTEMP_5_0_ROADMAP.md#r14) and [the existing R0 foundation CI](../../.github/workflows/drawtemp5-r0.yml).

## Second tranche — GUI action journeys and visual baseline tooling

The R14 continuation adds `--gui --visual` to the evidence runner:

```sh
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software DRAWTEMP_R14_ARTIFACT_DIR=r14-images \
  python scripts/certify_drawtemp5_r14.py --report r14-report.json --qt --gui --visual
```

- **R14.4 (partial):** `tests_standalone/test_drawtemp5_r14_gui.py` drives the real R5 `MapWindow` with Qt mouse events: paint a tile, Undo, Redo, Save, reopen the Content/GameProject pair. It also loads the actual R12 `Main.qml` with its production `PlayerBridge`, clicks New Game → narrative choice → mission → Save → Continue, and compares replay recordings. The bridge is now exposed by `create_bridge` so the test does not mock Player calls.
- **R14.5 (partial):** `drawtemp.quality.visual.compare_png` compares decoded RGBA pixels rather than PNG files, with explicit per-channel tolerance and changed-pixel fraction; a diff heatmap is emitted on demand. A missing approved golden is **always an error**; no capture is silently promoted to baseline. `tests_standalone/test_drawtemp5_r14_visual.py` asserts exact equivalence, tolerance behavior, visible differences, mismatched dimensions and rejection of missing goldens.
- **Capture evidence:** the GUI job uploads `r14-images/r14-studio.png` from the actual R3 viewport and, when supported, `r14-images/r14-player.png` from the Player. These are **candidate snapshots for review**, not approvals or golden comparisons. CI does not claim multi-DPI coverage.
- **Scope still open:** full onscreen GUI paths on physical desktops, approved and versioned per-backend goldens across DPI/zoom, color management/font variation policy, accessibility QA and real GPU frame samples. R14.4 and R14.5 remain `partial`, and R14.12 remains `blocked`.

To compare a reviewed reference with a fresh screenshot:

```python
from drawtemp.quality.visual import compare_png
result = compare_png(
    "captures/studio.png", "approved/linux-qt6/studio.png",
    max_channel_delta=12, max_changed_fraction=0.001,
    diff_path="captures/studio.diff.png")
assert result["passed"], result
```

The reference must be reviewed and committed or supplied from a trusted release baseline, and matched to the tested Qt backend/DPI; generating a golden from the same run under test is not permitted.


## R14.5 — Visual Goldens multi-DPI / multi-zoom

This tranche extends the already merged compare_png comparator. It captures **real Qt Quick content**, not synthetic fixture PNGs. Each scene/DPI/zoom variant runs in a fresh Qt process so QT_SCALE_FACTOR is set before QApplication is instantiated. The Studio MapWindow and the reference R12 Player battle render through the shared R3 scene graph.

**Matrix:** Studio and Player × 1× and 2× pixel density × 0.75 / 1.0 / 1.5 camera zoom: **12 screenshots per OS**, on Linux, Windows and macOS. The software-backed runners pin Python 3.12 and PySide6 6.8.3. Failure to honor the requested DPR, unexpected backend, incomplete matrix or a null frame is a hard error.

Baselines are scoped to platform + Qt + backend under tests_standalone/goldens/r14/{os}-qt6.8.3-software/. A versioned manifest lists all twelve cases, dimensions, immutable SHA-256 hashes, captured commit, named human reviewer and approval time. Missing, invalid and modified approved references do not pass. A candidate capture is **never automatically promoted**.

### Run capture and review

~~~sh
python -m pip install ".[qt6]"

# Capture new candidate images and report; no certification implied.
python scripts/r14_visual_goldens.py capture --output r14-goldens-report

# Separately, after inspecting real images + side-by-side HTML,
# manually approve into a new commit/PR:
python scripts/r14_visual_goldens.py approve --capture r14-goldens-report \
  --reviewer "human-reviewer"
git add tests_standalone/goldens/r14

# Require previously approved references when comparing a fresh run:
python scripts/r14_visual_goldens.py capture --output r14-verified \
  --require-approved
~~~

The separate GitHub Actions workflow (.github/workflows/drawtemp5-r14-goldens.yml) uploads per OS: actual/*.png, baseline/*.png when reviewed, diff/*.png heatmaps, metadata/*.json, per-case logs, r14-visual.json and an index.html side-by-side comparison report.

**Tolerance:** a pixel changes when the maximum RGBA channel difference exceeds **12/255**; at most **0.1%** of pixels may exceed that channel limit. Exact dimensions are mandatory. Fully transparent pixels are compared by alpha only. This criterion is explicitly configurable in the existing comparison primitive but is fixed for the R14.5 release matrix. Use separate approved baselines for different OS / Qt / backend profiles, not artificially relaxed tolerances.

**Fail-closed interpretation:** a capture job may be successful while the *golden comparison* is BLOCKED for want of a reviewed baseline. Strict --require-approved returns an error for missing or mismatched goldens. Even twelve passing software comparisons do not prove real GPU performance, onscreen composition, color management or accessibility. R14.5 stays partial until physical-desktop review and R14.12 stays blocked.
