# R39.A — PC publication profiles and preflight

Status: first incremental implementation of R39.A, **not completion of R39**.
The canonical R15 exporter remains the sole game bundle writer. R23.C portable
archives remain unchanged. No new runtime, save format or asset registry.

## Workflow

1. Build the native Player on the target OS from an exact Git revision.
2. Export the authored project with `drawtemp-creator5 export` and strict rights.
3. Record a producer provenance document outside the immutable bundle.
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
its exact hash and Player filename to the declaration, then reruns canonical
content/project/asset validation with strict redistribution rights. It verifies
integrity again after preflight. It never launches executables or writes inside
the bundle. Keep build inputs immutable during inspection.

Exit 0 means a valid plan was generated, **not release approval**. Its decision
is always `NO-GO`, `release_certified` is always false, and remaining qualification
steps are explicit. Invalid provenance, altered bytes, invalid projects, missing
rights, unsupported targets or incompatible executable names return exit 1.
JSON output goes to stdout and can be retained outside the bundle.

## Remaining work

- R39.A: build-system generation/authentication of provenance, native CPU/OS
  verification, complete dependency inventory, Studio export UI integration,
  same-SHA multi-OS build matrix and four real game-family export journeys.
- R39.B: clean-machine install/launch, hardware input/a11y/scaling, save migration,
  recovery/rollback, suspend/resume, GPU budgets, redistribution and signing review.
- R39.C: separate Web/mobile feasibility ADRs, without support commitments.

## Verification

`python -m unittest tests_standalone.test_r39_publishing
 tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r15_creator`
(on one shell line).

Tests use actual R15 exports with deliberately non-executable placeholder Player
bytes. This proves integrity/preflight behavior and guards against falsely
certifying a native release. No native OS, GUI, GPU or clean-machine result is
claimed by these tests.
