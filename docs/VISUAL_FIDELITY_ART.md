# Visual Fidelity & Art — Editor / Player

## Technical slice (3.7.2x): one compositing contract

The isometric Editor (through `EditorRenderCache`) and the Player
(`IsoBattleCanvas`) both call `render_isometric`. The approved Jeanne atlas
and the existing isometric terrain, prop, building, fortification, actor and
interactive-object atlases stay the only source of packaged visuals. There
is **no second renderer, gameplay schema or animation clock**.

### Changes covered

- Depth-sort *floor-anchored* interactive objects and decorations together
  with actors and architectural instances. Vector prop fallbacks use the
  same stable cell tag as transparent PNG props. Ties are deterministic:
  prop → interactive object → building → actor.
- During Player motion, re-raise the **whole** scene's depth groups, not just
  actors and buildings. Movement remains a cosmetic projection. Doorway
  cutaways still rebuild only at roof-visibility transitions.
- The approved 256×512 Jeanne atlas supplies isometric rows for idle, walk,
  attack, hit and defeat (4 facings). Generic chibi figures still have
  only idle/move and are **not** represented as fully animated.
- Existing 7 packaged PNG atlases are audited for full-chunk CRC,
  dimensions, 8-bit color and effective alpha (RGBA or indexed + tRNS).
  The test does not alter their artwork or palettes.
- An Xvfb regression compares **every Tk Canvas item in stacking order**,
  normalized for the Player camera shift, including its tags, shape,
  position, sprite dimensions, sampled colors and transparency. Cases:
  24/54/96px zoom × roof visible/cutaway, with actors, a tree, a chest
  and a house. Captures are optional locally and attached by Linux CI.

### Commands

```sh
python -m unittest tests_standalone.test_visual_fidelity_art_372 -v
SPOREBOUND_GUI_SMOKE=1 \
SPOREBOUND_FIDELITY_SCREENSHOT_DIR=/tmp/visual-fidelity \
xvfb-run -a python -m unittest tests_standalone.test_visual_fidelity_art_372_gui -v
```

The Linux standalone workflow uploads `editor-player-visual-fidelity`
(12 side-by-side source captures: 2 renderers × 3 zooms × 2 visibility
states) when its GUI proof succeeds. Screenshot comparison and human
art-direction approval are **separate** gates from the deterministic item
parity assertion.

## Watercolor asset-blocker — not silently resolved

The historical watercolor manifest currently lists 88 sprites and 15
animation bindings, but `assets/watercolor/sprites` contains no PNGs.
Do **not** claim these 88 assets ship or pass a production-art gate.

The nine original source illustrations or the corrected v3 ZIP must be
provided from the separate artwork deliverable. Import and clean using
the existing scripts documented in [assets/watercolor/README.md](../assets/watercolor/README.md);
do not procedurally generate replacements from the metadata.

```sh
python scripts/verify_watercolor_release.py --root assets/watercolor
# Must fail until all 88 real PNGs have been published.
python scripts/audit_watercolor_pack.py --bundle /path/to/v3.zip --strict
# After publication: review every marked transparent edge/weapon/foot frame.
```

`--allow-missing` exists for development installations and is **not**
the release gate. Publishing the full pack must also preserve provenance
hashes, validate all 88 file paths, and be followed by an in-game
Editor/Player review with the new PNGs bound (not only previewing empty
metadata). The older 88 PNG archive cannot be recreated from the index.

## Outstanding acceptance gates

- [x] Existing atlas format, CRC, alpha and dimensions: automated.
- [x] Editor/Player same-zoom stacking and cutaway regression: automated
  (CI execution required before claiming green).
- [x] Jeanne combat impact poses and image-cache consistency: implemented.
- [ ] Approve the **final** common watercolor/anime-chibi art direction;
  existing prop/building/chibi atlases are prototypes.
