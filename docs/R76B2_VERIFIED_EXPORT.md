# R76.B2 — Verified Optimized Project & R15 Export Preview

**Status: DEVELOPMENT / NO-GO.** This slice builds on R76.A–B1, merged into
`integration/consolidation-r51-r80-20261020` through #431. It is designed to
work without changing the original content, GameProject, source assets,
licenses, editor Undo stack, saves or gameplay simulation.

## What it implements

1. **Frozen, verifiable review** of canonical Content + GameProject, source
   files, dependencies, SHA-256 and R15 strict rights attestations.
   A byte-identical duplicate is eligible **only if the complete file-bound
   attestation also matches the retained canonical file**. Identical bytes do
   not transfer permission from one asset to another.
2. **Decoded PNG evidence**, using Pillow and full RGBA per-pixel hashes,
   with a 16 Mi-pixel limit. The before/after PNGs must decode and hash
   equally. Identical WAV/OGG streams are labelled **byte-identical but not
   decoded**; audio fidelity and playback timing require independent proof.
   This is technical parity, **not a human-approved artistic golden**.
3. **Atomic optimized project preview** in a *new* output directory outside
   the project: copy Content, GameProject, all required unique physical assets,
   `asset-licenses.json` and referenced R15 license evidence. Rewrite only
   the copied AssetRegistry paths and remove obsolete rights index keys after
   strict equivalence checks; no source file is modified or removed.
4. **Strict R15 gate both before and after staging**:
   `preflight(..., require_licenses=True)`. Refuse unsupported dependencies,
   stale inputs, missing evidence, invalid aliases, unreadable files, symlinks,
   case collisions, unexpected content, oversized projects (512 MiB / 2,048
   files) or an existing destination. A project with required ancillary files
   outside the explicit R15 copy list fails the staged preflight (no implicit
   compatibility promise).
5. **Auditable receipt and selective Undo**: source-plan hash, copied files
   hashes, decoded comparisons and explicit `release_certified=false`.
   Undo rechecks *every* expected file and strict staged preflight; a new file
   or modified asset prevents destruction.
6. **Native R15 preview export** from the independently verified optimized
   project: delegates to the existing `export_game(..., require_licenses=True,
   release=False)` and checks `verify_bundle`. It still requires a valid
   pre-built native Player runtime, and is **never a release candidate**.

## Optimizer Studio workflow

Open **Outils → R76 Optimizer Studio** with a saved source project. R76.B1
continues to offer the asset-only preview. The independent **Préparer projet
R15** action uses a separate destination and checkbox for author approval.
**Annuler projet R15** removes only the intact, generated project copy. The
original Studio session and Undo/Redo history are untouched.

The project-copy view confirms technical identity but does not automatically
approve artists' goldens or verify GameSession replay parity. A native Player
binary is supplied separately through the command-line export below.

## CLI

Install the image decoder when handling PNG duplicates:

```sh
python -m pip install -e ".[art]"
```

First inspect and record the returned `plan_sha256`:

```sh
python -m drawtemp.export.r76b2 plan --content /projects/game/game.json
```

Only after reviewing its output, explicitly approve **a new directory**:

```sh
python -m drawtemp.export.r76b2 stage \
  --content /projects/game/game.json \
  --output /projects/game-r76b2-preview \
  --expected-plan-sha256 YOUR_64_HEX_DIGEST \
  --approve
```

The resulting response contains `receipt_sha256`. The staged directory
contains `game.json`, `game.game.json`, retained assets, rights evidence,
and `r76b2-receipt.json`. Supply a separate native Player runtime and
another new output directory to create an R15 **preview**:

```sh
python -m drawtemp.export.r76b2 export \
  --stage /projects/game-r76b2-preview \
  --receipt-sha256 RECEIPT_SHA256 \
  --runtime-dir /runtimes/native-player \
  --bundle /exports/r76b2-test-player
```

To discard the project copy, without deleting the Player bundle:

```sh
python -m drawtemp.export.r76b2 undo \
  --stage /projects/game-r76b2-preview \
  --receipt-sha256 RECEIPT_SHA256
```

**Never pass the original project directory to `undo`.** A missing or
tampered receipt is rejected rather than causing deletion.

## Tests and release gates

```sh
python -m unittest -v \
  tests_standalone.test_r76_asset_audit \
  tests_standalone.test_r76b_optimizer \
  tests_standalone.test_r76b2_verified_export \
  tests_standalone.test_drawtemp5_r15 \
  tests_standalone.test_r17_asset_rights

QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest -v tests_standalone.test_r76b_optimizer_qt
```

The new tests create **synthetic** rights attestations, deliberate PNG
duplicates and a **fake Player executable for manifest-only checks**.
A successful `verify_bundle` does not mean that fake executable works.

**Remaining NO-GO criteria:** real Player launch, full replay/save-migration
parity for the rewritten project digest, audio decoding/fidelity, legitimate
human acceptance of goldens, independently reviewed rights, actual
clean-machine native installers, and R76.C startup/bundle/memory/GPU
p95/p99 measurements across real hardware. No production release is
authorized by this feature or by offscreen CI tests.
