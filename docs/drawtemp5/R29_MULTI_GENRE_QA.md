# R29.A — Multi-genre Quality Evidence (6.5, incremental)

**Status:** proposed code in PR; **NOT certified**. The R29.A tranche is a
headless, fail-closed evidence collector built on real R1/R13/R14/R15 tests.
It does **not** implement R25–R28 gameplay, an Action/RPG runtime, an
approved visual baseline, licensed distribution, a clean-machine test or a
human gameplay review. It must remain honest even when CI is green.

## Traceability

| Requirement | Current executable coverage | Remaining release blocker |
| --- | --- | --- |
| R29.1 / P0 | R1.E canonical Jeanne CT/RNG/event/disk replay | fixed-tick action and classic RPG deterministic replay, same versioned state digest |
| R29.2 / P0 | R14 pixel comparison contract | approved Studio/Player goldens for each genre, top-down/iso, OS and DPI |
| R29.3 / P0 | R14 recovery fault regressions | migration from historical saves and crash recovery across mixed gameplay modes |
| R29.4 / P0 | R15 export integrity regressions | actual runnable Windows/Linux/macOS bundles on clean machines |
| R29.5 / P0 | INT-03 asset contract tests | complete permissions/provenance of every shipped asset; verify distribution fail-closed |
| R29.6 / P1 | none; explicit blocked | externally measured GPU/CPU/memory/stutter data per mode |
| R29.7 / P0 | none; explicit blocked | controlled creator/user tests for each genre and complete export flow |
| R29.8 / P1 | R13 tactical replay/diagnostics | action timeline, AI causes, heatmaps and interactive explorer |
| R29.9 / P0 | certified tactical campaign path test contracts | authored quest/dungeon puzzle state-space checks and anti-softlock E2E corpus |
| R29.10 / P0 | SHA-bound no-go report and independent OS matrix | complete P0 proof, written human sign-off and release go/no-go decision |

The `partial` status means only that **bounded regression tests passed**,
not that a roadmap lot was delivered. `blocked` is missing proof;
`fail` means a probe genuinely failed. The tool intentionally has no way
to automatically issue an R29 release `pass` from these unit tests.

## Local usage

Prerequisite: Python 3.12 and the repository's pinned optional dependencies:

```sh
python -m pip install ".[qt6,art]"
python -m unittest tests_standalone.test_r29_quality -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python scripts/certify_multigenre_r29.py --report build/r29/r29-report.json
```

The CLI runs seven existing bounded test suites, records real process exit
codes and nonempty log bytes and writes `sha256` per log. Process failures
are reflected as `fail`, and the CLI exits nonzero. On successful probes
the CLI can exit 0 **while the report explicitly says `no-go`**; that is
green *QA infrastructure*, not a release approval.

For the intentional release gate:

```sh
python scripts/certify_multigenre_r29.py \
  --report build/r29/r29-report.json --require-release
```

It returns code 2 while the R29 certification is incomplete. No CI pipeline
should invert or omit this condition when labelling an actual release.

## CI evidence integrity

`.github/workflows/drawtemp-r29-quality.yml` tests the contracts and
collects the real logs on Linux, Windows and macOS (Python 3.12). A separate
aggregate job checks:

- all three unique OS reports, immutable 40-digit SHA identical to the
  aggregator revision;
- every declared probe actually executed with a valid exit-code/status pair;
- nonempty local logs, named by allowlisted probe and matching SHA-256;
- exact check matrix, including blocked action/RPG modes, and no modified
  `release_ready`, `decision` or status fields;
- no skipped, duplicated, corrupt, stale or failed source promoted to a
  successful matrix.

To inspect downloaded workflow artifacts locally:

```sh
python scripts/certify_multigenre_r29.py \
  --aggregate build/r29-artifacts --report build/r29-matrix.json
```

The matrix's `matrix_verified=true` means *only* that three consistent
sets of bounded test evidence were collected, not that R29 is complete.
`release_ready` stays false. A matrix cannot attest to GPU measurements
or installation on machines without Studio/Python.

## Next implementation gates (R29.B)

1. After R25/R26, add fixed-tick action command trace + replay/save
   comparison using actual Core/GameSession adapters.
2. After R28, add classic RPG and hybrid transition replay fixtures, verifying
   persistent inventory/quest flags and no duplicate rewards.
3. After R27, add gameplay state-space softlock checks, with an explicit
   visited-state cap, testable counterexamples and no false complete coverage.
4. Extend R14 approved screenshot manifests to top-down and isometric
   Studio/Player matrices; run hardware probes separately.
5. Integrate R15 clean-machine distribution, hard license gates, external user
   reports and release-manager sign-off. Never infer completeness from test
   names alone.

See [R29 in the multi-genre roadmap](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md#9-r29--quality-gameplay-lab--publishing-65),
the existing [R14 QA contract](R14_QUALITY.md) and
[R17 native export](R17_8_ISOLATED_NATIVE_EXPORT.md).
