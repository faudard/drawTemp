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

## Remaining work

- R39.A: wire provenance generation into native builds and authenticate it,
  verify launch/ABI compatibility, complete dependency inventory, Studio export UI integration,
  same-SHA multi-OS build matrix and four real game-family export journeys.
- R39.B: clean-machine install/launch, hardware input/a11y/scaling, save migration,
  recovery/rollback, suspend/resume, GPU budgets, redistribution and signing review.
- R39.C: separate Web/mobile feasibility ADRs, without support commitments.

## Verification

`python -m unittest tests_standalone.test_r39_native tests_standalone.test_r39_publishing
 tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r15_creator`
(on one shell line).

The dedicated R39 CI workflow runs these tests on Windows/Linux/macOS.
Tests use actual R15 exports with deliberately non-executable synthetic Player
headers. This proves integrity/preflight behavior and guards against falsely
certifying a native release. No native OS, GUI, GPU or clean-machine result is
claimed by these tests.
