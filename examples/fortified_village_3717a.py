"""3.7.17A — Reproducible medieval village, authored with real Studio commands.

This is intentionally NOT a handwritten map JSON or a second content schema.
The same Document brushes, structure stamps and guided authoring actions are
used by the Tk editor. Run the script, then open its output in the Studio.
"""
import argparse
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_event, add_object
from sporebound.editor import Document
from sporebound.iso_structures import place_structure
from sporebound.model import Content


MISSION_ID = 'fortified_village_3717a'
WIDTH, HEIGHT = 26, 20


def river_start(y):
    """A restrained bend with a straight, three-cell-wide bridge crossing."""
    return 12 if 6 <= y <= 13 else 11


def build_village_document(source):
    """Build a playable test scene using existing, undoable authoring operations.

    The source Content is never changed. No hand-edited terrain dictionaries,
    tactical rules or new asset identifiers are introduced.
    """
    data = add_blank_mission(source.to_dict(), MISSION_ID,
                             'Le Pont de Valcroix', WIDTH, HEIGHT)
    doc = Document(Content.from_dict(data))
    mission = next(m for m in doc.data['missions'] if m['id'] == MISSION_ID)
    player = next(u['id'] for u in mission['units'] if u['team'] == 'player')
    enemy = next(u['id'] for u in mission['units'] if u['team'] == 'enemy')
    # Keep the two original templates, but place combatants where a real
    # crossing and encounter can occur (not behind inaccessible ramparts).
    doc.place_unit(MISSION_ID, player, (2, 10))
    doc.place_unit(MISSION_ID, enemy, (23, 9))

    river = [(x, y) for y in range(HEIGHT)
             for x in range(river_start(y), river_start(y) + 3)]
    doc.paint_many(MISSION_ID, river, 'surface:water')
    banks = [(x, y) for y in range(HEIGHT)
             for x in (river_start(y) - 1, river_start(y) + 3)]
    doc.paint_many(MISSION_ID, banks, 'surface:sand')

    # Main cross-river route; smaller cobbled squares give the architecture
    # a readable visual hierarchy, with the crossing kept at y=9..10.
    doc.paint_many(MISSION_ID,
                   [(x, 9) for x in range(1, 12)]
                   + [(x, 9) for x in range(15, 26)],
                   'surface:dirt')
    doc.paint_rectangle(MISSION_ID, (3, 7), (8, 10), 'surface:cobble')
    doc.paint_rectangle(MISSION_ID, (20, 8), (24, 10), 'surface:cobble')
    doc.paint_many(MISSION_ID,
                   [(8, y) for y in (11, 12)]
                   + [(4, y) for y in (11, 12, 13)],
                   'surface:dirt')

    # These are real editable structure stamps. Put the two-row bridge on
    # water, and leave a four-cell opening in the east fortress wall.
    structures = (
        ('Pont', (12, 9), 0),
        ('Maison', (3, 3), 0),
        ('Maison', (6, 13), 0),
        ('Ruines', (1, 14), 0),
        ('Tour', (21, 3), 0),
        ('Maison', (21, 12), 0),
        ('Rempart', (19, 2), 1),
        ('Rempart', (19, 12), 1),
        ('Rempart', (20, 1), 0),
        ('Rempart', (20, 18), 0),
    )
    for name, anchor, turns in structures:
        doc.replace(place_structure(doc.data, MISSION_ID, name, anchor, turns))

    # Props are terrain features, not unrelated sprite objects. They remain
    # movable or erasable with the same brush used for other Studio assets.
    decorations = {
        'tree': ((1, 4), (9, 3), (8, 17), (17, 3), (17, 17), (25, 6)),
        'bush': ((10, 6), (6, 18), (16, 14)),
        'boulder': ((0, 7), (25, 15)),
        'lantern': ((9, 9), (18, 9), (20, 10)),
        'reeds': ((10, 4), (15, 12)),
        'crate': ((7, 10),),
    }
    for feature, cells in decorations.items():
        doc.paint_many(MISSION_ID, cells, 'feature:' + feature)

    # Existing guided actions: two objects and one non-blocking bridge event.
    doc.replace(add_object(doc.data, MISSION_ID, 'east_gate', 'door', (19, 9)))
    doc.replace(add_object(doc.data, MISSION_ID, 'village_chest',
                           'chest', (22, 13)))
    doc.replace(add_event(doc.data, MISSION_ID, 'crossed_valcroix_bridge',
                          condition='enter', action='message', pos=(15, 9),
                          text='La garnison de Valcroix vous a repérés.'))
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate the 3.7.17A Studio village')
    parser.add_argument('--output', type=Path, default=Path('fortified_village.json'))
    args = parser.parse_args(argv)
    doc = build_village_document(Content.load(DEFAULT_CONTENT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    # A live Battle uses a copy: generating the village never mutates combat
    # rules, saves or previous missions in the source content.
    battle = doc.playtest(MISSION_ID, seed=7)
    assert battle.mission.id == MISSION_ID
    print(f'Village created: {args.output} — {WIDTH} x {HEIGHT}, '
          f'{len(battle.mission.units)} actors, {len(battle.mission.objects)} objects')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
