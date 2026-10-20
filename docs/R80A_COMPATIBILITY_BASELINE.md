# R80.A — compatibility and security audit baseline (12.0 candidate)

**Status: implementation increment; release 12.0 is NO-GO.** This note extends the
[R51–R80 roadmap](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md),
not the already merged [#289](https://github.com/faudard/drawTemp/pull/289).

## Delivered in R80.A1

`drawtemp.quality.r80_compatibility` inventories 13 explicit evidence obligations:
public SDK ABI and change review, v0→v1 migration, canonical v1 round-trip,
unknown-schema rejection, historical Jeanne CT replay, mixed-mode replay,
GameSession v1 and SessionStore v2 save/recovery, long-session faults, rollback,
asset rights/hashes, and plugin failure behavior. The current public SDK is
probed **without Qt**, using its real `capabilities()` and `negotiate_sdk()`.
The report includes a SHA-256 of the observed SDK capability contract; this is
an **observation**, not a replacement for an ABI or migration test.

The auditor only reads bounded `records/*.json` and `artifacts/*` content,
checks exact schema, revision SHA, uniqueness, path confinement, symlinks and
SHA-256, and never executes attached data. Records are untrusted self-reports.
No release approval, schema rewrite, replay migration or plugin installation
is performed. The report **always** says `NO-GO`; independent test provenance
and R80.B/C gates must be established by a separate explicit release process.

### Usage

```sh
python -m unittest -v tests_standalone.test_r80a_compatibility
python -m drawtemp.quality.r80_compatibility \
  --revision <exact-40-lowercase-commit-sha> \
  --evidence-dir ./r80-evidence \
  --output ./r80a-audit.json
```

Optional `--enforce` makes a NO-GO exit nonzero. Unpopulated evidence folders
are valid inputs, but produce missing-check blockers. Any invalid revision or
unsafe output operation returns exit 2.

One user-supplied claim file under `r80-evidence/records/test.json`:

```json
{
  "kind": "drawtemp-r80a-compatibility-proof",
  "schema": 1,
  "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "check": "legacy_jeanne_ct_replay",
  "outcome": "passed",
  "artifact": "artifacts/jeanne-replay.log",
  "sha256": "<64 lowercase hex characters of the actual artifact>"
}
```

The example SHA and check outcome are placeholders, **not acceptance proof**.
Do not feed arbitrary untrusted files to Player/Studio or treat their checksums
as independent verification. Use real per-SHA CI runs, pinned fixtures and
reviewed certification authorities for release approvals.

## Mandatory next increments

- **R80.A2:** pin historical Content/GameProject and session/replay fixtures
  from real 5.x–11.x release commits, execute actual migration/load/replay
  validators, and prove no duplicate rewards or data loss after rollback.
- **R80.A3:** perform formal SDK API/ABI compatibility review, adversarial
  plugin/asset tests, licensing review, stale-preflight/TOCTOU testing and
  cross-OS importer checks. Do not equate a Python API version to native ABI.
- **R80.B:** six separate, original and editable games (including *gestion/vie*)
  with Player save/export and real authoring evidence.
- **R80.C:** independently reviewed CI logs, physical GPU, onscreen Qt,
  external creators, accessibility, SBOM, clean-machine installs and OS-specific
  GO/NO-GO. This audit cannot issue certification or authorize tags.
