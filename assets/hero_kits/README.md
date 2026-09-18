# Sporebound Hero Kits — V1.28

A guided kit is an art-directed full character, not a stack of modular stickers.

Required files per kit:

- `front.png`
- `right.png`
- `back.png`
- `left.png`
- optional `thumbnail.png`
- optional `kit.json` metadata

Optional state-specific files use `<direction>_<state>.png`, for example `front_attack.png` or `right_ko.png`. If a complete 4-direction state is missing, the compositor deliberately falls back to the kit Idle view instead of fabricating a lower-quality pose.

V1.28 bundled kits:

- `forest_scout`
- `forest_guardian`
- `nature_mage`

`kit.json` can define `display_name`, `role`, `description`, `tags`, `art_family`, `default_scale`, and `preferred_portrait_direction`.
