# INT-03 — Jeanne production art publication / certification

**Scope:** 88 approved-source watercolor PNGs + **11 computed intermediate Jeanne
frames** = **99 physical PNGs** and **15 canonical animations**, using the
existing `assets/watercolor/{index,registry,provenance}.json`. No additional
gameplay schema, runtime frame synthesis, or made-up licensing assertion.

## Distinguish creation, publication, licensing and runtime availability

1. **Creation:** `scripts/generate_jeanne_motion.py` uses the original 88
   SHA-256-pinned PNGs and pinned authoring dependencies. It writes 11
   `sprites/jeanne_motion/*.png` plus derived hashes / registry entries.
   Generated intermediate cels are deformations, **not new hand-authored art**.
2. **Publication:** the new PNGs **must be committed in the PR tree**.
   `jeanne-motion-publish.yml` attempts publication on the dedicated INT-03
   branch. A successful generator log alone does **not** count.
3. **Rights:** `assets/watercolor/rights.json` starts `pending`, on purpose.
   The project owner must identify the copyright holder, actual license or
   grant, evidence, permission to **modify** source art and **redistribute**
   originals/derivatives. Do not set `approved` based solely on a ZIP hash.
   An attestation is still subject to human/legal verification.
4. **Runtime:** the strict gate validates CRC/dimensions, original **and**
   derived SHA-256, 99 on-disk files, stable registry/index IDs,
   `anim_jeanne_walk` (8) and `anim_jeanne_attack` (12), the installer
   bindings and R4 renderer-neutral `AssetResolver`. 99-frame installations
   **require the validated provenance and approved rights**, and preserve
   those files in exported project copies. Historical 88-frame preview
   installs remain supported and are not called certified production assets.
5. **Certification:** `.github/workflows/drawtemp5-int03.yml` checks the
   *actual checkout* on Linux/macOS/Windows, fails closed and uploads
   per-OS JSON proof tied to `GITHUB_SHA`. A passing report is not a GPU,
   animation-quality or legal-rights audit.

## Development CI versus certified publication

The normal `Standalone gameplay` test matrix runs from the tracked **88-source**
preview checkout, where the 11 derivative PNGs are not yet published. Its
`test_jeanne_motion_pack` and full motion timing assertions are therefore
**skipped only when publication is completely absent**. Once derived hashes,
extended animation metadata, more than 88 sprites, or even a single derived
PNG is present, the same assertions run and reject incomplete publication.

`test_optional_motion_gate_ci` protects this boundary, and the dedicated
`drawtemp5-int03.yml` certification remains deliberately **fail-closed** on
real published bytes, exact hashes, animation counts and legal rights. A green
general gameplay matrix is **not** evidence that the INT-03 asset release gate
has passed, and it never authorizes placeholder frames or rights approvals.

## Commands

```bash
# Publisher only: this is NOT release certification.
python -m pip install Pillow==11.3.0 numpy==2.2.6 opencv-python-headless==4.12.0.88
python scripts/generate_jeanne_motion.py --root assets/watercolor
python scripts/certify_int03_assets.py --root assets/watercolor --technical-only
git status --short   # should show the real PNG binaries and metadata changes

# Published art and its rights must pass without regeneration:
python -m unittest tests_standalone.test_drawtemp5_int03 tests_standalone.test_install_watercolor_pack -v
python scripts/certify_int03_assets.py --root assets/watercolor --report int03-report.json
```

**Gate remains OPEN** while files are absent from the target Git tree, rights
are `pending`, any hash or Player binding fails, or the last-commit multi-OS
reports are missing. No fallback to `--allow-missing`, placeholder images,
or a passing workflow on an unrelated SHA is acceptable. Once publication,
legal provenance and runtime checks pass, review actual Jeanne walk/attack
at 100%, multiple zoom levels and on a real GPU before visual sign-off.
