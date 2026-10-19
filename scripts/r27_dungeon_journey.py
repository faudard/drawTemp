"""R27.D journey fixture generator: no handwritten map or project JSON.

Example:
 python -m scripts.r27_dungeon_journey --output /tmp/amber.json
 python -m drawtemp.player.qt_app --content /tmp/amber.json --campaign r27_journey
"""
from __future__ import annotations

import argparse
from pathlib import Path

from drawtemp.studio.dungeon_journey import build_dungeon_journey
from drawtemp.studio.map_authoring import MapStudio


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create an R27 village/dungeon/boss/return tactical demo")
    parser.add_argument("--output", required=True, type=Path,
                        help="Content JSON destination; paired GameProject saved alongside")
    parser.add_argument("--prefix", default="r27",
                        help="Unique campaign and mission prefix (default r27)")
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".json":
        parser.error("--output requires a .json path")
    studio = MapStudio.reference()
    created = build_dungeon_journey(studio, prefix=args.prefix)
    studio.save_as(output)
    pair_path = output.with_suffix(".game.json")
    print("Created canonical Content:", output)
    print("Created canonical GameProject:", pair_path)
    print("Campaign:", created["campaign_id"])
    print("Launch:")
    print("python -m drawtemp.player.qt_app --content " + str(output) +
          " --campaign " + created["campaign_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
