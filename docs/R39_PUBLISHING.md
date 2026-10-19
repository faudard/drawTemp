# R39.A — PC publication profiles and preflight

Status: incremental implementation of R39.A, **not completion of R39**.
The canonical R15 exporter remains the sole game bundle writer. R23.C portable
archives remain unchanged. No new runtime, save format or asset registry.

## Workflow

1. Build the native Player on the target OS from an exact Git revision.
2. Export the authored project with `drawtemp-creator5 export` and strict rights.
3. Generate a producer provenance document outside the immutable bundle:

   ```sh
   python -m drawtemp.export.cli build-provenance \
     --bundle ./exported-game --dependencies ./dependencies.json \
     --revision 0123456789abcdef0123456789abcdef01234567 \
     --target linux-x86_64 > build-provenance.json
   ```

   `dependencies.json` is an array of `{name, version, license}` objects from
   the build's inventory. The command computes the manifest hash and validates
   the bundle, native header, and asset rights before emitting JSON to stdout.
   It uses the supplied build revision; it does not infer it from a local checkout.
   Output must stay outside the bundle. Shell redirection may create an empty
   output on failure; check exit status before retaining or consuming the file.
4. Run the read-only publication preflight:

```sh
python -m drawtemp.export.cli publish-plan \
  --bundle ./exported-game --provenance ./build-provenance.json \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --target linux-x86_64 --family srpg
```

Supported *planning targets*: `windows-x86_64`, `linux-x86_64`, `macos-x86_64`,
`macos-arm64`. Declared game families: `srpg`, `action-adventure`, `metroidvania`,
`roguelite`. These options do not establish that a binary runs on that OS/CPU
or that the project implements that genre. Web/mobile/consoles are rejected.

Producer document (replace example values with actual build data):

```json
{
  "schema": 1,
  "kind": "drawtemp-r39-build-provenance",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "target": "linux-x86_64",
  "manifest_sha256": "<SHA-256 of the exact exported manifest.json bytes>",
  "dependencies": [
    {"name": "Python", "version": "3.12.0", "license": "PSF-2.0"}
  ]
}
```

Include the full actual runtime dependency inventory, including Qt/PySide and
other redistributed components. The preflight validates inventory structure,
not completeness, SPDX validity or legal approval. The example is not an SBOM.
A producer-supplied revision/hash is a binding declaration, not independently
verified build provenance or a publisher signature.

The command verifies the canonical R15 manifest and all indexed bytes, matches
its exact hash and Player filename to the declaration, checks the native header
format/CPU against the target, then reruns canonical
content/project/asset validation with strict redistribution rights. It verifies
integrity again after preflight. It never launches executables or writes inside
the bundle. Keep build inputs immutable during inspection.

Exit 0 means a valid plan was generated, **not release approval**. Its decision
is always `NO-GO`, `release_certified` is always false, and remaining qualification
steps are explicit. Invalid provenance, altered bytes, invalid projects, missing
rights, unsupported targets or incompatible executable names return exit 1.
JSON output goes to stdout and can be retained outside the bundle.

## Native header inspection

Inspection uses bounded fixed-size reads and validates header/table extents:
ELF64 little-endian x86_64 (System V/Linux ABI tag), PE32+ AMD64 executables,
and thin Mach-O64 x86_64/arm64 executables. Truncated headers, incompatible CPUs,
32-bit headers, PE DLLs, Mach-O dylibs, scripts and unknown formats are rejected.
Universal/fat Mach-O is deliberately unsupported in this increment.

The header identifies a container and declared CPU, not a complete valid program.
For example, an ELF System V tag does not prove Linux ABI compatibility. Loadable
segments, dependencies, minimum OS versions and actual launch behavior still
require platform build/runtime checks. Synthetic headers can pass inspection;
`native_header_identity: passed` must never be used as a release certificate.

## Native build integration and blocked evidence

The R15 `native-bundle` job now runs `build-evidence` immediately after export
and verification, with the exact checked-out `${{ github.sha }}`. The target is
mapped from the runner OS/CPU and then crosschecked against the Player header.
Unsupported host architectures fail explicitly. Each OS uploads an external
`r39-build-evidence-<OS>` dossier, without altering its R15 bundle.

