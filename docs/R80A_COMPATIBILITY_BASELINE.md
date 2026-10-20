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

## Delivered in R80.A2 (historical regression subset)

`drawtemp.quality.r80_historical` performs **executable** checks against
four source documents that were present in
[R16 merge commit 7829988c](https://github.com/faudard/drawTemp/commit/7829988c587b7761e2ec07944b343fef59a06943)
(2026-10-15). It pins the *actual* Git blob object identity for:

| Historical source | Git blob SHA-1 |
|---|---|
| `sporebound/content/core.json` | `cff5763c18c5bc34feefa35db8ba4f971bbb6851` |
| `sporebound/content/core.game.json` | `3d8d9751d0573b44dd75bd965df5e360b18e2053` |
| `sporebound/content/jeanne.json` | `5246292a14b66bc9a4a3ed011c34468dc192662e` |
| `sporebound/content/jeanne.game.json` | `e252012b7b46799a85b712c4243e4bc7d4775287` |

These identical bytes remain in the repository. The harness refuses changes
to any pinned source; it computes SHA-256 observations in its own JSON report.
It deliberately does **not** duplicate large content files as divergent
fixtures or fetch from the network during tests.

### Executed contracts

1. Real `Content.from_dict` / `GameProject.from_dict` canonical v1 parse +
   serialized round trips for both source pairs.
2. R1.6 v0 envelope derived from core v1 with **only** the version tags
   removed/changed. `preview_pair` and `commit_pair` produce a separate
   canonical v1 copy while preserving source bytes; stale plans and version
   99 are rejected. **This synthetic envelope is not a separate archived v0
   user project.**
3. R16 `migrate_project` / `rollback_project` preserve both original
   v1 file payloads byte for byte. An existing destination and a damaged
   backup prevent rollback.
4. Jeanne tactical replay (seed 17, choice → mission → lever → end turn)
   through `verify_sequence` and `verify_recording`, with checkpoints
   including tactical state.
5. Newly generated GameSession v1 save is migrated explicitly to the real
   SessionStore v2 envelope, preserving the original .bak bytes. A damaged
   primary falls back to the verified v1 backup, without rewriting the
   corrupted primary; double corruption is rejected. Loading twice does not
   itself apply another gameplay command.

### Two-runtime R16 → current verification (CI)

A second gate, `drawtemp.quality.r80_cross_revision`, requires a real Git
checkout at the full R16 merge SHA. It authenticates `git rev-parse HEAD`,
rechecks the four historical Git blobs, and launches the **R16 Python runtime**
in a separate process. That historical code creates a campaign v1 save, a
tactical v1 save after Jeanne operates the lever, and a SessionStore v2
checkpoint for the same tactical state. The **current** runtime then validates
their recordings, mode, nested tactical replay, digest, v2 envelope and
repeat-load stability; an unsupported v2 revision fails closed. Neither
runtime is allowed to rewrite the historical save bytes during inspection.

```sh
git -C r16-pinned rev-parse HEAD
# Must equal: 7829988c587b7761e2ec07944b343fef59a06943
python -m drawtemp.quality.r80_cross_revision \
  --historical-checkout r16-pinned \
  --report r80a2-cross-revision.json
```

The CI job checks out that exact revision separately, not a floating branch.
**This is a test to be run and reviewed**, not an assertion that it currently
passes on GitHub Actions. If historical and current formats are incompatible,
the R80.A2 job must fail; changing the pinned SHA just to silence a failure is
not an acceptable fix.

### Reproduce

```sh
python -m unittest -v tests_standalone.test_r80a_compatibility \
  tests_standalone.test_r80a2_historical
python -m drawtemp.quality.r80_historical --report r80a2-historical.json
```

CI attempts these real validators on Ubuntu, Windows and macOS and uploads
R80.A1, R80.A2 local-runtime and R16 cross-runtime reports. **CI must be observed and reviewed; adding a
workflow does not mean it ran successfully.** The regression runner reports
`result: passed` *only for its enumerated checks*, and always reports
`release_certified: false` and `tag_allowed: false`.

**Unproven:** no real user-owned archived v0 saves, no independently retained
user-generated save fixture (CI generates files through genuine R16 code),
no 5.x→11.x multi-version chain,
no completed battle reward-deduplication test, no long-session fault injection
and no mixed-mode replay certification. The generated save checks the current
runtime's handling of the *old envelope*, not binary equivalence with all
historic releases. Do not promote these to completed R80.A release gates.

## Mandatory next increments

- **R80.A2 continuation:** acquire independently archived historical customer/project saves and replay fixtures across genuine releases; run their original readers, reproduce completed-combat rewards and prove non-duplication after restart. The R16-pinned current-runtime subset above is not sufficient.
- **R80.A3:** perform formal SDK API/ABI compatibility review, adversarial
  plugin/asset tests, licensing review, stale-preflight/TOCTOU testing and
  cross-OS importer checks. Do not equate a Python API version to native ABI.
- **R80.B:** six separate, original and editable games (including *gestion/vie*)
  with Player save/export and real authoring evidence.
- **R80.C:** independently reviewed CI logs, physical GPU, onscreen Qt,
  external creators, accessibility, SBOM, clean-machine installs and OS-specific
  GO/NO-GO. This audit cannot issue certification or authorize tags.
