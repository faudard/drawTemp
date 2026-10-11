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
