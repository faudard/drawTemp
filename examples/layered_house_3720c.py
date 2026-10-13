"""3.7.20C — reproducible layered-house mission, authored without raw JSON.

Usage: python -m examples.layered_house_3720c --output /tmp/layered_house.json
Open result with the Map Editor and use the stair move in its playtest.
"""
import argparse
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.interior_levels import add_interior_floor, edit_interior_tile
from sporebound.iso_structures import place_structure
from sporebound.level_navigation import add_level_link, place_unit_on_level
from sporebound.model import Content
from sporebound.storage import write_json


def create():
    mid = 'layered_house_3720c'
    data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                             mid, 'L’escalier de Valcroix', 16, 16)
    data = place_structure(data, mid, 'Maison', (3, 3))
    house = next(m for m in data['missions'] if m['id'] == mid)['structures'][0]
    data = add_interior_floor(data, mid, house['id'], 1)
    data = edit_interior_tile(data, mid, house['id'], 1, (4, 5),
                              feature='stairs')
    data = add_level_link(data, mid, [0, 4, 5], [1, 4, 5])
    mission = next(m for m in data['missions'] if m['id'] == mid)
    player = next(u['id'] for u in mission['units'] if u['team'] == 'player')
    enemy = next(u['id'] for u in mission['units'] if u['team'] == 'enemy')
    data = place_unit_on_level(data, mid, player, 0, (4, 5))
    data = place_unit_on_level(data, mid, enemy, 1, (4, 4))
    return Content.from_dict(data).to_dict(), mid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    data, mission_id = create()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, data)
    Content.load(args.output)
    print(f'Validated {mission_id} -> {args.output}')
    print('Map Editor: playtest, select level_move, target N1 / (4,5),')
    print('then attack the enemy at N1 / (4,4).')


if __name__ == '__main__':
    main()
