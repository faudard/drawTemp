# DrawTemp 5.0 — R14 Quality, Performance & Reliability

## Scope and current acceptance state

R14 uses an **executable, fail-closed certification baseline**, not a release sign-off. The follow-up tranche adds strict multi-OS artefact provenance and input-driven Qt Studio/Player regression journeys.
R14 is transverse across R0–R16. The existing Tk application is kept intact until an equivalent Qt path is exercised and certified.

| Roadmap lot | What this tranche exercises | Still required to close the lot |
| --- | --- | --- |
| R14.1 Cross-Platform CI | Python 3.12 + pinned PySide6 6.8.3 on three OSes; aggregation rejects duplicate/missing runners, missing logs, nonzero exit codes and mixed or stale revisions | Actual green three-runner CI on the last SHA, manual review of artefacts |
| R14.2 Core Unit Tests | Existing R0/R1 simulation, authoring, replay and migration suites | Broader Core, AI, rules and schema matrix |
| R14.3 Qt Integration Tests | Real Qt Widgets + project QML composition, resize, focus and keyboard events under offscreen | Studio/Player production models, signals, transactions and focus |
| R14.4 GUI End-to-End | Qt Map Studio paint → undo/redo → save/reopen; production Qt Player title → dialogue → campaign → battle → F5 → title → reload (offscreen/software) | Joined Studio-authored project → Player journey on a real display, runner recordings |
| R14.5 Visual Goldens | Framework specification | Reproducible Studio/Player scene goldens at DPI and zoom variants, diff artefacts, tolerances |
| R14.6 GPU Profiling | Reject software/offscreen profiles; validate external real-GPU frame samples and percentile computation | Real GPU measurements for CPU/GPU/VRAM/leaks/loading and repeatable runner |
| R14.7 Large Map Scale | Require 32²/64²/128² × 24/54/96 px, ≥120 frames/scene and ≥80 actors in supplied profile | Author and benchmark representative renderer scenes and calibrate budgets |
| R14.8 Long Session | Existing checkpointed three-mission, two-seed, two-ending integration | Prolonged soak with resume/fault cycles and memory leak detection |
| R14.9 Crash Recovery | Persistence fault suite plus interrupted backup copy/atomic publish tests against the real R12 PlayerController; last valid backup preserved | GUI recovery messaging and full power-loss interruption test on each OS |
| R14.10 Security & Validation | Non-destructive asset path containment, drive/traversal/symlink and SHA-256 manifest checks | Apply to all real import/export entry points and fuzz third-party inputs |
| R14.11 Accessibility QA | Keyboard driver foundation only | Screen-reader, focus/contrast/text-size audit of real Qt UI |
| R14.12 Release Certification | Structured report, revision matching, environment verification, logs for every probe and explicit missing/failed checks | Full R14 gate, release acceptance and signed-off performance/visual evidence |

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

The latter environment syntax is for bash; on Windows set those environment variables before running Python. The script executes the existing Core SDK tests, the R14 contract/matrix tests, optionally both native Qt GUI journeys and the composition smoke, the checkpointed gameplay fixture, the legacy crash/fault suite, and Player slot-backup interruption tests. Each test writes a log, records a process return code, and fails its CI job on a non-zero result. The generated JSON does **not** certify R14. The long-session and fault probes are intentionally bounded and are not full-duration soak tests.

The GitHub Actions workflow `.github/workflows/drawtemp5-r14.yml` runs the same evidence probes on all three OSes, uploads per-run artefacts, and aggregates them.

### UI regression journeys (R14.4 — partial)

The Qt test module `tests_standalone.test_drawtemp5_r14_gui` uses real Qt mouse/keyboard injection. The Map Studio journey paints a tile through QML MouseArea, uses toolbar undo/redo and saves/reopens canonical Content/GameProject. A separate Player subprocess drives production `Main.qml` and `PlayerBridge`: New Game, narrative decision, mission, F5, pause/title, Continue, and comparison of the reloaded battle snapshot.

Run the Player journey independently with an isolated slot directory:

```sh
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.qt_app --reference --gui-journey \
  --save-dir /tmp/drawtemp-r14-ui-slots
```

This is software-backed input E2E only. It does not prove OS compositor behaviour, Studio-to-Player transfer of arbitrary edited content, frame-rate, visual identity, screen readers or GPU performance. A passing test marks R14.4 `partial`, never a release-certified `pass`.

### CI evidence integrity

The `drawtemp.quality.r14_matrix.inspect_matrix` gate requires Linux, macOS and Windows independently. Each source must have a unique runner, Python 3.12, PySide6 6.8.3, the same 40-hex commit ID as the aggregate run, six completed probes (QA, Core, Qt, GUI, soak and faults) and their nonempty per-probe logs. Missing, corrupt, ambiguous or stale evidence yields a nonzero aggregation exit and an explicit `R14.1=fail` reason. This does not certify any other unfinished lot.
 The aggregate refuses to mark the cross-platform check passed if any required probe is missing or unsuccessful.

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
