#!/usr/bin/env python3
"""Generate a deterministic real-Studio screenshot gallery for PR review.

Builds the existing Valcroix authored fixture in an isolated temporary
directory; screenshot mode is opt-in and cannot modify tracked project files.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from examples.fortified_village_3717a import MISSION_ID, build_village_document
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("DISPLAY"):
        parser.error("A real display is required; use xvfb-run on Linux")
    with TemporaryDirectory(prefix="drawtemp-studio-pr-") as tmp:
        content_path = Path(tmp) / "valcroix.json"
        document = build_village_document(Content.load(DEFAULT_CONTENT))
        document.save(content_path)
        content = Content.from_dict(document.data)
        GameProject.default(content).save(content_path.with_suffix(".game.json"),
                                          content)
        os.environ["DRAWTEMP_STUDIO_VISUAL_DIR"] = str(output)
        os.environ["DRAWTEMP_STUDIO_VISUAL_MISSION"] = MISSION_ID
        from sporebound.editor import launch
        launch(content_path)

    if not (output / "manifest.json").is_file():
        raise RuntimeError("Studio terminated without recording its screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
