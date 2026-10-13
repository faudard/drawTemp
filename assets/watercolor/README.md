# Jeanne watercolor sprite importer

This authoring-only importer cuts **88 assets from nine user-provided RGBA
illustration sheets**, grouped as VFX (16), wolf (12), Jeanne (12),
spearman (12), medieval props (12), townsfolk (6), soldiers (6),
bestiary (6), and heroes (6).

The uploaded original artwork is **not present in GitHub**. To generate
the files, put the nine source PNGs in one directory under their exact
original filenames (including punctuation and French accents).

```bash
python -m pip install pillow numpy opencv-python-headless
python scripts/import_watercolor_sheets.py --input-dir /path/to/source-sheets \
  --output-dir assets/watercolor --force
python -m unittest discover -s tests_standalone -p test_watercolor_importer.py -v
```

The tool writes `sprites/<group>/<pose>.png`, an `index.json`
(including SHA-256 provenance, cell coordinates, sizes, and foot pivots),
and an `AssetRegistry` v1-compatible `registry.json` (88 sprites and 15
sample animation sequences). All paths in that registry are relative
to the output directory; copy or bind entries explicitly in a game's
`*.game.json` rather than overwriting existing game assets.

**Limitations:** Generated sprites are individual, fixed-canvas
single-view poses, not 4-way directional frames or polished seamless
animations. The automatic silhouette masks are heuristic: manually
review transparent PNGs, especially fine weapon shafts, hair,
separated objects, VFX glow and frames near cell boundaries.
Use `--no-matte` for unaltered cell crops when retouching.
The runtime/headless engine requires none of the above image libraries.

## Validation and local Player integration

`AssetRegistry` requires unique IDs across sprites **and** animations, so the
15 animation IDs use the `anim_` prefix (for example `anim_jeanne_walk`).
The importer tests instantiate `AssetRegistry` to prevent regressions.

The artwork ZIP is a **separate binary deliverable** and is not yet in this
GitHub branch. With the **corrected v2 pack** downloaded from the ChatGPT
conversation, launch a demonstrator without modifying the canonical campaign:

```sh
python scripts/install_watercolor_pack.py \
  --bundle /path/to/drawTemp_assets_Jeanne_88_sprites_v2.zip \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.game.json \
  --output /tmp/jeanne-art-demo
python -m sporebound player \
  --content /tmp/jeanne-art-demo/jeanne.json \
  --project /tmp/jeanne-art-demo/jeanne.game.json
```

The installer validates the ZIP paths, image signatures, 88 sprites, 15
animations and all registry references; preserves the source project and
savegames; copies the images and game JSON into a standalone directory;
and binds Jeanne, her allies, and enemy soldier slots to the Tk Player.
No additional Pillow/OpenCV dependencies are needed for **installation**.

### Real Jeanne campaign compatibility

The current `jeanne.game.json` already contains **57 asset entries** pointing
to the original directional Jeanne atlas and five expression portraits (six
existing PNG files). The installer now copies all referenced original files
into the demo, so the resulting project is truly relocatable and diagnostics
do not fail on missing old media.

In the isolated **watercolor preview only**, the importer overrides the
existing `jeanne_move_<direction>`, `jeanne_attack_<direction>`,
`jeanne_hit_<direction>` and `jeanne_defeat_<direction>` bindings, because
the Player resolves directional animations before generic ones. The
`jeanne_idle_<direction>` aliases are removed in this preview so the
`jeanne_idle` static sprite displays instead of the old atlas idle cycle.
All four directional aliases intentionally share the same 2D illustration;
**they are not valid four-view animation assets**. The source project
and original assets are left unchanged.

The integration test installs the actual `jeanne.json` /
`jeanne.game.json` pair, validates the resulting `GameProject` and
`AssetRegistry`, and checks which sprite ID `animation_sprite_id`
selects for the Player.

**Quality gate:** These are single-view preliminary cutouts. Some weapon
shafts, feet and props cross source-grid boundaries and are clipped or
contaminated by adjacent illustrations. Manual cleanup is required before
marking this set production-ready. The branch remains draft until 88 PNGs are
actually committed and the in-game rendering is reviewed.


## Alpha-boundary audit (authoring-only)

Before merging the binary artwork, run the standalone visual QA tool on the
**corrected v2 ZIP**. Pillow is needed for this audit, not for the game runtime:

```sh
python -m pip install pillow
python scripts/audit_watercolor_pack.py \
  --bundle /path/to/drawTemp_assets_Jeanne_88_sprites_v2.zip \
  --output /tmp/jeanne-alpha-audit.json
# --strict fails when any frame needs a visual review.
```

The report records the fraction of pixels with alpha >= 128 on each of
the four *outermost* sprite-frame edges. Default manual-review threshold:
**more than 12% on any edge**. This is a conservative indicator of
cropping/bleed, **not proof of a visual defect**: large props and VFX may
intentionally reach the frame boundary. It does not detect missing art
which was cut off by the source grid. No gameplay state is changed.

