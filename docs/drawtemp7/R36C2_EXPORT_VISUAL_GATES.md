# R36.C2 — Export rights & independently reviewed visual candidates

**PR:** [#375](https://github.com/faudard/drawTemp/pull/375).
**Status:** candidate code, unexecuted CI; **not** a release certification.

## 1. Canonical R15 export preflight now covers R36 assets

The existing R15 `preflight(content_path, require_licenses=...)` remains the
authoritative gate for project integrity, all registered on-disk assets,
human-supplied file-bound rights attestations, evidence files and any
native-bundle packaging. For GameProjects with an
`org.drawtemp.animation` controller extension, it also includes
`report["r36_animation"]` from `audit_r36_rights()`.

R36-specific checks (headless, no second asset schema):

- Discover every R28 animation reference in authored R36 controllers,
  and every R28 sprite ID used by those animation frames (max 256 IDs).
- Resolve each physical PNG relative to the existing project root using
  R15 safe paths and R28 registry confinement.
- Validate actual PNG chunks, IHDR, CRC, file limit and each atlas region
  using existing R4 `png_dimensions`.
- Hash **physical files** once by path: two sprites sharing one atlas are
  not independently relicensed or accidentally copied twice.
- When present, validate R4 optional annotations, source SHA-256 and
  license claim against the PNG and approved R15 license ID.
- Reuse R15 `_check_asset_rights` for `asset-licenses.json` schema 1:
  `approved` status, modification and redistribution permissions,
  rights holder/license ID, matching PNG hash and project-local non-empty
  `licenses/` evidence.

A missing rights index warns during preview. Strict `--require-licenses`
turns missing/invalid evidence into errors and rejects R36 files with
inconsistent R4 metadata. There is no automatic legal attestation;
validation establishes **internal consistency, not legal ownership**.

Projects with no R36 controller retain the historical R15 preflight
report schema and behavior. All existing R15 release requirements,
including native executable and R14 evidence, still apply.

Usage:

```bash
python -m drawtemp.export.cli check --content /project/game.json
python -m drawtemp.export.cli check --content /project/game.json --require-licenses
```

The `r36_animation.release_ready` flag can only be true when strict
R15 rights evidence passed; it does not replace global `report.passed`
and is **not** a standalone export approval.

## 2. R36 visual candidate matrix, separate from approved R14.5 baselines

`scripts/r36_visual_candidates.py` reuses R14.5 screenshot manifest,
`compare_png`, reviewer approval and HTML comparison machinery.
The R36 capture folders and baseline root are separate from R14:

```bash
python scripts/r36_visual_candidates.py matrix
python scripts/r36_visual_candidates.py capture --output r36-candidates
```

The script generates **12 actual Qt frames**, each in a separate
subprocess with DPI and software backend fixed before Qt startup:

| Target | DPI | Zoom |
|---|---|---|
| Studio R36 visual timeline | 1× and 2× | 0.75, 1.0, 1.5 |
| R26 Action Player with R36-bound PNG hero | 1× and 2× | 0.75, 1.0, 1.5 |

The Studio target displays a real R1-authored animation/marker timeline.
The Player uses the same authored R28 PNG frames, R36 Animation Controller
and R3 Qt viewport. It does not silently reuse a tactical-board screenshot.

`actual/*.png`, `metadata/*.json`, `r36-visual.json`,
`r14-visual.json`, HTML diff report and diagnostics are candidate artifacts.
A real capture is required; null/blank frames fail. Missing independent
approved goldens produce `comparison=blocked`, never `pass`.

Only **after a human reviews all twelve pictures** can a reviewer run:

```bash
python scripts/r36_visual_candidates.py approve \
  --capture r36-candidates --reviewer "Reviewer name"
```

This explicitly copies the approved images and reviewed manifest to
`tests_standalone/goldens/r36/<os>-qt6.8.3-software/` using R14.5's
immutable/hash-checked approval process. It fails if the baseline already
exists. Do **not** use this in CI; approval belongs to an independent PR.

Once approved images exist, enforce:

```bash
python scripts/r36_visual_candidates.py capture \
  --output r36-verify --require-approved
```

The R14.5 pixel-diff thresholds are reused (12/255 per channel,
0.1% changed pixels maximum), but an offscreen software comparison is
not a physical GPU parity certification.

## 3. Tests and CI

Headless:

```bash
python -m unittest tests_standalone.test_r36_release_rights -v
python -m unittest tests_standalone.test_r36_visual_candidates -v
python -m unittest tests_standalone.test_drawtemp5_r15 -v
```

Qt 6.8.3 offscreen job also captures 12 real candidate images and
uploads them as temporary CI artifacts for independent review. No job
auto-approves baselines.

## 4. Explicit open gates

- Actual GitHub Actions runners have so far failed before scheduling jobs.
  **No green CI certification may be inferred from authored tests.**
- Real independent review and a committed R36 12-case baseline per OS.
- R36 hardware-backed GPU timing and capture, resource usage and
  p95/p99 against agreed budgets and render backends.
- Directional/equipment art, tactical/platform parity, authoritative
  combat-hitbox synchronization, true per-pixel lighting and effects.
- Licensed native release requires all global R15/R14 preconditions;
  R36.C2 alone never authorizes one.
