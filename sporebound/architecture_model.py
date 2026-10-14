"""Pure structure identity and inference shared by authoring and renderers."""
from dataclasses import dataclass
from .iso_structures import structure_template, door_slots
from .model import require

ARCHITECTURE_NAMES = ('Maison', 'Tour', 'Ruines')
SCENERY_NAMES = ('Rempart', 'Escalier', 'Pont')
# Only appearance tokens are matched; an edited wall, floor or entrance
# intentionally invalidates the derived facade until the stamp is reapplied.
MATCH_KEYS = ('surface', 'feature', 'height', 'blocked', 'cost', 'cover', 'hazard')


@dataclass(frozen=True)
class ArchitectureInstance:
    name: str
    anchor: tuple
    turns: int
    door_slot: int
    width: int
    height: int
    cells: frozenset
    entry: tuple | None
    id: str = ''
    appearance: dict | None = None


def _same_tile(current, expected):
    defaults = dict(surface='grass', feature='', height=0, blocked=False,
                    cost=1, cover=0, hazard=0)
    return all(getattr(current, key) == expected.get(key, defaults[key])
               for key in MATCH_KEYS)


def _stored_instance(record):
    """Recompute geometry from a validated visual identity, not current tiles."""
    clip = structure_template(record['name'], record['turns'],
                              door_slot=record['door_slot'])
    x, y = record['anchor']
    cells = frozenset((x+dx, y+dy) for dx, dy in clip.offsets)
    entry = next(((x+dx, y+dy) for (dx, dy), tile
                  in zip(clip.offsets, clip.terrain)
                  if tile.get('surface') == 'cobble' and not tile.get('blocked')),
                 None)
    return ArchitectureInstance(record['name'], (x, y),
                                record['turns'], record['door_slot'],
                                clip.width, clip.height, cells, entry,
                                record['id'], record.get('appearance'))


def architecture_instances(board, structures=()):
    """Use stable authored identities first, and infer only remaining legacy.

    Existing missions keep their previous detection logic. Recorded buildings
    do not disappear when a tactical wall, floor or door tile is repainted.
    """
    seed_cells = {
        'wall': [cell for cell, tile in board.tiles.items()
                 if tile.feature == 'stone_wall'],
        'stairs': [cell for cell, tile in board.tiles.items()
                   if tile.feature == 'stairs'],
        'bridge': [cell for cell, tile in board.tiles.items()
                   if tile.surface == 'bridge'],
    }
    candidates = []
    for name in (*ARCHITECTURE_NAMES, *SCENERY_NAMES):
        for turns in range(4):
            for door_slot in range(len(door_slots(name))):
                clip = structure_template(name, turns, door_slot=door_slot)
                # A rotated plan need not begin with its distinguishing
                # wall/step/bridge tile. Seed from a matching non-default
                # terrain token; legacy blank maps remain untouched.
                if name == 'Escalier':
                    kind = 'stairs'
                    index = next((i for i, t in enumerate(clip.terrain)
                                  if t.get('feature') == 'stairs'), None)
                elif name == 'Pont':
                    kind = 'bridge'
                    index = next((i for i, t in enumerate(clip.terrain)
                                  if t.get('surface') == 'bridge'), None)
                else:
                    kind = 'wall'
                    index = next((i for i, t in enumerate(clip.terrain)
                                  if t.get('feature') == 'stone_wall'), None)
                if index is None:
                    continue
                dx, dy = clip.offsets[index]
                for wx, wy in seed_cells[kind]:
                    x, y = wx-dx, wy-dy
                    if (x < 0 or y < 0 or x + clip.width > board.width
                            or y + clip.height > board.height):
                        continue
                    cells = tuple((x+dx, y+dy) for dx, dy in clip.offsets)
                    if not all(_same_tile(board.tile(cell), spec)
                               for cell, spec in zip(cells, clip.terrain)):
                        continue
                    entry = next(((x+dx, y+dy) for (dx, dy), spec
                                  in zip(clip.offsets, clip.terrain)
                                  if spec.get('surface') == 'cobble'
                                  and not spec.get('blocked')), None)
                    candidates.append(ArchitectureInstance(
                        name, (x, y), turns, door_slot, clip.width, clip.height,
                        frozenset(cells), entry))
    # Matching rotated symmetric stamps produce duplicates; choose one stable
    # representation and never paint two roofs over the same ground cells.
    claimed, result = set(), []
    for record in structures:
        persistent = _stored_instance(record)
        require(not persistent.cells.intersection(claimed),
                'Overlapping authored structure identities')
        result.append(persistent)
        claimed.update(persistent.cells)
    for candidate in sorted(candidates,
                            key=lambda v: (-len(v.cells), v.anchor[1],
                                           v.anchor[0], v.name, v.turns, v.door_slot)):
        if not candidate.cells.intersection(claimed):
            result.append(candidate)
            claimed.update(candidate.cells)
    return tuple(result)