Reference run on the v2 archive provided separately in the conversation:
**88 inspected; 51 marked for manual review**, including 11/12 props,
9/12 Jeanne poses and 10/12 spearman poses. Inspect source-sheet spillover
and fine edges carefully before converting this pack to production art.

The ZIP itself and its 88 individual PNG binaries have **not been committed**
to this branch; test green does not mean production-ready. Import the archive
using the documented installer for a non-destructive Player preview.


## V3 bleed cleanup and publication gate

After importing the 9 sheets or receiving the corrected v2 ZIP, use the authoring-only cleaner to remove **detached foreign-cell artifacts**:

```bash
python -m pip install pillow numpy opencv-python-headless
python scripts/cleanup_watercolor_bleed.py \
  --input /path/to/drawTemp_assets_Jeanne_88_sprites_v2.zip \
  --output /path/to/drawTemp_assets_Jeanne_88_sprites_v3.zip
python scripts/audit_watercolor_pack.py \
  --bundle /path/to/drawTemp_assets_Jeanne_88_sprites_v3.zip \
  --output /tmp/watercolor_v3_audit.json
```

**V3 reference results:** 88 sprites preserved, **12 cleaned**, 17 disconnected neighbour-cell fragments erased. Edge-occupancy QA flags fell from **51** (v2) to **46** (v3) at a 12% threshold. The 15 animation sequences and `AssetRegistry` IDs are unchanged. The cleaner intentionally does **not** touch VFX or the bestiary, where detached magical particles may be intentional.

Use the **v3 ZIP** instead of v2 when running `scripts/install_watercolor_pack.py` or publishing the PNGs to PR #71. On Windows, publish from a clean checkout with:

```powershell
.\scripts\publish_watercolor_art.ps1 -RepoPath C:\dev\drawTemp -BundlePath C:\Downloads\drawTemp_assets_Jeanne_88_sprites_v3.zip
```

The new QA stage only removes visually detached cell bleed. It cannot recover a spear, sword or leg that was already truncated by the sheet's rectangular layout. The final visual gate still requires manual review on gameplay scale and animation timing, particularly **Jeanne**, **spearman**, and modular **props**. The PR remains draft until the 88 PNGs are committed and visually verified in Player.


## Native Tk 52px renderer regression gate

The Player previously used Tk PhotoImage copy with zoom and subsample in **one operation**. Tk samples the input at the subsample interval **before** zooming; for 384×341 source sprites down to a 52px cell, this reproduced only a small corner and left Jeanne, the spearman and wolf effectively invisible.

PR #71 now repairs the **shared** CanvasRenderer._cell_photo path (also used by existing Jeanne atlas frames): magnify the complete source photo first, subsample in a separate operation, then centre the result in the target cell. This uses native Tk only, remains cached by image ID and camera scale, and does **not** affect tactical rules, replay, saves or project schemas. The scale ratio chooser is bounded to keep each temporary dimension <= 2048 px.

Run the new regression tests:

```sh
python -m unittest discover -s tests_standalone -p 'test_tk_sprite_scaling_3710.py' -v
# On Linux with Xvfb, actually check the lower-right pixels of large PNGs:
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest discover -s tests_standalone -p 'test_tk_sprite_scaling_3710.py' -v
```

The GUI test constructs transparent 384×341 source pixels with a bright rectangle in the **lower-right**. That rectangle was lost with single-pass Tk zoom/subsample, and must survive the corrected two-pass resize at 52px. The test also checks the existing 64×64 atlas, stable image caching and camera zoom to 78px.

Local offscreen Tk proof on the v3 ZIP: all 18 reviewed action poses for Jeanne, spearman and wolf are visible at the Player's 52px cell size. This is a renderer QA snapshot, **not** an end-to-end interactive Player gameplay test; that remains required once the 88 PNGs are committed.


## 2026-10-13: V3 provenance and current PR #114

The corrected V3 ZIP was recovered in the author's personal file Library
(the PNG binaries are still absent from GitHub). SHA-256 of the complete ZIP:
\`2a3089fc05184f62048c1484a114a467d626411452d8e6d9104f57e4cb20bf0a\`.

For a clean local checkout, use \`scripts/publish_watercolor_pack.py\` to
validate and atomically add exactly 88 real PNGs against the tracked
\`assets/watercolor/provenance.json\`. The command is idempotent but refuses
partial packs or edited art. \`--dry-run\` validates without writing. To
commit and push directly to PR #114 on Windows, use the updated
\`scripts/publish_watercolor_art.ps1\` with \`-RepoPath\` and \`-BundlePath\`.
Do not use the older instructions above targeting the historical PR #71.

The preflight identified 46 potential transparency/bleed issues requiring
visual review. See \`docs/evidence/watercolor_v3_art_review.json\`.
A successful hash gate proves **identity and integrity**, not visual quality.