```sh
python -m drawtemp.export.cli build-evidence \
  --bundle ./exported-game --output ./r39-evidence \
  --revision 0123456789abcdef0123456789abcdef01234567 --family srpg
```

- `build-evidence.json`: bundle hash, exact declared revision, native header,
  strict asset-rights result, preflight status and explicit blockers.
- `build-environment.json`: installed Python distribution metadata, including
  unknown licenses as JSON null. This includes build tools and is **not a runtime
  SBOM**; it omits native/system libraries and does not establish redistribution rights.
- With `--dependencies reviewed-runtime-dependencies.json` and successful strict
  checks, also emits `build-provenance.json` and `publication-plan.json`.

Without a reviewed runtime inventory, publication preflight remains blocked;
Python package metadata is never substituted for that inventory. Missing asset
rights also remain blockers. Jeanne currently lacks `asset-licenses.json`, so
this integration does not silently turn that preview into a publishable release.

The output directory must be new and outside the bundle. Documents are staged
then published together. Invalid native identity, tampered bundles or an existing
output are fatal errors (exit 1), not successful missing-evidence reports.
Collection success (exit 0) only means the dossier was produced. Use
`--require-preflight` for exit 2 when the dossier records a blocked preflight.
The native workflow intentionally collects the blockers without claiming release
approval. Even a passed preflight retains `decision: NO-GO` and
`release_certified: false`; launch/hardware/signature gates remain separate.

## Cross-platform matrix

The `r39-publication-matrix` job collects all available per-OS build reports even
when the native matrix has failed. Missing artifacts remain visible as missing
targets; artifact download failure is tolerated only to produce that blocked
matrix, never to declare success of native builds.

```sh
python -m drawtemp.export.cli publication-matrix \
  --directory ./downloaded-r39-artifacts \
  --revision 0123456789abcdef0123456789abcdef01234567 --family srpg
```

The directory contains nested `build-evidence.json` files, as produced by artifact
download without merging. Output is JSON on stdout. The default requires all four
PC targets, including both macOS architectures. The current three-runner native
workflow therefore does **not** demonstrate all four targets; the absent macOS
architecture is reported explicitly. An explicit `--targets linux-x86_64 ...`
selects a narrower matrix and that scope is retained in `required_targets`.

The aggregator rejects duplicate/unexpected targets, mixed Git revisions or game
families, invalid hashes/native identities, contradictory preflight states, and
unsupported certification claims. Bundle hashes may differ across OS builds.
Absent targets and blocked targets have separate arrays. An empty directory
produces an entirely missing/blocked matrix rather than an implicit pass.

Exit 0 means a consistent matrix report was generated. `--require-preflight`
returns 2 for missing/blocked targets; malformed or conflicting inputs return 1.
The workflow deliberately retains the NO-GO report for diagnosis without using
collection success as release approval. Even a complete passed preflight matrix
remains non-certified: it aggregates producer declarations, does not independently
reverify remote binaries, and does not replace four-family or hardware journeys.

## Remaining work

- R39.A: supply reviewed runtime inventories in native builds and authenticate provenance,
  verify launch/ABI compatibility, complete dependency inventory, Studio export UI integration,
  same-SHA multi-OS build matrix and four real game-family export journeys.
- R39.B: clean-machine install/launch, hardware input/a11y/scaling, save migration,
  recovery/rollback, suspend/resume, GPU budgets, redistribution and signing review.
- R39.C: separate Web/mobile feasibility ADRs, without support commitments.

## Verification

`python -m unittest tests_standalone.test_r39_matrix tests_standalone.test_r39_build_evidence tests_standalone.test_r39_native tests_standalone.test_r39_publishing
 tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r15_creator`
(on one shell line).

The dedicated R39 CI workflow runs these tests on Windows/Linux/macOS.
Tests use actual R15 exports with deliberately non-executable synthetic Player
headers. This proves integrity/preflight behavior and guards against falsely
certifying a native release. No native OS, GUI, GPU or clean-machine result is
claimed by these tests.