- [ ] Receive, repair, and commit the 88 actual watercolor PNG files.
- [ ] Manually validate transparency, feet anchors and partially occluded
  characters at all three zooms across Windows, macOS and Linux.
- [ ] Approve full directional attack/walk frames for the generic cast,
  pose timing, VFX layering and dynamic objects beyond the existing atlas.

No changes to Content/JSON, save/replay format, battle actions or RNG.

## October 2026 follow-up — frame sampling and release certification

- The shared `IsoActorAtlas` used by the Editor and isometric Player exposes
  `packaged_actor_catalog()`, with the real action coverage and a
  bottom-center foot pivot. Generic hero/guard/archer artwork still **lacks**
  attack/hit/defeat images: the fallback is not advertised as delivered art.
  Project-specific art remains in the existing `AssetRegistry`.
- `MotionDirector` supplies cosmetic 0/1 sub-frames for walking and attacks.
  Jeanne's second `move` (row 3) and `attack` (row 5) frames are now selected
  from her existing atlas instead of being skipped. Tactical timing, save,
  replay and existing four-argument `ActorPose` consumers remain unchanged.
- `actor_foot_point()` is shared at 24/54/96px zoom. The Tk regression also
  checks actor→façade→foreground stacking plus roof cutaway, beyond mere
  renderer-to-renderer agreement.
- The watercolor validator checks PNG chunk CRCs, completeness, dimensions,
  and SHA-256 hashes when supplied in metadata. The `standalone` workflow
  checks optional developer packs; **version-tag distribution** performs the
  strict 88-PNG check without `--allow-missing` and will fail until published.

**Still blocked:** the original 88 watercolor PNG files have not been
committed. This PR does not reconstruct them from metadata or certify final
art direction. QA on final art, all actor combat frames and actual Windows,
macOS and Linux visuals must be completed after delivery.


## October 2026 recovery — original V3 source archive found

The historical 23 MB \`drawTemp_assets_Jeanne_88_sprites_v3.zip\`
has been recovered **in the author's ChatGPT file Library**, not in GitHub.
Its archive SHA-256 is
\`2a3089fc05184f62048c1484a114a467d626411452d8e6d9104f57e4cb20bf0a\`.
The 88 RGBA images decode, their hashes match the archived preflight, and
\`assets/watercolor/provenance.json\` now pins **all 88** original PNG hashes.
This tracked provenance is not a substitute for the binary files.

A strict and atomic publisher is provided for the owner to run from a local
checkout of the PR branch once the original ZIP is downloaded:

\`\`\`sh
python scripts/publish_watercolor_pack.py --bundle /path/to/drawTemp_assets_Jeanne_88_sprites_v3.zip --dry-run
python scripts/publish_watercolor_pack.py --bundle /path/to/drawTemp_assets_Jeanne_88_sprites_v3.zip
python scripts/verify_watercolor_release.py --root assets/watercolor
git add assets/watercolor/sprites
git commit -m "art(jeanne): publish 88 approved watercolor v3 PNGs"
git push origin feat/visual-fidelity-art-gates-20261013
\`\`\`

On Windows, \`scripts/publish_watercolor_art.ps1 -RepoPath <checkout> -BundlePath <archive>\`
performs the clean-tree, branch and push checks. Importing never modifies
savegames, tactical data, or authored campaign JSON. If the target already
contains a different or partial pack, publishing fails without overwriting it.

The archived visual preflight identified **46/88 manual-review candidates**:
2 VFX, 6 wolf, 7 Jeanne, 9 spearman, 10 props, 2 townsfolk, 3 soldiers,
3 bestiary and 4 heroes. See \`docs/evidence/watercolor_v3_art_review.json\`.
These are transparent-edge/bleed warnings, **not** a claim that every
flagged image is defective. The real final render review must still compare
Studio and Player at identical zooms, with roof cutaways and wall occlusion.
The archive is recovered, but **the 88 PNGs have not been pushed to GitHub**.
