"""Create an inspectable production QA contact sheet from R7.C authored art.

No Qt dependency; deliberately renders the same R7 compositor/export inputs as
the Player pack. This is a review artifact, NOT automatic artistic certification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drawtemp.assets.characters import DIRECTIONS, render_frame
from drawtemp.assets.jeanne_art import OUTFITS


def contact_sheet(root, destination):
    from PIL import Image, ImageDraw
    root = Path(root)
    recipe = json.loads((root / "jeanne.character.json").read_text("utf-8"))
    samples = ("idle", "walk", "attack")
    scale, spacing, cell_w, cell_h = 2, 12, 148, 170
    image = Image.new("RGB", (cell_w * len(DIRECTIONS),
                              cell_h * len(OUTFITS) * len(samples)), "#172433")
    draw = ImageDraw.Draw(image)
    for variant_i, outfit in enumerate(OUTFITS):
        for action_i, action in enumerate(samples):
            y = (variant_i * len(samples) + action_i) * cell_h
            for direction_i, direction in enumerate(DIRECTIONS):
                x = direction_i * cell_w
                frame = render_frame(recipe, outfit, action, direction, 0, root)
                sprite = frame.resize((64 * scale, 64 * scale),
                                      Image.Resampling.NEAREST)
                image.paste(sprite, (x + 10, y + 32), sprite)
                draw.text((x + 9, y + 7), f"{outfit} • {direction} • {action}",
                          fill="#eed5ac")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG")
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("jeanne_r7c_review.png"))
    args = parser.parse_args(argv)
    contact_sheet(args.root, args.output)


if __name__ == "__main__":
    main()
