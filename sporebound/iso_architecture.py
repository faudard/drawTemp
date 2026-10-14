"""Visual architecture with authored identity and legacy stamp inference.

New structures remain visible after painting a tile. Old Content without
metadata still uses deterministic intact-tile recognition. No Tk imports.
"""

from .iso_structures import structure_template
from .architecture_model import (ArchitectureInstance, ARCHITECTURE_NAMES,
                                 SCENERY_NAMES, MATCH_KEYS, _same_tile,
                                 _stored_instance, architecture_instances)
from .iso_depth import cutaway_intersects, depth_order
from .iso_interiors import draw_interior, draw_stacked_floors, interior_plan
from .model import RuleError, require


PIVOTS = ('Coin', 'Centre', 'Porte')


def placement_origin(clip, clicked, pivot='Coin'):
    """Map cursor cell to stamp's top-left anchor, using a selectable pivot."""
    require(pivot in PIVOTS, 'Unknown structure pivot')
    require(isinstance(clicked, (tuple, list)) and len(clicked) == 2 and
            all(type(n) is int for n in clicked),
            'Choose a valid structure cursor cell')
    if pivot == 'Centre':
        offset = ((clip.width - 1)//2, (clip.height - 1)//2)
    elif pivot == 'Porte':
        entries = [offset for offset, tile in zip(clip.offsets, clip.terrain)
                   if tile.get('surface') == 'cobble' and not tile.get('blocked')]
        require(len(entries) == 1,
                'This preset has no door; choose the Coin or Centre pivot')
        offset = entries[0]
    else:
        offset = (0, 0)
    return clicked[0]-offset[0], clicked[1]-offset[1]


def preview_structure_sprite_position(geo, name, anchor, turns=0, *, door_slot=0):
    """Position an uncommitted structure exactly like the rendered atlas.

    Preview and final display share the same structure plan, roof geometry
    and PNG anchor. No tiles are changed and no editor/Tk import is needed.
    """
    from .iso_structures import structure_footprint

    require(isinstance(anchor, (tuple, list)) and len(anchor) == 2
            and all(type(value) is int for value in anchor),
            'Choose a valid structure anchor')
    clip = structure_template(name, turns, door_slot=door_slot)
    cells = frozenset(structure_footprint(clip, anchor))
    entry = next(((anchor[0] + dx, anchor[1] + dy)
                  for (dx, dy), tile in zip(clip.offsets, clip.terrain)
                  if tile.get('surface') == 'cobble'
                  and not tile.get('blocked')), None)
    instance = ArchitectureInstance(name, tuple(anchor), turns, door_slot,
                                    clip.width, clip.height, cells, entry)
    if name in ARCHITECTURE_NAMES:
        from .iso_building_atlas import building_sprite_top_left
        origin = building_sprite_top_left(geo, instance)
    else:
        from .iso_fortification_atlas import fortification_sprite_top_left
        origin = fortification_sprite_top_left(geo, instance)
    return instance, origin


def roof_cutaway(instance, selected_cell, units, poses=None):
    """Cut away the roof even while a unit moves across its footprint."""
    return (selected_cell in instance.cells or
            any(cutaway_intersects(instance, actor, poses) for actor in units))


def architecture_outline(geo, instance, wall_level=2):
    """Return a four-corner isometric roof and apex without Tk or 3D imports."""
    x, y = instance.anchor
    w, h = instance.width, instance.height
    hw, hh = geo.half_width, geo.half_height
    level = wall_level * geo.step
    def center(ix, iy):
        return (geo.origin_x + (ix-iy)*hw,
                geo.origin_y + (ix+iy)*hh - level)
    nx, ny = center(x, y)
    ex, ey = center(x+w-1, y)
    sx, sy = center(x+w-1, y+h-1)
    wx, wy = center(x, y+h-1)
    roof = ((nx, ny-hh), (ex+hw, ey), (sx, sy+hh), (wx-hw, wy))
    peak = ((roof[0][0]+roof[2][0])/2,
            (roof[1][1]+roof[3][1])/2 - geo.cell_size*.85)
    return roof, peak


def draw_architecture(canvas, geo, board, units, selected_cell, layers,
                      atlas=None, scenery_atlas=None, poses=None, structures=(),
                      interior_floors=(), prop_atlas=None, unit_levels=None,
                      objects=(), props=()):
    """Paint hand-authored sprite overlays with deterministic vector fallback.

    Cutaway remains a vector outline: opaque sprites may never hide occupants.
    Existing layer flags continue to work independently.
    """
    if not (layers.get('Bâtiments', True) or layers.get('Toitures', True)):
        return ()
    instances = architecture_instances(board, structures)
    for index, building in enumerate(instances):
        instance_tag = 'architecture_instance_' + str(index)
        outline, peak = architecture_outline(geo, building)
        north, east, south, west = outline
        building_floors = tuple(f for f in interior_floors
                                if f['structure_id'] == building.id)
        active_level = layers.get('Étage actif', 0)
        appearance = building.appearance or {}
        facade_tones = {
            'pierre': ('#a89a85', '#c0ad90'),
            'torchis': ('#b69f78', '#dbc59e'),
            'brique': ('#aa6758', '#c77f61'),
        }
        roof_tones = {
            'tuiles': ('#a85749', '#c47759', '#b15d4b', '#dd9470'),
            'ardoise': ('#465d6c', '#70818d', '#536873', '#9caab5'),
        }
        # A designer may open all existing interiors without placing a unit.
        # In the Player, roof_cutaway still follows selected/occupied cells.
        cutaway = (roof_cutaway(building, selected_cell, units, poses)
                   or (layers.get('Intérieurs', False)
                       and building.name in ARCHITECTURE_NAMES)
                   or (active_level > 0 and bool(building_floors)))
        if (cutaway and building.name in ARCHITECTURE_NAMES
                and layers.get('Bâtiments', True)):
            # The overlay is non-opaque: tactical tiles, props and picking
            # remain the source of truth in both Studio and Player.
            draw_interior(canvas, geo, interior_plan(board, building),
                          instance_tag)
        upper_occupied = any(
            (unit_levels or {}).get(getattr(actor, 'id', None), 0) > 0
            and tuple(actor.pos) in building.cells for actor in units)
        if ((active_level > 0 or upper_occupied) and building_floors
                and layers.get('Bâtiments', True)):
            draw_stacked_floors(canvas, geo, building, building_floors,
                                active_level, instance_tag, prop_atlas=prop_atlas)
        if building.name in SCENERY_NAMES:
            # No opaque scenery may hide selected cells or tactical actors.
            # Without a PNG, the existing tile/prop renderer is the fallback.
            if (layers.get('Bâtiments', True) and not cutaway
                    and scenery_atlas is not None):
                photo = scenery_atlas.sprite(building.name, building.turns,
                                             geo.cell_size)
                if photo is not None:
                    from .iso_fortification_atlas import fortification_sprite_top_left
                    x, y = fortification_sprite_top_left(geo, building)
                    canvas.create_image(x, y, image=photo, anchor='nw',
                                        tags=('architecture',
                                              'architecture_scenery_sprite',
                                              instance_tag))
            continue
        use_sprite = ((layers.get('Bâtiments', True)
                       and (building.name == 'Ruines' or layers.get('Toitures', True)))
                      and not cutaway and atlas is not None
                      and building.appearance is None)
        if use_sprite:
            photo = atlas.sprite(building.name, building.turns, geo.cell_size)
            if photo is not None:
                from .iso_building_atlas import building_sprite_top_left
                x, y = building_sprite_top_left(geo, building)
                canvas.create_image(x, y, image=photo, anchor='nw',
                                    tags=('architecture', 'architecture_sprite',
                                          instance_tag))
                # The sprite includes both stone facades and a roof.
                continue
        if layers.get('Bâtiments', True):
            # Faces on the two foreground sides. Separate faces preserve
            # painter order; this remains a decorative visual layer only.
            depth = max(8, geo.step * 2)
            for a, b, tone in ((east, south, facade_tones.get(
                                   appearance.get('facade', 'pierre'), facade_tones['pierre'])[0]),
                               (south, west, facade_tones.get(
                                   appearance.get('facade', 'pierre'), facade_tones['pierre'])[1])):
                canvas.create_polygon(a[0], a[1], b[0], b[1],
                                      b[0], b[1]+depth, a[0], a[1]+depth,
                                      fill=tone if not cutaway else '',
                                      outline='#66594e', width=2,
                                      tags=('architecture', 'architecture_facade',
                                            instance_tag))
            if building.entry:
                # Door is an editable floor token (cobble), not a new entity.
                dx, dy = building.entry
                door_x = geo.origin_x + (dx-dy)*geo.half_width
                door_y = geo.origin_y + (dx+dy)*geo.half_height
                if not cutaway:
                    canvas.create_rectangle(door_x-geo.cell_size*.13,
                                            door_y-geo.cell_size*.34,
                                            door_x+geo.cell_size*.13,
                                            door_y+geo.cell_size*.03,
                                            fill='#684b37', outline='#dfc196',
                                            width=2,
                                            tags=('architecture', 'architecture_door',
                                                  instance_tag))
                    canvas.create_oval(door_x+geo.cell_size*.07,
                                       door_y-geo.cell_size*.16,
                                       door_x+geo.cell_size*.10,
                                       door_y-geo.cell_size*.13,
                                       fill='#edcb69', outline='',
                                       tags=('architecture', 'architecture_door',
                                             instance_tag))
            if not cutaway and appearance.get('windows'):
                # Local exterior-wall offsets survive translations and rotate
                # together with the structure preset. These outlines never
                # change tactical wall blockage or picking geometry.
                for ox, oy in appearance['windows']:
                    wx, wy = building.anchor[0] + ox, building.anchor[1] + oy
                    px, py = geo.center((wx, wy))
                    edge = max(4, geo.cell_size * .105)
                    top = py - 2 * geo.step - geo.cell_size * .26
                    canvas.create_rectangle(
                        px-edge, top, px+edge, top+edge*1.5,
                        fill='#405b69', outline='#e2c99d', width=2,
                        tags=('architecture', 'architecture_window', instance_tag))
                    canvas.create_line(px, top, px, top+edge*1.5,
                                       fill='#d6c1a1', width=1,
                                       tags=('architecture', 'architecture_window',
                                             instance_tag))
        if layers.get('Toitures', True) and building.name != 'Ruines':
            if cutaway:
                canvas.create_polygon(*_flat(outline), fill='', outline='#b66e5c',
                                      dash=(5, 4), width=2,
                                      tags=('architecture', 'architecture_cutaway',
                                          instance_tag))
            else:
                profile = appearance.get('roof', 'tuiles')
                if profile == 'plat':
                    canvas.create_polygon(
                        *_flat(outline), fill='#74777a', outline='#45484d',
                        width=3, tags=('architecture', 'architecture_roof',
                                       'architecture_flat_roof', instance_tag))
                else:
                    tones = (roof_tones.get(profile, roof_tones['tuiles'])
                             if appearance else
                             (('#a85749', '#c47759', '#b15d4b', '#dd9470')
                              if building.name == 'Maison' else
                              ('#5b6d79', '#8696a1', '#647f88', '#a9b6b9')))
                    corners = (north, east, south, west)
                    for roof_index in range(4):
                        a, b = corners[roof_index], corners[(roof_index+1) % 4]
                        canvas.create_polygon(*_flat((a, b, peak)),
                                              fill=tones[roof_index], outline='#534c48',
                                              width=2,
                                              tags=('architecture', 'architecture_roof',
                                                    instance_tag))
                    canvas.create_line(*north, *peak, fill='#f1c49c',
                                       width=2, tags=('architecture', 'architecture_ridge',
                                                      instance_tag))
        elif layers.get('Bâtiments', True) and building.name == 'Ruines':
            canvas.create_line(*north, *east, fill='#6d7468',
                               width=3, dash=(4, 3),
                               tags=('architecture', 'architecture_ruin',
                                     instance_tag))
    # Canvas items for selection are emitted by the existing tile pass and
    # must remain visible even when a roof spans several of those cells.
    # Sort whole actor and architecture groups by ground depth. Actors behind
    # a façade stay behind it; foreground actors rise above its silhouette.
    # Individual tag groups prevent an "all actors on top" regression.
    for tag in depth_order(instances, units, poses, objects=objects, props=props):
        canvas.tag_raise(tag)
    canvas.tag_raise('selection')
    return instances


def _flat(points):
    return tuple(v for pair in points for v in pair)
