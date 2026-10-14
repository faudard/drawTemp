# Jeanne — watercolor asset pack (art extraction)

This pack contains **88 individually sliced PNGs** from 9 uploaded source
sheets: 16 VFX, 12 wolf poses, 12 Jeanne poses, 12 spearman poses, 12 props,
6 townsfolk, 6 soldiers, 6 bestiary creatures, and 6 heroes.

The full source PNG files are not committed by the importer. To regenerate,
place the nine original sheets in a single directory with their original French
filenames and run (from the repository root):

```bash
python -m pip install pillow numpy opencv-python-headless
python scripts/import_watercolor_sheets.py \
  --input-dir /path/to/9-sheets \
  --output-dir assets/watercolor --force
python -m unittest tests_standalone.test_watercolor_importer -v
```

The generated files are under `sprites/<group>/<pose>.png`.
`index.json` provides the pixel frame bounds, approximate foot pivots, source
SHA-256 and source grid cell positions. `registry.json` is a **standalone
AssetRegistry v1** manifest relative to `assets/watercolor`; it has sprite
and sample animation entries but **no automatic Player bindings**. To make an
asset visible in a game, copy/export it into the authored project's art folder,
then add the corresponding asset entries/bindings to its `*.game.json` via the
project asset registry. The headless tactical engine is not modified.

## Image quality caveats

* The source artwork includes a mostly opaque blurred background. The optional
  OpenCV matting is an **approximate** mask; inspect transparent silhouettes
  at 100% before using them in production, especially around hair, weapons,
  spectral glow and transparent light VFX.
* Dynamic sprites keep their fixed grid-cell canvas for stable anchoring, even
  if this leaves extra transparent margins. Their named poses are **not** true
  directional sprites and are not guaranteed to form seamless animations.
* Use `--no-matte` to produce a no-detour full-crop backup from the originals.
* All pose names are suggestions; the original artwork remains the source of
  truth for alignment, additional retouching, and licensing provenance.
