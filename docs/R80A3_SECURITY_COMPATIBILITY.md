# R80.A3 — SDK compatibility and fail-closed import hardening

**Scope: additive R80.A3 increment. This is not a native ABI audit, penetration test, release certification, or approval of asset redistribution. Release 12.0 remains NO-GO.**

Follows the R80.A1/A2 branch integrated through [PR #437](https://github.com/faudard/drawTemp/pull/437) and the [R51–R80 roadmap](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).

## Runtime changes

- `drawtemp.export.safe_inputs.read_regular_snapshot` reads bounded regular files once, using a descriptor; checks `lstat`, inode identity, file size, modification and metadata timestamps before/after reading, and `O_NOFOLLOW` where provided by the operating system. No silent truncate or replacement of the approved bytes.
- `creator_packs.inspect_pack` rejects symlinked or changed ZIP input before parsing. Existing checks for ZIP entry paths, duplicates, budgets, hashes, declared inert resource types and unapproved rights still apply.
- `pack_import` uses the same bounded snapshot strategy for the ZIP and both project JSON documents (32 MiB each). Duplicate object keys, `NaN`, `Infinity`, unknown/nonobject JSON and invalid encodings are rejected. Read and parsed bytes are the same bytes recorded in the source SHA-256; a changed source/archive between preview and commit still fails.
- No migration of gameplay state, no new arbitrary plugin permissions, no second asset registry, no auto-install, no shell invocation during asset import. Existing original project files remain untouched by a successful import, and every imported project is a new copy with explicit confirmation.

## Compatibility evidence

`drawtemp.quality.r80_security.check_python_sdk()` validates the Python SDK's R16 exported API names and five original capabilities against the exact [R16 commit 7829988c](https://github.com/faudard/drawTemp/commit/7829988c587b7761e2ec07944b343fef59a06943) (`drawtemp/sdk/__init__.py`, blob `aca6076af2e34e1351829d32d8534bb7c7c7a454`). It resolves legacy import symbols with the current runtime and verifies incompatible API/feature requests are refused.

This check is **Python import-level compatibility**, *not* compiled binary ABI compatibility or a guarantee for every historical signature/behavior. The SDK remains `(1, 0)`, `provisional`. Stabilization or native ABI claims require separate artifact-level review and versioned release evidence.

`check_inert_import_security()` challenges existing validators with six traversal/unsafe-extension paths, executable/elevated mod declarations, bounded file reads and symlink handling (where test OS permits). Its report explicitly leaves rights approval false.

## Reproduce

```sh
python -m unittest -v \
  tests_standalone.test_r80a3_security \
  tests_standalone.test_drawtemp_r30b_pack_import \
  tests_standalone.test_drawtemp_r47a_modding \
  tests_standalone.test_drawtemp_r47f_project_preflight
python -m drawtemp.quality.r80_security --output r80a3-security.json
```

Workflow `.github/workflows/r80a3-security.yml` runs the tests headlessly on Windows, Linux and macOS plus Python 3.10 on Linux, then saves a **NO-GO** JSON report. Workflow presence is not successful CI execution: use per-job logs and a pinned SHA before accepting the gate.

## Unresolved security and release gates

- OS file-system / reparse-point and *parent-directory* race defenses remain constrained by host ACLs, sandboxing and filesystem APIs. A checked descriptor narrows races but is **not** a cross-process transaction. Windows share modes/ACLs and malicious writable parent paths need independent validation.
- Preflight-copy-publication still has a narrow race with hostile concurrent directory modification, especially on network drives. Validate native CI hardware and revisit descriptor-relative/openat or equivalent staged roots before promising untrusted multi-user imports.
- An internal adversarial smoke is not professional penetration testing, fuzzing, malware scanning, SBOM or independent copyright clearance.
- R80.A2 additional archived user saves and multi-version behavior remain incomplete. R80.B independent game catalogue and R80.C real GPU, external authors, accessibility, clean-machine distribution and release-signing gates remain open.
- No A3 code unilaterally sets `release_certified`, authorizes a tag or changes SDK/GameProject/save schema versions.
