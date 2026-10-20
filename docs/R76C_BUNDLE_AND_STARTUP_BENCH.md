# R76.C1 — reproducible Bundle & Python-Load Benchmarks

**State: evidence tooling delivered, R76.C release gate remains NO-GO.**
This first slice starts from the R76.A–B1 code already on `master`.
R76.B2 PR #450 was closed without merge: this benchmark **does not depend on**
the abandoned consolidation branch or on an unmerged export feature.

## What is actually measured

- **Real R15 bundle bytes** from a `verify_bundle`-validated directory:
  total filesystem bytes (including manifest), Player, game and other, physical
  file count, SHA-256 of manifest, Content and GameProject. Fail if any
  manifest entry, hash, symlink, unexpected file or path is invalid.
- **Fresh Python process project load latency** via a fixed
  `sys.executable -m drawtemp.quality.r76_bench _probe` command, without
  `shell=True`, using the bundled Content/GameProject pair and canonical
  `validate_pair` / `AssetRegistry`.
- **Observed heap peak** from `tracemalloc` and **process peak RSS**
  via `resource.getrusage` on Linux/macOS when available. Windows RSS is
  `null` until a separate supported collector is implemented; never zero.
- **Empirical distributions** from independent runs, after optional warmups:
  samples, minimum, p50, p95, p99, maximum, mean, population standard
  deviation and variance. Values from fewer than **100 samples** have
  `tail_exploratory=true`; 5..500 samples allowed.
- **Environment and provenance**: provided *exact* 40-hex Git revision,
  OS, architecture, Python and CPU identity, runner, interpreter path,
  manifest/content/project SHA-256, stable named corpus, asset/mission counts.
  `--revision` is an identifier and **not a cryptographic attestation that
  these bytes were compiled from that commit**.

These measurements are **not** OS cold boot, native Player startup,
texture upload, RAM of the GPU, FPS or frame-time benchmarks. Executing a
fake Player binary for evidence is forbidden. There is no native Player
automation or physical GPU telemetry in the first slice.

## Measured corpus and commands

Create two real, already-validated R15 standalone bundle directories using
the **same Content and workload** (e.g. baseline and byte-optimized variant).
They must each contain `manifest.json`, `game/` and `Player/`. The
comparison refuses different Content hashes, OS/Python/CPU environments,
revision, corpus or sampling configuration.

```sh
python -m drawtemp.quality.r76_bench collect \
  --bundle /data/r76-baseline-r15 \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --corpus jeanne-castle-v1 \
  --samples 120 --warmups 5 --output /reports/r76-baseline.json

python -m drawtemp.quality.r76_bench collect \
  --bundle /data/r76-candidate-r15 \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --corpus jeanne-castle-v1 \
  --samples 120 --warmups 5 --output /reports/r76-candidate.json

python -m drawtemp.quality.r76_bench compare \
  --baseline /reports/r76-baseline.json \
  --candidate /reports/r76-candidate.json \
  --max-p95-growth-pct 15
```

**Replace the example revision with the real 40-character checkout SHA.**
Run both on the **same machine** under controlled conditions, then repeat
on Linux, Windows and macOS with their own separately recorded comparisons.
One OS cannot be silently passed off as another. `--output` creates a
**new** JSON file and refuses overwrites or symlink destinations. Runtime
flags and repeat count must match for a fair comparison.

Open **Studio → Outils → R76.C Benchmarks et preuves de bundle…** to load
the JSON reports, inspect measured costs and see a non-certifying delta.
The Qt dialog never launches 120 child processes on its GUI thread.

### Why the comparison never authorizes a release

The relative p95 latency-growth threshold (default 15%) and whether the
bundle shrank are informational. Even a lower byte count and no slowdown
cannot establish parity of actual native game startup, screen rendering,
savegames, audio or combat.

### Externally measured GPU evidence

For additional real GPU observations, R76 reuses the **R14**
`validate_gpu_profile` contract, rather than fabricating samples:

```sh
python -m drawtemp.quality.r76_bench inspect-gpu \
  --report /external/physical-gpu-r14.json
```

R14 requires a declared non-software adapter/backend, GPU + driver +
Qt/OS/resolution, **120 frame times per scene**, the complete size/zoom
matrix and an 80-actor stress scene. This command validates the **schema
and statistics**, reporting the SHA-256 of the supplied evidence. It does
**not** independently attest that the GPU was physical, and it does not
accept GPU-memory numbers without measurements. Treat it as an
**external self-reported record**, not an R76 release certificate.

## Test gates

```sh
python -m unittest -v \
  tests_standalone.test_r76_asset_audit \
  tests_standalone.test_r76b_optimizer \
  tests_standalone.test_r76c_bench \
  tests_standalone.test_drawtemp5_r15

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest -v tests_standalone.test_r76c_bench_qt
```

`test_r76c_bench` includes an isolated real Python subprocess smoke check.
Most distribution and fault-injection tests use **labelled mocks** to keep CI
bounded, **never representing mocks as measured benchmark outputs**.
The tri-OS CI jobs validate the tooling contract, not physical GPU evidence.

### Remaining R76.C2 gates (all NO-GO)

- Real **native Player** startup measurements, with process exit/ready-event
  contract, sample timeout, cold-cache vs warm-cache classification.
- Process RSS on Windows and real GPU allocations/textures/VRAM from a
  physical device; frame p95/p99, FPS, GPU driver and backend.
- Versioned scene/corpus and actual before/after gameplay, save/replay and
  artistic/rights approval, plus individual OS/hardware-run evidence.
- CI runners must actually execute tests and report jobs on the final SHA.
  Historical R76 workflows that returned **failure with 0 jobs** do not
  demonstrate successful or unsuccessful test assertions.

**Release / platform verdict: NO-GO until all evidence is satisfied.**
