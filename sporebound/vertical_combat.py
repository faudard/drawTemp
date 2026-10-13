"""Conservative cross-floor shooting policy for 3.7.20C2.

A projectile only crosses adjacent decks through an authored missing floor
tile (a hole), with entry/exit adjacent to that opening. Solid ceilings
always occlude. No other 3D collision or area effects are inferred.
"""
from .model import distance, require


def shaft_openings(mission, upper_level):
    """World coordinates of holes within persistent building footprints."""
    from .iso_structures import structure_footprint, structure_template
    structures = {row['id']: row for row in mission.structures}
    holes = set()
    for floor in mission.interior_floors:
        if floor['level'] != upper_level:
            continue
        structure = structures[floor['structure_id']]
        clip = structure_template(structure['name'], structure['turns'],
                                  door_slot=structure['door_slot'])
        anchor = structure['anchor']
        footprint = set(structure_footprint(clip, anchor))
        solid = {(anchor[0] + row['pos'][0], anchor[1] + row['pos'][1])
                 for row in floor['tiles']}
        holes.update(footprint - solid)
    return frozenset(holes)


def vertical_shot_allowed(battle, caster, target, skill):
    """True only for short-range projectile shots through visible floor holes.

    Requires a basic ranged/focus attack, adjacent floors, a 1x1 target and
    a traversable line from the lower actor to an opening in the upper deck.
    Upper-level side is checked geometrically against the opening only:
    there is no upper-floor wall model yet.
    """
    low_level = min(battle.unit_levels.get(caster.id, 0),
                    battle.unit_levels.get(target.id, 0))
    high_level = max(battle.unit_levels.get(caster.id, 0),
                     battle.unit_levels.get(target.id, 0))
    if (high_level - low_level != 1 or skill.id != 'attack'
            or caster.weapon not in {'ranged', 'focus'}
            or caster.footprint != (1, 1) or target.footprint != (1, 1)):
        return False
    range_cost = distance(caster.pos, target.pos) + 1
    if not skill.min_range <= range_cost <= skill.range:
        return False
    low = caster if battle.unit_levels.get(caster.id, 0) == low_level else target
    high = target if low is caster else caster
    for hole in sorted(shaft_openings(battle.mission, high_level)):
        if (distance(low.pos, hole) <= 1 and distance(high.pos, hole) <= 1
                and battle.board.contains(hole)
                and not battle.board.tile(hole).blocked
                and (low_level != 0 or battle.line_of_sight(low.pos, hole))):
            return True
    return False


def target_floor(battle, caster, requested):
    current = battle.unit_levels.get(caster.id, 0)
    if requested is None:
        return current
    require(type(requested) is int and 0 <= requested <= 3,
            'Target level must be 0..3')
    require(battle.mission.level_links or requested == current,
            'Cross-floor targeting requires authored level links')
    return requested
