"""2.8.1 graphical Castle Vertical Slice. Run from the repo root:

    python -m examples.castle_player
    python -m examples.castle_player --save saves/my-castle.json
"""
import argparse
from pathlib import Path

from examples.castle_vertical_slice import castle_blueprint, castle_content
from sporebound.castle_player_app import launch
from sporebound.tactical_rpg3 import tactical_rpg_rules


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sporebound graphical castle campaign")
    parser.add_argument("--save", type=Path, default=Path("saves/castle-2.8-gui.json"),
                        help="Independent castle save, never a legacy GameSession slot")
    args = parser.parse_args(argv)
    launch(castle_content(), castle_blueprint(), args.save,
           rules=tactical_rpg_rules())


if __name__ == "__main__":
    main()
