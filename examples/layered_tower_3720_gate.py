"""Reproducible two-level tower for Interior Builder 2.0 acceptance.

Run: python -m examples.layered_tower_3720_gate --output /tmp/tower.json

N0 contains the entrance. N1 contains an explicit authored deck.
A staircase is the *only* transition: tile.height is never used as a level ID.
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


MISSION_ID = 'interior_tower_3720_gate'


def create():
    data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                             MISSION_ID, 'Tour à deux étages', 16, 16)
    data = place_structure(data, MISSION_ID, 'Tour', (3, 3))
    mission = next(m for m in data['missions'] if m['id'] == MISSION_ID)
    tower_id = mission['structures'][0]['id']
    data = add_interior_floor(data, MISSION_ID, tower_id, 1)
    data = edit_interior_tile(data, MISSION_ID, tower_id, 1,
                              (4, 5), feature='stairs')
    data = add_level_link(data, MISSION_ID, [0, 4, 5], [1, 4, 5])
    mission = next(m for m in data['missions'] if m['id'] == MISSION_ID)
    hero = next(u['id'] for u in mission['units'] if u['team'] == 'player')
    foe = next(u['id'] for u in mission['units'] if u['team'] == 'enemy')
    data = place_unit_on_level(data, MISSION_ID, hero, 0, (4, 5))
    data = place_unit_on_level(data, MISSION_ID, foe, 1, (4, 4))
    mission = next(m for m in data['missions'] if m['id'] == MISSION_ID)
    for unit in mission['units']:
        unit['speed'] = 1000 if unit['id'] == hero else 1
    return Content.from_dict(data).to_dict(), MISSION_ID


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    source, mission_id = create()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, source)
    Content.load(args.output)
    print(f'Validated {mission_id} -> {args.output}')
    print('Enter the tower at (4,5), use level_move to N1/(4,5),')
    print('then attack the enemy at N1/(4,4). Save and reload the battle.')


if __name__ == '__main__':
    main()
