# Jeanne — validated direction / playable assets

Artwork location: `sporebound/content/art/jeanne/`.

## Character design and use

Approved by the project owner for the alternate-history Jeanne d'Arc campaign:
blonde long braided hair with navy ribbon, blue eyes, polished silver plate,
royal blue cloth and subdued gold. The visual language is original French
medieval fantasy with expressive anime illustration.

### Runtime filenames

- `jeanne_portrait.png` (256 × 256): main approved illustration crop, used
  automatically by the Player for dialogue speaker `Jeanne`.
- `jeanne_neutral.png`, `jeanne_smile.png`,
  `jeanne_determined.png`, `jeanne_battle_shout.png` (192 × 192):
  additional expression portraits, bound to explicit named slots.
- `jeanne_atlas.png` (256 × 512 RGBA): 4 columns in order
  `south,north,east,west` and 8 rows
  `idle_0,idle_1,move_0,move_1,attack_0,attack_1,hit_0,defeat_0`.
  Individual frames remain 64 × 64 and are cropped by the existing Tk
  renderer via `region`.

The portrait files are cropped from the **user-approved Jeanne character
sheet** produced during the project's art-direction review. The battle poses
are converted from a coordinated project character sprite proof sheet.
Transparent battle tiles are PNG; portrait backgrounds remain part of the
approved artwork intentionally.

### Limits and QA

The approved **design** is consistent; not all 32 tactical poses are
hand-animated final drawings. In particular, back-facing movement/attack
states have limited variations and need a dedicated later polish pass.
Neither the renderer comparison nor final animation sign-off is claimed by
this asset PR.

Do not change tactical rules, scenario JSON, saved battle commands, or
replay timing for art presentation. Renaming or adding manifest assets
changes the project digest and invalidates saves unless explicitly migrated.
