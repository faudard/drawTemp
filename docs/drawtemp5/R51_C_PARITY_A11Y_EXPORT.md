# R51.C — UI & HUD parity, accessibility and export safety (initial tranche)

**20 October 2026 — Implementation PR on top of the integration branch.**
**Status: engineering increments only; R51 and 10.0 release gate are NO-GO.**
R51.A #397, R51.B #404 and R51.B2 #405 were merged into
`integration/consolidate-r31-r55-20261020`, **not into `master`** at
the time this lot was authored.

The product roadmap demands complete replacement of the CT and Action
game interfaces, approved screenshot goldens, keyboard and physical
controller UX, licenses, and real clean-machine PC exports. These criteria
are **not** fulfilled by this PR.

## Implemented

### 1. Shared Studio/Player themes

- Shared `R51Layout.qml` exposes `highContrast` and `textScale` and
  passes them into recursively authored `R51Node.qml` descendants.
- High-contrast black/white surface and foreground, clearly visible
  keyboard focus borders, scalable plain-text labels/gauges/buttons,
  minimum authored button height 44 logical pixels, action/state
  descriptions in Qt's accessibility tree.
- The Player passes through actual R12 `settings.display.high_contrast`
  and `settings.display.text_scale`, without altering saves or CT rules.
- Studio preview now exposes equivalent contrast and text-scale inputs;
  retained preview samples remain marked **synthetic**, and Studio warns
  when `DIALOGUE`, `INVENTORY`, `HUD_ACTION` have no Player equivalent.

### 2. Explicit Player capability / parity report

Run from repository root:

```bash
python -m drawtemp.quality.r51_ui --project path/to/game.game.json
```

The returned JSON has `present`, canonical schema SHA-256, screens
and explicit errors/warnings. Current runtime supported screen kinds:
`MENU` and `HUD_CT`, with only implemented action intents:

- MENU: `menu.new_game`, `menu.continue`, `menu.options`,
  `menu.quit` (options/quit are fixed, native Qt actions).
- HUD_CT: `combat.end_turn` (guarded, canonical R12/R1 execution).

An unsupported kind or unsupported action is **not** reported as a
functional Player screen. A title MENU with session/combat bindings or
without New Game is reported as invalid. Multiple runtime layouts of
the same kind are explicitly blocked to prevent ambiguous selection.

### 3. R15/Creator fail-closed export

Legacy games without `org.drawtemp.ui` retain their current R15 behavior.
For **opted-in R51 UI games**:

- `preflight` checks actual runtime capabilities against the authored
  catalog (not only whether the JSON can deserialize).
- Every registered physical asset requires approved, file-hash-bound,
  project-local rights evidence **even for a preview export**, rather
  than silently continuing on a warning. Existing R17 rights checks and
  cross-OS path guards are reused; this code cannot judge legal truth.
- The preflight runs again on copied bytes. The hash and exact enumerated
  screens enter the *existing* hashed bundle manifest as `ui`.
- `verify_bundle` rejects missing or forged UI evidence and checks that
  the manifest's UI digest and screen rows match the actual archived
  canonical `GameProject`. Already-hashed files continue to be checked.
- `require_release=True` still demands complete separate R14 release
  evidence; synthetic unit-test authorizations do **not** grant licenses.

### 4. Verifiable tests and distribution resources

```bash
python -m unittest -v tests_standalone.test_r51c_export \
  tests_standalone.test_r51c_theme_contract \
  tests_standalone.test_r51c_wheel \
  tests_standalone.test_drawtemp5_r15 \
  tests_standalone.test_r17_asset_rights

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R51_QT_GATE=1 python -m unittest -v \
  tests_standalone.test_r51b_qt tests_standalone.test_r51c_qt_parity

python -m pip install build
python -m build --wheel
python scripts/r51c_verify_wheel.py dist/<wheel-file>.whl
```

- R51.C GitHub Actions stages headless rights/parity tests on
  **Linux/Windows/macOS**, Qt offscreen software parity captures on
  Linux, and actual wheel QML presence/hash checks on three OS.
- The Qt test compares framebuffer digests of two instances of the
  exact shared `R51Layout.qml` using identical projection and theme;
  it also requires visual output to change in high contrast.
  This is **not** an approved screenshot golden or complete
  Studio-vs-Player-window pixel comparison.
- Wheel proof only confirms resources in the built Python distribution.
  It is **not** a native PyInstaller runtime presence proof, GPU E2E
  or clean-machine trial.

## Gate R51: currently NOT MET

| Gate | Status |
| --- | --- |
| Typed screen contract, R1 authoring transaction | In code; CI to validate |
| Real CT Player HUD intent | Implemented narrow opt-in; E2E open |
| Studio/Player contrast and typography | Component path implemented; manual UX open |
| New Game/Continue authored title | Implemented opt-in; hardware verification open |
| Dialogue/inventory/action game full replacements | **NOT IMPLEMENTED** |
| Real AZERTY/QWERTY/gamepad physical UX and screen reader | **NOT VERIFIED** |
| Approved screenshots at DPI 1x/2x and high contrast | **NOT APPROVED** |
| Actual executable bundles on clean machines, 3 OS | **NOT VERIFIED** |
| Redistribution provenance for all distributed assets | Technical preflight added; human/OS evidence open |
| Whole-game release on final `master` SHA | **NO-GO** |

### Merge discipline

1. Base branch: `integration/consolidate-r31-r55-20261020` after
   #397/#404/#405. No implicit merge into `master`.
2. Run tests on PR SHA with **actually launched** jobs, inspect failure
   logs and list remaining issues. Prior GitHub Actions failures with
   zero spawned jobs do not count as executed tests.
3. Reconcile with any subsequent changes to the integration branch.
4. Proceed with missing `DIALOGUE`/`INVENTORY`/`HUD_ACTION`
   Player renderers and full physical-machine qualification, then
   make an explicit GO/NO-GO decision for R51.C.
