# Front Hair – directional parts

This folder is reserved for separately authored 192 × 192 transparent PNG layers.

Place four files per variation: `name_front.png`, `name_right.png`,
`name_back.png`, `name_left.png`. They must align on the same canvas and
foot pivot as all existing `assets/hero_parts` pieces.

The visual generator also exposes hairstyles from the existing `../hair/`
folder as a temporary fallback when no separately authored variation exists.
For **Front Hair**, fallback renders an upper-fringe alpha crop of the full
hairstyle; **Rear Hair** renders the source behind the head. This is an
approximation, **not** new original front/rear artwork. Once a complete
four-way variation is placed here, the generator prefers these authored PNGs
and does not crop them.

The original `hair/` files and existing character recipes are never rewritten
by simply opening the editor.
